import json
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html, dash_table

# Constantes
K = 0.14
N = 0.02
CTI = 0.2
MAX_TIME = 10.0

# Rutas relativas dentro del contenedor
RELAY_DATA_PATH = "data/processed/data_relays_scenario_base_optimized.json"
RELAY_PAIRS_PATH = "data/config/relay_pairs.json"
SHORT_CIRCUIT_PATH = "data/raw/data_short_circuit_scenario_base.json"
RELAY_DATA_BASE_PATH = "data/raw/data_relays_scenario_base.json"

# Cargar datos
def load_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error cargando {file_path}: {e}")
        return None

relay_data = load_json_file(RELAY_DATA_PATH)
relay_pairs = load_json_file(RELAY_PAIRS_PATH)
short_circuit_data = load_json_file(SHORT_CIRCUIT_PATH)
relay_data_base = load_json_file(RELAY_DATA_BASE_PATH)

if not all([relay_data, relay_pairs, short_circuit_data, relay_data_base]) or relay_data.get("scenario_id") != "scenario_1" or short_circuit_data.get("scenario_id") != "scenario_1":
    layout = html.Div("Error: No se pudieron cargar los datos o no corresponden a scenario_1.")
else:
    # Funciones
    def calculate_operation_time(I_shc, I_pi, TDS):
        if I_pi <= 0 or I_shc <= 0:
            return MAX_TIME
        M = I_shc / I_pi
        if M <= 1:
            return MAX_TIME
        try:
            time = (K / (M**N - 1)) * TDS
            return min(time, MAX_TIME)
        except:
            return MAX_TIME

    def generate_inverse_time_curve(I_pi, TDS, I_shc_range):
        return [calculate_operation_time(I, I_pi, TDS) for I in I_shc_range]

    def analyze_coordination(relay_data, relay_pairs, short_circuit_data):
        coordinated_pairs = []
        uncoordinated_pairs = []
        
        for line, pair_data in relay_pairs.items():
            for scenario in pair_data["scenarios"].keys():
                config = pair_data["scenarios"][scenario]
                main_relay = config["main"]["relay"]
                backups = config["backups"]
                
                main_tds = relay_data["optimized_relay_values"][main_relay]["TDS"]
                main_pickup = relay_data["optimized_relay_values"][main_relay]["pickup"]
                main_currents = short_circuit_data["lines"][line]["scenarios"][scenario]["main"]["currents"]
                I_shc_main = max(main_currents["bus1"], main_currents["bus2"])
                t_m_ref = calculate_operation_time(I_shc_main, main_pickup, main_tds)
                
                I_shc_range = np.linspace(main_pickup, max(I_shc_main, main_pickup * 10), 100)
                main_curve = generate_inverse_time_curve(main_pickup, main_tds, I_shc_range)
                
                for backup in backups:
                    backup_relay = backup["relay"]
                    backup_line = backup["line"]
                    backup_tds = relay_data["optimized_relay_values"][backup_relay]["TDS"]
                    backup_pickup = relay_data["optimized_relay_values"][backup_relay]["pickup"]
                    backup_currents = next(b["currents"] for b in short_circuit_data["lines"][line]["scenarios"][scenario]["backups"] if b["relay"] == backup_relay)
                    I_shc_backup = max(backup_currents["bus1"], backup_currents["bus2"])
                    t_b_ref = calculate_operation_time(I_shc_backup, backup_pickup, backup_tds)
                    
                    delta_t = t_b_ref - t_m_ref - CTI
                    MT = (delta_t - abs(delta_t)) / 2 if np.isfinite(delta_t) else 0
                    
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
                    
                    if delta_t >= 0 and np.isfinite(delta_t):
                        coordinated_pairs.append(pair_info)
                    else:
                        uncoordinated_pairs.append(pair_info)
        
        valid_mts = [pair["MT"] for pair in (coordinated_pairs + uncoordinated_pairs) if np.isfinite(pair["MT"])]
        tmt_total = sum(valid_mts) if valid_mts else 0.0
        total_pairs = len(coordinated_pairs) + len(uncoordinated_pairs)
        
        return coordinated_pairs, uncoordinated_pairs, tmt_total, total_pairs

    coordinated_pairs, uncoordinated_pairs, tmt_total, total_pairs = analyze_coordination(relay_data, relay_pairs, short_circuit_data)

    # Comparación TDS y Pickup
    comparison_data = []
    for relay in relay_data_base["relay_values"].keys():
        base_tds = relay_data_base["relay_values"][relay]["TDS"]
        base_pickup = relay_data_base["relay_values"][relay]["pickup"]
        opt_tds = relay_data["optimized_relay_values"][relay]["TDS"]
        opt_pickup = relay_data["optimized_relay_values"][relay]["pickup"]
        comparison_data.append({
            "Relay": relay,
            "TDS Base": f"{base_tds:.5f}",
            "TDS Opt": f"{opt_tds:.5f}",
            "ΔTDS": f"{opt_tds - base_tds:.5f}",
            "Pickup Base": f"{base_pickup:.5f}",
            "Pickup Opt": f"{opt_pickup:.5f}",
            "ΔPickup": f"{opt_pickup - base_pickup:.5f}"
        })

    # Dropdowns y tablas
    coordinated_options = [{"label": f"{pair['line']}_{pair['scenario']}_{pair['backup_relay']}", "value": idx} for idx, pair in enumerate(coordinated_pairs)]
    uncoordinated_options = [{"label": f"{pair['line']}_{pair['scenario']}_{pair['backup_relay']}", "value": idx} for idx, pair in enumerate(uncoordinated_pairs)]

    coordinated_summary = [
        {"Línea": f"{pair['line']}_{pair['scenario']}", "Main Relay": pair["main_relay"], "TDS (Main)": f"{pair['main_tds']:.5f}", "Pickup (Main)": f"{pair['main_pickup']:.5f}", "I_shc (Main)": f"{pair['main_I_shc']:.3f}", "t_m": f"{pair['t_m_ref']:.3f}" if np.isfinite(pair['t_m_ref']) else "inf", "Backup Relay": pair["backup_relay"], "TDS (Backup)": f"{pair['backup_tds']:.5f}", "Pickup (Backup)": f"{pair['backup_pickup']:.5f}", "I_shc (Backup)": f"{pair['backup_I_shc']:.3f}", "t_b": f"{pair['t_b_ref']:.3f}" if np.isfinite(pair['t_b_ref']) else "inf", "Δt": f"{pair['delta_t']:.3f}" if np.isfinite(pair['delta_t']) else "NaN", "MT": f"{pair['MT']:.3f}" if np.isfinite(pair['MT']) else "NaN"}
        for pair in coordinated_pairs
    ]
    uncoordinated_summary = [
        {"Línea": f"{pair['line']}_{pair['scenario']}", "Main Relay": pair["main_relay"], "TDS (Main)": f"{pair['main_tds']:.5f}", "Pickup (Main)": f"{pair['main_pickup']:.5f}", "I_shc (Main)": f"{pair['main_I_shc']:.3f}", "t_m": f"{pair['t_m_ref']:.3f}" if np.isfinite(pair['t_m_ref']) else "inf", "Backup Relay": pair["backup_relay"], "TDS (Backup)": f"{pair['backup_tds']:.5f}", "Pickup (Backup)": f"{pair['backup_pickup']:.5f}", "I_shc (Backup)": f"{pair['backup_I_shc']:.3f}", "t_b": f"{pair['t_b_ref']:.3f}" if np.isfinite(pair['t_b_ref']) else "inf", "Δt": f"{pair['delta_t']:.3f}" if np.isfinite(pair['delta_t']) else "NaN", "MT": f"{pair['MT']:.3f}" if np.isfinite(pair['MT']) else "NaN"}
        for pair in uncoordinated_pairs
    ]

    # Layout
    layout = html.Div([
        html.H1(f"Análisis Optimizado - Scenario_1 (TMT Total: {tmt_total:.3f}s, Total Pares: {total_pairs})"),
        dcc.Tabs([
            dcc.Tab(label=f"Coordinados ({len(coordinated_pairs)})", children=[
                dcc.Dropdown(id='coordinated-dropdown-opt', options=coordinated_options, value=0 if coordinated_pairs else None),
                dcc.Graph(id='coordinated-graph-opt'),
                dash_table.DataTable(id='coordinated-pair-table-opt', columns=[{"name": "Parámetro", "id": "parameter"}, {"name": "Valor", "id": "value"}]),
                html.H3("Resumen de Pares Coordinados"),
                dash_table.DataTable(id='coordinated-summary-table-opt', columns=[{"name": i, "id": i} for i in coordinated_summary[0].keys()] if coordinated_summary else [], data=coordinated_summary)
            ]),
            dcc.Tab(label=f"Descoordinados ({len(uncoordinated_pairs)})", children=[
                dcc.Dropdown(id='uncoordinated-dropdown-opt', options=uncoordinated_options, value=0 if uncoordinated_pairs else None),
                dcc.Graph(id='uncoordinated-graph-opt'),
                dash_table.DataTable(id='uncoordinated-pair-table-opt', columns=[{"name": "Parámetro", "id": "parameter"}, {"name": "Valor", "id": "value"}]),
                html.H3("Curva de Valores de MT por Par"),
                dcc.Graph(id='mt-graph-opt'),
                html.H3("Resumen de Pares Descoordinados"),
                dash_table.DataTable(id='uncoordinated-summary-table-opt', columns=[{"name": i, "id": i} for i in uncoordinated_summary[0].keys()] if uncoordinated_summary else [], data=uncoordinated_summary)
            ]),
            dcc.Tab(label="Comparación TDS y Pickup", children=[
                html.H3("Comparación Antes y Después de la Optimización"),
                dash_table.DataTable(
                    id='comparison-table',
                    columns=[{"name": i, "id": i} for i in comparison_data[0].keys()],
                    data=comparison_data,
                    style_table={'overflowX': 'auto'}
                )
            ])
        ])
    ])

    # Función para actualizar el dashboard
    def update_dashboard(coordinated_idx, uncoordinated_idx):
        coordinated_fig = go.Figure()
        coordinated_table_data = []
        if coordinated_idx is not None and coordinated_pairs:
            pair = coordinated_pairs[coordinated_idx]
            pair_id = f"{pair['line']}_{pair['scenario']}_{pair['backup_relay']}"
            coordinated_fig.add_trace(go.Scatter(x=pair["I_shc_range"], y=pair["main_curve"], mode="lines", name=f"{pair['main_relay']} (Main)", line=dict(color="blue")))
            if np.isfinite(pair["t_m_ref"]):
                coordinated_fig.add_trace(go.Scatter(x=[pair["main_I_shc"]], y=[pair["t_m_ref"]], mode="markers", name=f"Op {pair['main_relay']}", marker=dict(color="blue", size=10)))
            coordinated_fig.add_trace(go.Scatter(x=pair["I_shc_range"], y=pair["backup_curve"], mode="lines", name=f"{pair['backup_relay']} (Backup)", line=dict(color="red")))
            if np.isfinite(pair["t_b_ref"]):
                coordinated_fig.add_trace(go.Scatter(x=[pair["backup_I_shc"]], y=[pair["t_b_ref"]], mode="markers", name=f"Op {pair['backup_relay']}", marker=dict(color="red", size=10)))
            coordinated_fig.update_layout(title=f"Curva - {pair_id}", xaxis_title="I_shc (A)", yaxis_title="Tiempo (s)", yaxis_type="log")
            coordinated_table_data = [
                {"parameter": "Línea", "value": f"{pair['line']}_{pair['scenario']}"},
                {"parameter": "Relé Principal", "value": pair["main_relay"]},
                {"parameter": "TDS (Main)", "value": f"{pair['main_tds']:.5f}"},
                {"parameter": "Pickup (Main)", "value": f"{pair['main_pickup']:.5f} A"},
                {"parameter": "I_shc (Main)", "value": f"{pair['main_I_shc']:.3f} A"},
                {"parameter": "t_m", "value": f"{pair['t_m_ref']:.3f} s" if np.isfinite(pair['t_m_ref']) else "inf"},
                {"parameter": "Relé Backup", "value": f"{pair['backup_relay']} ({pair['backup_line']})"},
                {"parameter": "TDS (Backup)", "value": f"{pair['backup_tds']:.5f}"},
                {"parameter": "Pickup (Backup)", "value": f"{pair['backup_pickup']:.5f} A"},
                {"parameter": "I_shc (Backup)", "value": f"{pair['backup_I_shc']:.3f} A"},
                {"parameter": "t_b", "value": f"{pair['t_b_ref']:.3f} s" if np.isfinite(pair['t_b_ref']) else "inf"},
                {"parameter": "Δt", "value": f"{pair['delta_t']:.3f} s" if np.isfinite(pair['delta_t']) else "NaN"},
                {"parameter": "MT", "value": f"{pair['MT']:.3f} s" if np.isfinite(pair['MT']) else "NaN"}
            ]
        
        uncoordinated_fig = go.Figure()
        uncoordinated_table_data = []
        if uncoordinated_idx is not None and uncoordinated_pairs:
            pair = uncoordinated_pairs[uncoordinated_idx]
            pair_id = f"{pair['line']}_{pair['scenario']}_{pair['backup_relay']}"
            uncoordinated_fig.add_trace(go.Scatter(x=pair["I_shc_range"], y=pair["main_curve"], mode="lines", name=f"{pair['main_relay']} (Main)", line=dict(color="blue")))
            if np.isfinite(pair["t_m_ref"]):
                uncoordinated_fig.add_trace(go.Scatter(x=[pair["main_I_shc"]], y=[pair["t_m_ref"]], mode="markers", name=f"Op {pair['main_relay']}", marker=dict(color="blue", size=10)))
            uncoordinated_fig.add_trace(go.Scatter(x=pair["I_shc_range"], y=pair["backup_curve"], mode="lines", name=f"{pair['backup_relay']} (Backup)", line=dict(color="red")))
            if np.isfinite(pair["t_b_ref"]):
                uncoordinated_fig.add_trace(go.Scatter(x=[pair["backup_I_shc"]], y=[pair["t_b_ref"]], mode="markers", name=f"Op {pair['backup_relay']}", marker=dict(color="red", size=10)))
            uncoordinated_fig.update_layout(title=f"Curva - {pair_id}", xaxis_title="I_shc (A)", yaxis_title="Tiempo (s)", yaxis_type="log")
            uncoordinated_table_data = [
                {"parameter": "Línea", "value": f"{pair['line']}_{pair['scenario']}"},
                {"parameter": "Relé Principal", "value": pair["main_relay"]},
                {"parameter": "TDS (Main)", "value": f"{pair['main_tds']:.5f}"},
                {"parameter": "Pickup (Main)", "value": f"{pair['main_pickup']:.5f} A"},
                {"parameter": "I_shc (Main)", "value": f"{pair['main_I_shc']:.3f} A"},
                {"parameter": "t_m", "value": f"{pair['t_m_ref']:.3f} s" if np.isfinite(pair['t_m_ref']) else "inf"},
                {"parameter": "Relé Backup", "value": f"{pair['backup_relay']} ({pair['backup_line']})"},
                {"parameter": "TDS (Backup)", "value": f"{pair['backup_tds']:.5f}"},
                {"parameter": "Pickup (Backup)", "value": f"{pair['backup_pickup']:.5f} A"},
                {"parameter": "I_shc (Backup)", "value": f"{pair['backup_I_shc']:.3f} A"},
                {"parameter": "t_b", "value": f"{pair['t_b_ref']:.3f} s" if np.isfinite(pair['t_b_ref']) else "inf"},
                {"parameter": "Δt", "value": f"{pair['delta_t']:.3f} s" if np.isfinite(pair['delta_t']) else "NaN"},
                {"parameter": "MT", "value": f"{pair['MT']:.3f} s" if np.isfinite(pair['MT']) else "NaN"}
            ]
        
        mt_fig = go.Figure()
        if coordinated_pairs or uncoordinated_pairs:
            all_pairs = coordinated_pairs + uncoordinated_pairs
            mt_values = [pair["MT"] for pair in all_pairs]
            mt_labels = [f"{pair['main_relay']}-{pair['backup_relay']}" for pair in all_pairs]
            mt_fig.add_trace(go.Scatter(x=mt_labels, y=mt_values, mode="lines+markers", name="MT", line=dict(color="purple"), marker=dict(size=8)))
            mt_fig.update_layout(title="Evolución de MT por Par", xaxis_title="Pares de Relés", yaxis_title="MT (s)", xaxis={'tickangle': 45}, height=400)
        
        return coordinated_fig, coordinated_table_data, uncoordinated_fig, uncoordinated_table_data, mt_fig