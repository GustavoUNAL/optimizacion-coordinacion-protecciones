import json
import numpy as np
import logging
from typing import Dict, List

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constantes según la norma IEC 60255-151 para curva SI
K = 0.14
N = 0.02
CTI = 0.2  # Intervalo de tiempo de coordinación típico (en segundos)
MIN_TDS = 0.05
MAX_TDS = 10.0
MIN_PICKUP = 0.01
MAX_TIME = 10.0  # Tiempo máximo razonable para evitar valores extremos

# Rutas de los archivos
ORIGINAL_RELAY_DATA_PATH = "/Users/gustavo/Documents/Projects/TESIS_UNAL/optimizacion-coordinacion-protecciones/data/raw/data_relays_scenario_base.json"
RELAY_PAIRS_PATH = "/Users/gustavo/Documents/Projects/TESIS_UNAL/optimizacion-coordinacion-protecciones/data/config/relay_pairs.json"
SHORT_CIRCUIT_PATH = "/Users/gustavo/Documents/Projects/TESIS_UNAL/optimizacion-coordinacion-protecciones/data/raw/data_short_circuit_scenario_base.json"
OPTIMIZED_RELAY_DATA_PATH = "/Users/gustavo/Documents/Projects/TESIS_UNAL/optimizacion-coordinacion-protecciones/data/raw/data_relays_scenario_base_optimized.json"

# Cargar los datos desde los archivos
def load_json_file(file_path: str) -> Dict:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error(f"No se encontró el archivo en {file_path}")
        return {}
    except json.JSONDecodeError:
        logger.error(f"No se pudo decodificar el JSON en {file_path}")
        return {}

relay_data = load_json_file(ORIGINAL_RELAY_DATA_PATH)
relay_pairs = load_json_file(RELAY_PAIRS_PATH)
short_circuit_data = load_json_file(SHORT_CIRCUIT_PATH)

# Verificar que los datos se cargaron correctamente
if not relay_data or not relay_pairs or not short_circuit_data:
    raise SystemExit("No se pudieron cargar los datos necesarios. Verifica las rutas y el formato de los archivos.")

# Función para calcular el tiempo de operación del relé
def calculate_operation_time(I_shc: float, I_pi: float, TDS: float) -> float:
    if I_pi <= 0 or I_shc <= 0 or TDS < MIN_TDS or TDS > MAX_TDS:
        logger.debug(f"Valores inválidos: I_shc={I_shc}, I_pi={I_pi}, TDS={TDS}. Retornando {MAX_TIME}")
        return MAX_TIME
    M = I_shc / I_pi
    if M <= 1.001:  # Margen para evitar valores cercanos a 1
        return MAX_TIME
    try:
        time = TDS * (K / (M**N - 1))
        return min(time, MAX_TIME) if time > 0 else MAX_TIME
    except ZeroDivisionError:
        return MAX_TIME

# Optimizar TDS y pickup para todos los relés
def optimize_relay_settings(relay_data: Dict, relay_pairs: Dict, short_circuit_data: Dict) -> Dict[str, Dict[str, float]]:
    # Identificar todos los relés únicos
    all_relays = set()
    for pair_data in relay_pairs.values():
        for scenario in pair_data["scenarios"].keys():
            config = pair_data["scenarios"][scenario]
            all_relays.add(config["main"]["relay"])
            for backup in config["backups"]:
                all_relays.add(backup["relay"])
    logger.info(f"Total de relés únicos encontrados: {len(all_relays)}")

    # Inicializar valores optimizados y recopilar datos de corriente
    relay_settings = {}
    relay_currents = {}
    for relay in all_relays:
        relay_settings[relay] = {
            "TDS": relay_data["relay_values"][relay]["TDS"],
            "pickup": relay_data["relay_values"][relay]["pickup"]
        }
        relay_currents[relay] = []

    # Recopilar corrientes de cortocircuito para cada relé
    for line, pair_data in relay_pairs.items():
        for scenario in pair_data["scenarios"].keys():
            config = pair_data["scenarios"][scenario]
            main_relay = config["main"]["relay"]
            main_currents = short_circuit_data["lines"][line]["scenarios"][scenario]["main"]["currents"]
            I_shc_main = max(main_currents["bus1"], main_currents["bus2"])
            relay_currents[main_relay].append(I_shc_main)

            for backup in config["backups"]:
                backup_relay = backup["relay"]
                backup_currents = next(
                    b["currents"] for b in short_circuit_data["lines"][line]["scenarios"][scenario]["backups"]
                    if b["relay"] == backup_relay
                )
                I_shc_backup = max(backup_currents["bus1"], backup_currents["bus2"])
                relay_currents[backup_relay].append(I_shc_backup)

    # Calcular corriente máxima por relé
    for relay in relay_currents:
        relay_currents[relay] = max(relay_currents[relay]) if relay_currents[relay] else 500.0  # Valor por defecto si no hay datos

    # Algoritmo de optimización iterativa
    pairs_info = []
    for line, pair_data in relay_pairs.items():
        for scenario in pair_data["scenarios"].keys():
            config = pair_data["scenarios"][scenario]
            main_relay = config["main"]["relay"]
            for backup in config["backups"]:
                backup_relay = backup["relay"]
                pairs_info.append({
                    "line": line,
                    "scenario": scenario,
                    "main_relay": main_relay,
                    "backup_relay": backup_relay,
                    "I_shc_main": relay_currents[main_relay],
                    "I_shc_backup": relay_currents[backup_relay]
                })

    # Iterar para optimizar
    target_tmt = -0.005  # Objetivo para TMT (mínimo negativo aceptable)
    w_k = 1.0  # Peso para penalizar MT negativos
    w_pickup = 0.5  # Peso para diferencias en pickup

    for iteration in range(100):
        # Calcular tiempos y MT para todos los pares
        total_time = 0
        tmt = 0
        optimized_pairs = []
        for pair in pairs_info:
            main_relay = pair["main_relay"]
            backup_relay = pair["backup_relay"]
            I_shc_main = pair["I_shc_main"]
            I_shc_backup = pair["I_shc_backup"]

            tds_main = relay_settings[main_relay]["TDS"]
            pickup_main = relay_settings[main_relay]["pickup"]
            tds_backup = relay_settings[backup_relay]["TDS"]
            pickup_backup = relay_settings[backup_relay]["pickup"]

            main_time = calculate_operation_time(I_shc_main, pickup_main, tds_main)
            backup_time = calculate_operation_time(I_shc_backup, pickup_backup, tds_backup)
            delta_t = backup_time - main_time
            mt = delta_t - CTI

            optimized_pairs.append({
                "main_time": main_time,
                "backup_time": backup_time,
                "delta_t": delta_t,
                "mt": mt,
                "main_relay": main_relay,
                "backup_relay": backup_relay
            })

            total_time += main_time
            if mt < 0:
                tmt += mt

        # Función objetivo
        pickup_diff = sum(abs(relay_settings[pair["main_relay"]]["pickup"] - relay_settings[pair["backup_relay"]]["pickup"])
                          for pair in optimized_pairs)
        of = total_time + w_k * sum((pair["mt"]**2 if pair["mt"] < 0 else 0) for pair in optimized_pairs) + w_pickup * pickup_diff

        logger.debug(f"Iteración {iteration}: OF={of:.3f}, TMT={tmt:.3f}, Total Time={total_time:.3f}, Pickup Diff={pickup_diff:.3f}")

        # Verificar convergencia
        if abs(tmt - target_tmt) < 0.01 and all(pair["mt"] >= -0.01 for pair in optimized_pairs):
            logger.info(f"Convergencia alcanzada en iteración {iteration}")
            break

        # Ajustar TDS y pickup para pares descoordinados
        for pair in optimized_pairs:
            if pair["mt"] < 0:
                main_relay = pair["main_relay"]
                backup_relay = pair["backup_relay"]
                I_shc_main = relay_currents[main_relay]
                I_shc_backup = relay_currents[backup_relay]

                tds_main = relay_settings[main_relay]["TDS"]
                tds_backup = relay_settings[backup_relay]["TDS"]
                pickup_main = relay_settings[main_relay]["pickup"]
                pickup_backup = relay_settings[backup_relay]["pickup"]

                # Ajustes agresivos si mt es muy negativo
                if pair["mt"] < -CTI:
                    tds_backup *= 1.1
                    pickup_backup *= 1.05
                    tds_main *= 0.9
                    pickup_main *= 0.95
                else:
                    tds_backup += 0.05
                    pickup_backup *= 1.02
                    tds_main -= 0.02
                    pickup_main *= 0.98

                # Limitar valores
                tds_backup = min(MAX_TDS, max(MIN_TDS, tds_backup))
                pickup_backup = min(I_shc_backup * 0.9, max(MIN_PICKUP, pickup_backup))
                tds_main = min(MAX_TDS, max(MIN_TDS, tds_main))
                pickup_main = min(I_shc_main * 0.9, max(MIN_PICKUP, pickup_main))

                relay_settings[main_relay]["TDS"] = tds_main
                relay_settings[backup_relay]["TDS"] = tds_backup
                relay_settings[main_relay]["pickup"] = pickup_main
                relay_settings[backup_relay]["pickup"] = pickup_backup

    # Limpiar valores para JSON
    for relay in relay_settings:
        relay_settings[relay]["TDS"] = float(f"{relay_settings[relay]['TDS']:.5f}")
        relay_settings[relay]["pickup"] = float(f"{relay_settings[relay]['pickup']:.5f}")

    return relay_settings

# Generar valores optimizados
optimized_relay_values = optimize_relay_settings(relay_data, relay_pairs, short_circuit_data)

# Crear y guardar el archivo optimizado
optimized_data = {
    "scenario_id": "scenario_1",
    "optimized_relay_values": optimized_relay_values
}

with open(OPTIMIZED_RELAY_DATA_PATH, 'w') as file:
    json.dump(optimized_data, file, indent=4)

logger.info(f"Archivo optimizado guardado en: {OPTIMIZED_RELAY_DATA_PATH}")