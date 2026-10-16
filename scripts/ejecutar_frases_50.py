"""
Pregunta 1: EjecutaR las 50 frases por /interpretar_orden y por el clasificador por palabras clave.

¿Que realiza?
    - Envia cada frase al servicio ROS 2 /interpretar_orden y mide la latencia en el cliente (ida y vuelta: red + calculo del servidor).
    - Si la respuesta informa el calculo del servidor (campo `tiempo_servidor_ms`), separa ese tiempo del de red. Hoy el servicio no lo informa: esas columnas quedan vacias.
    - Ejecuta tambien, en local, el clasificador por palabras clave sobre las mismas frases.
    - Compara cada decision con el resultado esperado del CSV de frases.

Produce, en evidencias/pregunta_1/mediciones/ (nunca sobrescribe: el nombre lleva la hora):
    <escenario>_<fecha>_frases.csv    una fila por frase y repeticion, con la decision de cada metodo
    <escenario>_<fecha>_resumen.md    tablas de latencia (mediana y p95), exactitud y prediccion
    predicciones.csv                  lo que el equipo esperaba medir, registrado ANTES de medir

Uso
    1) midiendo con el laboratorio en calma (la prediccion es obligatoria)
    python3 scripts/ejecutar_frases_50.py --escenario calma \\
        --prediccion-mediana-ms 40 --prediccion-p95-ms 80 --justificacion "red local, servidor libre"

    2) midiendo con todos los equipos consultando a la vez
    python3 scripts/ejecutar_frases_50.py --escenario carga \\
        --prediccion-mediana-ms 120 --prediccion-p95-ms 400 --justificacion "cola en el servidor"

    3) ensayo para probar el script (no exige prediccion; los archivos llevan prefijo ensayo_)
    python3 scripts/ejecutar_frases_50.py --escenario calma --ensayo

    4) comparar dos mediciones ya hechas (no necesita ROS)
    python3 scripts/ejecutar_frases_50.py --comparar mediciones/calma_X_frases.csv mediciones/carga_Y_frases.csv

Requiere el entorno de ROS 2 (source /opt/ros/humble/setup.bash e install/setup.bash) y el servicio /interpretar_orden en ejecucion.
"""

import argparse
import csv
import os
import socket
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FRASES_POR_DEFECTO = RAIZ / "evidencias/pregunta_1/frases_practica_50.csv"
SALIDA_POR_DEFECTO = RAIZ / "evidencias/pregunta_1/mediciones"
CARPETA_NODO = RAIZ / "src/interprete_ordenes/interprete_ordenes"
FRASE_CALENTAMIENTO = "Recoge el cubo rojo y colócalo en la zona verde"

COLUMNAS_FRASES = ["id", "frase", "resultado_esperado", "color_cubo_esperado", "color_zona_esperada"]

COLUMNAS_SALIDA = [
    "fecha", "escenario", "repeticion", "id", "frase",
    "resultado_esperado", "color_cubo_esperado", "color_zona_esperada",
    # servicio /interpretar_orden
    "estado_servicio", "metodo_servicio", "servicio_permitido", "servicio_accion",
    "servicio_color", "servicio_destino", "servicio_prioridad", "servicio_degradado",
    "servicio_motivo", "servicio_correcto",
    "tiempo_total_ms", "tiempo_servidor_ms", "tiempo_red_ms",
    # clasificador por palabras clave (local)
    "palabras_permitido", "palabras_color", "palabras_destino", "palabras_motivo",
    "palabras_correcto", "tiempo_palabras_ms",
]

COLUMNAS_PREDICCION = [
    "fecha_registro", "escenario", "prediccion_mediana_ms", "prediccion_p95_ms",
    "prediccion_exactitud_servicio_pct", "justificacion",
]


# logica 
def leer_frases(ruta):
    with Path(ruta).open(newline="", encoding="utf-8-sig") as archivo:
        filas = list(csv.DictReader(archivo))
    faltan = [c for c in COLUMNAS_FRASES if not filas or c not in filas[0]]
    if faltan:
        raise ValueError(f"El CSV de frases no tiene las columnas: {', '.join(faltan)}")
    for fila in filas:
        if fila["resultado_esperado"] not in ("ACEPTAR", "RECHAZAR"):
            raise ValueError(f"Frase {fila['id']}: resultado_esperado debe ser ACEPTAR o RECHAZAR")
    return filas


def es_correcto(permitido, color, destino, fila):
    """Correcta si acepta/rechaza como se esperaba y, al aceptar, con los colores esperados."""
    if permitido != (fila["resultado_esperado"] == "ACEPTAR"):
        return False
    if not permitido:
        return True
    return color == fila["color_cubo_esperado"] and destino == fila["color_zona_esperada"]


def percentil(valores, p):
    """Percentil p (0-100) con interpolacion lineal entre vecinos (igual que numpy por defecto)."""
    if not valores:
        return None
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * p / 100
    bajo = int(posicion)
    alto = min(bajo + 1, len(ordenados) - 1)
    return ordenados[bajo] + (ordenados[alto] - ordenados[bajo]) * (posicion - bajo)


def estadisticas(valores):
    if not valores:
        return {"n": 0, "mediana": None, "p95": None, "minimo": None, "maximo": None, "media": None}
    return {
        "n": len(valores),
        "mediana": statistics.median(valores),
        "p95": percentil(valores, 95),
        "minimo": min(valores),
        "maximo": max(valores),
        "media": statistics.fmean(valores),
    }

def numero(texto):
    if texto is None or not str(texto).strip():
        return None
    try:
        return float(texto)
    except ValueError:
        return None

def booleano(texto):
    return str(texto).strip().lower() == "true"

def formato(valor, decimales=1):
    return "—" if valor is None else f"{valor:.{decimales}f}"

def tabla_md(cabeceras, filas):
    lineas = ["| " + " | ".join(cabeceras) + " |", "|" + "|".join(["---"] * len(cabeceras)) + "|"]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return "\n".join(lineas)

def exactitud(filas, prefijo, condicion=lambda f: True):
    """Cuenta correctas, falsos positivos y falsos negativos de un metodo."""
    elegidas = [f for f in filas if condicion(f)]
    correctas = sum(booleano(f[f"{prefijo}_correcto"]) for f in elegidas)
    fp = sum(1 for f in elegidas if f["resultado_esperado"] == "RECHAZAR" and booleano(f[f"{prefijo}_permitido"]))
    fn = sum(1 for f in elegidas if f["resultado_esperado"] == "ACEPTAR"
             and f[f"{prefijo}_permitido"] != "" and not booleano(f[f"{prefijo}_permitido"]))
    return len(elegidas), correctas, fp, fn

def resumir(filas):
    """Estadisticas de latencia y exactitud a partir de las filas de resultados (ya como texto)."""
    ok = [f for f in filas if f["estado_servicio"] == "ok"]
    laya = [f for f in ok if not booleano(f["servicio_degradado"])]
    totales = [numero(f["tiempo_total_ms"]) for f in ok]
    servidor = [numero(f["tiempo_servidor_ms"]) for f in ok if numero(f["tiempo_servidor_ms"]) is not None]
    red = [numero(f["tiempo_red_ms"]) for f in ok if numero(f["tiempo_red_ms"]) is not None]
    return {
        "filas": len(filas),
        "sin_respuesta": len(filas) - len(ok),
        "total": estadisticas(totales),
        "total_laya": estadisticas([numero(f["tiempo_total_ms"]) for f in laya]),
        "servidor": estadisticas(servidor),
        "red": estadisticas(red),
        "palabras_ms": estadisticas([numero(f["tiempo_palabras_ms"]) for f in filas]),
        "exact_laya": exactitud(filas, "servicio", lambda f: f["estado_servicio"] == "ok" and not booleano(f["servicio_degradado"])),
        "exact_respaldo": exactitud(filas, "servicio", lambda f: f["estado_servicio"] == "ok" and booleano(f["servicio_degradado"])),
        "exact_servicio_todo": exactitud(filas, "servicio", lambda f: f["estado_servicio"] == "ok"),
        "exact_palabras": exactitud(filas, "palabras"),
    }

def fila_exactitud(nombre, datos, nota=""):
    n, correctas, fp, fn = datos
    if n == 0:
        return [nombre, 0, "—", "—", "—", "—", nota]
    return [nombre, n, correctas, f"{100 * correctas / n:.1f} %", fp, fn, nota]


def fila_latencia(nombre, e, decimales=1):
    return [nombre, e["n"], formato(e["mediana"], decimales), formato(e["p95"], decimales),
            formato(e["minimo"], decimales), formato(e["maximo"], decimales), formato(e["media"], decimales)]

CABECERA_LATENCIA = ["Tiempo (ms)", "Muestras", "Mediana", "Percentil 95", "Mínimo", "Máximo", "Media"]
CABECERA_EXACTITUD = ["Método", "Frases", "Correctas", "Exactitud", "Falsos positivos", "Falsos negativos", "Nota"]

def construir_resumen(filas, meta, prediccion):
    r = resumir(filas)
    md = [f"# Medición de la Pregunta 1 — escenario «{meta['escenario']}»"
          + (" (ENSAYO, no cuenta como evidencia)" if meta["ensayo"] else ""), "",
          f"- **Fecha:** {meta['fecha']}",
          f"- **Equipo:** {meta['equipo']} · **ROS_DOMAIN_ID:** {meta['dominio']}",
          f"- **Frases:** {meta['n_frases']} × {meta['repeticiones']} repetición(es) = {r['filas']} consultas "
          f"(archivo `{meta['archivo_frases']}`)",
          f"- **Calentamiento:** {'1 consulta fuera de la medición' if meta['calentamiento'] else 'ninguno'}",
          f"- **Límite por consulta:** {meta['timeout']:g} s · **Sin respuesta:** {r['sin_respuesta']}",
          "", "## Latencia del servicio", "",
          "El tiempo total se mide en el cliente, de ida y vuelta, y **incluye la red y el cálculo del servidor**. "
          "Solo cuentan las consultas que recibieron respuesta. Los percentiles usan interpolación lineal.", "",
          tabla_md(CABECERA_LATENCIA, [
              fila_latencia("Total (red + cálculo)", r["total"]),
              fila_latencia("Cálculo del servidor", r["servidor"]),
              fila_latencia("Red (total − servidor)", r["red"]),
              fila_latencia("Solo respuestas de LAYA", r["total_laya"]),
              fila_latencia("Palabras clave (local)", r["palabras_ms"], 4),
          ])]
    if r["servidor"]["n"] == 0:
        md += ["", "> El servicio **no informó el tiempo de cálculo del servidor**, por eso no se puede separar de la red. "
                   "Cuando el servicio devuelva `tiempo_servidor_ms`, estas filas se llenan solas."]
    if r["total_laya"]["n"] == 0:
        md += ["", "> Ninguna respuesta vino de LAYA (`degradado=True` en todas): la latencia medida es la del respaldo por reglas."]

    md += ["", "## Exactitud sobre las mismas frases", "",
           tabla_md(CABECERA_EXACTITUD, [
               fila_exactitud("LAYA (respuestas con degradado=False)", r["exact_laya"],
                              "sin respuestas de LAYA" if r["exact_laya"][0] == 0 else ""),
               fila_exactitud("Servicio en modo respaldo (degradado=True)", r["exact_respaldo"]),
               fila_exactitud("Clasificador por palabras clave (local)", r["exact_palabras"]),
           ]), "",
           "Falso positivo = aceptó una orden que debía rechazar. Falso negativo = rechazó una orden válida. "
           "Una consulta sin respuesta no se cuenta en la exactitud del servicio."]
    if r["sin_respuesta"]:
        md += [f"", f"> **Atención:** {r['sin_respuesta']} consulta(s) sin respuesta quedaron fuera de la exactitud del servicio."]

    md += ["", "## Predicción frente a medición", ""]
    if prediccion is None:
        md += ["_No se registró predicción (ensayo)._"]
    else:
        exact_pred = prediccion.get("prediccion_exactitud_servicio_pct")
        n, c, _, _ = r["exact_servicio_todo"]
        exact_medida = None if n == 0 else 100 * c / n
        comparacion = []
        for nombre, pred, medido in (
            ("Mediana del total (ms)", numero(prediccion["prediccion_mediana_ms"]), r["total"]["mediana"]),
            ("Percentil 95 del total (ms)", numero(prediccion["prediccion_p95_ms"]), r["total"]["p95"]),
            ("Exactitud del servicio (%)", numero(exact_pred), exact_medida),
        ):
            if pred is None or medido is None:
                comparacion.append([nombre, formato(pred), formato(medido), "—", "—"])
            else:
                comparacion.append([nombre, formato(pred), formato(medido), f"{medido - pred:+.1f}",
                                    f"{100 * (medido - pred) / pred:+.0f} %" if pred else "—"])
        md += [tabla_md(["Magnitud", "Predicho", "Medido", "Diferencia", "Diferencia relativa"], comparacion), "",
               f"Justificación escrita antes de medir: «{prediccion.get('justificacion') or 'sin justificación'}»."]

    errores = filas_con_error(filas)
    md += ["", "## Frases con decisión incorrecta", ""]
    if not errores:
        md += ["Ninguna."]
    else:
        md += [tabla_md(["Id", "Frase", "Esperado", "Servicio", "Palabras clave"],
                        [[f["id"], f["frase"], f["resultado_esperado"],
                          "sin respuesta" if f["estado_servicio"] != "ok" else
                          ("ACEPTA" if booleano(f["servicio_permitido"]) else "RECHAZA")
                          + ("" if booleano(f["servicio_correcto"]) else " ✗"),
                          ("ACEPTA" if booleano(f["palabras_permitido"]) else "RECHAZA")
                          + ("" if booleano(f["palabras_correcto"]) else " ✗")]
                         for f in errores])]
    return "\n".join(md) + "\n"

def filas_con_error(filas):
    vistos, errores = set(), []
    for f in filas:
        incorrecto = (f["estado_servicio"] == "ok" and not booleano(f["servicio_correcto"])) \
            or not booleano(f["palabras_correcto"])
        if incorrecto and f["id"] not in vistos:
            vistos.add(f["id"])
            errores.append(f)
    return errores

def comparar(ruta_calma, ruta_carga, salida):
    """Tabla comparativa de dos mediciones (calma y carga)."""
    datos = {}
    for nombre, ruta in (("calma", ruta_calma), ("carga", ruta_carga)):
        with Path(ruta).open(newline="", encoding="utf-8") as archivo:
            datos[nombre] = resumir(list(csv.DictReader(archivo)))
    filas = []
    for etiqueta, clave in (("Total (red + cálculo)", "total"), ("Cálculo del servidor", "servidor"), ("Red", "red")):
        for estadistico, nombre in (("mediana", "mediana"), ("p95", "percentil 95")):
            a, b = datos["calma"][clave][estadistico], datos["carga"][clave][estadistico]
            razon = "—" if a in (None, 0) or b is None else f"×{b / a:.2f}"
            filas.append([f"{etiqueta} · {nombre}", formato(a), formato(b), razon])
    md = ["# Comparación: laboratorio en calma frente a todos los equipos consultando", "",
          f"- Calma: `{Path(ruta_calma).name}` ({datos['calma']['total']['n']} respuestas)",
          f"- Carga: `{Path(ruta_carga).name}` ({datos['carga']['total']['n']} respuestas)", "",
          tabla_md(["Magnitud (ms)", "Calma", "Carga", "Carga / calma"], filas), "",
          "## Explicación de la diferencia", "",
          "_Redactar con los datos de arriba: cuál componente creció más (red o cálculo del servidor), "
          "si crece la cola de espera en el servidor y por qué el percentil 95 se mueve más que la mediana._", ""]
    Path(salida).write_text("\n".join(md), encoding="utf-8")
    return salida

# medicion
def cargar_clasificador():
    sys.path.insert(0, str(CARPETA_NODO))
    from interprete_ordenes import clasificar_orden  # importa rclpy: requiere el entorno de ROS 2
    return clasificar_orden

def crear_medidor(timeout):
    import rclpy
    from rclpy.node import Node
    from interprete_ordenes_interfaces.srv import InterpretarOrden

    class Medidor(Node):
        def __init__(self):
            super().__init__("medidor_frases_p1")
            self.cliente = self.create_client(InterpretarOrden, "/interpretar_orden")

        def consultar(self, frase):
            """Devuelve (respuesta | None, milisegundos, estado)."""
            solicitud = InterpretarOrden.Request()
            solicitud.frase = frase
            inicio = time.perf_counter()
            futuro = self.cliente.call_async(solicitud)
            rclpy.spin_until_future_complete(self, futuro, timeout_sec=timeout)
            milisegundos = (time.perf_counter() - inicio) * 1000
            if not futuro.done():
                futuro.cancel()
                return None, milisegundos, "sin_respuesta"
            return futuro.result(), milisegundos, "ok"

    return Medidor()

def construir_fila(ahora, escenario, repeticion, f, respuesta, ms, estado, reglas, ms_reglas):
    permitido_pal, color_pal, destino_pal, motivo_pal = reglas[5], reglas[2], reglas[3], reglas[6]
    fila = {
        "fecha": ahora, "escenario": escenario, "repeticion": repeticion, "id": f["id"], "frase": f["frase"],
        "resultado_esperado": f["resultado_esperado"], "color_cubo_esperado": f["color_cubo_esperado"],
        "color_zona_esperada": f["color_zona_esperada"], "estado_servicio": estado,
        "tiempo_total_ms": round(ms, 3),
        "palabras_permitido": permitido_pal, "palabras_color": color_pal, "palabras_destino": destino_pal,
        "palabras_motivo": motivo_pal, "palabras_correcto": es_correcto(permitido_pal, color_pal, destino_pal, f),
        "tiempo_palabras_ms": round(ms_reglas, 4),
    }
    vacio = dict.fromkeys(["metodo_servicio", "servicio_permitido", "servicio_accion", "servicio_color",
                           "servicio_destino", "servicio_prioridad", "servicio_degradado", "servicio_motivo",
                           "servicio_correcto", "tiempo_servidor_ms", "tiempo_red_ms"], "")
    fila.update(vacio)
    if respuesta is not None:
        servidor = getattr(respuesta, "tiempo_servidor_ms", None)
        fila.update({
            "metodo_servicio": "palabras_clave" if respuesta.degradado else "laya",
            "servicio_permitido": respuesta.permitido, "servicio_accion": respuesta.accion,
            "servicio_color": respuesta.color, "servicio_destino": respuesta.destino,
            "servicio_prioridad": respuesta.prioridad, "servicio_degradado": respuesta.degradado,
            "servicio_motivo": respuesta.motivo,
            "servicio_correcto": es_correcto(respuesta.permitido, respuesta.color, respuesta.destino, f),
        })
        if servidor is not None and float(servidor) > 0:  # 0 = el servidor no lo informó
            fila["tiempo_servidor_ms"] = round(float(servidor), 3)
            fila["tiempo_red_ms"] = round(ms - float(servidor), 3)
    return fila


def registrar_prediccion(carpeta, args):
    ruta = carpeta / "predicciones.csv"
    nuevo = not ruta.exists() or ruta.stat().st_size == 0
    registro = {
        "fecha_registro": datetime.now().isoformat(timespec="seconds"), "escenario": args.escenario,
        "prediccion_mediana_ms": args.prediccion_mediana_ms, "prediccion_p95_ms": args.prediccion_p95_ms,
        "prediccion_exactitud_servicio_pct": "" if args.prediccion_exactitud_pct is None else args.prediccion_exactitud_pct,
        "justificacion": args.justificacion or "",
    }
    with ruta.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS_PREDICCION)
        if nuevo:
            escritor.writeheader()
        escritor.writerow(registro)
    return registro

def prefijo_unico(carpeta, prefijo):
    """Evita pisar resultados: si ya existe el nombre (misma hora), agrega _2, _3..."""
    candidato, k = prefijo, 1
    while (carpeta / f"{candidato}_frases.csv").exists() or (carpeta / f"{candidato}_resumen.md").exists():
        k += 1
        candidato = f"{prefijo}_{k}"
    return candidato

def ruta_legible(ruta):
    ruta = Path(ruta).resolve()
    return str(ruta.relative_to(RAIZ)) if RAIZ in ruta.parents else str(ruta)

def leer_argumentos(argv):
    if "--ros-args" in argv:  # lo que va despues de --ros-args es de ROS, no de este script
        argv = argv[:argv.index("--ros-args")]
    p = argparse.ArgumentParser(description="Mide /interpretar_orden y el clasificador por palabras clave con las frases de prueba.")
    p.add_argument("--escenario", choices=["calma", "carga"], help="calma = laboratorio libre; carga = todos los equipos consultando a la vez")
    p.add_argument("--frases", default=str(FRASES_POR_DEFECTO), help="CSV con id, frase, resultado_esperado, color_cubo_esperado, color_zona_esperada")
    p.add_argument("--salida", default=str(SALIDA_POR_DEFECTO), help="carpeta de resultados")
    p.add_argument("--repeticiones", type=int, default=1, help="veces que se recorre el conjunto (por defecto 1)")
    p.add_argument("--timeout", type=float, default=5.0, help="segundos maximos por consulta (por defecto 5)")
    p.add_argument("--sin-calentamiento", action="store_true", help="no hacer una consulta previa fuera de la medicion")
    p.add_argument("--prediccion-mediana-ms", help="mediana que se espera medir (obligatoria salvo --ensayo)")
    p.add_argument("--prediccion-p95-ms", help="percentil 95 que se espera medir (obligatorio salvo --ensayo)")
    p.add_argument("--prediccion-exactitud-pct", help="exactitud del servicio que se espera (opcional)")
    p.add_argument("--justificacion", help="por que se espera ese valor (se guarda junto a la prediccion)")
    p.add_argument("--ensayo", action="store_true", help="prueba del script: no exige prediccion y los archivos llevan prefijo ensayo_")
    p.add_argument("--comparar", nargs=2, metavar=("CALMA_CSV", "CARGA_CSV"), help="compara dos archivos *_frases.csv y termina")
    args = p.parse_args(argv)
    if not args.comparar:
        if not args.escenario:
            p.error("falta --escenario (calma o carga)")
        if not args.ensayo and (args.prediccion_mediana_ms is None or args.prediccion_p95_ms is None):
            p.error("el examen exige escribir ANTES de medir lo que se espera obtener: indica "
                    "--prediccion-mediana-ms y --prediccion-p95-ms (o usa --ensayo para probar el script)")
        for nombre in ("prediccion_mediana_ms", "prediccion_p95_ms", "prediccion_exactitud_pct"):
            valor = getattr(args, nombre)
            if valor is not None and numero(valor) is None:
                p.error(f"--{nombre.replace('_', '-')} debe ser un numero")
        if args.repeticiones < 1 or args.timeout <= 0:
            p.error("--repeticiones debe ser >= 1 y --timeout > 0")
    return args

def main():
    args = leer_argumentos(sys.argv[1:])
    carpeta = Path(args.salida)

    if args.comparar:
        destino = carpeta / f"comparacion_calma_vs_carga_{datetime.now():%Y%m%d_%H%M%S}.md"
        carpeta.mkdir(parents=True, exist_ok=True)
        print(f"Comparación escrita en {comparar(args.comparar[0], args.comparar[1], destino)}")
        return 0

    frases = leer_frases(args.frases)
    clasificar = cargar_clasificador()
    carpeta.mkdir(parents=True, exist_ok=True)

    prediccion = None
    if not args.ensayo:
        prediccion = registrar_prediccion(carpeta, args)  # antes de medir, con su hora
        print(f"Predicción registrada en {carpeta / 'predicciones.csv'} antes de medir.")

    import rclpy
    rclpy.init(args=sys.argv)
    medidor = crear_medidor(args.timeout)
    try:
        if not medidor.cliente.wait_for_service(timeout_sec=args.timeout):
            print(f"[ERROR] /interpretar_orden no está disponible tras {args.timeout:g} s. "
                  "Inicia interprete_ordenes y revisa ROS_DOMAIN_ID.")
            return 1

        if not args.sin_calentamiento:
            medidor.consultar(FRASE_CALENTAMIENTO)  # frase ajena al conjunto, no se registra

        marca = datetime.now()
        prefijo = prefijo_unico(carpeta, ("ensayo_" if args.ensayo else "") + f"{args.escenario}_{marca:%Y%m%d_%H%M%S}")
        filas = []
        for repeticion in range(1, args.repeticiones + 1):
            for f in frases:
                respuesta, ms, estado = medidor.consultar(f["frase"])
                inicio = time.perf_counter()
                reglas = clasificar(f["frase"])
                ms_reglas = (time.perf_counter() - inicio) * 1000
                filas.append({c: str(v) if not isinstance(v, str) else v for c, v in construir_fila(
                    marca.isoformat(timespec="seconds"), args.escenario, repeticion, f,
                    respuesta, ms, estado, reglas, ms_reglas).items()})
                if estado != "ok":
                    print(f"[AVISO] Sin respuesta a la frase {f['id']} en {args.timeout:g} s")
    finally:
        medidor.destroy_node()
        rclpy.shutdown()

    ruta_csv = carpeta / f"{prefijo}_frases.csv"
    with ruta_csv.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS_SALIDA)
        escritor.writeheader()
        escritor.writerows(filas)

    meta = {"escenario": args.escenario, "ensayo": args.ensayo, "fecha": marca.isoformat(timespec="seconds"),
            "equipo": socket.gethostname(), "dominio": os.environ.get("ROS_DOMAIN_ID", "(sin definir)"),
            "n_frases": len(frases), "repeticiones": args.repeticiones, "timeout": args.timeout,
            "calentamiento": not args.sin_calentamiento,
            "archivo_frases": ruta_legible(args.frases)}
    ruta_md = carpeta / f"{prefijo}_resumen.md"
    ruta_md.write_text(construir_resumen(filas, meta, prediccion), encoding="utf-8")

    r = resumir(filas)
    print(f"\nEscenario: {args.escenario} | consultas: {r['filas']} | sin respuesta: {r['sin_respuesta']}")
    print(f"Latencia total: mediana {formato(r['total']['mediana'])} ms | p95 {formato(r['total']['p95'])} ms")
    for nombre, clave in (("Servicio", "exact_servicio_todo"), ("Palabras clave", "exact_palabras")):
        n, c, fp, fn = r[clave]
        print(f"Exactitud {nombre}: {c}/{n} | falsos positivos {fp} | falsos negativos {fn}")
    print(f"\nResultados: {ruta_csv}\nResumen:    {ruta_md}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
