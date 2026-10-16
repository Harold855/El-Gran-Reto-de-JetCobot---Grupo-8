"""Contrato de /pick_place: validación pura y admisión en el broker (sin ROS ni hardware)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ros_falso as ros
from arm_broker.tarea_pickplace import validar_tarea

HAY_FALSO = ros.instalar()


class TestValidarTarea(unittest.TestCase):

    def test_orden_valida(self):
        self.assertEqual(validar_tarea("p3-001", "rojo", "verde", 1), (None, ""))

    def test_otra_combinacion_valida(self):
        self.assertEqual(validar_tarea("p3-002", "azul", "amarillo", 2)[0], None)

    def test_mismo_color_es_valido(self):
        self.assertIsNone(validar_tarea("x", "rojo", "rojo", 1)[0])

    def test_destino_derecha_se_rechaza(self):
        self.assertEqual(validar_tarea("p3-003", "rojo", "derecha", 1)[0], "DESTINO_INVALIDO")

    def test_color_desconocido(self):
        self.assertEqual(validar_tarea("p3-004", "morado", "azul", 1)[0], "COLOR_INVALIDO")

    def test_prioridad_fuera_de_1_a_3(self):
        for prioridad in (0, 4, 255):
            self.assertEqual(validar_tarea("p3-005", "rojo", "verde", prioridad)[0], "PRIORIDAD_INVALIDA")

    def test_id_invalido(self):
        for id_malo in ("", "a b", "x" * 65, "con/barra"):
            self.assertEqual(validar_tarea(id_malo, "rojo", "verde", 1)[0], "ID_INVALIDO")

    def test_no_normaliza_mayusculas(self):
        self.assertEqual(validar_tarea("p3-006", "Rojo", "verde", 1)[0], "COLOR_INVALIDO")


@unittest.skipUnless(HAY_FALSO, "hay ROS 2 real: estas pruebas usan el ROS falso")
class TestAdmisionBroker(unittest.TestCase):

    def setUp(self):
        self.broker = ros.crear_broker(archivo_rechazos="", archivo_registro_tareas="", cola_max=3)

    def test_admite_y_encola(self):
        respuesta, handle = ros.enviar_pick(self.broker, "p3-001", "rojo", "verde", 1)
        self.assertEqual(respuesta, "ACCEPT")
        self.assertEqual(len(self.broker.pendientes), 1)
        self.assertEqual(self.broker.pendientes[0].id_solicitud, "p3-001")

    def test_rechaza_destino_prohibido_sin_encolar(self):
        respuesta, handle = ros.enviar_pick(self.broker, "p3-002", "rojo", "derecha", 1)
        self.assertEqual(respuesta, "REJECT")
        self.assertEqual(len(self.broker.pendientes), 0)
        self.assertEqual(self.broker.n_rechazados, 1)

    def test_rechaza_id_duplicado(self):
        ros.enviar_pick(self.broker, "p3-003", "rojo", "verde", 1)
        respuesta, _ = ros.enviar_pick(self.broker, "p3-003", "azul", "verde", 1)
        self.assertEqual(respuesta, "REJECT")
        self.assertEqual(len(self.broker.pendientes), 1)

    def test_cola_llena(self):
        for i in range(3):
            self.assertEqual(ros.enviar_pick(self.broker, f"p3-10{i}", "rojo", "verde", 1)[0], "ACCEPT")
        self.assertEqual(ros.enviar_pick(self.broker, "p3-110", "rojo", "verde", 1)[0], "REJECT")

    def test_modo_real_exige_permiso(self):
        with self.assertRaises(RuntimeError):
            ros.crear_broker(modo_ejecucion="real", archivo_rechazos="", archivo_registro_tareas="")

    def test_modo_desconocido(self):
        with self.assertRaises(RuntimeError):
            ros.crear_broker(modo_ejecucion="otro", archivo_rechazos="", archivo_registro_tareas="")

    def test_modo_real_sin_estado_conocido_rechaza(self):
        broker = ros.crear_broker(modo_ejecucion="real", permitir_movimiento_real=True,
                                  archivo_rechazos="", archivo_registro_tareas="")
        self.assertEqual(broker.origen_q, "desconocido")
        self.assertEqual(ros.enviar_pick(broker, "p3-200", "rojo", "verde", 1)[0], "REJECT")
        self.assertEqual(ros.enviar_move(broker, [0.1, 0, 0, 0, 0, 0], "c", 1)[0], "REJECT")


if __name__ == "__main__":
    unittest.main()
