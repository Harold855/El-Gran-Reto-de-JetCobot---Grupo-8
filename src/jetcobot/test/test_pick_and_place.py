"""Secuencia de pick and place con percepción, movimiento y pinza falsos (sin hardware)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/

from arm_broker.ejecutor_simulado import config_ficticia
from jetcobot.pick_and_place import ejecutar_secuencia


class Banco:
    """Registra la secuencia de llamadas y permite inyectar fallos."""

    def __init__(self, presente=True, mover_ok=True, cierre="agarrado", abrir_ok=True, fallar_en=None):
        self.llamadas = []
        self.presente, self.mover_ok, self.cierre = presente, mover_ok, cierre
        self.abrir_ok, self.fallar_en = abrir_ok, fallar_en
        self.cancelar_tras = None

    def percibir(self, color):
        self.llamadas.append(("percibir", color))
        return {"presente": self.presente}

    def mover(self, pose):
        self.llamadas.append(("mover", pose[2]))
        n_movs = sum(1 for l in self.llamadas if l[0] == "mover")
        return self.mover_ok and n_movs != self.fallar_en

    def abrir(self):
        self.llamadas.append(("abrir",))
        return self.abrir_ok

    def cerrar(self):
        self.llamadas.append(("cerrar",))
        return self.cierre

    def correr(self, color="rojo", destino="verde", **extra):
        return ejecutar_secuencia(color, destino, config=config_ficticia(), percibir=self.percibir,
                                  mover_a_pose=self.mover, pinza=self, **extra)


class TestSecuencia(unittest.TestCase):

    def test_camino_feliz_y_orden_de_acciones(self):
        b = Banco()
        r = b.correr()
        self.assertTrue(r.success)
        self.assertEqual(r.codigo, "COMPLETADO")
        acciones = [l[0] for l in b.llamadas]
        self.assertEqual(acciones.index("percibir"), 1)               # tras ir a la pose de escaneo
        self.assertLess(acciones.index("cerrar"), len(acciones) - 1)
        self.assertEqual(acciones.count("abrir"), 2)                  # antes de agarrar y al depositar

    def test_objeto_ausente_no_mueve_mas_alla_del_escaneo(self):
        b = Banco(presente=False)
        r = b.correr()
        self.assertEqual(r.codigo, "OBJETO_AUSENTE")
        self.assertNotIn(("cerrar",), b.llamadas)
        self.assertEqual(sum(1 for l in b.llamadas if l[0] == "mover"), 1)

    def test_agarre_en_vacio_no_es_exito_ni_deposita(self):
        b = Banco(cierre="vacia")
        r = b.correr()
        self.assertFalse(r.success)
        self.assertEqual(r.codigo, "ERROR_AGARRE")
        self.assertEqual(b.llamadas.count(("abrir",)), 1)             # no llegó a depositar

    def test_fallo_de_movimiento_detiene_las_etapas_posteriores(self):
        b = Banco(fallar_en=3)
        r = b.correr()
        self.assertEqual(r.codigo, "ERROR_PLANIFICACION")
        self.assertNotIn(("cerrar",), b.llamadas)

    def test_pinza_que_no_abre(self):
        r = Banco(abrir_ok=False).correr()
        self.assertEqual(r.codigo, "ERROR_AGARRE")

    def test_validacion_antes_de_mover(self):
        for color, destino, codigo in (("morado", "verde", "COLOR_INVALIDO"),
                                       ("rojo", "derecha", "DESTINO_INVALIDO")):
            b = Banco()
            self.assertEqual(b.correr(color, destino).codigo, codigo)
            self.assertEqual(b.llamadas, [])

    def test_sin_poses_de_recogida_es_no_configurado_sin_nameerror(self):
        from jetcobot.posiciones import cargar_configuracion
        b = Banco()
        r = ejecutar_secuencia("rojo", "verde", config=cargar_configuracion(), percibir=b.percibir,
                               mover_a_pose=b.mover, pinza=b)
        self.assertEqual(r.codigo, "NO_CONFIGURADO")
        self.assertEqual(b.llamadas, [])

    def test_sin_pose_de_escaneo(self):
        b = Banco()
        self.assertTrue(b.correr(usar_pose_escaneo=False).success)
        self.assertEqual(b.llamadas[0], ("percibir", "rojo"))

    def test_excepcion_de_la_percepcion(self):
        def rota(color):
            raise RuntimeError("cámara")
        r = ejecutar_secuencia("rojo", "verde", config=config_ficticia(), percibir=rota,
                               mover_a_pose=lambda p: True, pinza=Banco())
        self.assertEqual(r.codigo, "ERROR_INTERNO")

    def test_cancelacion_con_cubo_sujeto(self):
        b = Banco()
        etapas = []
        r = b.correr(on_etapa=etapas.append, cancelado=lambda: "TRASLADO" in etapas)
        self.assertEqual(r.codigo, "CANCELADO")
        self.assertIn("cubo sujeto", r.motivo)
        self.assertEqual(b.llamadas.count(("abrir",)), 1)


if __name__ == "__main__":
    unittest.main()
