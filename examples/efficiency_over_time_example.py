"""Standalone example for the Efficiency Over Time card.

Run:
    python examples/efficiency_over_time_example.py
"""

import dash
from dash import Dash, Input, Output, dcc, html

from plot_card_common import ASSETS_DIR, apply_theme, load_dashboard_summary

# Load once at startup; callbacks only change the rolling window.
cleaner, total_summary = load_dashboard_summary()


def build_efficiency_figure(window_days: int):
    """Build only figure 2 (efficiency scatter + rolling trend)."""
    _, fig2, _, _ = cleaner.return_figures(total_summary, "7D", window_days)
    return apply_theme(fig2)


app = Dash(
    __name__,
    assets_folder=ASSETS_DIR,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

app.layout = html.Div(
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
                                html.Div("Example Card", className="hero__eyebrow"),
                                html.H1("Efficiency Over Time", className="hero__title"),
                                html.P(
                                    "Isolated example of the efficiency trend card with rolling-window controls.",
                                    className="hero__subtitle",
                                ),
                            ]
                        ),
                    ],
                ),
                html.Div(
                    className="card graph-card graph-card--tall",
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
                            id="trend_fig",
                            figure=build_efficiency_figure(90),
                            config={"displayModeBar": False, "responsive": True},
                            style={"height": "100%", "minHeight": "360px"},
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# Update rolling trend window and keep button active states in sync.
@app.callback(
    Output("trend_fig", "figure"),
    Output("trend_label", "children"),
    Output("trend_90", "className"),
    Output("trend_180", "className"),
    Output("trend_365", "className"),
    Input("trend_90", "n_clicks"),
    Input("trend_180", "n_clicks"),
    Input("trend_365", "n_clicks"),
)
def update_trend_window(_input_90, _input_180, _input_365):
    triggered = dash.callback_context.triggered
    trigger_id = triggered[0]["prop_id"].split(".")[0] if triggered else ""

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

    class_90 = "range-btn active" if active == "90" else "range-btn"
    class_180 = "range-btn active" if active == "180" else "range-btn"
    class_365 = "range-btn active" if active == "365" else "range-btn"

    return build_efficiency_figure(window_days), label, class_90, class_180, class_365


if __name__ == "__main__":
    # Dedicated port so this example can run alongside other examples.
    app.run(host="0.0.0.0", port=5001, debug=True)
