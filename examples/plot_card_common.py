"""Shared helpers for standalone dashboard card examples.

This module centralizes:
- project path resolution for running scripts from `examples/`
- dashboard data loading from `data/`
- common Plotly styling used by all card examples
"""

import logging
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

if PROJECT_ROOT not in sys.path:
    # Let example scripts import `pace_view` without installing the package first.
    sys.path.insert(0, PROJECT_ROOT)

from pace_view.data_cleaning import DataCleaner
from pace_view.data_parsing import DataParser

LOGGER = logging.getLogger(__name__)


def load_exercises_with_filenames(parser: DataParser, directory_name: str):
    """Load readable TCX files and keep `(source_file, exercise)` tuples."""
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
    return exercises


def load_dashboard_summary():
    """Return the shared cleaner instance and prepared dashboard summary dataframe."""
    parser = DataParser()
    cleaner = DataCleaner()
    exercises = load_exercises_with_filenames(parser, DATA_DIR)
    total_summary = cleaner.build_dashboard(exercises)
    return cleaner, total_summary


def apply_theme(fig):
    """Apply the same visual theme used by the main dashboard."""
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
