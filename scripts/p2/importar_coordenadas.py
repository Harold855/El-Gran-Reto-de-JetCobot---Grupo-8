import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import ZONAS_TRABAJO

ruta = ZONAS_TRABAJO

datos = json.loads(ruta.read_text(encoding="utf-8"))

datos["posiciones_originales"] = {
    "escaneo": [140.4, -13.9, 265.0, -171.38, -2.81, -42.55],
    "agarre": [240.7, -1.3, 134.5, 167.77, 8.41, -48.7],
    "final": [51.6, -63.2, 409.7, -91.87, -49.01, -87.0]
}

destinos = {
    "rojo": [69.6, 225.5, 195.9, 131.8, -177.84, 2.62, 50.03],
    "verde": [0.7, 234.7, 201.9, 132.3, 177.21, 3.14, 46.72],
    "azul": [-52.9, 241.9, 197.0, 137.4, 174.03, 8.86, 45.55],
    "amarillo": [148.0, 223.7, 186.0, 147.3, 179.99, 1.97, 49.38]
}

for color, valores in destinos.items():
    x, y, z_alta, z_dejar, rx, ry, rz = valores

    datos["zonas_destino"][color] = {
        "aproximacion": [x, y, z_alta, rx, ry, rz],
        "deposito": [x, y, z_dejar, rx, ry, rz],
        "origen": "codigo_original",
        "validada": False
    }

datos["pinza"] = {
    "abierta": 100,
    "cerrada": 14,
    "velocidad": 50
}

ruta.write_text(
    json.dumps(datos, indent=4),
    encoding="utf-8"
)

print("=== COORDENADAS IMPORTADAS ===")

for color, zona in datos["zonas_destino"].items():
    print(color, zona["deposito"])

print("Archivo:", ruta)
print("No se ha movido el robot")
