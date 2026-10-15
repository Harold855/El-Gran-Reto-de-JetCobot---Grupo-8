"""Configuración única de zonas de trabajo (sin hardware)."""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/

from jetcobot.posiciones import (COLORES, ColorInvalido, ConfigTrabajo, ConfiguracionError,
                                 DestinoInvalido, NoConfigurado, cargar_configuracion)
from jetcobot.rutas import ZONAS_TRABAJO


class TestConfigReal(unittest.TestCase):

    def setUp(self):
        self.config = cargar_configuracion()

    def test_el_json_del_repositorio_cumple_el_esquema(self):
        self.assertEqual(set(self.config.datos["zonas_destino"]), set(COLORES))

    def test_destinos_por_color_y_aproximacion_sobre_deposito(self):
        for color in COLORES:
            alta, dejar = self.config.poses_destino(color)
            self.assertGreater(alta[2], dejar[2])
            self.assertEqual(alta[:2], dejar[:2])

    def test_destinos_siguen_sin_validar(self):
        self.assertTrue(all(not self.config.destino_validado(c) for c in COLORES))

    def test_orden_de_los_destinos_en_la_fila_izquierda(self):
        x = {c: self.config.poses_destino(c)[0][0] for c in COLORES}
        self.assertLess(x["azul"], x["verde"])
        self.assertLess(x["verde"], x["rojo"])
        self.assertLess(x["rojo"], x["amarillo"])

    def test_recogida_en_null_es_no_configurado(self):
        for color in COLORES:
            with self.assertRaises(NoConfigurado):
                self.config.poses_objeto(color)

    def test_destino_del_tablero_derecho_o_inexistente(self):
        for malo in ("derecha", "izquierda", "morado", "", None):
            with self.assertRaises(DestinoInvalido):
                self.config.poses_destino(malo)

    def test_color_invalido(self):
        with self.assertRaises(ColorInvalido):
            self.config.poses_objeto("morado")

    def test_la_disposicion_historica_es_solo_descriptiva(self):
        historica = self.config.datos["disposicion_cubos_historica"]
        self.assertEqual(set(historica["centros_px"]), set(COLORES))
        self.assertIn("no son poses XYZ", historica["nota"])


class TestEsquema(unittest.TestCase):

    def datos(self):
        with open(ZONAS_TRABAJO, encoding="utf-8") as f:
            return json.load(f)

    def test_rechaza_zona_extra(self):
        d = self.datos()
        d["zonas_destino"]["derecha"] = d["zonas_destino"]["rojo"]
        with self.assertRaises(ConfiguracionError):
            ConfigTrabajo(d)

    def test_rechaza_pose_con_cinco_valores(self):
        d = self.datos()
        d["zonas_destino"]["rojo"]["deposito"] = d["zonas_destino"]["rojo"]["deposito"][:5]
        with self.assertRaises(ConfiguracionError):
            ConfigTrabajo(d)

    def test_rechaza_valores_no_finitos(self):
        d = self.datos()
        d["zonas_destino"]["rojo"]["aproximacion"][0] = float("nan")
        with self.assertRaises(ConfiguracionError):
            ConfigTrabajo(d)

    def test_rechaza_unidad_incorrecta(self):
        d = self.datos()
        d["unidad"] = "cm"
        with self.assertRaises(ConfiguracionError):
            ConfigTrabajo(d)

    def test_acepta_recogida_completa(self):
        d = copy.deepcopy(self.datos())
        d["zonas_recogida"]["rojo"] = {"alta": [1, 2, 9, 0, 0, 0], "agarre": [1, 2, 5, 0, 0, 0],
                                       "validada": False}
        self.assertEqual(ConfigTrabajo(d).poses_objeto("rojo")[1][2], 5)

    def test_json_inexistente(self):
        with self.assertRaises(ConfiguracionError):
            ConfigTrabajo.cargar("/no/existe.json")


if __name__ == "__main__":
    unittest.main()
