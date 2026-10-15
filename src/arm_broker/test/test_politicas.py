import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/

from arm_broker.politicas import FIFO, PrioridadConEnvejecimiento, RoundRobin


class PedidoPrueba:
    """Lo mínimo que usan las políticas de un Pedido (espera_s() es un método, como en Pedido)."""

    def __init__(self, nombre, prioridad, llegada, espera, cliente="c"):
        self.nombre = nombre
        self.priority = prioridad
        self.t_llegada = llegada
        self.client_id = cliente
        self._espera = espera

    def espera_s(self):
        return self._espera


class TestPoliticas(unittest.TestCase):

    def setUp(self):
        self.pedidos = [
            PedidoPrueba("A", 1, 1, 5),
            PedidoPrueba("B", 5, 2, 3),
            PedidoPrueba("C", 2, 3, 2),
        ]

    def test_fifo(self):
        indice = FIFO().siguiente(self.pedidos)
        self.assertEqual(self.pedidos[indice].nombre, "A")

    def test_prioridad(self):
        indice = PrioridadConEnvejecimiento(8).siguiente(self.pedidos)
        self.assertEqual(self.pedidos[indice].nombre, "B")

    def test_fifo_cola_vacia(self):
        self.assertIsNone(FIFO().siguiente([]))

    def test_prioridad_cola_vacia(self):
        self.assertIsNone(PrioridadConEnvejecimiento(8).siguiente([]))

    def test_envejecimiento(self):
        pedidos = [
            PedidoPrueba("Antiguo", 1, 1, 80),
            PedidoPrueba("Reciente", 5, 2, 1),
        ]
        indice = PrioridadConEnvejecimiento(8).siguiente(pedidos)
        self.assertEqual(pedidos[indice].nombre, "Antiguo")

    def test_desempate_por_llegada(self):
        pedidos = [
            PedidoPrueba("Primero", 3, 1, 8),
            PedidoPrueba("Segundo", 3, 2, 8),
        ]
        indice = PrioridadConEnvejecimiento(8).siguiente(pedidos)
        self.assertEqual(pedidos[indice].nombre, "Primero")

    def test_tau_invalido(self):
        with self.assertRaises(ValueError):
            PrioridadConEnvejecimiento(0)

    def test_round_robin_rota_entre_clientes(self):
        pendientes = [
            PedidoPrueba("a1", 1, 1, 0, "a"),
            PedidoPrueba("a2", 1, 2, 0, "a"),
            PedidoPrueba("b1", 1, 3, 0, "b"),
        ]
        politica = RoundRobin()
        orden = []
        while pendientes:
            pedido = pendientes.pop(politica.siguiente(pendientes))
            politica.atendido(pedido)
            orden.append(pedido.nombre)
        self.assertEqual(orden, ["a1", "b1", "a2"])


if __name__ == "__main__":
    unittest.main()
