"""Cinemática directa de referencia a partir del URDF del JetCobot.

Es una referencia para validar fk.py (tests y scripts de calibración); el broker no la usa.
"""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

JOINT_NAMES = [f"{i}_Joint" for i in range(1, 7)]

# src/jetcobot/modelos/jetcobot.urdf, relativo a este archivo (src/arm_broker/)
URDF_JETCOBOT = Path(__file__).resolve().parents[1] / "jetcobot" / "modelos" / "jetcobot.urdf"


def multiplicar(a, b):
    return [
        [
            sum(a[i][k] * b[k][j] for k in range(4))
            for j in range(4)
        ]
        for i in range(4)
    ]


def identidad():
    return [
        [1.0 if i == j else 0.0 for j in range(4)]
        for i in range(4)
    ]


def traslacion(x, y, z):
    t = identidad()
    t[0][3], t[1][3], t[2][3] = x, y, z
    return t


def rotacion_eje(eje, angulo):
    x, y, z = eje
    norma = math.sqrt(x*x + y*y + z*z)

    if norma == 0:
        raise ValueError("Eje de rotación inválido")

    x, y, z = x/norma, y/norma, z/norma
    c = math.cos(angulo)
    s = math.sin(angulo)
    v = 1 - c

    t = identidad()

    t[0][:3] = [c+x*x*v, x*y*v-z*s, x*z*v+y*s]
    t[1][:3] = [y*x*v+z*s, c+y*y*v, y*z*v-x*s]
    t[2][:3] = [z*x*v-y*s, z*y*v+x*s, c+z*z*v]

    return t


def origen(joint):
    nodo = joint.find("origin")

    if nodo is None:
        return identidad()

    xyz = [float(v) for v in nodo.get("xyz", "0 0 0").split()]
    r, p, y = [
        float(v) for v in nodo.get("rpy", "0 0 0").split()
    ]

    t = traslacion(*xyz)

    for eje, angulo in [
        ((0, 0, 1), y),
        ((0, 1, 0), p),
        ((1, 0, 0), r),
    ]:
        t = multiplicar(t, rotacion_eje(eje, angulo))

    return t


def cargar_modelo(ruta):
    raiz = ET.parse(ruta).getroot()
    return {
        j.get("name"): j
        for j in raiz.findall("joint")
    }, raiz


def calcular(q, ruta_urdf=URDF_JETCOBOT, efector="jiazhua_Link"):
    if len(q) != 6:
        raise ValueError("Se requieren seis ángulos articulares")

    if not all(math.isfinite(float(v)) for v in q):
        raise ValueError("Los ángulos deben ser finitos")

    joints, raiz = cargar_modelo(ruta_urdf)

    # Construir la cadena desde el efector hasta base_link.
    por_hijo = {}
    for joint in raiz.findall("joint"):
        hijo = joint.find("child")
        if hijo is not None:
            por_hijo[hijo.get("link")] = joint

    cadena = []
    actual = efector

    while actual != "base_link":
        if actual not in por_hijo:
            raise ValueError(f"No existe conexión hacia {actual}")

        joint = por_hijo[actual]
        cadena.append(joint)

        padre = joint.find("parent")
        actual = padre.get("link")

    cadena.reverse()

    valores = dict(zip(JOINT_NAMES, q))
    t = identidad()

    for joint in cadena:
        t = multiplicar(t, origen(joint))

        if joint.get("type") in ("revolute", "continuous"):
            nombre = joint.get("name")

            if nombre not in valores:
                raise ValueError(f"Articulación desconocida: {nombre}")

            nodo_eje = joint.find("axis")
            eje = (
                [float(v) for v in nodo_eje.get("xyz").split()]
                if nodo_eje is not None else [1, 0, 0]
            )

            t = multiplicar(
                t, rotacion_eje(eje, valores[nombre])
            )
        elif joint.get("type") != "fixed":
            raise ValueError(
                f"Tipo de articulación no soportado: {joint.get('type')}"
            )

    return tuple(1000 * t[i][3] for i in range(3))


def calcular_matriz(q, ruta_urdf=URDF_JETCOBOT, efector="jiazhua_Link"):
    """Matriz 4x4 base-efector: traslacion en milimetros."""
    if len(q) != 6:
        raise ValueError("Se requieren seis angulos articulares")

    if not all(math.isfinite(float(v)) for v in q):
        raise ValueError("Los angulos deben ser finitos")

    _, raiz = cargar_modelo(ruta_urdf)

    por_hijo = {}
    for joint in raiz.findall("joint"):
        hijo = joint.find("child")
        if hijo is not None:
            por_hijo[hijo.get("link")] = joint

    cadena = []
    actual = efector
    visitados = set()

    while actual != "base_link":
        if actual in visitados or actual not in por_hijo:
            raise ValueError("Cadena cinematica invalida")

        visitados.add(actual)
        joint = por_hijo[actual]
        cadena.append(joint)
        actual = joint.find("parent").get("link")

    valores = dict(zip(JOINT_NAMES, q))
    t = identidad()

    for joint in reversed(cadena):
        t = multiplicar(t, origen(joint))
        tipo = joint.get("type")

        if tipo in ("revolute", "continuous"):
            nombre = joint.get("name")
            if nombre not in valores:
                raise ValueError(f"Articulacion desconocida: {nombre}")

            nodo = joint.find("axis")
            eje = (
                [float(v) for v in nodo.get("xyz").split()]
                if nodo is not None else [1, 0, 0]
            )
            t = multiplicar(t, rotacion_eje(eje, valores[nombre]))
        elif tipo != "fixed":
            raise ValueError(f"Tipo no soportado: {tipo}")

    resultado = [fila[:] for fila in t]
    for i in range(3):
        resultado[i][3] *= 1000

    return resultado

