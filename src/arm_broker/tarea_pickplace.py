"""Contrato de la tarea /pick_place: validación, códigos de resultado y contexto de ejecución.

Sin ROS: el broker y los ejecutores comparten estas definiciones y se prueban sin hardware.
"""

import re
from dataclasses import dataclass

COLORES = ("rojo", "verde", "azul", "amarillo")
PRIORIDADES = (1, 2, 3)   # las que entrega P1; mayor número = más urgente
PATRON_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

CODIGOS = (
    "COMPLETADO", "OBJETO_AUSENTE", "COLOR_INVALIDO", "DESTINO_INVALIDO", "PRIORIDAD_INVALIDA",
    "ID_INVALIDO", "ID_DUPLICADO", "COLA_LLENA", "NO_CONFIGURADO", "ESTADO_DESCONOCIDO",
    "ERROR_PLANIFICACION", "ERROR_AGARRE", "CANCELADO", "ERROR_INTERNO",
)


@dataclass(frozen=True)
class Tarea:
    id_solicitud: str
    color_objetivo: str
    destino: str
    priority: int


@dataclass
class ResultadoTarea:
    success: bool
    codigo: str
    mensaje: str
    etapa: str = ""


def validar_tarea(id_solicitud, color_objetivo, destino, priority):
    """(None, '') si la tarea es admisible, o (codigo, motivo). Comparación exacta, sin normalizar."""
    if not isinstance(id_solicitud, str) or not PATRON_ID.match(id_solicitud):
        return "ID_INVALIDO", "id_solicitud debe tener de 1 a 64 letras, dígitos, '_', '.' o '-'"
    if color_objetivo not in COLORES:
        return "COLOR_INVALIDO", f"color_objetivo {color_objetivo!r} no está en {list(COLORES)}"
    if destino not in COLORES:
        return "DESTINO_INVALIDO", (f"destino {destino!r} no es una zona de color {list(COLORES)} "
                                    "del tablero izquierdo")
    if priority not in PRIORIDADES:
        return "PRIORIDAD_INVALIDA", f"priority {priority!r} no está en {list(PRIORIDADES)}"
    return None, ""


class ContextoEjecucion:
    """Lo que el broker le da al ejecutor: cancelación, etapas con feedback y eventos del registro."""

    def __init__(self, cancelado, al_cambiar_etapa, al_evento):
        self._cancelado = cancelado
        self._al_cambiar_etapa = al_cambiar_etapa
        self._al_evento = al_evento
        self._etapa = None

    def cancelado(self):
        return bool(self._cancelado())

    def etapa(self, nombre):
        """Cierra la etapa anterior, abre la nueva y avisa al cliente (feedback)."""
        if self._etapa:
            self._al_evento(f"fin_{self._etapa.lower()}", "")
        self._etapa = nombre
        self._al_evento(f"inicio_{nombre.lower()}", "")
        self._al_cambiar_etapa(nombre)

    def evento(self, nombre, detalle=""):
        self._al_evento(nombre, detalle)

    def cerrar_etapa(self):
        if self._etapa:
            self._al_evento(f"fin_{self._etapa.lower()}", "")
            self._etapa = None
