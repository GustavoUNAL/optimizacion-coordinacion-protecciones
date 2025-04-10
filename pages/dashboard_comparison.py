import json
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html, dash_table

# Rutas relativas
RELAY_DATA_BASE_PATH = "data/raw/data_relays_scenario_base.json"
RELAY_DATA_OPT_PATH = "data/raw/data_relays_scenario_base_optimized.json"
RELAY_PAIRS_PATH = "data/config/relay_pairs.json"
SHORT_CIRCUIT_PATH = "data/raw/data_short_circuit_scenario_base.json"

# Constantes
K = 0.14
N = 0.02
CTI = 0.2
MAX_TIME = 10.0

# Cargar datos
def load_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error cargando {file_path}: {e}")
        return None

relay_data_base = load_json_file(RELAY_DATA_BASE_PATH)
relay_data_opt = load_json_file(RELAY_DATA_OPT_PATH)
relay_pairs = load_json_file(RELAY_PAIRS_PATH)
short_circuit_data = load_json_file(SHORT_CIRCUIT_PATH)

if not all([relay_data_base, relay_data_opt, relay_pairs, short_circuit_data]):
    layout = html.Div("Error: No se pudieron cargar los datos.")
else:
    # Función para calcular tiempo de operación
    def calculate_operation_time(I_shc, I_pi, TDS, max_time=MAX_TIME):
        if I_pi <= 0 or I_shc <= 0:
            return max_time
        M = I_shc / I_pi
        if M <= 1:
            return max_time
        try:
            time = (K / (M**N - 1)) * TDS
            return min(time, max_time)
        except:
            return max_time

    # Analizar coordinación para MT
    def analyze_coordination(relay_data, relay_pairs, short_circuit_data, optimized=False):
        mt_values = {}
        for line, pair_data in relay_pairs.items():
            for scenario in pair_data["scenarios"].keys():
                config = pair_data["scenarios"][scenario]
                main_relay = config["main"]["relay"]
                backups = config["backups"]
                
                key = "optimized_relay_values" if optimized else "relay_values"
                main_tds = relay_data[key][main_relay]["TDS"]
                main_pickup = relay_data[key][main_relay]["pickup"]
                main_currents = short_circuit_data["lines"][line]["scenarios"][scenario]["main"]["currents"]
                I_shc_main = max(main_currents["bus1"], main_currents["bus2"])
                t_m_ref = calculate_operation_time(I_shc_main, main_pickup, main_tds)
                
                for backup in backups:
                    backup_relay = backup["relay"]
                    backup_tds = relay_data[key][backup_relay]["TDS"]
                    backup_pickup = relay_data[key][backup_relay]["pickup"]
                    backup_currents = next(b["currents"] for b in short_circuit_data["lines"][line]["scenarios"][scenario]["backups"] if b["relay"] == backup_relay)
                    I_shc_backup = max(backup_currents["bus1"], backup_currents["bus2"])
                    t_b_ref = calculate_operation_time(I_shc_backup, backup_pickup, backup_tds)
                    
                    delta_t = t_b_ref - t_m_ref - CTI
                    MT = (delta_t - abs(delta_t)) / 2 if np.isfinite(delta_t) else 0
                    mt_values[(main_relay, backup_relay)] = MT
        
        return mt_values

    mt_base = analyze_coordination(relay_data_base, relay_pairs, short_circuit_data, optimized=False)
    mt_opt = analyze_coordination(relay_data_opt, relay_pairs, short_circuit_data, optimized=True)

    # Datos de comparación
    comparison_data = []
    relays = set(relay_data_base["relay_values"].keys())
    for relay in relays:
        base_tds = relay_data_base["relay_values"][relay]["TDS"]
        base_pickup = relay_data_base["relay_values"][relay]["pickup"]
        opt_tds = relay_data_opt["optimized_relay_values"][relay]["TDS"]
        opt_pickup = relay_data_opt["optimized_relay_values"][relay]["pickup"]
        
        mt_base_avg = np.mean([mt for (main, backup), mt in mt_base.items() if main == relay or backup == relay])
        mt_opt_avg = np.mean([mt for (main, backup), mt in mt_opt.items() if main == relay or backup == relay])
        
        comparison_data.append({
            "Relay": relay,
            "TDS Base": f"{base_tds:.5f}",
            "TDS Opt": f"{opt_tds:.5f}",
            "ΔTDS": f"{opt_tds - base_tds:.5f}",
            "Pickup Base": f"{base_pickup:.5f}",
            "Pickup Opt": f"{opt_pickup:.5f}",
            "ΔPickup": f"{opt_pickup - base_pickup:.5f}",
            "MT Base": f"{mt_base_avg:.3f}" if np.isfinite(mt_base_avg) else "N/A",
            "MT Opt": f"{mt_opt_avg:.3f}" if np.isfinite(mt_opt_avg) else "N/A",
            "ΔMT": f"{mt_opt_avg - mt_base_avg:.3f}" if np.isfinite(mt_opt_avg) and np.isfinite(mt_base_avg) else "N/A"
        })

    # Layout
    layout = html.Div([
        html.H1("Comparación de TDS, Pickup y MT - Scenario_1"),
        html.H3("Valores por Relé"),
        dash_table.DataTable(
            id='comparison-table',
            columns=[{"name": i, "id": i} for i in comparison_data[0].keys()],
            data=comparison_data,
            style_table={'overflowX': 'auto', 'width': '90%', 'margin': '20px auto'}
        ),
        html.H3("Evolución de TDS por Relé"),
        dcc.Graph(id='tds-graph'),
        html.H3("Evolución de Pickup por Relé"),
        dcc.Graph(id='pickup-graph'),
        html.H3("Evolución de MT Promedio por Relé"),
        dcc.Graph(id='mt-graph'),
        html.H3("Evolución de MT por Par de Relés"),
        dcc.Graph(id='mt-pairs-graph')
    ])

    # Función para actualizar gráficos
    def update_dashboard(_):  # El argumento es dummy ya que no usamos el dropdown
        # Gráfico TDS
        tds_fig = go.Figure()
        tds_base = [float(d["TDS Base"]) for d in comparison_data]
        tds_opt = [float(d["TDS Opt"]) for d in comparison_data]
        relays_list = [d["Relay"] for d in comparison_data]
        tds_fig.add_trace(go.Scatter(x=relays_list, y=tds_base, mode="lines+markers", name="Base", line=dict(color="blue")))
        tds_fig.add_trace(go.Scatter(x=relays_list, y=tds_opt, mode="lines+markers", name="Optimizado", line=dict(color="green")))
        tds_fig.update_layout(title="Evolución de TDS", xaxis_title="Relés", yaxis_title="TDS", xaxis={'tickangle': 45}, height=400, showlegend=True)

        # Gráfico Pickup
        pickup_fig = go.Figure()
        pickup_base = [float(d["Pickup Base"]) for d in comparison_data]
        pickup_opt = [float(d["Pickup Opt"]) for d in comparison_data]
        pickup_fig.add_trace(go.Scatter(x=relays_list, y=pickup_base, mode="lines+markers", name="Base", line=dict(color="blue")))
        pickup_fig.add_trace(go.Scatter(x=relays_list, y=pickup_opt, mode="lines+markers", name="Optimizado", line=dict(color="green")))
        pickup_fig.update_layout(title="Evolución de Pickup", xaxis_title="Relés", yaxis_title="Pickup (A)", xaxis={'tickangle': 45}, height=400, showlegend=True)

        # Gráfico MT promedio
        mt_fig = go.Figure()
        mt_base_vals = [float(d["MT Base"]) if d["MT Base"] != "N/A" else 0 for d in comparison_data]
        mt_opt_vals = [float(d["MT Opt"]) if d["MT Opt"] != "N/A" else 0 for d in comparison_data]
        mt_fig.add_trace(go.Scatter(x=relays_list, y=mt_base_vals, mode="lines+markers", name="Base", line=dict(color="blue")))
        mt_fig.add_trace(go.Scatter(x=relays_list, y=mt_opt_vals, mode="lines+markers", name="Optimizado", line=dict(color="green")))
        mt_fig.update_layout(title="Evolución de MT Promedio", xaxis_title="Relés", yaxis_title="MT (s)", xaxis={'tickangle': 45}, height=400, showlegend=True)

        # Gráfico MT por par
        mt_pairs_fig = go.Figure()
        mt_base_pairs = [mt for mt in mt_base.values()]
        mt_opt_pairs = [mt for mt in mt_opt.values()]
        pair_labels = [f"{main}-{backup}" for (main, backup) in mt_base.keys()]
        mt_pairs_fig.add_trace(go.Scatter(x=pair_labels, y=mt_base_pairs, mode="lines+markers", name="Base", line=dict(color="blue")))
        mt_pairs_fig.add_trace(go.Scatter(x=pair_labels, y=mt_opt_pairs, mode="lines+markers", name="Optimizado", line=dict(color="green")))
        mt_pairs_fig.update_layout(title="Evolución de MT por Par", xaxis_title="Pares de Relés", yaxis_title="MT (s)", xaxis={'tickangle': 45}, height=400, showlegend=True)

        return tds_fig, pickup_fig, mt_fig, mt_pairs_fig