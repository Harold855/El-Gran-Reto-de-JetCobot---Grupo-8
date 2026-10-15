# CALIBRACIÓN SUPERVISADA: abre el puerto serie del brazo directamente, sin pasar por el broker.
# Usar solo con el broker detenido y con alguien junto al robot; nunca durante P3 ni la demostración.
import cv2
import json
import time
from pathlib import Path
from datetime import datetime
from pymycobot.mycobot import MyCobot
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from jetcobot.rutas import CALIBRACION
from jetcobot.vision_colores import detectar_cubos, dibujar_detecciones


BASE = CALIBRACION / "encuadres"
AJUSTE_Y = -5.0
MARGEN = 15


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
        raise RuntimeError("No se pudieron leer los angulos")

    imagen = capturar(camara)
    objetos = detectar_cubos(imagen)
    marcada = dibujar_detecciones(imagen, objetos)

    alto, ancho = imagen.shape[:2]

    evaluacion = {}

    for objeto in objetos:
        x, y, w, h = objeto["rectangulo"]

        evaluacion[objeto["color"]] = {
            "centro": [objeto["centro_x"], objeto["centro_y"]],
            "rectangulo": [x, y, w, h],
            "completo": (
                x >= MARGEN
                and y >= MARGEN
                and x + w <= ancho - MARGEN
                and y + h <= alto - MARGEN
            )
        }

    cv2.imwrite(str(carpeta / f"{nombre}_original.png"), imagen)
    cv2.imwrite(str(carpeta / f"{nombre}_detectada.png"), marcada)

    datos = {
        "posicion": posicion,
        "angulos": angulos,
        "resolucion": [ancho, alto],
        "objetos": objetos,
        "evaluacion": evaluacion
    }

    (carpeta / f"{nombre}.json").write_text(
        json.dumps(datos, indent=4),
        encoding="utf-8"
    )

    return datos, marcada


def main():
    identificador = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    carpeta = BASE / identificador
    carpeta.mkdir(parents=True, exist_ok=False)

    brazo = MyCobot("/dev/ttyUSB0", 1000000)
    camara = cv2.VideoCapture(0, cv2.CAP_V4L2)

    if not camara.isOpened():
        raise SystemExit("No se pudo abrir la camara")

    try:
        antes, imagen_antes = registrar(
            brazo, camara, carpeta, "antes"
        )

        objetivo = antes["posicion"].copy()
        objetivo[1] += AJUSTE_Y

        print("Posicion actual:", antes["posicion"])
        print("Objetivo:", objetivo)
        print("Cubos detectados:", len(antes["objetos"]))

        print("\nVerifica que la trayectoria este libre.")

        with open("/dev/tty") as terminal:
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
            print("No se pudo confirmar que el movimiento termino.")
            print("Revisa el brazo antes de continuar.")
            return

        time.sleep(1)

        despues, imagen_despues = registrar(
            brazo, camara, carpeta, "despues"
        )

        comparacion = cv2.hconcat([
            imagen_antes,
            imagen_despues
        ])

        cv2.imwrite(
            str(carpeta / "comparacion.png"),
            comparacion
        )

        print("\nRESULTADOS DEL ENCUADRE")
        print("Posicion final:", despues["posicion"])

        for color, evaluacion in despues["evaluacion"].items():
            estado = "DENTRO" if evaluacion["completo"] else "CERCA DEL BORDE"
            print(color, evaluacion["centro"], estado)

        print("\nHistorial:", carpeta.resolve())

    finally:
        camara.release()


if __name__ == "__main__":
    main()
