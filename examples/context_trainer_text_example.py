"""Run ContextTrainer without Flask/Dash and print text-only output.

Run:
    python examples/context_trainer_text_example.py
    python examples/context_trainer_text_example.py --target-file 8.tcx
"""

import argparse
import os
import sys
from typing import Any

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
DEFAULT_HISTORY_FOLDER = os.path.join(CURRENT_DIR, "data")
DEFAULT_TARGET_FILE = "1.tcx"

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pace_view.core import ContextTrainer
from pace_view.config import get_weather_api_key


def print_section(title: str):
    print(f"\n{title}")
    print("-" * len(title))


def print_mapping(data: dict[str, Any]):
    if not data:
        print("No data.")
        return
    for key, value in data.items():
        print(f"- {key}: {value}")


def print_lines(lines: list[Any], limit: int = 5):
    if not lines:
        print("No entries.")
        return
    for idx, line in enumerate(lines[:limit], start=1):
        print(f"{idx}. {line}")


def resolve_target_file(history_folder: str, target_file: str | None) -> str:
    if target_file:
        candidate = target_file if os.path.isabs(target_file) else os.path.join(history_folder, target_file)
        if os.path.isfile(candidate):
            return candidate
        raise FileNotFoundError(f"Target TCX file not found: {candidate}")

    tcx_files = sorted([name for name in os.listdir(history_folder) if name.lower().endswith(".tcx")])
    if not tcx_files:
        raise FileNotFoundError(f"No TCX files found in {history_folder}")
    fallback = DEFAULT_TARGET_FILE if DEFAULT_TARGET_FILE in tcx_files else tcx_files[0]
    return os.path.join(history_folder, fallback)


def parse_args():
    parser = argparse.ArgumentParser(description="ContextTrainer text-only example")
    parser.add_argument(
        "--history-folder",
        default=DEFAULT_HISTORY_FOLDER,
        help="Folder with historical TCX files used for fitting and pattern mining.",
    )
    parser.add_argument(
        "--target-file",
        default=DEFAULT_TARGET_FILE,
        help="TCX file (name or absolute path) to explain after fitting.",
    )
    parser.add_argument(
        "--weather-api-key",
        default=None,
        help="Optional Visual Crossing API key for weather enrichment.",
    )
    parser.add_argument(
        "--time-delta",
        type=int,
        default=1,
        help="Weather sampling delta used by DataParser.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    history_folder = os.path.abspath(args.history_folder)
    if not os.path.isdir(history_folder):
        raise FileNotFoundError(f"History folder not found: {history_folder}")

    target_file = resolve_target_file(history_folder, args.target_file)
    weather_api_key = args.weather_api_key or get_weather_api_key()
    weather_key_source = "cli" if args.weather_api_key else ("env/.env" if weather_api_key else "none")

    print_section("Configuration")
    print(f"History folder: {history_folder}")
    print(f"Target file: {target_file}")
    print(f"Weather API key set: {'yes' if weather_api_key else 'no'}")
    print(f"Weather API key source: {weather_key_source}")

    trainer = ContextTrainer(
        history_folder=history_folder,
        weather_api_key=weather_api_key,
        time_delta=args.time_delta,
    )

    trainer.fit()
    pattern_report = trainer.mine_patterns() or {}
    activity_report = trainer.explain(target_file) or {}

    print_section("Activity Summary Metrics")
    print_mapping(activity_report.get("Summary_Metrics", {}))

    print_section("Activity Rationales")
    print_mapping(activity_report.get("Rationales", {}))

    print_section("Activity Conclusion")
    print(activity_report.get("Conclusion", "No conclusion produced."))

    print_section("Pattern Mining Summary")
    print(pattern_report.get("Summary", "No summary produced."))

    print_section("Pattern Mining Insights")
    print_lines(pattern_report.get("Insights", []), limit=5)

    print_section("Top Pattern Rules")
    print_lines(pattern_report.get("Top_Rules", []), limit=5)


if __name__ == "__main__":
    main()
