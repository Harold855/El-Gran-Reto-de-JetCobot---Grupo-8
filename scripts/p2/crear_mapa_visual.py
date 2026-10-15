import cv2
import json
import math
from datetime import datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import CALIBRACION, MAPAS


BASE = CALIBRACION
CARPETA_SALIDA = MAPAS


def cargar_ultima_observacion():
    carpetas = sorted(BASE.glob("validacion_modelo_*"))

    if not carpetas:
        raise RuntimeError("No se encontraron validaciones")

    carpeta = carpetas[-1]

    datos = json.loads(
        (carpeta / "despues.json").read_text(encoding="utf-8")
    )

    imagen = cv2.imread(str(carpeta / "despues_original.png"))

    if imagen is None:
        raise RuntimeError("No se pudo abrir la fotografia")

    return datos, imagen, carpeta


def crear_mapa():
    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

    datos, imagen, origen = cargar_ultima_observacion()

    objetos = datos["objetos"]

    if len(objetos) != 4:
        raise RuntimeError(
            f"Se esperaban 4 cubos, se encontraron {len(objetos)}"
        )

    colores = {
        "rojo": (0, 0, 255),
        "verde": (0, 255, 0),
        "azul": (255, 0, 0),
        "amarillo": (0, 255, 255)
    }

    mapa = imagen.copy()
    centros = {}

    for objeto in objetos:
        color = objeto["color"]
        x = int(objeto["centro_x"])
        y = int(objeto["centro_y"])

        centros[color] = [x, y]

        cv2.circle(mapa, (x, y), 7, colores[color], -1)

        cv2.putText(
            mapa,
            f"{color}: ({x},{y})",
            (x + 12, y + 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            2
        )

    distancias = {}

    nombres = sorted(centros)

    for i in range(len(nombres)):
        for j in range(i + 1, len(nombres)):
            a = nombres[i]
            b = nombres[j]

            xa, ya = centros[a]
            xb, yb = centros[b]

            distancia = math.hypot(xb - xa, yb - ya)

            distancias[f"{a}_{b}"] = round(distancia, 2)

    identificador = datetime.now().strftime("%Y%m%d_%H%M%S")

    ruta_imagen = CARPETA_SALIDA / f"mapa_{identificador}.png"
    ruta_json = CARPETA_SALIDA / f"mapa_{identificador}.json"

    resultado = {
        "origen": str(origen),
        "posicion_brazo": datos["posicion"],
        "angulos_brazo": datos["angulos"],
        "centros_pixeles": centros,
        "distancias_pixeles": distancias,
        "unidad": "pixeles",
        "calibracion_metrica": False
    }

    if not cv2.imwrite(str(ruta_imagen), mapa):
        raise RuntimeError("No se pudo guardar el mapa")

    ruta_json.write_text(
        json.dumps(resultado, indent=4),
        encoding="utf-8"
    )

    print("\nMAPA VISUAL GENERADO")
    print("Posicion del brazo:", datos["posicion"])

    print("\nCentros:")
    for color, centro in centros.items():
        print(color, centro)

    print("\nDistancias:")
    for pareja, distancia in distancias.items():
        print(pareja, distancia, "px")

    print("\nImagen:", ruta_imagen.resolve())
    print("Datos:", ruta_json.resolve())


if __name__ == "__main__":
    crear_mapa()
