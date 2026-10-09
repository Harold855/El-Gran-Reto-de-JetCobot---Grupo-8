import math
from numbers import Real

POS_OBJETOS = {
    "rojo": {"alta": [], "agarre": []},
    "verde": {"alta": [], "agarre": []},
    "azul": {"alta": [], "agarre": []},
    "amarillo": {"alta": [], "agarre": []},
}

DESTINOS = {
    "rojo": {"xy": (69.6, 225.5), "z_alta": 195.9, "z_dejar": 131.8,
             "rx": -177.84, "ry": 2.62, "rz": 50.03},
    "verde": {"xy": (0.7, 234.7), "z_alta": 201.9, "z_dejar": 132.3,
              "rx": 177.21, "ry": 3.14, "rz": 46.72},
    "azul": {"xy": (-52.9, 241.9), "z_alta": 197.0, "z_dejar": 137.4,
             "rx": 174.03, "ry": 8.86, "rz": 45.55},
    "amarillo": {"xy": (148.0, 223.7), "z_alta": 186.0, "z_dejar": 147.3,
                 "rx": 179.99, "ry": 1.97, "rz": 49.38},
}

def validar_pose(pose):
    return (
        isinstance(pose, (list, tuple)) #La funcion isinstance comprueba si un objeto pertenece a una clase específica
        and len(pose) == 6
        and all(isinstance(v, Real) and not isinstance(v, bool)
                and math.isfinite(v) for v in pose)
    )


def validar_aproximacion(alta, baja):
    return (
        validar_pose(alta) and validar_pose(baja)
        and alta[2] > baja[2]
        and alta[:2] == baja[:2]
        and alta[3:] == baja[3:]
    )


def obtener_poses_objeto(color):
    objeto = POS_OBJETOS.get(color, {})
    alta = objeto.get("alta", [])
    agarre = objeto.get("agarre", [])
    if not validar_aproximacion(alta, agarre):
        raise ValueError(f"Falta calibrar las poses alta y agarre del objeto {color}") #Calibrar en el lab
    return list(alta), list(agarre)


def obtener_poses_destino(nombre):
    if nombre not in DESTINOS:
        raise ValueError(f"Destino no configurado: {nombre}")
    d = DESTINOS[nombre]
    try:
        xy = list(d["xy"])
        orientacion = [d["rx"], d["ry"], d["rz"]]
        alta = xy + [d["z_alta"]] + orientacion
        dejar = xy + [d["z_dejar"]] + orientacion
    except (KeyError, TypeError) as error:
        raise ValueError(f"Destino incompleto: {nombre}") from error
    if not validar_aproximacion(alta, dejar):
        raise ValueError(f"Poses alta/dejar invalidas del destino {nombre}")
    return alta, dejar






















