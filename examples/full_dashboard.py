"""Standalone dashboard entrypoint for PACE-VIEW."""

import logging
import os
import sys

# Allow running this module directly from examples/ while importing project packages.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import dash
import pandas as pd
from dash import Dash, html, dcc, Input, Output
from flask import Flask, abort, redirect, render_template
from pace_view.config import get_weather_api_key
from pace_view.data_parsing import DataParser
from pace_view.data_cleaning import DataCleaner

LOGGER = logging.getLogger(__name__)


def format_metric(value, suffix="", precision=1):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.{precision}f}{suffix}"


def format_datetime(value, date_format):
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "N/A"
    return timestamp.strftime(date_format)


def zone_percentages(activity_row):
    zone_seconds = []
    for zone in range(1, 6):
        raw_value = activity_row.get(f"z{zone}_sec", 0)
        if raw_value is None or pd.isna(raw_value):
            zone_seconds.append(0.0)
        else:
            zone_seconds.append(float(raw_value))

    total_seconds = sum(zone_seconds)
    if total_seconds <= 0:
        return [0.0] * 5
    return [seconds / total_seconds * 100.0 for seconds in zone_seconds]


def build_activity_explanation(activity_row):
    details = []

    distance_km = activity_row.get("distance_km")
    duration_min = activity_row.get("duration_min")
    speed_kmh = activity_row.get("speed_kmh")
    avg_h_r = activity_row.get("avg_h_r")

    if pd.notna(distance_km) and pd.notna(duration_min):
        details.append(f"Covered {distance_km:.1f} km in {duration_min:.0f} minutes.")
    elif pd.notna(distance_km):
        details.append(f"Covered {distance_km:.1f} km.")
    elif pd.notna(duration_min):
        details.append(f"Workout duration was {duration_min:.0f} minutes.")

    zone_shares = zone_percentages(activity_row)
    if sum(zone_shares) > 0:
        dominant_zone_index = max(range(5), key=lambda idx: zone_shares[idx])
        dominant_zone = dominant_zone_index + 1
        details.append(
            f"Main intensity was in Z{dominant_zone} ({zone_shares[dominant_zone_index]:.0f}% of zone time)."
        )

        hard_share = zone_shares[3] + zone_shares[4]
        easy_share = zone_shares[0] + zone_shares[1]
        if hard_share >= 35:
            details.append("This was a demanding effort with extended high-intensity work (Z4-Z5).")
        elif easy_share >= 65:
            details.append("Intensity stayed mostly aerobic (Z1-Z2), indicating an endurance-focused ride.")
        else:
            details.append("The ride kept a balanced intensity profile across aerobic and threshold zones.")

    if pd.notna(speed_kmh) and pd.notna(avg_h_r) and avg_h_r > 0:
        efficiency = speed_kmh / avg_h_r
        if efficiency >= 0.19:
            details.append("Efficiency was strong for the recorded heart rate.")
        elif efficiency >= 0.15:
            details.append("Efficiency was moderate for the recorded heart rate.")
        else:
            details.append("Speed to heart-rate efficiency was low compared with usual endurance pacing.")

    if not details:
        return "Not enough information to build an explanation for this activity."

    return " ".join(details)


def build_activity_table(total_summary: pd.DataFrame) -> pd.DataFrame:
    activity_table = (
        total_summary.copy()
        .sort_values("start_time", ascending=False)
        .reset_index(drop=True)
    )
    if "source_file" not in activity_table.columns:
        activity_table["source_file"] = None
    activity_table["activity_id"] = activity_table.index
    activity_table["explanation"] = activity_table.apply(build_activity_explanation, axis=1)
    return activity_table


def load_exercises_with_filenames(parser: DataParser, directory_name: str):
    file_names = sorted([f for f in os.listdir(directory_name) if f.lower().endswith(".tcx")])
    exercises = []
    for file_name in file_names:
        file_path = os.path.join(directory_name, file_name)
        try:
            exercise = parser.parse_tcx_file(file_path)
            if exercise is not None:
                exercises.append((file_name, exercise))
        except Exception as exc:
            LOGGER.warning("Skipping unreadable file %s: %s", file_name, exc)
    return exercises, file_names


def get_triggered_input_id() -> str:
    """Return the Dash input id that triggered the current callback."""
    trigger = dash.callback_context.triggered
    return trigger[0]["prop_id"].split(".")[0] if trigger else ""


def extract_activity_id_from_click(click_data):
    if not click_data or not click_data.get("points"):
        return None

    for point in click_data["points"]:
        custom_data = point.get("customdata")
        candidate = custom_data[0] if isinstance(custom_data, (list, tuple)) and custom_data else custom_data
        if candidate is None or pd.isna(candidate):
            continue
        try:
            return int(candidate)
        except (TypeError, ValueError):
            continue
    return None


def initialize_context_pipeline(history_folder: str):
    context_state = {
        "trainer": None,
        "pattern_report": {},
        "activity_report_cache": {},
        "error": None,
        "_initialized": True,
    }

    try:
        from pace_view.core import ContextTrainer
    except Exception as exc:
        context_state["error"] = f"Context pipeline import failed: {exc}"
        return context_state

    try:
        trainer = ContextTrainer(
            history_folder=history_folder,
            weather_api_key=get_weather_api_key(),
        )
        trainer.fit()
        pattern_report = trainer.mine_patterns()

        context_state["trainer"] = trainer
        context_state["pattern_report"] = pattern_report if isinstance(pattern_report, dict) else {}
    except Exception as exc:
        context_state["error"] = f"Context pipeline initialization failed: {exc}"

    return context_state


def ensure_context_pipeline(server: Flask):
    context_state = server.config.get("CONTEXT_PIPELINE")
    if isinstance(context_state, dict) and context_state.get("_initialized"):
        return context_state

    history_folder = server.config.get("DATA_DIRECTORY", "")
    if not history_folder:
        context_state = {
            "trainer": None,
            "pattern_report": {},
            "activity_report_cache": {},
            "error": "Data directory is not configured.",
            "_initialized": True,
        }
    else:
        context_state = initialize_context_pipeline(history_folder)

    server.config["CONTEXT_PIPELINE"] = context_state
    return context_state


def get_context_activity_report(context_state: dict, file_path: str):
    trainer = context_state.get("trainer")
    if trainer is None:
        return None, context_state.get("error") or "Digital twin model is not available."

    cache = context_state.setdefault("activity_report_cache", {})
    if file_path in cache:
        return cache[file_path], None

    try:
        report = trainer.explain(file_path)
        cache[file_path] = report
        return report, None
    except Exception as exc:
        return None, f"Activity explanation failed: {exc}"


def format_rationale_item(title: str, raw_text):
    text = raw_text.strip() if isinstance(raw_text, str) else "No rationale available."
    status = "Neutral"
    detail = text

    if ":" in text:
        prefix, suffix = text.split(":", 1)
        if prefix.strip():
            status = prefix.strip().replace("_", " ").title()
            detail = suffix.strip() or text

    tone_source = f"{status} {detail}".upper()
    if any(token in tone_source for token in ("NEGATIVE", "HIGH RESISTANCE", "HEAT STRESS", "STRUGGLING")):
        tone = "negative"
    elif any(token in tone_source for token in ("ASSISTED", "COOLING EFFECT", "PERFECT", "STRONG")):
        tone = "positive"
    else:
        tone = "neutral"

    if status == "Neutral":
        if tone == "negative":
            status = "Challenging"
        elif tone == "positive":
            status = "Favorable"

    return {
        "title": title,
        "status": status,
        "text": detail,
        "tone": tone,
    }

def create_flask_server() -> Flask:
    # Flask serves the Dash app shell and the dedicated activity detail page.
    server = Flask(__name__, template_folder=os.path.join(PROJECT_ROOT, "templates"))
    server.config["ACTIVITY_TABLE"] = pd.DataFrame()
    server.config["DATA_DIRECTORY"] = ""
    server.config["CONTEXT_PIPELINE"] = {"_initialized": False}

    @server.get("/")
    def idx():
        return redirect("/dash/")

    @server.get("/activity/<int:activity_id>")
    def activity_detail(activity_id: int):
        activity_table = server.config.get("ACTIVITY_TABLE")
        if activity_table is None or activity_table.empty:
            abort(404)
        if activity_id < 0 or activity_id >= len(activity_table):
            abort(404)

        row = activity_table.iloc[activity_id]
        zone_shares = zone_percentages(row)
        default_explanation = row.get("explanation")
        if default_explanation is None or pd.isna(default_explanation):
            default_explanation = "No explanation available."

        summary_metrics = {}
        rationale_items = []
        conclusion = default_explanation
        context_error = None
        mining_summary = "Pattern mining was not available."
        mining_explanation = ""
        mining_insights = []
        mining_rules = []

        # Load contextual model output lazily to avoid expensive startup work.
        context_state = ensure_context_pipeline(server)
        data_directory = server.config.get("DATA_DIRECTORY", "")
        source_file = row.get("source_file")
        source_file_label = source_file if isinstance(source_file, str) and source_file else "N/A"

        if isinstance(context_state, dict):
            if context_state.get("error"):
                context_error = context_state.get("error")

            if isinstance(source_file, str) and source_file:
                file_path = os.path.join(data_directory, source_file)
                if os.path.exists(file_path):
                    report, explain_error = get_context_activity_report(context_state, file_path)
                    if explain_error and context_error is None:
                        context_error = explain_error
                    if isinstance(report, dict):
                        if isinstance(report.get("Summary_Metrics"), dict):
                            summary_metrics = report["Summary_Metrics"]
                        if isinstance(report.get("Rationales"), dict):
                            rationale_items = [
                                format_rationale_item(key, value)
                                for key, value in report["Rationales"].items()
                            ]
                        conclusion = report.get("Conclusion") or conclusion
                else:
                    context_error = context_error or f"Source file not found: {source_file}"

            pattern_report = context_state.get("pattern_report")
            if isinstance(pattern_report, dict) and pattern_report:
                mining_summary = pattern_report.get("Summary", mining_summary)
                mining_explanation = pattern_report.get("Explanation", "")
                mining_insights = pattern_report.get("Insights", [])[:3]
                mining_rules = pattern_report.get("Top_Rules", [])[:3]

        activity = {
            "id": int(row["activity_id"]),
            "source_file": source_file_label,
            "date_label": format_datetime(row.get("date"), "%b %d, %Y"),
            "start_label": format_datetime(row.get("start_time"), "%b %d, %Y %H:%M"),
            "distance_label": format_metric(row.get("distance_km"), " km", precision=1),
            "duration_label": format_metric(row.get("duration_min"), " min", precision=0),
            "speed_label": format_metric(row.get("speed_kmh"), " km/h", precision=1),
            "heart_rate_label": format_metric(row.get("avg_h_r"), " bpm", precision=0),
            "trimp_label": format_metric(row.get("trimp_bannister"), "", precision=1),
            "zone_labels": [f"{pct:.0f}%" for pct in zone_shares],
            "explanation": conclusion,
            "summary_metrics": summary_metrics,
            "rationale_items": rationale_items,
            "mining_summary": mining_summary,
            "mining_explanation": mining_explanation,
            "mining_insights": mining_insights,
            "mining_rules": mining_rules,
            "context_error": context_error,
        }

        return render_template("activity_detail.html", activity=activity)

    return server

def create_dash_app(server: Flask) -> Dash:
    dash_app = Dash(
        __name__,
        server=server,
        url_base_pathname="/dash/",
        assets_folder=os.path.join(PROJECT_ROOT, "assets"),
        suppress_callback_exceptions=True,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    )

    # Load and preprocess activity data once during app bootstrap.
    directory_name = os.path.join(PROJECT_ROOT,"examples", "data")
    parser = DataParser()
    cleaner = DataCleaner()
    exercises, file_names = load_exercises_with_filenames(parser, directory_name)

    total_summary = cleaner.build_dashboard(exercises)
    activity_table = build_activity_table(total_summary)
    total_summary_with_ids = total_summary.merge(
        activity_table[["activity_id", "start_time", "source_file"]],
        on=["start_time", "source_file"],
        how="left",
    )
    server.config["ACTIVITY_TABLE"] = activity_table
    server.config["DATA_DIRECTORY"] = directory_name
    server.config["CONTEXT_PIPELINE"] = {"_initialized": False}

    def apply_theme(fig):
        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color="#0f172a"),
            title=dict(font=dict(family="Space Grotesk", size=18), x=0.02, xanchor="left"),
            margin=dict(l=40, r=28, t=56, b=40),
            colorway=["#0f172a", "#334155", "#64748b", "#94a3b8", "#0ea5a4"],
            hoverlabel=dict(bgcolor="#0f172a", font=dict(color="#ffffff", family="DM Sans")),
        )
        fig.update_xaxes(showgrid=True, gridcolor="rgba(15, 23, 42, 0.08)", zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(15, 23, 42, 0.08)", zeroline=False)
        fig.update_traces(marker=dict(line=dict(width=0)), selector=dict(type="scatter"))

        if fig.data:
            fig_type = fig.data[0].type
            if fig_type == "pie":
                fig.update_traces(
                    hole=0.5,
                    textinfo="percent+label",
                    marker=dict(line=dict(color="#ffffff", width=1)),
                    domain=dict(x=[0.15, 0.85], y=[0.1, 0.9]),
                    selector=dict(type="pie"),
                )
                fig.update_layout(showlegend=False)
            if fig_type == "heatmap":
                fig.update_layout(
                    coloraxis_colorscale=[[0, "#e2e8f0"], [0.5, "#94a3b8"], [1, "#0f172a"]],
                    coloraxis_colorbar=dict(title="Avg HR"),
                )
        fig.update_traces(marker=dict(size=7, opacity=0.8), selector=dict(mode="markers"))
        fig.update_traces(line=dict(width=3), selector=dict(mode="lines"))
        return fig

    def themed_figures(period: str):
        fig1, fig2, fig3, fig4 = cleaner.return_figures(total_summary_with_ids, period)
        return (
            apply_theme(fig1),
            apply_theme(fig2),
            apply_theme(fig3),
            apply_theme(fig4),
        )

    fig1, fig2, _, fig4 = themed_figures("7D")

    total_sessions = int(len(total_summary))
    total_distance_km = total_summary["distance_km"].sum()
    total_time_hours = total_summary["duration_min"].sum() / 60.0
    avg_speed_kmh = total_summary["speed_kmh"].mean()
    avg_hr = total_summary["avg_h_r"].mean()
    last_activity = total_summary["date"].max()
    last_activity_label = last_activity.strftime("%b %d, %Y") if pd.notna(last_activity) else "N/A"
    data_start = total_summary["date"].min()
    data_end = total_summary["date"].max()
    data_range_label = (
        f"{data_start.strftime('%b %d, %Y')} - {data_end.strftime('%b %d, %Y')}"
        if pd.notna(data_start) and pd.notna(data_end)
        else "N/A"
    )
    file_count = len(file_names)
    activity_records = activity_table.to_dict("records")

    activity_list_items = [
        html.Div(
            className="activity-list__item",
            children=[
                html.A(
                    href=f"/activity/{int(record['activity_id'])}",
                    className="activity-list__link",
                    children=[
                        html.Div(
                            format_datetime(record.get("start_time"), "%b %d, %Y %H:%M"),
                            className="activity-list__title",
                        ),
                        html.Div(
                            className="activity-list__meta",
                            children=[
                                html.Span(format_metric(record.get("distance_km"), " km", precision=1)),
                                html.Span(format_metric(record.get("duration_min"), " min", precision=0)),
                                html.Span(format_metric(record.get("speed_kmh"), " km/h", precision=1)),
                            ],
                        ),
                        html.Div("Open detailed explanation", className="activity-list__hint"),
                    ],
                ),
            ],
        )
        for record in activity_records
    ]

    dash_app.layout = html.Div(
        className="app",
        children=[
            # Optional server-side redirect target for figure click callbacks.
            dcc.Location(id="activity_redirect", refresh=True),
            html.Div(
                className="container",
                children=[
                    html.Div(
                        className="hero",
                        children=[
                            html.Div(
                                children=[
                                    html.Div("PACE-VIEW", className="hero__eyebrow"),
                                    html.H1("Physics-Augmented Contextual Explainer and Visual Interface for Endurance Workflows", className="hero__title"),
                                    html.P(
                                        "A clean view of workload, efficiency, and intensity distribution across your rides.",
                                        className="hero__subtitle",
                                    ),
                                ]
                            ),
                        ],
                    ),
                    html.Div(
                        className="kpi-grid",
                        children=[
                            html.Div(
                                className="kpi-card",
                                children=[
                                    html.Div("Sessions", className="kpi-label"),
                                    html.Div(f"{total_sessions:,}", className="kpi-value"),
                                    html.Div("All time", className="kpi-meta"),
                                ],
                            ),
                            html.Div(
                                className="kpi-card",
                                children=[
                                    html.Div("Total Distance", className="kpi-label"),
                                    html.Div(format_metric(total_distance_km, " km", precision=1), className="kpi-value"),
                                    html.Div("All time", className="kpi-meta"),
                                ],
                            ),
                            html.Div(
                                className="kpi-card",
                                children=[
                                    html.Div("Total Time", className="kpi-label"),
                                    html.Div(format_metric(total_time_hours, " hrs", precision=1), className="kpi-value"),
                                    html.Div("All time", className="kpi-meta"),
                                ],
                            ),
                            html.Div(
                                className="kpi-card",
                                children=[
                                    html.Div("Avg Speed", className="kpi-label"),
                                    html.Div(format_metric(avg_speed_kmh, " km/h", precision=1), className="kpi-value"),
                                    html.Div("All time", className="kpi-meta"),
                                ],
                            ),
                            html.Div(
                                className="kpi-card",
                                children=[
                                    html.Div("Avg Heart Rate", className="kpi-label"),
                                    html.Div(format_metric(avg_hr, " bpm", precision=0), className="kpi-value"),
                                    html.Div("All time", className="kpi-meta"),
                                ],
                            ),
                            html.Div(
                                className="kpi-card",
                                children=[
                                    html.Div("Last Activity", className="kpi-label"),
                                    html.Div(last_activity_label, className="kpi-value"),
                                    html.Div("Most recent ride", className="kpi-meta"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="card info-card",
                        children=[
                            html.Details(
                                className="data-details",
                                children=[
                                    html.Summary(
                                        [
                                            html.Span("Data used in this dashboard"),
                                            html.Span("Tap to expand", className="data-details__hint"),
                                        ],
                                        className="data-details__summary",
                                    ),
                                    html.Div(
                                        className="data-details__body",
                                        children=[
                                            html.Div(
                                                className="data-details__item",
                                                children=[
                                                    html.Div("Source folder", className="data-details__label"),
                                                    html.Div("./data (TCX files)", className="data-details__value"),
                                                ],
                                            ),
                                            html.Div(
                                                className="data-details__item",
                                                children=[
                                                    html.Div("Files found", className="data-details__label"),
                                                    html.Div(f"{file_count:,}", className="data-details__value"),
                                                ],
                                            ),
                                            html.Div(
                                                className="data-details__item",
                                                children=[
                                                    html.Div("Sessions used", className="data-details__label"),
                                                    html.Div(f"{total_sessions:,}", className="data-details__value"),
                                                ],
                                            ),
                                            html.Div(
                                                className="data-details__item",
                                                children=[
                                                    html.Div("Date range", className="data-details__label"),
                                                    html.Div(data_range_label, className="data-details__value"),
                                                ],
                                            ),
                                            html.Div(
                                                className="data-details__item",
                                                children=[
                                                    html.Div("Latest activity", className="data-details__label"),
                                                    html.Div(last_activity_label, className="data-details__value"),
                                                ],
                                            ),
                                            html.Div(
                                                className="data-details__item",
                                                children=[
                                                    html.Div("Filter logic", className="data-details__label"),
                                                    html.Div(
                                                        "Biking activities with valid trackpoints",
                                                        className="data-details__value",
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="card activity-card",
                        children=[
                            html.Div(
                                className="card__header",
                                children=[
                                    html.H3("Activities", className="card__title"),
                                    html.Div("Click an activity to open its explanation page", className="card__pill card__pill--alt"),
                                ],
                            ),
                            html.Details(
                                className="data-details data-details--activities",
                                children=[
                                    html.Summary(
                                        [
                                            html.Span(
                                                [
                                                    html.Span("Show activity list", className="activity-list-toggle__show"),
                                                    html.Span("Hide activity list", className="activity-list-toggle__hide"),
                                                ],
                                                className="activity-list-toggle",
                                            ),
                                            html.Span(f"{total_sessions:,} activities", className="data-details__hint"),
                                        ],
                                        className="data-details__summary",
                                    ),
                                    html.Div(
                                        className="activity-list",
                                        children=activity_list_items
                                        if activity_list_items
                                        else [html.Div("No activities available.", className="activity-list__empty")],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="grid",
                        children=[
                            html.Div(
                                className="card graph-card graph-card--tall card--wide",
                                children=[
                                    html.Div(
                                        className="card__header",
                                        children=[
                                            html.H3("HR Zone Mix", className="card__title"),
                                            html.Div(
                                                className="card__header-actions",
                                                children=[
                                                    html.Div(
                                                        className="range-toggle",
                                                        children=[
                                                            html.Button("7 days", id="1_week", n_clicks=0, className="range-btn active"),
                                                            html.Button("30 days", id="1_month", n_clicks=0, className="range-btn"),
                                                            html.Button("12 months", id="1_year", n_clicks=0, className="range-btn"),
                                                        ],
                                                    ),
                                                    html.Div("Last 7 days", id="range_label", className="card__pill"),
                                                    html.Div(
                                                        className="zone-meta",
                                                        children=[
                                                            html.Div("HRR zones", className="zone-meta__label"),
                                                            html.Div(
                                                                className="zone-legend",
                                                                children=[
                                                                    html.Span("Z1 <=50%", className="zone-legend__item"),
                                                                    html.Span("Z2 50-60%", className="zone-legend__item"),
                                                                    html.Span("Z3 60-70%", className="zone-legend__item"),
                                                                    html.Span("Z4 70-80%", className="zone-legend__item"),
                                                                    html.Span("Z5 >=80%", className="zone-legend__item"),
                                                                ],
                                                            ),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    dcc.Graph(
                                        id="fig1",
                                        figure=fig1,
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"height": "100%", "minHeight": "360px"},
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card graph-card graph-card--tall card--wide",
                                children=[
                                    html.Div(
                                        className="card__header",
                                        children=[
                                            html.H3("Efficiency Over Time", className="card__title"),
                                            html.Div(
                                                className="card__header-actions",
                                                children=[
                                                    html.Div(
                                                        className="range-toggle",
                                                        children=[
                                                            html.Button("90 days", id="trend_90", n_clicks=0, className="range-btn active"),
                                                            html.Button("180 days", id="trend_180", n_clicks=0, className="range-btn"),                                                            
                                                            html.Button("365 days", id="trend_365", n_clicks=0, className="range-btn"),
                                                        ],
                                                    ),
                                                    html.Div("Rolling trend: 90 days", id="trend_label", className="card__pill card__pill--alt"),
                                                ],
                                            ),
                                        ],
                                    ),
                                    dcc.Graph(
                                        id="fig2",
                                        figure=fig2,
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"height": "90%", "minHeight": "360px"},
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card graph-card graph-card--tall card--wide",
                                children=[
                                    html.Div(
                                        className="card__header",
                                        children=[
                                            html.H3("HR vs Speed x Duration", className="card__title"),
                                            html.Div("Heatmap", className="card__pill card__pill--amber"),
                                        ],
                                    ),
                                    dcc.Graph(
                                        id="fig4",
                                        figure=fig4,
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"height": "100%", "minHeight": "360px"},
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="footer",
                children=[
                    html.Div("PACE-VIEW - Physics-Augmented Contextual Explainer and Visual Interface for Endurance Workflows", className="footer__text"),
                ],
            ),
        ],
    )

    @dash_app.callback(
        Output("fig1", "figure"),
        Output("range_label", "children"),
        Output("1_week", "className"),
        Output("1_month", "className"),
        Output("1_year", "className"),
        Input("1_week", "n_clicks"),
        Input("1_month", "n_clicks"),
        Input("1_year", "n_clicks"),
    )
    def update_range(_n_week, _n_month, _n_year):
        trigger_id = get_triggered_input_id()

        if trigger_id == "1_month":
            period = "30D"
            label = "Aggregated by 30 days"
            active = "month"
        elif trigger_id == "1_year":
            period = "365D"
            label = "Aggregated by 12 months"
            active = "year"
        else:
            period = "7D"
            label = "Aggregated by 7 days"
            active = "week"

        fig1, _, _, _ = themed_figures(period)

        week_class = "range-btn active" if active == "week" else "range-btn"
        month_class = "range-btn active" if active == "month" else "range-btn"
        year_class = "range-btn active" if active == "year" else "range-btn"

        return fig1, label, week_class, month_class, year_class
    
    @dash_app.callback(
        Output("fig2", "figure"),
        Output("trend_label", "children"),
        Output("trend_90", "className"),
        Output("trend_180", "className"),
        Output("trend_365", "className"),
        Input("trend_90", "n_clicks"),
        Input("trend_180", "n_clicks"),
        Input("trend_365", "n_clicks"),
    )
    def update_trend_window(_input_90, _input_180, _input_365):
        trigger_id = get_triggered_input_id()

        if trigger_id == "trend_365":
            window_days = 365
            label = "Rolling trend: 365 days"
            active = "365"
        elif trigger_id == "trend_180":
            window_days = 180
            label = "Rolling trend: 180 days"
            active = "180"
        else:
            window_days = 90
            label = "Rolling trend: 90 days"
            active = "90"

        # period only affects fig1, so we keep a fixed value while updating fig2.
        _, fig2, _, _ = cleaner.return_figures(total_summary_with_ids, "7D", window_days)

        fig2 = apply_theme(fig2)

        class_90 = "range-btn active" if active == "90" else "range-btn"
        class_180 = "range-btn active" if active == "180" else "range-btn"
        class_365 = "range-btn active" if active == "365" else "range-btn"

        return fig2, label, class_90, class_180, class_365

    @dash_app.callback(
        Output("activity_redirect", "pathname"),
        Input("fig2", "clickData"),
        prevent_initial_call=True,
    )
    def open_activity_detail_from_efficiency(click_data):
        activity_id = extract_activity_id_from_click(click_data)
        if activity_id is None:
            return dash.no_update

        return f"/activity/{activity_id}"

    return dash_app

server = create_flask_server()
dash_app = create_dash_app(server)

if __name__ == "__main__":
    server.run(host="127.0.0.1", port=5000, debug=True)
