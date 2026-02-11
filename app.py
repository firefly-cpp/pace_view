from flask import Flask, render_template_string, redirect
from dash import Dash, html, dcc, Input, Output
import plotly.express as px
import os
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
        # prevent_initial_call='initial_duplicate',
        prevent_initial_callbacks='initial_duplicate'
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

    fig1, fig2, fig3, fig4 = reader.return_figures(total_summary, "7D")

    # df = px.data.iris()
    # fig = px.scatter(df, x="sepal_width", y="sepal_length", color="species")

    dash_app.layout = html.Div(
        style={"maxWidth": 900, "margin": "40px auto", "fontFamily": "system-ui"},
        children=[
            html.H2("Dashboard"),
            # html.P("This Dash app is mounted at /dash/ and shares the same Flask server."),
            html.Center(children=[
                html.Button("1 week", id="1_week", n_clicks=0, style={"backgroundColor":"red"}),
                html.Button("1 month", id="1_month", n_clicks=0),
                html.Button("1 year", id="1_year", n_clicks=0)
            ]),
            html.Div(children=[
                dcc.Graph(id="fig1", figure=fig1),
                dcc.Graph(id="fig2", figure=fig2),
            # ]),
            # html.Div(children=[
                # dcc.Graph(id="fig3", figure=fig3),
                dcc.Graph(id="fig4", figure=fig4),
            ]),
            html.Hr(),
            # html.A("Back to Flask home", href="/"),
        ],
    )

    @dash_app.callback(
        Output("fig1", "figure", allow_duplicate=True),
        Output("1_week", "style", allow_duplicate=True),
        Output("1_month", "style", allow_duplicate=True),
        Output("1_year", "style", allow_duplicate=True),
        # Output("fig2", "figure"),
        Input("1_week", "n_clicks")
    )
    def create_figure_for_1_week(n):
        fig1, _, _, _ = reader.return_figures(total_summary, "7D")
        return fig1, {"backgroundColor": "red"}, {}, {}

    @dash_app.callback(
        Output("fig1", "figure", allow_duplicate=True),
        Output("1_week", "style", allow_duplicate=True),
        Output("1_month", "style", allow_duplicate=True),
        Output("1_year", "style", allow_duplicate=True),
        Input("1_month", "n_clicks"),
        prevent_initial_call=True,
    )
    def create_figure_for_1_month(n):
        fig1, _, _, _ = reader.return_figures(total_summary, "30D")
        return fig1, {}, {"backgroundColor": "red"}, {}

    @dash_app.callback(
        Output("fig1", "figure", allow_duplicate=True),
        # Output("fig2", "figure"),
        Output("1_week", "style", allow_duplicate=True),
        Output("1_month", "style", allow_duplicate=True),
        Output("1_year", "style", allow_duplicate=True),
        Input("1_year", "n_clicks"),
        prevent_initial_call=True,
    )
    def create_figure_for_1_year(n):
        fig1, _, _, _ = reader.return_figures(total_summary, "365D")
        return fig1, {}, {},  {"backgroundColor": "red"}

    return dash_app

server = create_flask_server()
dash_app = create_dash_app(server)

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=5000, debug=True)