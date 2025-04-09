import json
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, dash_table
from dash.dependencies import ALL

# Constantes según la norma IEC 60255-151 para curva SI
K = 0.14
N = 0.02
CTI = 0.2  # Intervalo de tiempo de coordinación típico (en segundos)

# Rutas de los archivos
RELAY_DATA_PATH = "/Users/gustavo/Documents/Projects/TESIS_UNAL/optimizacion-coordinacion-protecciones/data/raw/data_relays_scenario_base.json"
RELAY_PAIRS_PATH = "/Users/gustavo/Documents/Projects/TESIS_UNAL/optimizacion-coordinacion-protecciones/data/config/relay_pairs.json"
SHORT_CIRCUIT_PATH = "/Users/gustavo/Documents/Projects/TESIS_UNAL/optimizacion-coordinacion-protecciones/data/raw/data_short_circuit_scenario_base.json"

# Cargar los datos desde los archivos
def load_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo en {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: No se pudo decodificar el JSON en {file_path}")
        return None

relay_data = load_json_file(RELAY_DATA_PATH)
relay_pairs = load_json_file(RELAY_PAIRS_PATH)
short_circuit_data = load_json_file(SHORT_CIRCUIT_PATH)

# Verificar que los datos se cargaron correctamente y corresponden a scenario_1
if not relay_data or not relay_pairs or not short_circuit_data or relay_data.get("scenario_id") != "scenario_1" or short_circuit_data.get("scenario_id") != "scenario_1":
    raise SystemExit("No se pudieron cargar los datos necesarios o no corresponden a scenario_1. Verifica las rutas y el formato de los archivos.")

# Función para calcular el tiempo de operación del relé
def calculate_operation_time(I_shc, I_pi, TDS):
    M = I_shc / I_pi
    if M <= 1:
        return float('inf')
    return (K / (M**N - 1)) * TDS

# Generar curva de tiempo inverso para un relé
def generate_inverse_time_curve(I_pi, TDS, I_shc_range):
    return [calculate_operation_time(I, I_pi, TDS) for I in I_shc_range]

# Analizar la coordinación
def analyze_coordination(relay_data, relay_pairs, short_circuit_data):
    coordinated_pairs = []
    uncoordinated_pairs = []
    
    for line, pair_data in relay_pairs.items():
        for scenario in pair_data["scenarios"].keys():
            config = pair_data["scenarios"][scenario]
            main_relay = config["main"]["relay"]
            backups = config["backups"]
            
            main_tds = relay_data["relay_values"][main_relay]["TDS"]
            main_pickup = relay_data["relay_values"][main_relay]["pickup"]
            main_currents = short_circuit_data["lines"][line]["scenarios"][scenario]["main"]["currents"]
            I_shc_main = max(main_currents["bus1"], main_currents["bus2"])
            t_m_ref = calculate_operation_time(I_shc_main, main_pickup, main_tds)
            
            I_shc_range = np.linspace(main_pickup, max(I_shc_main, main_pickup * 10), 100)
            main_curve = generate_inverse_time_curve(main_pickup, main_tds, I_shc_range)
            
            for backup in backups:
                backup_relay = backup["relay"]
                backup_line = backup["line"]
                
                backup_tds = relay_data["relay_values"][backup_relay]["TDS"]
                backup_pickup = relay_data["relay_values"][backup_relay]["pickup"]
                backup_currents = next(
                    b["currents"] for b in short_circuit_data["lines"][line]["scenarios"][scenario]["backups"]
                    if b["relay"] == backup_relay
                )
                I_shc_backup = max(backup_currents["bus1"], backup_currents["bus2"])
                t_b_ref = calculate_operation_time(I_shc_backup, backup_pickup, backup_tds)
                
                delta_t = t_b_ref - t_m_ref - CTI
                MT = (delta_t - abs(delta_t)) / 2
                
                backup_curve = generate_inverse_time_curve(backup_pickup, backup_tds, I_shc_range)
                
                pair_info = {
                    "line": line,
                    "scenario": scenario,
                    "main_relay": main_relay,
                    "main_pickup": main_pickup,
                    "main_tds": main_tds,
                    "main_curve": main_curve,
                    "main_I_shc": I_shc_main,
                    "backup_relay": backup_relay,
                    "backup_pickup": backup_pickup,
                    "backup_tds": backup_tds,
                    "backup_curve": backup_curve,
                    "backup_I_shc": I_shc_backup,
                    "t_m_ref": t_m_ref,
                    "t_b_ref": t_b_ref,
                    "delta_t": delta_t,
                    "MT": MT,
                    "backup_line": backup_line,
                    "I_shc_range": I_shc_range
                }
                
                if delta_t >= 0:
                    coordinated_pairs.append(pair_info)
                else:
                    uncoordinated_pairs.append(pair_info)
    
    tmt_total = sum(pair["MT"] for pair in coordinated_pairs + uncoordinated_pairs)
    total_pairs = len(coordinated_pairs) + len(uncoordinated_pairs)
    
    return coordinated_pairs, uncoordinated_pairs, tmt_total, total_pairs

# Analizar datos
coordinated_pairs, uncoordinated_pairs, tmt_total, total_pairs = analyze_coordination(relay_data, relay_pairs, short_circuit_data)

# Crear la aplicación Dash
app = dash.Dash(__name__)

# Opciones para los dropdowns
coordinated_options = [
    {"label": f"{pair['line']}_{pair['scenario']}_{pair['backup_relay']}", "value": idx}
    for idx, pair in enumerate(coordinated_pairs)
]
uncoordinated_options = [
    {"label": f"{pair['line']}_{pair['scenario']}_{pair['backup_relay']}", "value": idx}
    for idx, pair in enumerate(uncoordinated_pairs)
]

# Resumen de pares para las tablas
coordinated_summary = [
    {
        "Línea": f"{pair['line']}_{pair['scenario']}",
        "Main Relay": pair["main_relay"],
        "TDS (Main)": f"{pair['main_tds']:.5f}",
        "Pickup (Main)": f"{pair['main_pickup']:.5f}",
        "I_shc (Main)": f"{pair['main_I_shc']:.3f}",
        "t_m": f"{pair['t_m_ref']:.3f}",
        "Backup Relay": pair["backup_relay"],
        "TDS (Backup)": f"{pair['backup_tds']:.5f}",
        "Pickup (Backup)": f"{pair['backup_pickup']:.5f}",
        "I_shc (Backup)": f"{pair['backup_I_shc']:.3f}",
        "t_b": f"{pair['t_b_ref']:.3f}",
        "Δt": f"{pair['delta_t']:.3f}",
        "MT": f"{pair['MT']:.3f}"
    }
    for pair in coordinated_pairs
]
uncoordinated_summary = [
    {
        "Línea": f"{pair['line']}_{pair['scenario']}",
        "Main Relay": pair["main_relay"],
        "TDS (Main)": f"{pair['main_tds']:.5f}",
        "Pickup (Main)": f"{pair['main_pickup']:.5f}",
        "I_shc (Main)": f"{pair['main_I_shc']:.3f}",
        "t_m": f"{pair['t_m_ref']:.3f}",
        "Backup Relay": pair["backup_relay"],
        "TDS (Backup)": f"{pair['backup_tds']:.5f}",
        "Pickup (Backup)": f"{pair['backup_pickup']:.5f}",
        "I_shc (Backup)": f"{pair['backup_I_shc']:.3f}",
        "t_b": f"{pair['t_b_ref']:.3f}",
        "Δt": f"{pair['delta_t']:.3f}",
        "MT": f"{pair['MT']:.3f}"
    }
    for pair in uncoordinated_pairs
]

# Layout de la aplicación
app.layout = html.Div([
    html.H1(f"Análisis de Coordinación - Scenario_1 (TMT Total: {tmt_total:.3f}s, Total Pares: {total_pairs})", style={'textAlign': 'center'}),
    dcc.Tabs([
        dcc.Tab(label=f"Coordinados ({len(coordinated_pairs)})", children=[
            html.Div([
                dcc.Dropdown(
                    id='coordinated-dropdown',
                    options=coordinated_options,
                    value=0 if coordinated_pairs else None,
                    style={'width': '50%', 'margin': '20px auto'}
                ),
                dcc.Graph(id='coordinated-graph', style={'height': '600px', 'width': '90%', 'margin': '0 auto'}),
                dash_table.DataTable(
                    id='coordinated-pair-table',
                    columns=[
                        {"name": "Parámetro", "id": "parameter"},
                        {"name": "Valor", "id": "value"}
                    ],
                    style_table={'width': '50%', 'margin': '20px auto'},
                    style_cell={'textAlign': 'left', 'padding': '5px'}
                ),
                html.H3("Resumen de Pares Coordinados", style={'textAlign': 'center'}),
                dash_table.DataTable(
                    id='coordinated-summary-table',
                    columns=[{"name": i, "id": i} for i in coordinated_summary[0].keys()] if coordinated_summary else [],
                    data=coordinated_summary,
                    style_table={'overflowX': 'auto', 'width': '90%', 'margin': '20px auto'},
                    style_cell={'textAlign': 'center', 'minWidth': '100px', 'padding': '5px'}
                )
            ])
        ]),
        dcc.Tab(label=f"Descoordinados ({len(uncoordinated_pairs)})", children=[
            html.Div([
                dcc.Dropdown(
                    id='uncoordinated-dropdown',
                    options=uncoordinated_options,
                    value=0 if uncoordinated_pairs else None,
                    style={'width': '50%', 'margin': '20px auto'}
                ),
                dcc.Graph(id='uncoordinated-graph', style={'height': '600px', 'width': '90%', 'margin': '0 auto'}),
                dash_table.DataTable(
                    id='uncoordinated-pair-table',
                    columns=[
                        {"name": "Parámetro", "id": "parameter"},
                        {"name": "Valor", "id": "value"}
                    ],
                    style_table={'width': '50%', 'margin': '20px auto'},
                    style_cell={'textAlign': 'left', 'padding': '5px'}
                ),
                html.H3("Curva de Valores de MT (Descoordinados)", style={'textAlign': 'center'}),
                dcc.Graph(id='mt-graph', style={'height': '400px', 'width': '90%', 'margin': '0 auto'}),
                html.H3("Resumen de Pares Descoordinados", style={'textAlign': 'center'}),
                dash_table.DataTable(
                    id='uncoordinated-summary-table',
                    columns=[{"name": i, "id": i} for i in uncoordinated_summary[0].keys()] if uncoordinated_summary else [],
                    data=uncoordinated_summary,
                    style_table={'overflowX': 'auto', 'width': '90%', 'margin': '20px auto'},
                    style_cell={'textAlign': 'center', 'minWidth': '100px', 'padding': '5px'}
                )
            ])
        ])
    ])
])

# Callback para actualizar gráficos y tablas
@app.callback(
    [Output('coordinated-graph', 'figure'), Output('coordinated-pair-table', 'data'),
     Output('uncoordinated-graph', 'figure'), Output('uncoordinated-pair-table', 'data'),
     Output('mt-graph', 'figure')],
    [Input('coordinated-dropdown', 'value'), Input('uncoordinated-dropdown', 'value')]
)
def update_dashboard(coordinated_idx, uncoordinated_idx):
    # Gráfico y tabla para coordinados
    coordinated_fig = go.Figure()
    coordinated_table_data = []
    if coordinated_idx is not None and coordinated_pairs:
        pair = coordinated_pairs[coordinated_idx]
        pair_id = f"{pair['line']}_{pair['scenario']}_{pair['backup_relay']}"
        
        # Curva y punto para relé principal
        coordinated_fig.add_trace(go.Scatter(x=pair["I_shc_range"], y=pair["main_curve"], mode="lines", name=f"{pair['main_relay']} (Main)", hovertemplate=f"Main: {pair['main_relay']}<br>I_shc: %{{x:.3f}}<br>t: %{{y:.3f}}s", line=dict(color="blue")))
        coordinated_fig.add_trace(go.Scatter(x=[pair["main_I_shc"]], y=[pair["t_m_ref"]], mode="markers", name=f"Op {pair['main_relay']}", hovertemplate=f"Main: {pair['main_relay']}<br>I_shc: {pair['main_I_shc']:.3f}A<br>t: {pair['t_m_ref']:.3f}s", marker=dict(color="blue", size=10)))
        coordinated_fig.add_trace(go.Scatter(x=[pair["main_I_shc"], pair["main_I_shc"]], y=[0, pair["t_m_ref"]], mode="lines", name=f"I_shc {pair['main_relay']}", hovertemplate=f"I_shc Main: {pair['main_I_shc']:.3f}A<br>t: {pair['t_m_ref']:.3f}s", line=dict(color="blue", dash="dash")))
        
        # Curva y punto para relé de respaldo
        coordinated_fig.add_trace(go.Scatter(x=pair["I_shc_range"], y=pair["backup_curve"], mode="lines", name=f"{pair['backup_relay']} (Backup)", hovertemplate=f"Backup: {pair['backup_relay']}<br>I_shc: %{{x:.3f}}<br>t: %{{y:.3f}}s", line=dict(color="red")))
        coordinated_fig.add_trace(go.Scatter(x=[pair["backup_I_shc"]], y=[pair["t_b_ref"]], mode="markers", name=f"Op {pair['backup_relay']}", hovertemplate=f"Backup: {pair['backup_relay']}<br>I_shc: {pair['backup_I_shc']:.3f}A<br>t: {pair['t_b_ref']:.3f}s", marker=dict(color="red", size=10)))
        coordinated_fig.add_trace(go.Scatter(x=[pair["backup_I_shc"], pair["backup_I_shc"]], y=[0, pair["t_b_ref"]], mode="lines", name=f"I_shc {pair['backup_relay']}", hovertemplate=f"I_shc Backup: {pair['backup_I_shc']:.3f}A<br>t: {pair['t_b_ref']:.3f}s", line=dict(color="red", dash="dash")))
        
        coordinated_fig.update_layout(
            title_text=f"Curva de Tiempo Inverso - {pair_id}", title_x=0.5,
            xaxis_title="Corriente de cortocircuito (I_shc, A)", yaxis_title="Tiempo de operación (s)",
            yaxis_type="log", yaxis_range=[np.log10(0.01), np.log10(10)], showlegend=True,
            margin=dict(l=50, r=50, t=50, b=50)
        )
        
        coordinated_table_data = [
            {"parameter": "Línea", "value": f"{pair['line']}_{pair['scenario']}"},
            {"parameter": "Relé Principal", "value": pair["main_relay"]},
            {"parameter": "TDS (Main)", "value": f"{pair['main_tds']:.5f}"},
            {"parameter": "Pickup (Main)", "value": f"{pair['main_pickup']:.5f} A"},
            {"parameter": "I_shc (Main)", "value": f"{pair['main_I_shc']:.3f} A"},
            {"parameter": "t_m", "value": f"{pair['t_m_ref']:.3f} s"},
            {"parameter": "Relé Backup", "value": f"{pair['backup_relay']} ({pair['backup_line']})"},
            {"parameter": "TDS (Backup)", "value": f"{pair['backup_tds']:.5f}"},
            {"parameter": "Pickup (Backup)", "value": f"{pair['backup_pickup']:.5f} A"},
            {"parameter": "I_shc (Backup)", "value": f"{pair['backup_I_shc']:.3f} A"},
            {"parameter": "t_b", "value": f"{pair['t_b_ref']:.3f} s"},
            {"parameter": "Δt", "value": f"{pair['delta_t']:.3f} s"},
            {"parameter": "MT", "value": f"{pair['MT']:.3f} s"}
        ]
    else:
        coordinated_fig.update_layout(title_text="No hay pares coordinados", title_x=0.5)

    # Gráfico y tabla para descoordinados
    uncoordinated_fig = go.Figure()
    uncoordinated_table_data = []
    if uncoordinated_idx is not None and uncoordinated_pairs:
        pair = uncoordinated_pairs[uncoordinated_idx]
        pair_id = f"{pair['line']}_{pair['scenario']}_{pair['backup_relay']}"
        
        # Curva y punto para relé principal
        uncoordinated_fig.add_trace(go.Scatter(x=pair["I_shc_range"], y=pair["main_curve"], mode="lines", name=f"{pair['main_relay']} (Main)", hovertemplate=f"Main: {pair['main_relay']}<br>I_shc: %{{x:.3f}}<br>t: %{{y:.3f}}s", line=dict(color="blue")))
        uncoordinated_fig.add_trace(go.Scatter(x=[pair["main_I_shc"]], y=[pair["t_m_ref"]], mode="markers", name=f"Op {pair['main_relay']}", hovertemplate=f"Main: {pair['main_relay']}<br>I_shc: {pair['main_I_shc']:.3f}A<br>t: {pair['t_m_ref']:.3f}s", marker=dict(color="blue", size=10)))
        uncoordinated_fig.add_trace(go.Scatter(x=[pair["main_I_shc"], pair["main_I_shc"]], y=[0, pair["t_m_ref"]], mode="lines", name=f"I_shc {pair['main_relay']}", hovertemplate=f"I_shc Main: {pair['main_I_shc']:.3f}A<br>t: {pair['t_m_ref']:.3f}s", line=dict(color="blue", dash="dash")))
        
        # Curva y punto para relé de respaldo
        uncoordinated_fig.add_trace(go.Scatter(x=pair["I_shc_range"], y=pair["backup_curve"], mode="lines", name=f"{pair['backup_relay']} (Backup)", hovertemplate=f"Backup: {pair['backup_relay']}<br>I_shc: %{{x:.3f}}<br>t: %{{y:.3f}}s", line=dict(color="red")))
        uncoordinated_fig.add_trace(go.Scatter(x=[pair["backup_I_shc"]], y=[pair["t_b_ref"]], mode="markers", name=f"Op {pair['backup_relay']}", hovertemplate=f"Backup: {pair['backup_relay']}<br>I_shc: {pair['backup_I_shc']:.3f}A<br>t: {pair['t_b_ref']:.3f}s", marker=dict(color="red", size=10)))
        uncoordinated_fig.add_trace(go.Scatter(x=[pair["backup_I_shc"], pair["backup_I_shc"]], y=[0, pair["t_b_ref"]], mode="lines", name=f"I_shc {pair['backup_relay']}", hovertemplate=f"I_shc Backup: {pair['backup_I_shc']:.3f}A<br>t: {pair['t_b_ref']:.3f}s", line=dict(color="red", dash="dash")))
        
        uncoordinated_fig.update_layout(
            title_text=f"Curva de Tiempo Inverso - {pair_id}", title_x=0.5,
            xaxis_title="Corriente de cortocircuito (I_shc, A)", yaxis_title="Tiempo de operación (s)",
            yaxis_type="log", yaxis_range=[np.log10(0.01), np.log10(10)], showlegend=True,
            margin=dict(l=50, r=50, t=50, b=50)
        )
        
        uncoordinated_table_data = [
            {"parameter": "Línea", "value": f"{pair['line']}_{pair['scenario']}"},
            {"parameter": "Relé Principal", "value": pair["main_relay"]},
            {"parameter": "TDS (Main)", "value": f"{pair['main_tds']:.5f}"},
            {"parameter": "Pickup (Main)", "value": f"{pair['main_pickup']:.5f} A"},
            {"parameter": "I_shc (Main)", "value": f"{pair['main_I_shc']:.3f} A"},
            {"parameter": "t_m", "value": f"{pair['t_m_ref']:.3f} s"},
            {"parameter": "Relé Backup", "value": f"{pair['backup_relay']} ({pair['backup_line']})"},
            {"parameter": "TDS (Backup)", "value": f"{pair['backup_tds']:.5f}"},
            {"parameter": "Pickup (Backup)", "value": f"{pair['backup_pickup']:.5f} A"},
            {"parameter": "I_shc (Backup)", "value": f"{pair['backup_I_shc']:.3f} A"},
            {"parameter": "t_b", "value": f"{pair['t_b_ref']:.3f} s"},
            {"parameter": "Δt", "value": f"{pair['delta_t']:.3f} s"},
            {"parameter": "MT", "value": f"{pair['MT']:.3f} s"}
        ]
    else:
        uncoordinated_fig.update_layout(title_text="No hay pares descoordinados", title_x=0.5)

    # Gráfico de MT para descoordinados
    mt_fig = go.Figure()
    if uncoordinated_pairs:
        mt_values = [abs(pair["MT"]) for pair in uncoordinated_pairs]
        mt_labels = [f"{pair['line']}_{pair['scenario']}_{pair['backup_relay']}" for pair in uncoordinated_pairs]
        
        mt_fig.add_trace(go.Scatter(
            x=mt_labels, y=mt_values, mode="lines+markers", name="|MT|",
            hovertemplate="Par: %{x}<br>|MT|: %{y:.3f}s",
            line=dict(color="purple"), marker=dict(size=8)
        ))
        
        mt_fig.update_layout(
            title_text="Valores de |MT| para Pares Descoordinados", title_x=0.5,
            xaxis_title="Pares de Relés", yaxis_title="|MT| (s)",
            xaxis={'tickangle': 45}, showlegend=True,
            margin=dict(l=50, r=50, t=50, b=100)
        )
    else:
        mt_fig.update_layout(title_text="No hay pares descoordinados", title_x=0.5)

    return coordinated_fig, coordinated_table_data, uncoordinated_fig, uncoordinated_table_data, mt_fig

# Ejecutar la aplicación
if __name__ == '__main__':
    app.run_server(debug=True)