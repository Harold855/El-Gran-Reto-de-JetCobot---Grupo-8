import csv
import math
import os
import statistics
from datetime import datetime
from pathlib import Path

from laya_cliente import consultar_laya_tipado
from interprete_ordenes import clasificar_orden

ENTRADA = Path("evidencias/pregunta_1/frases_50.csv")
SALIDA = Path("evidencias/pregunta_1/mediciones")
SALIDA.mkdir(parents=True, exist_ok=True)

MARCA = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_SALIDA = SALIDA / f"comparacion_real_laya_{MARCA}.csv"
MD_SALIDA = SALIDA / f"tabla_exactitud_laya_{MARCA}.md"
PREDICCION = SALIDA / f"prediccion_laya_{MARCA}.txt"

URL = os.environ.get("LAYA_URL", "").strip()
if not URL:
    raise SystemExit("ERROR: falta configurar LAYA_URL")

with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    frases = list(csv.DictReader(f))

if len(frases) != 50:
    raise SystemExit(
        f"ERROR: se esperaban 50 frases, hay {len(frases)}"
    )

# Predicción registrada antes de consultar LAYA.
PREDICCION.write_text(
    "Predicciones previas:\n"
    "Exactitud completa LAYA: 80 %.\n"
    "Exactitud reglas locales: 100 %.\n"
    "Latencia HTTP mediana LAYA: 300 ms.\n"
    "Justificación: resultados históricos del laboratorio; "
    "LAYA confundió varios destinos y un objeto.\n",
    encoding="utf-8"
)

def booleano(valor):
    return str(valor).strip().lower() in (
        "true", "1", "si", "sí", "aceptar"
    )

def evaluar(esperado, permitido, accion, objeto, color, destino):
    # Para órdenes inválidas, el resultado correcto es rechazar.
    if not esperado["permitido"]:
        return not permitido

    return (
        permitido
        and accion == esperado["accion"]
        and objeto == esperado["objeto"]
        and color == esperado["color"]
        and destino == esperado["destino"]
    )

def percentil95(valores):
    if not valores:
        return None
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * 0.95
    inferior = math.floor(posicion)
    superior = math.ceil(posicion)
    fraccion = posicion - inferior
    return (
        ordenados[inferior] * (1 - fraccion)
        + ordenados[superior] * fraccion
    )

registros = []

print("=== EVALUANDO 50 FRASES CON LAYA REAL ===", flush=True)

for f in frases:
    frase = f["frase"]
    esperado = {
        "permitido": booleano(f["permitido_esperado"]),
        "accion": f["accion_esperada"].strip(),
        "objeto": f["objeto_esperado"].strip(),
        "color": f["color_cubo_esperado"].strip(),
        "destino": f["color_zona_esperada"].strip(),
    }

    # Evaluación independiente de las reglas locales.
    local = clasificar_orden(frase)
    la, lo, lc, ld, lp, lpermitido, lmotivo = local

    correcto_local = evaluar(
        esperado, lpermitido, la, lo, lc, ld
    )

    registro = {
        "id": f["id"],
        "frase": frase,
        "permitido_esperado": esperado["permitido"],
        "accion_esperada": esperado["accion"],
        "objeto_esperado": esperado["objeto"],
        "color_esperado": esperado["color"],
        "destino_esperado": esperado["destino"],
        "laya_accion": "",
        "laya_objeto": "",
        "laya_color": "",
        "laya_destino": "",
        "laya_prioridad": "",
        "laya_permitido": "",
        "laya_correcto": False,
        "laya_error": "",
        "modelo": "",
        "tiempo_http_ms": "",
        "tiempo_servidor_ms": "",
        "tiempo_restante_ms": "",
        "local_accion": la,
        "local_objeto": lo,
        "local_color": lc,
        "local_destino": ld,
        "local_permitido": lpermitido,
        "local_correcto": correcto_local,
        "local_motivo": lmotivo,
    }

    try:
        r = consultar_laya_tipado(
            frase, url=URL, timeout=4.0
        )

        decisiones = {
            clave: valor.get("choice", "")
            for clave, valor in r.respuestas_crudas.items()
            if isinstance(valor, dict)
        }

        permitido_laya = decisiones.get("permitido") == "si"

        correcto_laya = evaluar(
            esperado,
            permitido_laya,
            decisiones.get("accion", ""),
            decisiones.get("objeto", ""),
            decisiones.get("color", ""),
            decisiones.get("destino", ""),
        )

        registro.update({
            "laya_accion": decisiones.get("accion", ""),
            "laya_objeto": decisiones.get("objeto", ""),
            "laya_color": decisiones.get("color", ""),
            "laya_destino": decisiones.get("destino", ""),
            "laya_prioridad": decisiones.get("prioridad", ""),
            "laya_permitido": permitido_laya,
            "laya_correcto": correcto_laya,
            "modelo": r.modelo_usado or "",
            "tiempo_http_ms": round(r.tiempo_http_ms, 2),
            "tiempo_servidor_ms": (
                round(r.tiempo_servidor_ms, 2)
                if r.tiempo_servidor_ms is not None else ""
            ),
            "tiempo_restante_ms": (
                round(r.tiempo_http_ms - r.tiempo_servidor_ms, 2)
                if r.tiempo_servidor_ms is not None else ""
            ),
        })

    except Exception as e:
        registro["laya_error"] = str(e)

    registros.append(registro)

    resultado = "OK" if registro["laya_correcto"] else "ERROR"
    print(
        f"{len(registros):02d}/50 | "
        f"LAYA={resultado} | "
        f"LOCAL={'OK' if correcto_local else 'ERROR'}",
        flush=True
    )

with CSV_SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as f:
    escritor = csv.DictWriter(
        f, fieldnames=list(registros[0].keys())
    )
    escritor.writeheader()
    escritor.writerows(registros)

total = len(registros)
aciertos_laya = sum(r["laya_correcto"] for r in registros)
aciertos_local = sum(r["local_correcto"] for r in registros)
fallas_http = sum(bool(r["laya_error"]) for r in registros)

latencias = [
    float(r["tiempo_http_ms"])
    for r in registros
    if r["tiempo_http_ms"] != ""
]

porcentaje_laya = 100 * aciertos_laya / total
porcentaje_local = 100 * aciertos_local / total

lineas = [
    "# Pregunta 1 - Exactitud independiente de LAYA",
    "",
    "Evaluación de 50 frases con el servidor real.",
    "La evaluación utiliza las seis decisiones originales de LAYA.",
    "Las correcciones del intérprete híbrido no se contabilizan como aciertos de LAYA.",
    "",
    "| Método | Correctas | Incorrectas | Exactitud |",
    "|---|---:|---:|---:|",
    f"| LAYA real | {aciertos_laya}/50 | {total-aciertos_laya} | {porcentaje_laya:.1f} % |",
    f"| Palabras clave | {aciertos_local}/50 | {total-aciertos_local} | {porcentaje_local:.1f} % |",
    "",
    f"- Errores de consulta HTTP o formato: {fallas_http}",
    f"- Modelo utilizado: {next((r['modelo'] for r in registros if r['modelo']), 'No informado')}",
    "- Prioridad: registrada, pero no incluida en la exactitud porque el CSV no contiene prioridad esperada.",
    "- Para frases inválidas se evalúa el rechazo; para frases válidas se evalúan autorización, acción, objeto, color y destino.",
]

if latencias:
    lineas.extend([
        f"- Mediana HTTP: {statistics.median(latencias):.2f} ms",
        f"- P95 HTTP: {percentil95(latencias):.2f} ms",
    ])

lineas.extend([
    "",
    "## Frases incorrectas de LAYA",
    "",
    "| ID | Frase | LAYA objeto | LAYA color | LAYA destino |",
    "|---|---|---|---|---|",
])

for r in registros:
    if not r["laya_correcto"]:
        frase_corta = r["frase"].replace("|", "/")
        lineas.append(
            f"| {r['id']} | {frase_corta} | "
            f"{r['laya_objeto']} | {r['laya_color']} | "
            f"{r['laya_destino']} |"
        )

MD_SALIDA.write_text(
    "\n".join(lineas) + "\n",
    encoding="utf-8"
)

print("\n========== TABLA COMPARATIVA ==========")
print("Metodo          Correctas      Exactitud")
print(f"LAYA real       {aciertos_laya:2d}/50          {porcentaje_laya:.1f}%")
print(f"Palabras clave  {aciertos_local:2d}/50          {porcentaje_local:.1f}%")
print("Errores HTTP:", fallas_http)
print("\nCSV:", CSV_SALIDA)
print("TABLA:", MD_SALIDA)
print("PREDICCION:", PREDICCION)
