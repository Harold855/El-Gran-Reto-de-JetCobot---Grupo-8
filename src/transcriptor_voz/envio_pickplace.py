"""P3 hacia P2: envío de una orden ya autorizada por P1 a la acción /pick_place del broker.

P3 solo entrega la tarea (color, destino, prioridad), no mueve el JetCobot ni publica en /joint_states.
P2 valida de nuevo y decide. El resultado de un broker simulado queda marcado simulado=True.
Sin dependencias de ROS al importar: el cliente de acción, la interfaz y la espera se inyectan.
"""

import re
import time
from dataclasses import dataclass, field

COLORES = ("rojo", "verde", "azul", "amarillo")   # los únicos colores válidos, para el cubo y para la zona
PRIORIDADES = (1, 2, 3)                           # las que entrega P1; mayor número = más urgente
PATRON_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

# Columnas que se agregan al CSV de P3 (transcripciones.csv), en este orden
COLUMNAS_P2 = [
    "enviado_p2", "aceptado_p2", "estado_p2", "codigo_p2", "simulado_p2", "mensaje_p2",
    "tiempo_aceptacion_p2_ms", "tiempo_resultado_p2_ms", "espera_cola_p2_s", "ejecucion_p2_s",
    "etapas_p2", "tiempo_total_p2_ms",
]


@dataclass   # dataclass: clase que solo guarda datos; Python le genera el constructor
class ResultadoP2:
    """Lo que pasó al entregar la orden a P2. Los valores por defecto significan "no medido"."""
    enviado: bool = False
    aceptado: bool = False
    estado: str = ""            # NO_ENVIADO, SIN_SERVIDOR, RECHAZADO, EXITO, ABORTADO, CANCELADO, TIMEOUT_CLIENTE...
    codigo: str = ""            # codigo_resultado de P2; vacío si no hubo resultado
    simulado: bool = False
    mensaje: str = ""
    t_aceptacion_ms: float = None
    t_resultado_ms: float = None
    espera_cola_s: float = None
    ejecucion_s: float = None
    etapas: list = field(default_factory=list)

    @property
    def completado(self):
        return self.estado == "EXITO" and self.codigo == "COMPLETADO"

    def a_columnas(self, t_parcial_ms=None):
        # t_parcial_ms = tiempo ya gastado antes de P2 (captura, Google, P1); se suma al de P2 para el total
        """Valores en el orden de COLUMNAS_P2; lo no medido queda vacío (no es cero)."""
        def ms(valor, decimales=2):
            return "" if valor is None else round(valor, decimales)

        total = ""
        if self.t_resultado_ms is not None and t_parcial_ms is not None:
            total = round(t_parcial_ms + self.t_resultado_ms, 2)
        return [
            self.enviado, self.aceptado if self.enviado else "", self.estado, self.codigo,
            self.simulado if self.enviado and self.codigo else "", self.mensaje,
            ms(self.t_aceptacion_ms), ms(self.t_resultado_ms), ms(self.espera_cola_s, 3),
            ms(self.ejecucion_s, 3), ">".join(dict.fromkeys(self.etapas)), total,
        ]


def decision_apta(decision, permitir_degradado=False):
    # Filtro de seguridad de P3: solo pasa lo que P1 autorizó y que P2 sabe hacer.
    # "Degradado" = P1 contestó con su clasificador de respaldo en vez de LAYA; por defecto no se envía.
    """(True, '') si la decisión de P1 puede enviarse a P2; si no, (False, motivo)."""
    if decision is None:
        return False, "P1 no respondió"
    if not decision.permitido:
        return False, "P1 rechazó la orden"
    if decision.degradado and not permitir_degradado:
        return False, "decisión degradada (clasificador de respaldo): no apta para movimiento automático"
    if decision.accion != "trasladar" or decision.objeto != "cubo":
        return False, f"acción/objeto no soportados: {decision.accion!r}/{decision.objeto!r}"
    if decision.color not in COLORES:
        return False, f"color de cubo no válido: {decision.color!r}"
    if decision.destino not in COLORES:
        return False, f"destino no válido: {decision.destino!r}"
    if decision.prioridad not in PRIORIDADES:
        return False, f"prioridad fuera de {list(PRIORIDADES)}: {decision.prioridad!r}"
    return True, ""


def esperar_con_rclpy(nodo):
    # Devuelve una función esperar(futuro, segundos) -> True si el futuro terminó a tiempo.
    # ROS 2 se importa aquí dentro para que este módulo se pueda probar sin ROS 2.
    import rclpy

    def esperar(futuro, segundos):
        rclpy.spin_until_future_complete(nodo, futuro, timeout_sec=segundos)
        return futuro.done()
    return esperar


def enviar_pick_place(cliente, clase_accion, id_solicitud, decision, esperar,
                      timeout_servidor_s=3.0, timeout_resultado_s=120.0, permitir_degradado=False,
                      mostrar=print):
    """
    Envía la tarea y espera aceptación y resultado.
    Cliente: ActionClient de /pick_place; clase_accion: PickPlace; esperar(futuro, s) -> bool.
    Cualquier fallo queda en el ResultadoP2.
    """
    resultado = ResultadoP2()
    # 1) ¿La decisión y el id son aptos? Si no, no se toca el cliente de P2 y queda no_enviado
    ok, motivo = decision_apta(decision, permitir_degradado)
    if not ok:
        resultado.estado, resultado.mensaje = "NO_ENVIADO", motivo
        return resultado
    if not PATRON_ID.match(id_solicitud or ""):
        resultado.estado, resultado.mensaje = "NO_ENVIADO", f"id_solicitud no válido: {id_solicitud!r}"
        return resultado

    try:
        # 2) ¿Está P2 disponible? (wait_for_server espera a que exista el servidor de la acción)
        if not cliente.wait_for_server(timeout_sec=timeout_servidor_s):
            resultado.estado, resultado.mensaje = "SIN_SERVIDOR", "/pick_place no está disponible"
            return resultado

        # 3) Se arma y envía la meta: solo la tarea (color, destino, prioridad), sin ángulos
        meta = clase_accion.Goal(id_solicitud=id_solicitud, color_objetivo=decision.color,
                                 destino=decision.destino, priority=int(decision.prioridad))
        inicio = time.monotonic()
        resultado.enviado = True
        # send_goal_async: envía sin bloquear; feedback_callback anota cada etapa que P2 va informando
        futuro = cliente.send_goal_async(
            meta, feedback_callback=lambda fb: resultado.etapas.append(fb.feedback.etapa))
        if not esperar(futuro, timeout_servidor_s + 5.0):
            resultado.estado, resultado.mensaje = "SIN_RESPUESTA", "P2 no respondió a la solicitud"
            return resultado
        # 4) P2 acepta o rechaza la meta (rechaza si algo es inválido, hay un id repetido o la cola está llena)
        handle = futuro.result()
        resultado.t_aceptacion_ms = (time.monotonic() - inicio) * 1000
        if handle is None or not handle.accepted:
            resultado.estado = "RECHAZADO"
            resultado.mensaje = "P2 rechazó la tarea antes de encolarla (el motivo queda en su registro)"
            return resultado
        resultado.aceptado = True
        mostrar(f"[P2] Tarea {id_solicitud} aceptada; esperando resultado...")

        # 5) Se espera el resultado final, si se pasa el tiempo, se pide cancelar la tarea
        pedido = handle.get_result_async()
        if not esperar(pedido, timeout_resultado_s):
            handle.cancel_goal_async()
            resultado.estado = "TIMEOUT_CLIENTE"
            resultado.mensaje = f"sin resultado en {timeout_resultado_s:g} s; se pidió cancelar"
            resultado.t_resultado_ms = (time.monotonic() - inicio) * 1000
            return resultado
        envio = pedido.result()
        res = envio.result
        resultado.t_resultado_ms = (time.monotonic() - inicio) * 1000
        # Estados de ROS 2: 
        # 4 = terminó bien 
        # 5 = cancelada 
        # 6 = abortada (P2 no pudo completarla)
        resultado.estado = {4: "EXITO", 5: "CANCELADO", 6: "ABORTADO"}.get(envio.status, f"ESTADO_{envio.status}")
        resultado.codigo = res.codigo_resultado
        resultado.mensaje = res.message
        resultado.simulado = "SIMULADO" in res.message   # P2 marca así los resultados que no movieron el brazo
        resultado.espera_cola_s = float(res.wait_time_s)
        resultado.ejecucion_s = float(res.exec_time_s)
        return resultado
    except Exception as error:
        resultado.estado, resultado.mensaje = "ERROR_CLIENTE", f"{type(error).__name__}: {error}"
        return resultado
