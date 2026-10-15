import json
from pathlib import Path
from collections import deque

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import ZONAS_TRABAJO

RUTA = ZONAS_TRABAJO
COLORES = ["rojo", "verde", "azul", "amarillo"]


class ColaCubos:
    def __init__(self):
        self.pendientes = deque()
        self.en_proceso = None
        self.completados = []
        self.contador = 0

    def agregar(self, color, recogida, destino):
        if color not in COLORES:
            raise ValueError("Color no valido")

        self.contador += 1

        cubo = {
            "id": self.contador,
            "color": color,
            "recogida": recogida,
            "destino": destino,
            "estado": "pendiente"
        }

        self.pendientes.append(cubo)
        return cubo

    def iniciar_siguiente(self):
        if self.en_proceso is not None:
            raise RuntimeError("Ya existe un cubo en proceso")

        if not self.pendientes:
            return None

        self.en_proceso = self.pendientes.popleft()
        self.en_proceso["estado"] = "en_proceso"
        return self.en_proceso

    def completar(self):
        if self.en_proceso is None:
            raise RuntimeError("No existe un cubo en proceso")

        self.en_proceso["estado"] = "completado"
        self.completados.append(self.en_proceso)
        self.en_proceso = None

    def reintentar(self):
        if self.en_proceso is None:
            raise RuntimeError("No existe un cubo en proceso")

        self.en_proceso["estado"] = "pendiente"
        self.pendientes.appendleft(self.en_proceso)
        self.en_proceso = None

    def mostrar(self):
        return [
            (cubo["id"], cubo["color"])
            for cubo in self.pendientes
        ]


def main():
    configuracion = json.loads(
        RUTA.read_text(encoding="utf-8")
    )

    cola = ColaCubos()

    for color in COLORES:
        zona = configuracion["zonas_destino"][color]

        cola.agregar(
            color=color,
            recogida=configuracion["zonas_recogida"][color],
            destino=zona["deposito"]
        )

    print("=== COLA FIFO ===")
    print("Pendientes:", cola.mostrar())

    while cola.pendientes:
        cubo = cola.iniciar_siguiente()

        print("\nProcesando:", cubo["id"], cubo["color"])
        print("Recogida:", cubo["recogida"])
        print("Destino:", cubo["destino"])

        if cubo["recogida"] is None:
            print("SIMULACION: recogida pendiente de calibracion")

        cola.completar()
        print("SIMULACION: completado")
        print("Pendientes:", cola.mostrar())

    print("\nTotal simulados:", len(cola.completados))
    print("Ningun movimiento fisico ejecutado")


if __name__ == "__main__":
    main()
