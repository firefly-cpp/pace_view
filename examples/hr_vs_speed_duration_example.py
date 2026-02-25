"""Standalone example for the HR vs Speed x Duration card.

Run:
    python examples/hr_vs_speed_duration_example.py
"""

from dash import Dash, dcc, html

from plot_card_common import ASSETS_DIR, apply_theme, load_dashboard_summary

# This example renders a single static heatmap card.
cleaner, total_summary = load_dashboard_summary()
_, _, _, fig4 = cleaner.return_figures(total_summary, "7D")
fig4 = apply_theme(fig4)

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
                                html.H1("HR vs Speed x Duration", className="hero__title"),
                                html.P(
                                    "Isolated example of the heatmap card for speed-duration-heart-rate relationships.",
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
                                html.H3("HR vs Speed x Duration", className="card__title"),
                                html.Div("Heatmap", className="card__pill card__pill--amber"),
                            ],
                        ),
                        dcc.Graph(
                            id="heatmap_fig",
                            figure=fig4,
                            config={"displayModeBar": False, "responsive": True},
                            style={"height": "100%", "minHeight": "360px"},
                        ),
                    ],
                ),
            ],
        ),
    ],
)


if __name__ == "__main__":
    # Dedicated port so this example can run alongside other examples.
    app.run(host="0.0.0.0", port=5002, debug=True)
