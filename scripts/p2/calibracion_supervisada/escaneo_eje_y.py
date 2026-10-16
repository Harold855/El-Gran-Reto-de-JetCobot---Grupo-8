# CALIBRACIÓN SUPERVISADA: abre el puerto serie del brazo directamente, sin pasar por el broker.
# Usar solo con el broker detenido y con alguien junto al robot; nunca durante P3 ni la demostración.
import cv2
import json
import time
from datetime import datetime
from pathlib import Path
from pymycobot.mycobot import MyCobot
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from jetcobot.rutas import CALIBRACION
from jetcobot.vision_colores import detectar_cubos, dibujar_detecciones


CARPETA = CALIBRACION
DESPLAZAMIENTO_Y = 10.0


def fotografiar(camara):
    imagen = None

    for _ in range(15):
        correcto, fotograma = camara.read()
        if correcto:
            imagen = fotograma

    if imagen is None:
        raise RuntimeError("No se pudo capturar la imagen")

    return imagen


def registrar(brazo, camara, carpeta, nombre):
    posicion = brazo.get_coords()
    angulos = brazo.get_angles()

    if not posicion or len(posicion) != 6:
        raise RuntimeError("No se pudo leer la posicion")

    if not angulos or len(angulos) != 6:
        raise RuntimeError("No se pudieron leer los angulos")

    imagen = fotografiar(camara)
    objetos = detectar_cubos(imagen)
    marcada = dibujar_detecciones(imagen, objetos)

    original = carpeta / f"{nombre}_original.png"
    detectada = carpeta / f"{nombre}_detectada.png"

    if not cv2.imwrite(str(original), imagen):
        raise RuntimeError("No se pudo guardar la fotografia original")

    if not cv2.imwrite(str(detectada), marcada):
        raise RuntimeError("No se pudo guardar la fotografia detectada")

    datos = {
        "nombre": nombre,
        "fecha": time.time(),
        "posicion": posicion,
        "angulos": angulos,
        "objetos": objetos
    }

    (carpeta / f"{nombre}.json").write_text(
        json.dumps(datos, indent=4),
        encoding="utf-8"
    )

    print(f"\n{nombre.upper()}")
    print("Posicion:", posicion)
    print("Cubos:", len(objetos))

    for objeto in objetos:
        print(
            objeto["color"],
            (objeto["centro_x"], objeto["centro_y"])
        )

    return datos, marcada


def main():
    CARPETA.mkdir(parents=True, exist_ok=True)

    identificador = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    carpeta = CARPETA / f"escaneo_y_{identificador}"
    carpeta.mkdir()

    brazo = MyCobot("/dev/ttyUSB0", 1000000)
    camara = cv2.VideoCapture(0, cv2.CAP_V4L2)

    if not camara.isOpened():
        raise SystemExit("No se pudo abrir la camara")

    try:
        antes, imagen_antes = registrar(
            brazo, camara, carpeta, "antes"
        )

        objetivo = antes["posicion"].copy()
        objetivo[1] += DESPLAZAMIENTO_Y

        print("\nObjetivo:", objetivo)
        print("Verifica que toda la trayectoria este libre.")

        with open("/dev/tty", "r") as terminal:
            print("Escribe MOVER para continuar: ", end="", flush=True)
            confirmacion = terminal.readline().strip()

        if confirmacion != "MOVER":
            print("Movimiento cancelado. Foto inicial conservada.")
            return

        brazo.send_coords(objetivo, 10, 1)

        inicio = time.monotonic()
        movimiento_iniciado = False
        movimiento_terminado = False

        while time.monotonic() - inicio < 15:
            time.sleep(0.2)
            estado = brazo.is_moving()

            if estado == 1:
                movimiento_iniciado = True

            if estado == 0 and movimiento_iniciado:
                movimiento_terminado = True
                break

        if not movimiento_terminado:
            print("Movimiento no confirmado como finalizado.")
            print("No se capturara una foto durante un posible movimiento.")
            return

        time.sleep(1)

        despues, imagen_despues = registrar(
            brazo, camara, carpeta, "despues"
        )

        if imagen_antes.shape != imagen_despues.shape:
            raise RuntimeError("Las imagenes tienen resoluciones diferentes")

        comparacion = cv2.hconcat([
            imagen_antes,
            imagen_despues
        ])

        ruta_comparacion = carpeta / "comparacion.png"

        if not cv2.imwrite(str(ruta_comparacion), comparacion):
            raise RuntimeError("No se pudo guardar la comparacion")

        desplazamiento = [
            round(b - a, 2)
            for a, b in zip(
                antes["posicion"],
                despues["posicion"]
            )
        ]

        anteriores = {
            objeto["color"]: objeto
            for objeto in antes["objetos"]
        }

        actuales = {
            objeto["color"]: objeto
            for objeto in despues["objetos"]
        }

        print("\nRESULTADOS")
        print("Cambio real XYZ y orientacion:", desplazamiento)

        for color in anteriores.keys() & actuales.keys():
            a = anteriores[color]
            b = actuales[color]

            dx = b["centro_x"] - a["centro_x"]
            dy = b["centro_y"] - a["centro_y"]

            print(f"{color}: ({dx:+d}, {dy:+d}) pixeles")

        print("\nHistorial guardado:", carpeta.resolve())
        print("Comparacion:", ruta_comparacion.resolve())

    finally:
        camara.release()


if __name__ == "__main__":
    main()
