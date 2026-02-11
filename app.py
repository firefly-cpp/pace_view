import os

import dash
import pandas as pd
from dash import Dash, html, dcc, Input, Output
from flask import Flask, redirect
from pace_view.ast_tcx_reader import ASTTCXReader

def create_flask_server() -> Flask:
    server = Flask(__name__)

    @server.get("/")
    def idx():
        return redirect("/dash/")

    return server

def create_dash_app(server: Flask) -> Dash:
    dash_app = Dash(
        __name__,
        server=server,
        url_base_pathname="/dash/",
        suppress_callback_exceptions=True,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    )

    dirname = os.path.dirname(__file__)
    print(dirname)
    directory_name = os.path.join(dirname, 'data')    
    reader = ASTTCXReader(directory_name)

    total_summary = reader.build_dashboard()
    # print(total_summary)
    # print(total_summary.head())
    # zone_cols = [f"z{k}_sec" for k in range(1, 6)]
    # weekly_z_hours = total_summary.groupby("week")[zone_cols].sum().div(3600.0).reset_index()
    # weekly_z_hours["week"] = total_summary["week"]
    # print(weekly_z_hours)

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
        fig1, fig2, fig3, fig4 = reader.return_figures(total_summary, period)
        return (
            apply_theme(fig1),
            apply_theme(fig2),
            apply_theme(fig3),
            apply_theme(fig4),
        )

    fig1, fig2, fig3, fig4 = themed_figures("7D")

    def fmt(value, suffix="", precision=1):
        if value is None or pd.isna(value):
            return "N/A"
        return f"{value:,.{precision}f}{suffix}"

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
    file_names = sorted([f for f in os.listdir(directory_name) if f.lower().endswith(".tcx")])
    file_count = len(file_names)

    # df = px.data.iris()
    # fig = px.scatter(df, x="sepal_width", y="sepal_length", color="species")

    dash_app.layout = html.Div(
        className="app",
        children=[
            html.Div(
                className="container",
                children=[
                    html.Div(
                        className="hero",
                        children=[
                            html.Div(
                                children=[
                                    html.Div("AST Monitor AI", className="hero__eyebrow"),
                                    html.H1("Training Intelligence Dashboard", className="hero__title"),
                                    html.P(
                                        "A clean view of workload, efficiency, and intensity distribution across your recent rides.",
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
                                    html.Div(fmt(total_distance_km, " km", precision=1), className="kpi-value"),
                                    html.Div("All time", className="kpi-meta"),
                                ],
                            ),
                            html.Div(
                                className="kpi-card",
                                children=[
                                    html.Div("Total Time", className="kpi-label"),
                                    html.Div(fmt(total_time_hours, " hrs", precision=1), className="kpi-value"),
                                    html.Div("All time", className="kpi-meta"),
                                ],
                            ),
                            html.Div(
                                className="kpi-card",
                                children=[
                                    html.Div("Avg Speed", className="kpi-label"),
                                    html.Div(fmt(avg_speed_kmh, " km/h", precision=1), className="kpi-value"),
                                    html.Div("All time", className="kpi-meta"),
                                ],
                            ),
                            html.Div(
                                className="kpi-card",
                                children=[
                                    html.Div("Avg Heart Rate", className="kpi-label"),
                                    html.Div(fmt(avg_hr, " bpm", precision=0), className="kpi-value"),
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
                            html.Details(
                                className="data-details data-details--files",
                                children=[
                                    html.Summary(
                                        [
                                            html.Span("Show file list"),
                                            html.Span(f"{file_count:,} files", className="data-details__hint"),
                                        ],
                                        className="data-details__summary",
                                    ),
                                    html.Div(
                                        className="data-details__body",
                                        children=[
                                            html.Div(
                                                className="data-details__item data-details__item--full",
                                                children=[
                                                    html.Div("Files in ./data", className="data-details__label"),
                                                    html.Div(
                                                        className="file-list",
                                                        children=[
                                                            html.Div(name, className="file-list__item")
                                                            for name in (file_names or ["No .tcx files found"])
                                                        ],
                                                    ),
                                                ],
                                            )
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="grid",
                        children=[
                            html.Div(
                                className="card graph-card graph-card--tall",
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
                                                            html.Div("Aggregated by: time in zone (HRR)", className="zone-meta__label"),
                                                            html.Div(
                                                                className="zone-legend",
                                                                children=[
                                                                    html.Span("Z1 <=50% HRR", className="zone-legend__item"),
                                                                    html.Span("Z2 50-60% HRR", className="zone-legend__item"),
                                                                    html.Span("Z3 60-70% HRR", className="zone-legend__item"),
                                                                    html.Span("Z4 70-80% HRR", className="zone-legend__item"),
                                                                    html.Span("Z5 >=80% HRR", className="zone-legend__item"),
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
                                        style={"height": "100%", "minHeight": "380px"},
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card graph-card",
                                children=[
                                    html.Div(
                                        className="card__header",
                                        children=[
                                            html.H3("Efficiency Over Time", className="card__title"),
                                            html.Div("Speed / HR", className="card__pill card__pill--alt"),
                                        ],
                                    ),
                                    dcc.Graph(
                                        id="fig2",
                                        figure=fig2,
                                        config={"displayModeBar": False, "responsive": True},
                                        style={"height": "100%", "minHeight": "320px"},
                                    ),
                                ],
                            ),
                            html.Div(
                                className="card graph-card card--wide",
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
                    html.Div("AST Monitor AI - Training intelligence dashboard", className="footer__text"),
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
    def update_range(n_week, n_month, n_year):
        trigger = dash.callback_context.triggered
        trigger_id = trigger[0]["prop_id"].split(".")[0] if trigger else ""

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

    return dash_app

server = create_flask_server()
dash_app = create_dash_app(server)

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=5000, debug=True)
