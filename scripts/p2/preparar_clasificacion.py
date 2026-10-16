import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import ZONAS_TRABAJO

ruta = ZONAS_TRABAJO
ruta.parent.mkdir(parents=True, exist_ok=True)

if not ruta.exists():
    configuracion = {
        "unidad": "mm",
        "altura_segura": None,
        "zonas_recogida": {
            color: None
            for color in ["rojo", "verde", "azul", "amarillo"]
        },
        "zonas_destino": {
            color: None
            for color in ["rojo", "verde", "azul", "amarillo"]
        }
    }

    ruta.write_text(
        json.dumps(configuracion, indent=4),
        encoding="utf-8"
    )

class ColaCubos:
    def __init__(self):
        self.pendientes = deque()

    def agregar(self, color):
        self.pendientes.append(color)

    def siguiente(self):
        if not self.pendientes:
            return None
        return self.pendientes.popleft()

    def mostrar(self):
        return list(self.pendientes)


cola = ColaCubos()

for color in ["rojo", "verde", "azul", "amarillo"]:
    cola.agregar(color)

print("=== SISTEMA DE CLASIFICACION ===")
print("Configuracion:", ruta)
print("Cola inicial:", cola.mostrar())

while cola.mostrar():
    color = cola.siguiente()
    print("Procesando:", color)
    print("Destino:", f"zona_{color}")
    print("Pendientes:", cola.mostrar())

print("Prueba FIFO terminada")
print("No se ha movido el robot")
