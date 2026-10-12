"""Desarrollo de latencias parciales con P1 provisional (sin LAYA).

¿Que realiza?
Lee evidencias/pregunta_3/transcripciones.csv y no lo modifica.

Produce:
 - evidencias/pregunta_3/latencias_resumen.csv
 - evidencias/pregunta_3/tabla_solicitudes_p3.csv
"""

import csv
import statistics
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "evidencias" / "pregunta_3"
ENTRADA = CARPETA / "transcripciones.csv"
RESUMEN = CARPETA / "latencias_resumen.csv"
TABLA = CARPETA / "tabla_solicitudes_p3.csv"

# Valores no medidos (cola, visión, IK, planificación, brazo) quedan vacíos.
COLUMNAS_CADENA = [
    "id_solicitud", "fecha", "audio_original", "audio_copia", "transcripcion",
    "origen", "accion", "objeto", "color", "destino", "prioridad",
    "permitido", "degradado", "motivo", "resultado_p1",
    "resultado_broker", "resultado_brazo",
    "tiempo_google_ms", "tiempo_teclado_ms", "tiempo_servicio_p1_ms",
    "tiempo_total_parcial_ms", "tiempo_captura_audio_ms",
    "tiempo_decision_laya_ms", "tiempo_cola_ms", "tiempo_percepcion_ms",
    "tiempo_ik_ms", "tiempo_planificacion_ms",
    "tiempo_fin_habla_a_inicio_movimiento_ms", "observaciones",
]


def numero(valor):
    if valor is None or not str(valor).strip():
        return None  # Dato ausente != cero
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def percentil95(valores):
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return ordenados[0]
    posicion = (len(ordenados) - 1) * 0.95  # Interpolación lineal inclusiva
    inferior = int(posicion)
    superior = min(inferior + 1, len(ordenados) - 1)
    fraccion = posicion - inferior
    return ordenados[inferior] * (1 - fraccion) + ordenados[superior] * fraccion


def estadisticas(nombre, valores, nota):
    if not valores:
        return [nombre, 0, "", "", "", "", "", nota]
    return [
        nombre, len(valores), round(statistics.mean(valores), 2),
        round(statistics.median(valores), 2), round(percentil95(valores), 2),
        round(min(valores), 2), round(max(valores), 2), nota,
    ]


def ejecutar():
    if not ENTRADA.is_file():
        raise FileNotFoundError(f"No existe {ENTRADA}")
    with ENTRADA.open(newline="", encoding="utf-8-sig") as archivo:
        registros = list(csv.DictReader(archivo))

    medidas_google = []
    medidas_captura = []
    fallos_google = []
    medidas_teclado = []
    medidas_p1 = []
    intentos_p1_sin_respuesta = []
    medidas_total = []
    filas_cadena = []

    for fila in registros:
        origen = fila.get("origen", "").lower().strip()
        google = numero(fila.get("tiempo_google_ms"))
        captura = numero(fila.get("tiempo_captura_ms"))
        teclado = numero(fila.get("tiempo_teclado_ms"))
        servicio = numero(fila.get("tiempo_servicio_ms"))
        total = numero(fila.get("tiempo_total_ms"))

        if captura is not None:
            medidas_captura.append(captura)
        if origen == "google" and google is not None:
            medidas_google.append(google)
        if origen == "teclado" and google is not None:
            fallos_google.append(google)  # Intento que NO consiguió transcribir
        if origen == "teclado" and teclado is not None:
            medidas_teclado.append(teclado)
        resultado = fila.get("resultado", "").strip()
        if servicio is not None and resultado in ("autorizada_p1", "rechazada_p1", "decision_recibida"):
            medidas_p1.append(servicio)
        elif servicio is not None and resultado == "sin_decision":
            intentos_p1_sin_respuesta.append(servicio)
        if total is not None and fila.get("resultado", "").strip():
            medidas_total.append(total)

        observacion = "Histórica: sin decisión ROS 2 registrada" if not fila.get("resultado", "").strip() else "P1 provisional sin LAYA; no hubo movimiento"
        fila_cadena = {col: "" for col in COLUMNAS_CADENA}
        for origen_col, destino_col in {
            "id_solicitud": "id_solicitud", "fecha": "fecha",
            "audio_original": "audio_original", "audio_copia": "audio_copia",
            "transcripcion": "transcripcion", "origen": "origen",
            "accion": "accion", "objeto": "objeto", "color": "color",
            "destino": "destino", "prioridad": "prioridad",
            "permitido": "permitido", "degradado": "degradado",
            "motivo": "motivo", "resultado": "resultado_p1",
            "tiempo_google_ms": "tiempo_google_ms",
            "tiempo_captura_ms": "tiempo_captura_audio_ms",
            "tiempo_teclado_ms": "tiempo_teclado_ms",
            "tiempo_servicio_ms": "tiempo_servicio_p1_ms",
            "tiempo_total_ms": "tiempo_total_parcial_ms",
        }.items():
            fila_cadena[destino_col] = fila.get(origen_col, "")
        fila_cadena["observaciones"] = observacion
        filas_cadena.append(fila_cadena)

    resumen = [
        estadisticas("Captura micrófono: fin estimado a WAV", medidas_captura, "Solo --microfono; incluye espera de silencio. No es el instante exacto del fin de voz"),
        estadisticas("Google: transcripción exitosa", medidas_google, "Solo origen=google; incluye pruebas históricas"),
        estadisticas("Google: intento fallido", fallos_google, "No representa transcripción exitosa; origen=teclado"),
        estadisticas("Teclado: tiempo de escritura", medidas_teclado, "Tiempo humano; no sumar a latencia automática del robot"),
        estadisticas("P1 provisional: decisión recibida", medidas_p1, "Tiempo del servicio ROS 2, sin desglose de LAYA"),
        estadisticas("P1: intento sin respuesta", intentos_p1_sin_respuesta, "Tiempo de espera fallida; NO mide una decisión P1"),
        estadisticas("Total parcial registrado", medidas_total, "Micrófono: captura+Google+teclado+servicio; archivo: Google+teclado+servicio. NO es voz-a-movimiento"),
    ]

    with RESUMEN.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["metrica", "n", "promedio_ms", "mediana_ms", "p95_ms", "minimo_ms", "maximo_ms", "nota"])
        escritor.writerows(resumen)
    with TABLA.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS_CADENA)
        escritor.writeheader()
        escritor.writerows(filas_cadena)

    print(f"Filas analizadas: {len(registros)}")
    for fila in resumen:
        print(f"{fila[0]}: n={fila[1]}, mediana={fila[3] or 'N/D'} ms, P95={fila[4] or 'N/D'} ms")
    print(f"Resumen: {RESUMEN}")
    print(f"Tabla para completar con broker y brazo: {TABLA}")
    print("NOTA: LATENCIAS PARCIALES CON P1 PROVISIONAL. Sin datos de LAYA, cola, visión, IK, MoveIt2 ni movimiento.")


if __name__ == "__main__":
    ejecutar()


if __name__ == "__main__":
    ejecutar()


