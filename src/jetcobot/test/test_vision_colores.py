"""Visión por color sobre imágenes históricas del repositorio (sin cámara)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/

try:
    import cv2
    import numpy as np
    from jetcobot.vision_colores import buscar_color_en_frame, detectar_cubos
except ImportError:   # sin OpenCV las pruebas de imagen se saltan
    cv2 = None

from jetcobot.rutas import CAMARA, CALIBRACION

CENTROS = {"rojo": (145, 136), "azul": (379, 136), "verde": (135, 347), "amarillo": (376, 348)}


@unittest.skipIf(cv2 is None, "falta OpenCV")
class TestVisionColores(unittest.TestCase):

    def setUp(self):
        self.imagen = cv2.imread(str(CALIBRACION / "escaneo_inicial.png"))
        self.assertIsNotNone(self.imagen)

    def test_aparecen_los_cuatro_colores_historicos(self):
        encontrados = {d["color"]: (d["centro_x"], d["centro_y"]) for d in detectar_cubos(self.imagen)}
        self.assertEqual(set(encontrados), set(CENTROS))
        for color, (x, y) in CENTROS.items():
            self.assertLessEqual(abs(encontrados[color][0] - x), 3)
            self.assertLessEqual(abs(encontrados[color][1] - y), 3)

    def test_buscar_color_presente(self):
        r = buscar_color_en_frame(self.imagen, "verde")
        self.assertTrue(r["presente"])
        self.assertEqual(r["estado"], "DETECTADO")
        self.assertIsNotNone(r["rectangulo"])
        self.assertGreater(r["timestamp"], 0)

    def test_cubo_eliminado_da_ausente(self):
        sin_verde = self.imagen.copy()
        x, y, w, h = buscar_color_en_frame(self.imagen, "verde")["rectangulo"]
        sin_verde[max(0, y - 10):y + h + 10, max(0, x - 10):x + w + 10] = 255
        r = buscar_color_en_frame(sin_verde, "verde")
        self.assertFalse(r["presente"])
        self.assertEqual(r["estado"], "AUSENTE")
        self.assertTrue(buscar_color_en_frame(sin_verde, "rojo")["presente"])

    def test_color_invalido_e_imagen_vacia(self):
        self.assertEqual(buscar_color_en_frame(self.imagen, "morado")["estado"], "COLOR_INVALIDO")
        self.assertEqual(buscar_color_en_frame(None, "rojo")["estado"], "SIN_IMAGEN")
        self.assertEqual(buscar_color_en_frame(np.zeros((0, 0, 3), np.uint8), "rojo")["estado"], "SIN_IMAGEN")

    def test_captura_de_camara_con_cuatro_colores(self):
        imagen = cv2.imread(str(CAMARA / "prueba_cuatro_colores.png"))
        self.assertEqual(len(detectar_cubos(imagen)), 4)


if __name__ == "__main__":
    unittest.main()
