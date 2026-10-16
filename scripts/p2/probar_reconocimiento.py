import sys
from datetime import datetime
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import CAMARA
from jetcobot.vision_colores import detectar_cubos, dibujar_detecciones


def main():
    camara = cv2.VideoCapture(0, cv2.CAP_V4L2)

    if not camara.isOpened():
        print("No se pudo abrir /dev/video0")
        return

    camara.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camara.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    destino = CAMARA
    destino.mkdir(parents=True, exist_ok=True)

    print("Capturando imagen y reconociendo cubos...")

    try:
        imagen = None

        for _ in range(15):
            correcto, fotograma = camara.read()
            if correcto:
                imagen = fotograma

        if imagen is None:
            print("No se pudo obtener una imagen de la camara")
            return

        detecciones = detectar_cubos(imagen)
        resultado = dibujar_detecciones(imagen, detecciones)

        fecha = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        original = destino / f"captura_{fecha}_original.png"
        procesada = destino / f"captura_{fecha}_detectada.png"

        guardado_original = cv2.imwrite(str(original), imagen)
        guardado_procesada = cv2.imwrite(str(procesada), resultado)

        print(f"Imagen original: {original}")
        print(f"Guardado original: {guardado_original}")
        print(f"Imagen procesada: {procesada}")
        print(f"Guardado procesada: {guardado_procesada}")
        print(f"Objetos detectados: {len(detecciones)}")

        for objeto in detecciones:
            print(
                f"Color: {objeto['color']} | "
                f"Centro: ({objeto['centro_x']}, {objeto['centro_y']}) | "
                f"Area: {objeto['area']}"
            )

    finally:
        camara.release()


if __name__ == "__main__":
    main()
