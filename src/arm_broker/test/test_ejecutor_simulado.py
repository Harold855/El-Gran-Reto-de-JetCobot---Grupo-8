"""Ejecutor simulado de /pick_place y registro de eventos (sin ROS ni hardware)."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/

from arm_broker.ejecutor_real import EjecutorReal
from arm_broker.ejecutor_simulado import EjecutorSimulado
from arm_broker.registro_tarea import RegistroTareas
from arm_broker.tarea_pickplace import ContextoEjecucion, Tarea


def ejecutar(ejecutor, tarea, cancelar_en=None):
    registro = RegistroTareas()
    etapas = []

    def al_cambiar(etapa):
        etapas.append(etapa)

    def cancelado():
        return cancelar_en is not None and cancelar_en in etapas

    ctx = ContextoEjecucion(cancelado, al_cambiar, lambda n, d: registro.evento(tarea.id_solicitud, n, d))
    resultado = ejecutor.ejecutar(tarea, ctx)
    return resultado, etapas, registro


def tarea(color="rojo", destino="verde"):
    return Tarea("p3-001", color, destino, 1)


class TestEjecutorSimulado(unittest.TestCase):

    def setUp(self):
        self.sim = EjecutorSimulado(duracion_etapa_s=0.0)

    def test_rojo_a_verde_completa_y_se_etiqueta_simulado(self):
        res, etapas, _ = ejecutar(self.sim, tarea())
        self.assertTrue(res.success)
        self.assertEqual(res.codigo, "COMPLETADO")
        self.assertIn("COMPLETADO (SIMULADO)", res.mensaje)
        self.assertEqual(etapas, ["PERCEPCION", "APROXIMACION", "AGARRE", "TRASLADO", "DEPOSITO", "RETIRADA"])

    def test_objeto_ausente_no_ejecuta_agarre(self):
        res, etapas, _ = ejecutar(EjecutorSimulado(0.0, colores_ausentes=["verde"]), tarea("verde", "rojo"))
        self.assertEqual(res.codigo, "OBJETO_AUSENTE")
        self.assertNotIn("AGARRE", etapas)

    def test_error_de_planificacion(self):
        res, etapas, _ = ejecutar(EjecutorSimulado(0.0, fallo_simulado="ERROR_PLANIFICACION"), tarea())
        self.assertEqual(res.codigo, "ERROR_PLANIFICACION")
        self.assertNotIn("AGARRE", etapas)

    def test_agarre_en_vacio_no_es_exito(self):
        res, etapas, _ = ejecutar(EjecutorSimulado(0.0, fallo_simulado="ERROR_AGARRE"), tarea())
        self.assertFalse(res.success)
        self.assertEqual(res.codigo, "ERROR_AGARRE")
        self.assertNotIn("DEPOSITO", etapas)

    def test_cancelacion_antes_del_agarre(self):
        res, etapas, _ = ejecutar(self.sim, tarea(), cancelar_en="APROXIMACION")
        self.assertEqual(res.codigo, "CANCELADO")
        self.assertIn("antes de tomar", res.mensaje)

    def test_cancelacion_con_cubo_sujeto_no_lo_suelta(self):
        res, etapas, _ = ejecutar(self.sim, tarea(), cancelar_en="TRASLADO")
        self.assertEqual(res.codigo, "CANCELADO")
        self.assertIn("cubo sujeto", res.mensaje)
        self.assertNotIn("DEPOSITO", etapas)

    def test_fallo_simulado_desconocido(self):
        with self.assertRaises(ValueError):
            EjecutorSimulado(fallo_simulado="OTRO")

    def test_eventos_de_una_tarea_en_orden(self):
        _, _, registro = ejecutar(self.sim, tarea())
        nombres = registro.nombres("p3-001")
        for evento in ("inicio_percepcion", "fin_percepcion", "inicio_planificacion", "fin_planificacion",
                       "primer_comando_movimiento", "fin_retirada"):
            self.assertIn(evento, nombres)
        self.assertEqual(nombres.count("primer_comando_movimiento"), 1)
        self.assertLess(nombres.index("inicio_percepcion"), nombres.index("primer_comando_movimiento"))


class TestEjecutorReal(unittest.TestCase):

    def test_sin_respaldos_falla_cerrado(self):
        res, etapas, _ = ejecutar(EjecutorReal(), tarea())
        self.assertFalse(res.success)
        self.assertEqual(res.codigo, "NO_CONFIGURADO")
        self.assertEqual(etapas, [])

    def test_con_respaldos_pero_recogida_null_es_no_configurado(self):
        movimientos = []
        real = EjecutorReal(percibir=lambda c: {"presente": True},
                            mover_a_pose=lambda p: movimientos.append(p) or True,
                            pinza=object())
        res, _, _ = ejecutar(real, tarea("amarillo", "azul"))
        self.assertEqual(res.codigo, "NO_CONFIGURADO")
        self.assertEqual(movimientos, [])   # no se movió nada


class TestRegistro(unittest.TestCase):

    def test_csv_con_id_y_marca_de_simulado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = str(Path(carpeta) / "sub" / "registro.csv")
            registro = RegistroTareas(ruta, simulado=True)
            registro.evento("p3-001", "solicitud_recibida", "rojo->verde")
            registro.cerrar("p3-001", "COMPLETADO", True, "ok")
            with open(ruta, newline="", encoding="utf-8") as f:
                filas = list(csv.DictReader(f))
        self.assertEqual([f["evento"] for f in filas], ["solicitud_recibida", "fin_tarea"])
        self.assertTrue(all(f["id_solicitud"] == "p3-001" and f["simulado"] == "True" for f in filas))

    def test_duracion_entre_eventos(self):
        reloj = iter([10.0, 12.5])
        registro = RegistroTareas(reloj=lambda: next(reloj))
        registro.evento("a", "encolada")
        registro.evento("a", "inicio_worker")
        self.assertAlmostEqual(registro.duracion_s("a", "encolada", "inicio_worker"), 2.5)
        self.assertIsNone(registro.duracion_s("a", "encolada", "no_existe"))


if __name__ == "__main__":
    unittest.main()
