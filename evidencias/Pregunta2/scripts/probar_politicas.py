# ==============================================================================
# UNIVERSIDAD ESAN
# ROBOTICA 08079
# EXAMEN PARCIAL - GRAN RETO JETCOBOT
# Grupo 7
#
# Integrantes:
#   - Sebastian Pedro Aguirre Acosta
#   - Anahi Cortez Chinchay
#   - Ramirez Quevedo Karen Noelia
#   - Vara Vargas Valentino Uziel
#
# Archivo: probar_politicas.py
# Descripcion: Prueba aislada de FIFO y prioridad con envejecimiento.
# No utiliza ROS 2 ni publica comandos de movimiento.
# ==============================================================================

import sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
PAQUETE = RAIZ / "src" / "arm_broker"

sys.path.insert(0, str(PAQUETE))

from arm_broker.politicas import FIFO, SegundaPolitica


def crear_pedido(cliente, prioridad, llegada, espera):
    return SimpleNamespace(
        client_id=cliente,
        priority=prioridad,
        t_llegada=llegada,
        espera_s=espera
    )


def probar(nombre, politica, pedidos):
    pendientes = list(pedidos)

    print()
    print("POLITICA:", nombre)
    print("-" * 45)

    while pendientes:
        indice = politica.siguiente(pendientes)
        pedido = pendientes.pop(indice)

        print(
            f"Cliente: {pedido.client_id} | "
            f"Prioridad: {pedido.priority} | "
            f"Espera: {pedido.espera_s:.1f}s"
        )


def main():
    pedidos = [
        crear_pedido("cliente_1", 1, 1.0, 2.0),
        crear_pedido("cliente_2", 3, 2.0, 1.0),
        crear_pedido("cliente_3", 2, 3.0, 1.0),
        crear_pedido("cliente_4", 1, 4.0, 1.0),
    ]

    probar("FIFO", FIFO(), pedidos)
    probar(
        "PRIORIDAD CON ENVEJECIMIENTO",
        SegundaPolitica(tau_s=8.0),
        pedidos
    )


if __name__ == "__main__":
    main()
