"""Serve only the activity detail page using one TCX file from examples/data.

Unlike the lightweight version, this script runs the ContextTrainer pipeline
on `examples/data` and uses real digital twin outputs for the rendered page.

Run:
    python examples/activity_detail_page_example.py
"""

import logging
import os
import sys
from typing import Any

import pandas as pd
from flask import Flask, abort, redirect, render_template, send_from_directory

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
EXAMPLE_DATA_DIR = os.path.join(CURRENT_DIR, "data")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
DEFAULT_TCX_FILE = "1.tcx"
EXAMPLE_ACTIVITY_ID = 1

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pace_view.data_cleaning import DataCleaner
from pace_view.config import get_weather_api_key
from pace_view.data_parsing import DataParser

LOGGER = logging.getLogger(__name__)


def format_metric(value: Any, suffix: str = "", precision: int = 1) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.{precision}f}{suffix}"


def format_datetime(value: Any, date_format: str) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "N/A"
    return timestamp.strftime(date_format)


def zone_percentages(activity_row: pd.Series) -> list[float]:
    zone_seconds = []
    for zone in range(1, 6):
        raw_value = activity_row.get(f"z{zone}_sec", 0)
        zone_seconds.append(0.0 if raw_value is None or pd.isna(raw_value) else float(raw_value))

    total_seconds = sum(zone_seconds)
    if total_seconds <= 0:
        return [0.0] * 5
    return [seconds / total_seconds * 100.0 for seconds in zone_seconds]


def build_simple_explanation(activity_row: pd.Series) -> str:
    distance = activity_row.get("distance_km")
    duration = activity_row.get("duration_min")
    speed = activity_row.get("speed_kmh")
    hr = activity_row.get("avg_h_r")

    details = []
    if pd.notna(distance) and pd.notna(duration):
        details.append(f"Covered {distance:.1f} km in {duration:.0f} minutes.")
    if pd.notna(speed):
        details.append(f"Average speed was {speed:.1f} km/h.")
    if pd.notna(hr):
        details.append(f"Average heart rate was {hr:.0f} bpm.")

    if not details:
        return "Not enough information to build an explanation for this activity."
    return " ".join(details)


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


def build_rationale_items(zone_shares: list[float], speed_kmh: Any, avg_h_r: Any) -> list[dict[str, str]]:
    dominant_zone_idx = max(range(5), key=lambda idx: zone_shares[idx]) if zone_shares else 0
    dominant_zone = dominant_zone_idx + 1

    intensity_text = f"Most of the session was spent in Z{dominant_zone} ({zone_shares[dominant_zone_idx]:.0f}%)."
    if dominant_zone >= 4:
        intensity_status = "High Load"
        intensity_tone = "negative"
    elif dominant_zone <= 2:
        intensity_status = "Aerobic"
        intensity_tone = "positive"
    else:
        intensity_status = "Balanced"
        intensity_tone = "neutral"

    efficiency_tone = "neutral"
    efficiency_status = "Unavailable"
    efficiency_text = "No efficiency estimate available."
    if pd.notna(speed_kmh) and pd.notna(avg_h_r) and avg_h_r > 0:
        efficiency = float(speed_kmh) / float(avg_h_r)
        efficiency_text = f"Speed-to-heart-rate efficiency was {efficiency:.3f} (km/h per bpm)."
        if efficiency >= 0.19:
            efficiency_status = "Strong"
            efficiency_tone = "positive"
        elif efficiency >= 0.15:
            efficiency_status = "Moderate"
            efficiency_tone = "neutral"
        else:
            efficiency_status = "Low"
            efficiency_tone = "negative"

    return [
        {
            "title": "Intensity Profile",
            "status": intensity_status,
            "text": intensity_text,
            "tone": intensity_tone,
        },
        {
            "title": "Efficiency",
            "status": efficiency_status,
            "text": efficiency_text,
            "tone": efficiency_tone,
        },
    ]


def find_example_tcx_file(data_dir: str, preferred_file: str = DEFAULT_TCX_FILE) -> tuple[str, str]:
    tcx_files = sorted([name for name in os.listdir(data_dir) if name.lower().endswith(".tcx")])
    if not tcx_files:
        raise FileNotFoundError(f"No TCX files found in {data_dir}")

    selected_file = preferred_file if preferred_file in tcx_files else tcx_files[0]
    return selected_file, os.path.join(data_dir, selected_file)


def build_activity_payload_from_single_tcx(data_dir: str) -> dict[str, Any]:
    parser = DataParser()
    cleaner = DataCleaner()

    source_file, file_path = find_example_tcx_file(data_dir)
    exercise = parser.parse_tcx_file(file_path)
    if exercise is None:
        raise ValueError(f"Could not parse TCX file: {file_path}")

    total_summary = cleaner.build_dashboard([(source_file, exercise)])
    if total_summary.empty:
        raise ValueError(f"No summary data generated from: {file_path}")

    row = total_summary.iloc[0]
    zone_shares = zone_percentages(row)
    default_summary_metrics = {
        "source_file": source_file,
        "distance_km": format_metric(row.get("distance_km"), " km", precision=1),
        "duration_min": format_metric(row.get("duration_min"), " min", precision=0),
        "avg_speed_kmh": format_metric(row.get("speed_kmh"), " km/h", precision=1),
        "avg_heart_rate": format_metric(row.get("avg_h_r"), " bpm", precision=0),
        "trimp_bannister": format_metric(row.get("trimp_bannister"), "", precision=1),
    }
    default_explanation = build_simple_explanation(row)
    default_rationales = build_rationale_items(zone_shares, row.get("speed_kmh"), row.get("avg_h_r"))

    summary_metrics = default_summary_metrics
    rationale_items = default_rationales
    conclusion = default_explanation
    context_error = None
    mining_summary = "Pattern mining was not available."
    mining_explanation = ""
    mining_insights = []
    mining_rules = []

    # Use the same contextual pipeline as the full dashboard, but for one selected activity page.
    context_state = initialize_context_pipeline(data_dir)
    if isinstance(context_state, dict):
        if context_state.get("error"):
            context_error = context_state.get("error")

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

        pattern_report = context_state.get("pattern_report")
        if isinstance(pattern_report, dict) and pattern_report:
            mining_summary = pattern_report.get("Summary", mining_summary)
            mining_explanation = pattern_report.get("Explanation", "")
            mining_insights = pattern_report.get("Insights", [])[:3]
            mining_rules = pattern_report.get("Top_Rules", [])[:3]
        elif context_error:
            LOGGER.warning("Context pipeline fallback active: %s", context_error)

    return {
        "id": EXAMPLE_ACTIVITY_ID,
        "source_file": source_file,
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


def create_example_server() -> Flask:
    activity = build_activity_payload_from_single_tcx(EXAMPLE_DATA_DIR)
    server = Flask(__name__, template_folder=os.path.join(PROJECT_ROOT, "templates"))

    @server.get("/")
    def idx():
        return redirect(f"/activity/{EXAMPLE_ACTIVITY_ID}")

    @server.get("/activity/<int:activity_id>")
    def activity_detail(activity_id: int):
        if activity_id == 0:
            return redirect(f"/activity/{EXAMPLE_ACTIVITY_ID}")
        if activity_id != EXAMPLE_ACTIVITY_ID:
            abort(404)
        return render_template("activity_detail.html", activity=activity, show_back_link=False)

    # activity_detail.html references /dash/assets/styles.css, so we mirror that path here.
    @server.get("/dash/assets/<path:filename>")
    def dash_assets(filename: str):
        return send_from_directory(ASSETS_DIR, filename)

    return server


if __name__ == "__main__":
    app = create_example_server()
    app.run(host="0.0.0.0", port=5004, debug=False)
