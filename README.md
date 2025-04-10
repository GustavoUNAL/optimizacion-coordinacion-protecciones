Aquí tienes el contenido del archivo `README.md` listo para copiar y pegar directamente:

```
# Optimización de la Coordinación de Relés de Protección en Sistemas Eléctricos

Este repositorio contiene una implementación en Python para optimizar la coordinación de relés de protección en sistemas eléctricos de potencia, basada en la norma **IEC 60255-151** para curvas de tiempo inverso estándar (SI). El objetivo es ajustar los parámetros clave de los relés —**Time Dial Setting (TDS)** y **corriente de pickup (I_pi)**— para minimizar el **Tiempo de Margen Total (TMT)** negativo, garantizando una coordinación eficiente y segura entre relés principales y de respaldo.

---

## Descripción General

El método optimiza la coordinación ajustando iterativamente TDS y I_pi para:
- Reducir el tiempo total de operación de los relés principales.
- Penalizar márgenes de tiempo (MT) negativos entre relés principales y de respaldo.
- Mantener coherencia en las corrientes de pickup entre relés vecinos.

El resultado es una coordinación casi óptima con un TMT objetivo de **-0.005 s**, permitiendo un margen mínimo de descoordinación aceptable.

---

## Función Objetivo

La función objetivo (`OF`) se define como:

$$ OF = T_{total} + w_k \sum_{i \in P_{neg}} (MT_i)^2 + w_{pickup} \sum_{i \in P} |I_{pi,main,i} - I_{pi,backup,i}| $$

Donde:
- \( T_{total} = \sum_{i \in P} t_{main,i} \): Tiempo total de operación de los relés principales.
- \( w_k \sum_{i \in P_{neg}} (MT_i)^2 \): Penalización por MT negativos (\(w_k = 1.0\)).
- \( w_{pickup} \sum_{i \in P} |I_{pi,main,i} - I_{pi,backup,i}| \): Penalización por diferencias en pickup (\(w_{pickup} = 0.5\)).
- \( t_{main,i} = TDS_{main,i} \cdot \frac{0.14}{M_{main,i}^{0.02} - 1} \): Tiempo de operación (curva SI), con \( M_{main,i} = \frac{I_{shc,main,i}}{I_{pi,main,i}} \).
- \( MT_i = \Delta t_i - CTI \), con \( \Delta t_i = t_{backup,i} - t_{main,i} \) y \( CTI = 0.2 \, \text{s} \).

**Ejemplo de código:**
```python
def calculate_operation_time(I_shc: float, I_pi: float, TDS: float) -> float:
    M = I_shc / I_pi
    if M <= 1.001 or TDS < 0.05 or TDS > 10.0:
        return 10.0  # MAX_TIME
    return min(TDS * (0.14 / (M**0.02 - 1)), 10.0)
```

---

## Restricciones

1. **Límites de TDS**: \( 0.05 \leq TDS_{j} \leq 10.0 \).
2. **Límites de I_pi**: \( 0.01 \leq I_{pi,j} \leq 0.9 \cdot I_{shc,j} \).
3. **Tiempo máximo**: \( t_{j} \leq 10.0 \, \text{s} \).
4. **Condición de coordinación**: \( \Delta t_i \geq 0 \) (ajustada iterativamente).

**Ejemplo de código:**
```python
tds_backup = min(10.0, max(0.05, tds_backup))
pickup_backup = min(I_shc_backup * 0.9, max(0.01, pickup_backup))
```

---

## Variables de Optimización

- **TDS**: Factor continuo en \([0.05, 10.0]\).
- **I_pi**: Corriente continua en \([0.01, 0.9 \cdot I_{shc,j}]\).

Estas variables se ajustan para cada relé en el sistema.

---

## Algoritmo de Optimización

1. **Inicialización**: Carga de TDS y I_pi iniciales.
2. **Iteración**: Hasta 100 iteraciones, calcula tiempos, MT y OF.
3. **Ajuste**: Incrementa TDS y I_pi del relé de respaldo y reduce los del principal si \( MT < 0 \).
4. **Convergencia**: Termina si \( TMT \approx -0.005 \, \text{s} \) y \( MT_i \geq -0.01 \).

**Fragmento de código:**
```python
for iteration in range(100):
    tmt = sum(pair["mt"] for pair in optimized_pairs if pair["mt"] < 0)
    of = total_time + 1.0 * sum(pair["mt"]**2 if pair["mt"] < 0 else 0 for pair in optimized_pairs)
    if abs(tmt + 0.005) < 0.01 and all(pair["mt"] >= -0.01 for pair in optimized_pairs):
        break
    for pair in optimized_pairs:
        if pair["mt"] < 0:
            pair["tds_backup"] *= 1.1 if pair["mt"] < -0.2 else 1.05
            pair["tds_main"] *= 0.9 if pair["mt"] < -0.2 else 0.98
```

---

## Resultados

- **Salida**: Valores optimizados de TDS y I_pi en JSON.
- **Visualización**: Dashboards con curvas de tiempo inverso, tablas de coordinación y gráficos de evolución.

---

## Requisitos

- Python 3.x
- Dependencias: `numpy`, `matplotlib` (para visualización), `json`.

Instalación:
```bash
pip install -r requirements.txt
```

---

## Uso

1. Configura los datos iniciales en `input_data.json`.
2. Ejecuta el script principal:
   ```bash
   python optimize_relays.py
   ```
3. Revisa los resultados en `output.json` y los dashboards generados.

---

## Contribuciones

¡Las contribuciones son bienvenidas! Por favor, abre un *issue* o envía un *pull request* con mejoras o correcciones.

---

## Licencia

Este proyecto está bajo la licencia [MIT](LICENSE).
```

Solo copia este texto y pégalo en tu archivo `README.md`. ¡Listo!