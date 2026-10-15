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


OBJETIVO = [42, 0, 0, -85, -7, -3]
BASE = CALIBRACION / "recuperaciones"


def main():
    identificador = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    carpeta = BASE / identificador
    carpeta.mkdir(parents=True, exist_ok=False)

    brazo = MyCobot("/dev/ttyUSB0", 1000000)

    inicial = {
        "angulos": brazo.get_angles(),
        "posicion": brazo.get_coords()
    }

    (carpeta / "antes.json").write_text(
        json.dumps(inicial, indent=4),
        encoding="utf-8"
    )

    print("Articulaciones actuales:", inicial["angulos"])
    print("Articulaciones objetivo:", OBJETIVO)
    print("Verifica que la trayectoria este libre.")

    with open("/dev/tty") as terminal:
        print("Escribe MOVER para continuar: ", end="", flush=True)
        confirmacion = terminal.readline().strip()

    if confirmacion != "MOVER":
        print("Cancelado.")
        return

    brazo.send_angles(OBJETIVO, 10)

    inicio = time.monotonic()
    iniciado = False
    terminado = False

    while time.monotonic() - inicio < 20:
        time.sleep(0.2)
        estado = brazo.is_moving()

        if estado == 1:
            iniciado = True

        if iniciado and estado == 0:
            terminado = True
            break

    if not terminado:
        print("No se confirmo la finalizacion del movimiento.")
        print("Revisa fisicamente el brazo antes de continuar.")
        return

    time.sleep(1)

    final = {
        "angulos": brazo.get_angles(),
        "posicion": brazo.get_coords()
    }

    (carpeta / "despues.json").write_text(
        json.dumps(final, indent=4),
        encoding="utf-8"
    )

    camara = cv2.VideoCapture(0, cv2.CAP_V4L2)

    if not camara.isOpened():
        raise RuntimeError("No se pudo abrir la camara")

    try:
        imagen = None

        for _ in range(15):
            correcto, fotograma = camara.read()
            if correcto:
                imagen = fotograma

        if imagen is None:
            raise RuntimeError("No se pudo capturar una imagen")

        objetos = detectar_cubos(imagen)
        marcada = dibujar_detecciones(imagen, objetos)

        cv2.imwrite(str(carpeta / "escaneo_original.png"), imagen)
        cv2.imwrite(str(carpeta / "escaneo_detectado.png"), marcada)

        (carpeta / "detecciones.json").write_text(
            json.dumps(objetos, indent=4),
            encoding="utf-8"
        )

        print("\nRESULTADOS")
        print("Articulaciones finales:", final["angulos"])
        print("Coordenadas finales:", final["posicion"])
        print("Cubos detectados:", len(objetos))

        for objeto in objetos:
            print(
                objeto["color"],
                (objeto["centro_x"], objeto["centro_y"]),
                objeto["rectangulo"]
            )

        print("Historial:", carpeta.resolve())

    finally:
        camara.release()


if __name__ == "__main__":
    main()
