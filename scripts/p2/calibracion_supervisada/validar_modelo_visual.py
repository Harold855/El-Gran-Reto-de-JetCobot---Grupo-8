# CALIBRACIÓN SUPERVISADA: abre el puerto serie del brazo directamente, sin pasar por el broker.
# Usar solo con el broker detenido y con alguien junto al robot; nunca durante P3 ni la demostración.
import cv2
import json
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from pymycobot.mycobot import MyCobot
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from jetcobot.rutas import CALIBRACION
from jetcobot.vision_colores import detectar_cubos, dibujar_detecciones


CARPETA = CALIBRACION
DESPLAZAMIENTO_X = -8.0


def capturar(camara):
    imagen = None

    for _ in range(15):
        correcto, fotograma = camara.read()
        if correcto:
            imagen = fotograma

    if imagen is None:
        raise RuntimeError("No se pudo capturar una fotografia")

    return imagen


def registrar(brazo, camara, carpeta, nombre):
    posicion = brazo.get_coords()
    angulos = brazo.get_angles()

    if not posicion or len(posicion) != 6:
        raise RuntimeError("No se pudo leer la posicion")

    if not angulos or len(angulos) != 6:
        raise RuntimeError("No se pudieron leer las articulaciones")

    imagen = capturar(camara)
    objetos = detectar_cubos(imagen)
    marcada = dibujar_detecciones(imagen, objetos)

    if not cv2.imwrite(str(carpeta / f"{nombre}_original.png"), imagen):
        raise RuntimeError("Error guardando fotografia")

    if not cv2.imwrite(str(carpeta / f"{nombre}_detectada.png"), marcada):
        raise RuntimeError("Error guardando detecciones")

    datos = {
        "posicion": posicion,
        "angulos": angulos,
        "objetos": objetos
    }

    (carpeta / f"{nombre}.json").write_text(
        json.dumps(datos, indent=4),
        encoding="utf-8"
    )

    return datos, marcada


def main():
    identificador = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    carpeta = CARPETA / f"validacion_modelo_{identificador}"
    carpeta.mkdir(parents=True, exist_ok=False)

    modelo = json.loads(
        (CARPETA / "modelo_visual_preliminar.json").read_text()
    )

    matriz = np.array(modelo["matriz_robot_a_imagen"], dtype=float)

    brazo = MyCobot("/dev/ttyUSB0", 1000000)
    camara = cv2.VideoCapture(0, cv2.CAP_V4L2)

    if not camara.isOpened():
        raise SystemExit("No se pudo abrir la camara")

    try:
        antes, imagen_antes = registrar(
            brazo, camara, carpeta, "antes"
        )

        objetivo = antes["posicion"].copy()
        objetivo[0] += DESPLAZAMIENTO_X

        print("Posicion inicial:", antes["posicion"])
        print("Objetivo:", objetivo)
        print("Movimiento solicitado: -8 mm en X")
        print("Comprueba que toda la trayectoria este libre.")

        with open("/dev/tty", "r") as terminal:
            print("Escribe MOVER para continuar: ", end="", flush=True)
            confirmacion = terminal.readline().strip()

        if confirmacion != "MOVER":
            print("Cancelado. Fotografia inicial conservada.")
            return

        brazo.send_coords(objetivo, 10, 1)

        inicio = time.monotonic()
        iniciado = False
        terminado = False

        while time.monotonic() - inicio < 15:
            time.sleep(0.2)
            estado = brazo.is_moving()

            if estado == 1:
                iniciado = True

            if iniciado and estado == 0:
                terminado = True
                break

        if not terminado:
            print("No se confirmo el fin del movimiento.")
            print("Revisa el brazo antes de repetir cualquier orden.")
            return

        time.sleep(1)

        despues, imagen_despues = registrar(
            brazo, camara, carpeta, "despues"
        )

        if imagen_antes.shape != imagen_despues.shape:
            raise RuntimeError("Resoluciones diferentes")

        comparacion = cv2.hconcat([imagen_antes, imagen_despues])
        ruta = carpeta / "comparacion.png"

        if not cv2.imwrite(str(ruta), comparacion):
            raise RuntimeError("No se pudo guardar la comparacion")

        movimiento = np.array(
            despues["posicion"][:2],
            dtype=float
        ) - np.array(
            antes["posicion"][:2],
            dtype=float
        )

        prediccion = matriz @ movimiento

        origen = {o["color"]: o for o in antes["objetos"]}
        destino = {o["color"]: o for o in despues["objetos"]}

        observaciones = []

        print("\nRESULTADOS")
        print("Movimiento real XY:", movimiento.round(2).tolist())
        print("Prediccion visual:", prediccion.round(2).tolist())

        for color in sorted(origen.keys() & destino.keys()):
            a = origen[color]
            b = destino[color]

            cambio = np.array([
                b["centro_x"] - a["centro_x"],
                b["centro_y"] - a["centro_y"]
            ], dtype=float)

            observaciones.append(cambio)

            print(color, "cambio observado:", cambio.tolist())

        if observaciones:
            promedio = np.mean(observaciones, axis=0)
            error = promedio - prediccion

            print("Cambio promedio:", promedio.round(2).tolist())
            print("Error prediccion:", error.round(2).tolist())
            print("Error total:", round(float(np.linalg.norm(error)), 2), "px")

        print("Historial:", carpeta.resolve())
        print("Comparacion:", ruta.resolve())

    finally:
        camara.release()


if __name__ == "__main__":
    main()
