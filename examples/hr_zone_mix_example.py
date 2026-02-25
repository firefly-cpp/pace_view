"""Standalone example for the HR Zone Mix card.

Run:
    python examples/hr_zone_mix_example.py
"""

import dash
from dash import Dash, Input, Output, dcc, html

from plot_card_common import ASSETS_DIR, apply_theme, load_dashboard_summary

# Load once at startup; callbacks only swap chart aggregation windows.
cleaner, total_summary = load_dashboard_summary()


def build_zone_mix_figure(period: str):
    """Build only figure 1 (zone mix pie) for the selected period."""
    fig1, _, _, _ = cleaner.return_figures(total_summary, period)
    return apply_theme(fig1)


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
                                html.H1("HR Zone Mix", className="hero__title"),
                                html.P(
                                    "Isolated example of the zone distribution card with aggregation controls.",
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
                                html.H3("HR Zone Mix", className="card__title"),
                                html.Div(
                                    className="card__header-actions",
                                    children=[
                                        html.Div(
                                            className="range-toggle",
                                            children=[
                                                html.Button("7 days", id="zone_week", n_clicks=0, className="range-btn active"),
                                                html.Button("30 days", id="zone_month", n_clicks=0, className="range-btn"),
                                                html.Button("12 months", id="zone_year", n_clicks=0, className="range-btn"),
                                            ],
                                        ),
                                        html.Div("Aggregated by 7 days", id="zone_range_label", className="card__pill"),
                                    ],
                                ),
                            ],
                        ),
                        dcc.Graph(
                            id="zone_fig",
                            figure=build_zone_mix_figure("7D"),
                            config={"displayModeBar": False, "responsive": True},
                            style={"height": "100%", "minHeight": "360px"},
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# Update the zone mix period and keep button active states in sync.
@app.callback(
    Output("zone_fig", "figure"),
    Output("zone_range_label", "children"),
    Output("zone_week", "className"),
    Output("zone_month", "className"),
    Output("zone_year", "className"),
    Input("zone_week", "n_clicks"),
    Input("zone_month", "n_clicks"),
    Input("zone_year", "n_clicks"),
)
def update_zone_mix(_n_week, _n_month, _n_year):
    triggered = dash.callback_context.triggered
    trigger_id = triggered[0]["prop_id"].split(".")[0] if triggered else ""

    if trigger_id == "zone_month":
        period = "30D"
        label = "Aggregated by 30 days"
        active = "month"
    elif trigger_id == "zone_year":
        period = "365D"
        label = "Aggregated by 12 months"
        active = "year"
    else:
        period = "7D"
        label = "Aggregated by 7 days"
        active = "week"

    week_class = "range-btn active" if active == "week" else "range-btn"
    month_class = "range-btn active" if active == "month" else "range-btn"
    year_class = "range-btn active" if active == "year" else "range-btn"

    return build_zone_mix_figure(period), label, week_class, month_class, year_class


if __name__ == "__main__":
    # Dedicated port so this example can run alongside other examples.
    app.run(host="0.0.0.0", port=5003, debug=True)
