# Lee el brazo por el puerto serie (get_coords/get_angles) sin pasar por el broker: usar con el broker detenido.
import cv2
import json
import time
from pathlib import Path
from pymycobot.mycobot import MyCobot
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import CALIBRACION
from jetcobot.vision_colores import detectar_cubos


PUERTO = "/dev/ttyUSB0"
VELOCIDAD = 1000000
CARPETA = CALIBRACION


def capturar(camara):
    for _ in range(10):
        correcto, imagen = camara.read()
        if not correcto:
            raise RuntimeError("No se pudo capturar la imagen")
    return imagen


def registrar(brazo, camara, nombre):
    posicion = brazo.get_coords()
    angulos = brazo.get_angles()

    if not posicion or not angulos:
        raise RuntimeError("No se pudo leer la posicion del brazo")

    imagen = capturar(camara)
    objetos = detectar_cubos(imagen)

    registro = {
        "nombre": nombre,
        "fecha": time.time(),
        "posicion": posicion,
        "angulos": angulos,
        "resolucion": [imagen.shape[1], imagen.shape[0]],
        "objetos": objetos
    }

    ruta_imagen = CARPETA / f"{nombre}.png"
    ruta_datos = CARPETA / f"{nombre}.json"

    if not cv2.imwrite(str(ruta_imagen), imagen):
        raise RuntimeError("No se pudo guardar la imagen")

    ruta_datos.write_text(
        json.dumps(registro, indent=4),
        encoding="utf-8"
    )

    print("\nPosicion del brazo:", posicion)
    print("Angulos:", angulos)
    print("Cubos detectados:", len(objetos))

    for objeto in objetos:
        print(
            objeto["color"],
            objeto["centro_x"],
            objeto["centro_y"]
        )

    print("Registro:", ruta_datos)


def main():
    CARPETA.mkdir(parents=True, exist_ok=True)

    brazo = MyCobot(PUERTO, VELOCIDAD)
    camara = cv2.VideoCapture(0, cv2.CAP_V4L2)

    if not camara.isOpened():
        raise RuntimeError("No se pudo abrir la camara")

    try:
        registrar(brazo, camara, "escaneo_inicial")
    finally:
        camara.release()


if __name__ == "__main__":
    main()
