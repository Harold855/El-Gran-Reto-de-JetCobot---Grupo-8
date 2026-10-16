"""Ejecutor simulado de /pick_place: sin hardware, sin pymycobot, sin puertos serie.

Corre la MISMA secuencia que el ejecutor real (jetcobot.pick_and_place.ejecutar_secuencia) con
percepción, movimiento y pinza falsos. Las poses de config_ficticia() existen solo en memoria,
se usan únicamente aquí y no representan ninguna posición física del tablero.
Todo resultado, feedback y tiempo de este ejecutor está etiquetado como SIMULADO.
"""

import time

from arm_broker.tarea_pickplace import COLORES, ResultadoTarea
from jetcobot.pick_and_place import ejecutar_secuencia
from jetcobot.posiciones import ConfigTrabajo

FALLOS_SIMULABLES = ("", "ERROR_PLANIFICACION", "ERROR_AGARRE")


def config_ficticia():
    """Datos de trabajo inventados (SIMULADOS) que cumplen el esquema; nunca se guardan en el JSON."""
    recogida = {c: {"alta": [0.0, 0.0, 2.0, 0.0, 0.0, 0.0], "agarre": [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
                    "validada": False} for c in COLORES}
    destino = {c: {"aproximacion": [0.0, 0.0, 2.0, 0.0, 0.0, 0.0], "deposito": [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
                   "validada": False} for c in COLORES}
    return ConfigTrabajo({
        "unidad": "mm", "unidad_orientacion": "grados", "altura_segura": None,
        "zonas_recogida": recogida, "zonas_destino": destino,
        "posiciones_originales": {"escaneo": [0.0, 0.0, 3.0, 0.0, 0.0, 0.0]},
    }, simulada=True)


class EjecutorSimulado:
    nombre = "simulado"
    simulado = True

    def __init__(self, duracion_etapa_s=0.2, colores_ausentes=(), fallo_simulado="", dormir=time.sleep):
        if fallo_simulado not in FALLOS_SIMULABLES:
            raise ValueError(f"fallo_simulado debe ser uno de {list(FALLOS_SIMULABLES)}")
        self.duracion_etapa_s = max(0.0, float(duracion_etapa_s))
        self.colores_ausentes = set(colores_ausentes)
        self.fallo_simulado = fallo_simulado
        self._dormir = dormir

    def ejecutar(self, tarea, ctx):
        primero = {"movimiento": True}

        def percibir(color):
            return {"presente": color not in self.colores_ausentes, "simulado": True}

        def mover_a_pose(pose):
            ctx.evento("inicio_planificacion", "SIMULADO")
            self._dormir(self.duracion_etapa_s)
            if self.fallo_simulado == "ERROR_PLANIFICACION":
                ctx.evento("fin_planificacion", "SIMULADO: fallo inyectado")
                return False
            ctx.evento("fin_planificacion", "SIMULADO")
            if primero["movimiento"]:
                primero["movimiento"] = False
                ctx.evento("primer_comando_movimiento", "SIMULADO: no se envió nada al brazo")
            return True

        class PinzaFalsa:
            def abrir(_):
                return True

            def cerrar(_):
                return "vacia" if self.fallo_simulado == "ERROR_AGARRE" else "agarrado"

        resultado = ejecutar_secuencia(
            tarea.color_objetivo, tarea.destino, config=config_ficticia(), percibir=percibir,
            mover_a_pose=mover_a_pose, pinza=PinzaFalsa(), on_etapa=ctx.etapa, cancelado=ctx.cancelado)
        ctx.cerrar_etapa()
        etiqueta = "COMPLETADO (SIMULADO)" if resultado.success else f"{resultado.codigo} (SIMULADO)"
        return ResultadoTarea(resultado.success, resultado.codigo, f"{etiqueta}: {resultado.motivo}",
                              resultado.etapa)
