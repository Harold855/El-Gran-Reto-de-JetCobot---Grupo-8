"""CSV de P3 con las columnas de P2 (ROS 2 simulado con módulos vacíos; sin Google ni hardware)."""

import csv
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/transcriptor_voz


def _modulo(nombre, **atributos):
    m = types.ModuleType(nombre)
    m.__dict__.update(atributos)
    sys.modules.setdefault(nombre, m)


try:
    import rclpy  # noqa: F401
    HAY_ROS = True
except ImportError:
    HAY_ROS = False
    _modulo("rclpy")
    _modulo("rclpy.node", Node=type("Node", (), {}))
    _modulo("rclpy.utilities", remove_ros_args=lambda args=None: args)
    _modulo("interprete_ordenes_interfaces")
    _modulo("interprete_ordenes_interfaces.srv", InterpretarOrden=object)

_modulo("transcripcion_google", transcribir_audio=lambda *a, **k: "", TranscripcionError=Exception)  # sin google-genai

import transcriptor_voz as tv
from envio_pickplace import COLUMNAS_P2, ResultadoP2


def decision(permitido=True):
    return types.SimpleNamespace(accion="trasladar", objeto="cubo", color="rojo", destino="verde",
                                 prioridad=1, permitido=permitido, degradado=False, motivo="")


class TestRegistroP2(unittest.TestCase):

    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        base = Path(self.carpeta.name)
        self.guardado = (tv.EVIDENCIAS, tv.AUDIOS, tv.REGISTRO)
        tv.EVIDENCIAS, tv.AUDIOS, tv.REGISTRO = base, base / "audios", base / "transcripciones.csv"

    def tearDown(self):
        tv.EVIDENCIAS, tv.AUDIOS, tv.REGISTRO = self.guardado
        self.carpeta.cleanup()

    def filas(self):
        with tv.REGISTRO.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_las_columnas_de_p2_van_al_final(self):
        self.assertEqual(tv.COLUMNAS[-len(COLUMNAS_P2):], COLUMNAS_P2)

    def test_fila_completa_con_resultado_simulado(self):
        p2 = ResultadoP2(enviado=True, aceptado=True, estado="EXITO", codigo="COMPLETADO", simulado=True,
                         mensaje="COMPLETADO (SIMULADO)", t_aceptacion_ms=12.0, t_resultado_ms=1800.0,
                         espera_cola_s=0.1, ejecucion_s=1.7, etapas=["PERCEPCION", "DEPOSITO"])
        tv.registrar_evidencia("", "recoge el cubo rojo", "teclado",
                               {"teclado": 500.0, "servicio": 40.0}, decision(), "a1b2c3d4", p2)
        fila = self.filas()[0]
        self.assertEqual(fila["id_solicitud"], "a1b2c3d4")
        self.assertEqual(fila["codigo_p2"], "COMPLETADO")
        self.assertEqual(fila["simulado_p2"], "True")
        self.assertEqual(fila["etapas_p2"], "PERCEPCION>DEPOSITO")

    def test_sin_decision_p2_queda_no_enviado(self):
        tv.registrar_evidencia("", "x", "teclado", {"teclado": 1.0}, None, "a1b2c3d4")
        fila = self.filas()[0]
        self.assertEqual(fila["estado_p2"], "NO_ENVIADO")
        self.assertEqual(fila["tiempo_total_p2_ms"], "")

    def test_csv_antiguo_se_amplia_sin_perder_filas(self):
        antiguo = tv.COLUMNAS[:19]
        with tv.REGISTRO.open("w", newline="", encoding="utf-8") as f:
            escritor = csv.writer(f)
            escritor.writerow(antiguo)
            escritor.writerow(["2026-10-10T21:24:10", "a.aac", "", "texto", "google"] + [""] * 14)
        tv.registrar_evidencia("", "otra", "teclado", {"teclado": 1.0}, decision(False), "b2")
        filas = self.filas()
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0]["transcripcion"], "texto")
        self.assertTrue(all(len(f) == len(tv.COLUMNAS) for f in filas))


if __name__ == "__main__":
    unittest.main()
