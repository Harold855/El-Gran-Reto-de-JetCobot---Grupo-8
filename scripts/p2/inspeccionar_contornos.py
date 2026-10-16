import cv2
import json
from datetime import datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import CALIBRACION


base = CALIBRACION
carpeta = sorted(base.glob("validacion_modelo_*"))[-1]

datos = json.loads(
    (carpeta / "despues.json").read_text(encoding="utf-8")
)

imagen = cv2.imread(str(carpeta / "despues_original.png"))

if imagen is None:
    raise SystemExit("No se pudo abrir la fotografia")

colores = {
    "rojo": (0, 0, 255),
    "verde": (0, 255, 0),
    "azul": (255, 0, 0),
    "amarillo": (0, 255, 255)
}

for objeto in datos["objetos"]:
    color = objeto["color"]
    x, y, ancho, alto = objeto["rectangulo"]

    cv2.rectangle(
        imagen,
        (x, y),
        (x + ancho, y + alto),
        colores[color],
        2
    )

    cv2.circle(
        imagen,
        (objeto["centro_x"], objeto["centro_y"]),
        5,
        (255, 255, 255),
        -1
    )

    cv2.putText(
        imagen,
        f"{color} {ancho}x{alto}",
        (x, max(15, y - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        colores[color],
        2
    )

salida = CALIBRACION / (
    "inspeccion_contornos_" +
    datetime.now().strftime("%Y%m%d_%H%M%S") +
    ".png"
)

cv2.imwrite(str(salida), imagen)

print("Imagen guardada:", salida.resolve())
