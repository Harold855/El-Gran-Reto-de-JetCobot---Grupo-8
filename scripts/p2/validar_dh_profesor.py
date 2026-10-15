import sys
from math import pi, sin, cos
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from arm_broker.cinematica_urdf import calcular_matriz as fk_urdf

# Convención DH estándar.
# Columnas: alpha(rad), a(mm), d(mm), theta_offset(rad)
DH = [
    ( pi/2,    0.0, 134.75,       0.0),
    ( 0.0,  -110.0,   0.0,     -pi/2),
    ( 0.0,   -96.0,   0.0,       0.0),
    ( pi/2,    0.0,  63.4,     -pi/2),
    (-pi/2,    0.0,  75.05,     pi/2),
    ( 0.0,     0.0,  50.0,       0.0),
]

def matriz_dh(alpha, a, d, theta):
    c, s = cos(theta), sin(theta)
    ca, sa = cos(alpha), sin(alpha)

    return np.array([
        [c, -s*ca,  s*sa, a*c],
        [s,  c*ca, -c*sa, a*s],
        [0,     sa,     ca,   d],
        [0,      0,      0,   1],
    ], dtype=float)

def fk_dh(q):
    T = np.eye(4)
    for angulo, (alpha, a, d, offset) in zip(q, DH):
        T = T @ matriz_dh(alpha, a, d, angulo + offset)
    return T

posturas = [
    np.zeros(6),
    np.radians([0, -20, 20, 0, 0, -45]),
    np.radians([20, -30, 35, 15, -10, -30]),
    np.radians([-20, 10, -15, 20, 15, 0]),
]

print("=== TABLA DH DEL PROFESOR ===")
for i, fila in enumerate(DH, 1):
    print(f"J{i}: {fila}")

print("\n=== COMPARACIÓN CON URDF ===")

for i, q in enumerate(posturas, 1):
    A = fk_dh(q)
    B = np.asarray(fk_urdf(q), dtype=float)

    p_dh = A[:3, 3]
    p_urdf = B[:3, 3]
    error = np.linalg.norm(p_dh - p_urdf)

    print(f"\nPostura {i}")
    print("DH:   ", np.round(p_dh, 3))
    print("URDF: ", np.round(p_urdf, 3))
    print(f"Diferencia directa: {error:.3f} mm")

print("\nNOTA: La diferencia incluye posibles cambios")
print("de marco base y herramienta entre DH y URDF.")
