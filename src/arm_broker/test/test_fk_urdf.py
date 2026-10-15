"""Pruebas de cinemática directa del JetCobot."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/

from arm_broker.cinematica_urdf import URDF_JETCOBOT as URDF, calcular


class TestFKURDF(unittest.TestCase):

    def test_posicion_cero(self):
        x, y, z = calcular([0] * 6, URDF)

        self.assertAlmostEqual(x, 95.82, delta=0.02)
        self.assertAlmostEqual(y, -63.18, delta=0.02)
        self.assertAlmostEqual(z, 407.54, delta=0.02)

    def test_cambio_de_posicion(self):
        cero = calcular([0] * 6, URDF)
        girada = calcular([0.6, -0.4, 0.4, 0, 0.3, 0], URDF)

        self.assertNotEqual(cero, girada)

    def test_rechaza_cantidad_incorrecta(self):
        with self.assertRaises(ValueError):
            calcular([0, 0, 0], URDF)

    def test_rechaza_valores_invalidos(self):
        with self.assertRaises(ValueError):
            calcular([0, 0, math.nan, 0, 0, 0], URDF)

    def test_resultados_finitos(self):
        xyz = calcular([0, -0.5, 0.5, 0, 0.5, 0], URDF)

        self.assertTrue(all(math.isfinite(v) for v in xyz))


if __name__ == "__main__":
    unittest.main()


class TestMatrizURDF(unittest.TestCase):

    def test_matriz_homogenea(self):
        import numpy as np
        from arm_broker.cinematica_urdf import calcular_matriz

        poses = [
            [0, 0, 0, 0, 0, 0],
            [0, -0.5, 0.5, 0, 0.5, 0],
            [0.6, -0.4, 0.4, 0, 0.3, 0],
        ]

        for q in poses:
            with self.subTest(q=q):
                T = np.array(calcular_matriz(q, URDF))

                self.assertEqual(T.shape, (4, 4))

                R = T[:3, :3]

                np.testing.assert_allclose(
                    R.T @ R,
                    np.eye(3),
                    atol=1e-9
                )

                self.assertAlmostEqual(
                    np.linalg.det(R),
                    1.0,
                    delta=1e-9
                )

                xyz = calcular(q, URDF)

                np.testing.assert_allclose(
                    T[:3, 3],
                    xyz,
                    atol=1e-9
                )
