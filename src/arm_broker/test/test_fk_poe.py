import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/

from arm_broker.cinematica_urdf import URDF_JETCOBOT, calcular_matriz as fk_urdf
from arm_broker.fk_poe import calcular_matriz as fk_poe
from jetcobot.rutas import CALIBRACION


def cargar_datos():
    with np.load(CALIBRACION / "referencias_urdf.npz") as datos:
        return {nombre: datos[nombre].copy() for nombre in datos.files}


class TestFKPoE(unittest.TestCase):

    def test_comparacion_urdf(self):
        datos = cargar_datos()
        T_cero = np.asarray(fk_urdf([0] * 6, URDF_JETCOBOT))

        for q, referencia in zip(
            datos["q_validacion"],
            datos["T_validacion"]
        ):
            T = fk_poe(q, T_cero)

            error_mm = np.linalg.norm(
                T[:3, 3] - referencia[:3, 3]
            )

            R_error = T[:3, :3] @ referencia[:3, :3].T
            error_grados = np.degrees(
                Rotation.from_matrix(R_error).magnitude()
            )

            self.assertLess(error_mm, 0.25)
            self.assertLess(error_grados, 0.1)


if __name__ == "__main__":
    unittest.main()
