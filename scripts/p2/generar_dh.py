"""Construcción geométrica experimental de marcos DH del JetCobot."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from arm_broker.fk_poe import PUNTOS_MM, EJES


def normal_comun(i):
    """Puntos más cercanos entre dos ejes articulares."""
    p = PUNTOS_MM[i]
    q = PUNTOS_MM[i + 1]
    u = EJES[i]
    v = EJES[i + 1]

    A = np.column_stack((u, -v))
    t, s = np.linalg.lstsq(A, q - p, rcond=None)[0]

    c1 = p + t * u
    c2 = q + s * v

    return c1, c2


def main():
    print("=== GEOMETRÍA PARA MARCOS DH ===")

    for i in range(5):
        c1, c2 = normal_comun(i)
        distancia = np.linalg.norm(c2 - c1)

        print(
            f"J{i+1}-J{i+2}: "
            f"a={distancia:.4f} mm, "
            f"origen anterior={np.round(c1, 3)}, "
            f"origen siguiente={np.round(c2, 3)}"
        )


if __name__ == "__main__":
    main()


def construir_marcos():
    """Marcos geometricos iniciales en coordenadas de la base."""
    marcos = []

    for i in range(6):
        z = EJES[i].copy()

        if i < 5:
            c1, c2 = normal_comun(i)
            x = c2 - c1

            if np.linalg.norm(x) < 1e-8:
                x = np.cross(z, EJES[i + 1])
        else:
            x = np.array([0.0, 0.0, 1.0])

        x = x - np.dot(x, z) * z
        x = x / np.linalg.norm(x)

        y = np.cross(z, x)
        R = np.column_stack((x, y, z))

        marcos.append(R)

    return marcos


if __name__ == "__main__":
    print("\n=== VERIFICACION DE MARCOS ===")

    for i, R in enumerate(construir_marcos(), start=1):
        print(
            f"J{i}: det={np.linalg.det(R):.6f}, "
            f"ortogonal={np.allclose(R.T @ R, np.eye(3))}"
        )


def construir_marcos_dh():
    """Marcos candidatos DH en postura cero, en coordenadas base."""
    marcos = []

    for i in range(6):
        z = EJES[i].copy()

        if i == 0:
            origen = PUNTOS_MM[0].copy()
            x = np.array([-1.0, 0.0, 0.0])
        else:
            c1, c2 = normal_comun(i - 1)
            origen = c2.copy()
            x = c2 - c1

        x = x - np.dot(x, z) * z
        x /= np.linalg.norm(x)

        y = np.cross(z, x)

        T = np.eye(4)
        T[:3, :3] = np.column_stack((x, y, z))
        T[:3, 3] = origen

        marcos.append(T)

    return marcos
