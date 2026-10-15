"""Modelo PoE idealizado del JetCobot, referencia experimental."""

import numpy as np
from scipy.spatial.transform import Rotation

PUNTOS_MM = np.array([
    [0, 0, 74.52],
    [-0.026, -35, 134.52],
    [-0.026, -28.21, 244.52],
    [-0.026, -29.555, 340.52],
    [-0.051, -63.095, 375.349],
    [31.914, -63.124, 415.27],
], dtype=float)

EJES = np.array([
    [0, 0, 1],
    [0, -1, 0],
    [0, -1, 0],
    [0, -1, 0],
    [0, 0, 1],
    [1, 0, 0],
], dtype=float)


def calcular_matriz(q, T_cero):
    """Cinematica PoE. Posiciones y traslaciones en mm."""
    q = np.asarray(q, dtype=float)

    if q.shape != (6,) or not np.isfinite(q).all():
        raise ValueError("Se requieren seis angulos finitos")

    T = np.eye(4)

    for punto, eje, angulo in zip(PUNTOS_MM, EJES, q):
        R = Rotation.from_rotvec(eje * angulo).as_matrix()

        A = np.eye(4)
        A[:3, :3] = R
        A[:3, 3] = punto - R @ punto

        T = T @ A

    return T @ np.asarray(T_cero, dtype=float)
