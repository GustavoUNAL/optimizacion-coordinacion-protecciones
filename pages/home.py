from dash import Dash, html, dcc, callback, Output, Input
import dash_bootstrap_components as dbc
from pages import home, dashboard_opt, dashboard_base, dashboard_comparison

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    external_scripts=["https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.5/MathJax.js?config=TeX-MML-AM_CHTML"],
    suppress_callback_exceptions=True
)

# Barra de navegación
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Home", href="/")),
        dbc.NavItem(dbc.NavLink("Dashboard Automatización", href="/dashboard_base")),
        dbc.NavItem(dbc.NavLink("Dashboard Optimizado", href="/dashboard_opt")),
        dbc.NavItem(dbc.NavLink("Comparación TDS/Pickup/MT", href="/dashboard_comparison")),
    ],
    brand="Coordinación de Relés",
    brand_href="/",
    color="primary",
    dark=True,
)

# Layout principal
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    navbar,
    html.Div(id="page-content")
])

# Callback para cambiar de página
@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname == "/dashboard_base":
        return dashboard_base.layout
    elif pathname == "/dashboard_opt":
        return dashboard_opt.layout
    elif pathname == "/dashboard_comparison":
        return dashboard_comparison.layout
    else:
        return home.layout

# Registrar callbacks de dashboard_base (Automatización)
@callback(
    [Output('coordinated-graph-base', 'figure'), Output('coordinated-pair-table-base', 'data'),
     Output('uncoordinated-graph-base', 'figure'), Output('uncoordinated-pair-table-base', 'data'),
     Output('mt-graph-base', 'figure')],
    [Input('coordinated-dropdown-base', 'value'), Input('uncoordinated-dropdown-base', 'value')]
)
def update_dashboard_base(coordinated_idx, uncoordinated_idx):
    return dashboard_base.update_dashboard(coordinated_idx, uncoordinated_idx)

# Registrar callbacks de dashboard_opt
@callback(
    [Output('coordinated-graph-opt', 'figure'), Output('coordinated-pair-table-opt', 'data'),
     Output('uncoordinated-graph-opt', 'figure'), Output('uncoordinated-pair-table-opt', 'data'),
     Output('mt-graph-opt', 'figure')],
    [Input('coordinated-dropdown-opt', 'value'), Input('uncoordinated-dropdown-opt', 'value')]
)
def update_dashboard_opt(coordinated_idx, uncoordinated_idx):
    return dashboard_opt.update_dashboard(coordinated_idx, uncoordinated_idx)

# Registrar callbacks de dashboard_comparison
@callback(
    [Output('tds-graph', 'figure'), Output('pickup-graph', 'figure'), Output('mt-graph', 'figure'),
     Output('mt-pairs-graph', 'figure')],
    [Input('url', 'pathname')]
)
def update_dashboard_comparison(pathname):
    return dashboard_comparison.update_dashboard(None)

if __name__ == "__main__":
    app.run_server(debug=True)

server = app.server  # Para Gunicorn