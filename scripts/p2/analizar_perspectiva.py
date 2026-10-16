import cv2
import json
import numpy as np
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import CALIBRACION


carpeta_base = CALIBRACION
carpeta = sorted(carpeta_base.glob("validacion_modelo_*"))[-1]


def cargar(nombre):
    ruta = carpeta / f"{nombre}.json"
    return json.loads(ruta.read_text(encoding="utf-8"))


antes = cargar("antes")
despues = cargar("despues")

origen = {objeto["color"]: objeto for objeto in antes["objetos"]}
destino = {objeto["color"]: objeto for objeto in despues["objetos"]}

colores = sorted(origen.keys() & destino.keys())

if len(colores) != 4:
    raise SystemExit("Se necesitan exactamente cuatro cubos coincidentes")

puntos_antes = np.array([
    [origen[color]["centro_x"], origen[color]["centro_y"]]
    for color in colores
], dtype=np.float32)

puntos_despues = np.array([
    [destino[color]["centro_x"], destino[color]["centro_y"]]
    for color in colores
], dtype=np.float32)

matriz = cv2.getPerspectiveTransform(puntos_antes, puntos_despues)

imagen_antes = cv2.imread(str(carpeta / "antes_original.png"))
imagen_despues = cv2.imread(str(carpeta / "despues_original.png"))

if imagen_antes is None or imagen_despues is None:
    raise SystemExit("No se encontraron las fotografias originales")

alto, ancho = imagen_despues.shape[:2]

alineada = cv2.warpPerspective(
    imagen_antes,
    matriz,
    (ancho, alto)
)

comparacion = np.hstack([
    imagen_antes,
    imagen_despues,
    alineada
])

ruta = carpeta / "comparacion_perspectiva.png"
cv2.imwrite(str(ruta), comparacion)

print("COLORES UTILIZADOS:", colores)

print("\nMATRIZ DE HOMOGRAFIA")
print(np.round(matriz, 5))

print("\nPUNTOS ANTES Y DESPUES")
for i, color in enumerate(colores):
    print(
        color,
        puntos_antes[i].tolist(),
        "->",
        puntos_despues[i].tolist()
    )

print("\nImagen guardada:")
print(ruta.resolve())

print("\nOrden de las imagenes:")
print("IZQUIERDA: antes")
print("CENTRO: despues")
print("DERECHA: antes transformada")
