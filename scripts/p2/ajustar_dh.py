"""Ajuste y validacion de parametros DH frente al URDF."""

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import CALIBRACION

ARCHIVO = CALIBRACION / "referencias_urdf.npz"


def cargar_datos():
    with np.load(ARCHIVO) as datos:
        return {
            nombre: datos[nombre].copy()
            for nombre in datos.files
        }




def matriz_dh(q, parametros, base=None, herramienta=None):
    """Matriz DH con transformaciones opcionales de base y herramienta."""
    from arm_broker.fk import _t

    filas = np.asarray(parametros, dtype=float).reshape(6, 4)
    T = np.eye(4) if base is None else np.array(base, dtype=float).copy()

    for angulo, (alpha, a, d, offset) in zip(q, filas):
        T = T @ np.asarray(_t(alpha, a, d, angulo + offset))

    if herramienta is not None:
        T = T @ np.asarray(herramienta, dtype=float)

    return T


def residuos(parametros, posturas, referencias):
    """Errores de posicion y orientacion frente al URDF."""
    from scipy.spatial.transform import Rotation

    errores = []

    for q, T_ref in zip(posturas, referencias):
        T = matriz_dh(q, parametros)

        error_pos = T[:3, 3] - T_ref[:3, 3]

        R_error = T[:3, :3] @ T_ref[:3, :3].T
        error_rot = Rotation.from_matrix(R_error).as_rotvec()

        errores.extend(error_pos)
        errores.extend(100.0 * error_rot)

    return np.asarray(errores)

def main():
    datos = cargar_datos()

    for nombre, valores in datos.items():
        print(f"{nombre}: {valores.shape}")

    assert datos["q_ajuste"].shape == (80, 6)
    assert datos["T_ajuste"].shape == (80, 4, 4)
    assert datos["q_validacion"].shape == (20, 6)
    assert datos["T_validacion"].shape == (20, 4, 4)

    print("OK: datos listos para ajustar DH")


if __name__ == "__main__":
    main()
