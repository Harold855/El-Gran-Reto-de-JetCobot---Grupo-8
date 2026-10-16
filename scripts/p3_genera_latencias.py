"""Resumen de latencias de la cadena de voz: Google/teclado, P1 y la entrega a P2 (/pick_place).

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

# Valores no medidos (visión, IK, planificación, brazo) quedan vacíos. Lo que contesta un broker
# simulado va con simulado_p2=True: no es movimiento físico ni latencia real del brazo.
COLUMNAS_CADENA = [
    "id_solicitud", "fecha", "audio_original", "audio_copia", "transcripcion",
    "origen", "accion", "objeto", "color", "destino", "prioridad",
    "permitido", "degradado", "motivo", "resultado_p1",
    "estado_p2", "codigo_p2", "simulado_p2", "resultado_brazo",
    "tiempo_google_ms", "tiempo_teclado_ms", "tiempo_servicio_p1_ms",
    "tiempo_total_parcial_ms", "tiempo_captura_audio_ms",
    "tiempo_decision_laya_ms", "tiempo_aceptacion_p2_ms", "tiempo_cola_ms",
    "tiempo_resultado_p2_ms", "tiempo_total_p2_ms", "etapas_p2",
    "tiempo_percepcion_ms", "tiempo_ik_ms", "tiempo_planificacion_ms",
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
    p2_aceptacion, p2_cola = [], []
    p2_resultado_sim, p2_resultado_real = [], []
    p2_total_sim, p2_total_real = [], []

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

        enviado = fila.get("enviado_p2", "").strip() == "True"
        simulado = fila.get("simulado_p2", "").strip() == "True"
        if enviado:
            aceptacion = numero(fila.get("tiempo_aceptacion_p2_ms"))
            if aceptacion is not None:
                p2_aceptacion.append(aceptacion)
            cola = numero(fila.get("espera_cola_p2_s"))
            if cola is not None:
                p2_cola.append(cola * 1000)
            resultado_p2 = numero(fila.get("tiempo_resultado_p2_ms"))
            total_p2 = numero(fila.get("tiempo_total_p2_ms"))
            if resultado_p2 is not None and fila.get("codigo_p2", "").strip():
                (p2_resultado_sim if simulado else p2_resultado_real).append(resultado_p2)
                if total_p2 is not None:
                    (p2_total_sim if simulado else p2_total_real).append(total_p2)

        if not fila.get("resultado", "").strip():
            observacion = "Histórica: sin decisión ROS 2 registrada"
        elif enviado and simulado:
            observacion = "P2 simulado: no hubo movimiento físico"
        elif enviado:
            observacion = "P2 respondió; el movimiento físico no se verifica aquí"
        elif fila.get("estado_p2", "").strip():
            observacion = f"No llegó a P2: {fila.get('mensaje_p2', '').strip() or fila.get('estado_p2')}"
        else:
            observacion = "Anterior a la integración con P2; no hubo movimiento"
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
            "estado_p2": "estado_p2", "codigo_p2": "codigo_p2", "simulado_p2": "simulado_p2",
            "tiempo_aceptacion_p2_ms": "tiempo_aceptacion_p2_ms",
            "tiempo_resultado_p2_ms": "tiempo_resultado_p2_ms",
            "tiempo_total_p2_ms": "tiempo_total_p2_ms", "etapas_p2": "etapas_p2",
        }.items():
            fila_cadena[destino_col] = fila.get(origen_col, "")
        if enviado:
            cola = numero(fila.get("espera_cola_p2_s"))
            fila_cadena["tiempo_cola_ms"] = "" if cola is None else round(cola * 1000, 2)
        fila_cadena["observaciones"] = observacion
        filas_cadena.append(fila_cadena)

    resumen = [
        estadisticas("Captura micrófono: fin estimado a WAV", medidas_captura, "Solo --microfono; incluye espera de silencio. No es el instante exacto del fin de voz"),
        estadisticas("Google: transcripción exitosa", medidas_google, "Solo origen=google; incluye pruebas históricas"),
        estadisticas("Google: intento fallido", fallos_google, "No representa transcripción exitosa; origen=teclado"),
        estadisticas("Teclado: tiempo de escritura", medidas_teclado, "Tiempo humano; no sumar a latencia automática del robot"),
        estadisticas("P1: decisión recibida", medidas_p1, "Tiempo del servicio ROS 2, sin desglose de LAYA"),
        estadisticas("P1: intento sin respuesta", intentos_p1_sin_respuesta, "Tiempo de espera fallida; NO mide una decisión P1"),
        estadisticas("Total parcial registrado", medidas_total, "Micrófono: captura+Google+teclado+servicio; archivo: Google+teclado+servicio. NO es voz-a-movimiento"),
        estadisticas("P2: aceptación del goal", p2_aceptacion, "Envío a respuesta de aceptación; incluye aceptadas y rechazadas"),
        estadisticas("P2: espera en cola", p2_cola, "Reportada por el broker (wait_time_s)"),
        estadisticas("P2 simulado: resultado", p2_resultado_sim, "Broker simulado: NO es latencia del brazo real"),
        estadisticas("P2 simulado: total hasta resultado", p2_total_sim, "Total parcial + resultado de un broker simulado: NO es voz-a-movimiento"),
        estadisticas("P2 real: resultado", p2_resultado_real, "Resultado de un ejecutor no simulado; no prueba por sí solo el movimiento observado"),
        estadisticas("P2 real: total hasta resultado", p2_total_real, "Total parcial + resultado de un ejecutor no simulado"),
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
    print(f"Tabla de solicitudes (cada ID enlaza con registro_tareas.csv de P2): {TABLA}")
    print("NOTA: lo marcado como simulado no es movimiento del brazo. Visión, IK, MoveIt2 y primer movimiento físico no se miden aquí.")


if __name__ == "__main__":
    ejecutar()


