"""Ejecutor real de /pick_place. Falla cerrado: sin los tres respaldos de hardware no mueve nada.

percibir(color), mover_a_pose(pose) y pinza (abrir/cerrar) deben venir de un worker autorizado
(cámara, MoveIt y pinza del robot). Mientras no existan, cada tarea termina en NO_CONFIGURADO y
sin ningún efecto físico. Las poses salen siempre de jetcobot/config/zonas_trabajo.json.
"""

from arm_broker.tarea_pickplace import ResultadoTarea
from jetcobot.pick_and_place import ejecutar_secuencia
from jetcobot.posiciones import ConfigTrabajo, ConfiguracionError


class EjecutorReal:
    nombre = "real"
    simulado = False

    def __init__(self, config=None, percibir=None, mover_a_pose=None, pinza=None):
        self.config = config
        self.percibir = percibir
        self.mover_a_pose = mover_a_pose
        self.pinza = pinza

    def ejecutar(self, tarea, ctx):
        if None in (self.percibir, self.mover_a_pose, self.pinza):
            return ResultadoTarea(
                False, "NO_CONFIGURADO",
                "ejecutor real sin percepción, movimiento o pinza: no se mueve nada (falla cerrado)")
        try:
            config = self.config or ConfigTrabajo.cargar()
        except ConfiguracionError as error:
            return ResultadoTarea(False, "NO_CONFIGURADO", str(error))

        primero = {"movimiento": True}

        def mover(pose):
            if primero["movimiento"]:
                primero["movimiento"] = False
                ctx.evento("primer_comando_movimiento", "")
            return self.mover_a_pose(pose)

        resultado = ejecutar_secuencia(
            tarea.color_objetivo, tarea.destino, config=config, percibir=self.percibir,
            mover_a_pose=mover, pinza=self.pinza, on_etapa=ctx.etapa, cancelado=ctx.cancelado)
        ctx.cerrar_etapa()
        return ResultadoTarea(resultado.success, resultado.codigo, resultado.motivo, resultado.etapa)
