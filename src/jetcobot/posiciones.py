"""Posiciones de trabajo del JetCobot: una sola fuente de datos, config/zonas_trabajo.json.

Los destinos son las cuatro casillas de color (B/G/R/Y) del tablero izquierdo. Las poses de
recogida siguen en null hasta medirlas en el robot: pedirlas lanza NoConfigurado. Los destinos
heredados del código original llevan validada=false y no se presentan como aprobados.
"""

import json
import math
from numbers import Real

if __package__:
    from .rutas import ZONAS_TRABAJO
else:
    from rutas import ZONAS_TRABAJO

COLORES = ("rojo", "verde", "azul", "amarillo")


class ConfiguracionError(ValueError):
    """La configuración o lo que se pide de ella no es válido."""


class ColorInvalido(ConfiguracionError):
    """El color no es rojo, verde, azul ni amarillo."""


class DestinoInvalido(ConfiguracionError):
    """El destino no es una de las cuatro zonas de color del tablero izquierdo."""


class NoConfigurado(ConfiguracionError):
    """Falta medir o cargar la pose pedida (el JSON la tiene en null)."""


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


def validar_configuracion(datos):
    """Comprueba el esquema de zonas_trabajo.json; lanza ConfiguracionError si algo no cuadra."""
    if not isinstance(datos, dict):
        raise ConfiguracionError("la configuración debe ser un objeto JSON")
    if datos.get("unidad") != "mm":
        raise ConfiguracionError("unidad debe ser 'mm'")
    if datos.get("unidad_orientacion") != "grados":
        raise ConfiguracionError("unidad_orientacion debe ser 'grados'")

    altura = datos.get("altura_segura")
    if altura is not None and (not isinstance(altura, Real) or isinstance(altura, bool)
                               or not math.isfinite(altura) or altura <= 0):
        raise ConfiguracionError("altura_segura debe ser null o un número positivo")

    recogida = datos.get("zonas_recogida")
    destino = datos.get("zonas_destino")
    for nombre, zonas in (("zonas_recogida", recogida), ("zonas_destino", destino)):
        if not isinstance(zonas, dict) or set(zonas) != set(COLORES):
            raise ConfiguracionError(f"{nombre} debe tener exactamente {list(COLORES)}")

    for color, zona in recogida.items():
        if zona is None:
            continue
        if (not isinstance(zona, dict)
                or not validar_aproximacion(zona.get("alta"), zona.get("agarre"))
                or not isinstance(zona.get("validada"), bool)):
            raise ConfiguracionError(f"zonas_recogida.{color}: se esperan alta y agarre válidos y validada")

    for color, zona in destino.items():
        if (not isinstance(zona, dict)
                or not validar_aproximacion(zona.get("aproximacion"), zona.get("deposito"))
                or not isinstance(zona.get("validada"), bool)):
            raise ConfiguracionError(
                f"zonas_destino.{color}: se esperan aproximacion y deposito válidos y validada")

    escaneo = (datos.get("posiciones_originales") or {}).get("escaneo")
    if not validar_pose(escaneo):
        raise ConfiguracionError("posiciones_originales.escaneo debe ser una pose de seis valores")
    return datos


class ConfigTrabajo:
    """Datos de trabajo ya validados. simulada=True marca datos ficticios que nunca son físicos."""

    def __init__(self, datos, simulada=False):
        self.datos = validar_configuracion(datos)
        self.simulada = simulada

    @classmethod
    def cargar(cls, ruta=ZONAS_TRABAJO):
        try:
            with open(ruta, encoding="utf-8") as archivo:
                datos = json.load(archivo)
        except (OSError, json.JSONDecodeError) as error:
            raise ConfiguracionError(f"no se pudo leer {ruta}: {error}") from error
        return cls(datos)

    @staticmethod
    def color_valido(color):
        color = color.strip().lower() if isinstance(color, str) else color
        if color not in COLORES:
            raise ColorInvalido(f"Color no válido: {color!r}")
        return color

    def poses_objeto(self, color):
        """(pose_alta, pose_agarre) donde recoger el cubo de ese color."""
        color = self.color_valido(color)
        zona = self.datos["zonas_recogida"][color]
        if zona is None:
            raise NoConfigurado(f"Todavía faltan calibrar las poses altas y el agarre del objeto {color}")
        return list(zona["alta"]), list(zona["agarre"])

    def poses_destino(self, nombre):
        """(pose_alta, pose_dejar) de la zona de color nombre."""
        if not isinstance(nombre, str) or nombre.strip().lower() not in COLORES:
            raise DestinoInvalido(f"Destino no configurado: {nombre!r}")
        zona = self.datos["zonas_destino"][nombre.strip().lower()]
        return list(zona["aproximacion"]), list(zona["deposito"])

    def destino_validado(self, nombre):
        return bool(self.datos["zonas_destino"][nombre]["validada"])

    def pose_escaneo(self):
        return list(self.datos["posiciones_originales"]["escaneo"])


def cargar_configuracion(ruta=ZONAS_TRABAJO):
    return ConfigTrabajo.cargar(ruta)

def obtener_poses_objeto(color, config=None):
    return (config or cargar_configuracion()).poses_objeto(color)

def obtener_poses_destino(nombre, config=None):
    return (config or cargar_configuracion()).poses_destino(nombre)
