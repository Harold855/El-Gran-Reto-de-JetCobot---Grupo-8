# ==============================================================================
# UNIVERSIDAD ESAN
# ROBOTICA 08079
# EXAMEN PARCIAL - GRAN RETO JETCOBOT
# Grupo 7
#
# Integrantes:
# - Sebastian Pedro Aguirre Acosta
# - Anahi Cortez Chinchay
# - Ramirez Quevedo Karen Noelia
# - Vara Vargas Valentino Uziel
#
# Archivo: broker_p2_sim.py
# Descripcion: Integracion logica de la Pregunta 2.
# No publica movimientos ni controla hardware.
# ==============================================================================

import threading
import time
from dataclasses import dataclass, field

import rclpy
from rclpy.action import (
    ActionServer,
    GoalResponse,
    CancelResponse
)
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from arm_broker_interfaces.action import ProcesarObjeto
from arm_broker.politicas import FIFO, SegundaPolitica


@dataclass
class PedidoObjeto:
    goal_handle: object
    client_id: str
    accion: str
    objeto: str
    color: str
    priority: int
    t_llegada: float = field(default_factory=time.time)
    t_inicio_ejec: float = None
    fin: threading.Event = field(default_factory=threading.Event)
    resultado: object = None

    @property
    def espera_s(self):
        referencia = (
            self.t_inicio_ejec
            if self.t_inicio_ejec is not None
            else time.time()
        )
        return referencia - self.t_llegada


class BrokerP2Sim(Node):

    def __init__(self):
        super().__init__('broker_p2_sim')

        self.declare_parameter('politica', 'prioridad')
        self.declare_parameter('tau_envejecimiento_s', 8.0)
        self.declare_parameter('cola_max', 20)
        self.declare_parameter('duracion_simulada_s', 2.0)

        nombre = self.get_parameter('politica').value

        if nombre == 'fifo':
            self.politica = FIFO()
        elif nombre == 'prioridad':
            tau = self.get_parameter('tau_envejecimiento_s').value
            self.politica = SegundaPolitica(tau_s=tau)
        else:
            raise ValueError(f'Politica desconocida: {nombre}')

        self.cola_max = int(self.get_parameter('cola_max').value)
        self.duracion = float(
            self.get_parameter('duracion_simulada_s').value
        )

        self.lock = threading.Lock()
        self.pendientes = []
        self.ejecutando = None
        self.detener = threading.Event()

        self.servidor = ActionServer(
            self,
            ProcesarObjeto,
            '/procesar_objeto_sim',
            goal_callback=self.goal_callback,
            handle_accepted_callback=self.handle_accepted_callback,
            cancel_callback=self.cancel_callback,
            execute_callback=self.execute_callback,
            callback_group=ReentrantCallbackGroup()
        )

        self.worker = threading.Thread(
            target=self.procesar_cola,
            daemon=True
        )
        self.worker.start()

        self.get_logger().info(
            f'Broker P2 SIM listo. Politica={self.politica.nombre}. '
            'Sin control fisico.'
        )

    def goal_callback(self, solicitud):
        if not solicitud.client_id.strip():
            return GoalResponse.REJECT

        if not solicitud.accion.strip():
            return GoalResponse.REJECT

        if not solicitud.objeto.strip():
            return GoalResponse.REJECT

        if not solicitud.color.strip():
            return GoalResponse.REJECT

        with self.lock:
            ocupados = len(self.pendientes)
            if self.ejecutando is not None:
                ocupados += 1

            if ocupados >= self.cola_max:
                return GoalResponse.REJECT

        return GoalResponse.ACCEPT

    def handle_accepted_callback(self, goal_handle):
        req = goal_handle.request

        pedido = PedidoObjeto(
            goal_handle=goal_handle,
            client_id=req.client_id,
            accion=req.accion,
            objeto=req.objeto,
            color=req.color,
            priority=int(req.priority)
        )

        with self.lock:
            self.pendientes.append(pedido)
            total = len(self.pendientes)

        self.get_logger().info(
            f'ENCOLADO cliente={pedido.client_id} '
            f'objeto={pedido.objeto} color={pedido.color} '
            f'prioridad={pedido.priority} pendientes={total}'
        )

    def cancel_callback(self, goal_handle):
        return CancelResponse.ACCEPT

    def procesar_cola(self):
        while not self.detener.is_set():
            pedido = None

            with self.lock:
                if self.ejecutando is None and self.pendientes:
                    indice = self.politica.siguiente(self.pendientes)

                    if indice is not None:
                        pedido = self.pendientes.pop(indice)
                        pedido.t_inicio_ejec = time.time()
                        self.ejecutando = pedido

            if pedido is None:
                self.detener.wait(0.02)
                continue

            self.get_logger().info(
                f'DESENCOLADO cliente={pedido.client_id} '
                f'prioridad={pedido.priority}'
            )

            try:
                pedido.goal_handle.execute()

                while not pedido.fin.wait(0.1):
                    if self.detener.is_set():
                        break

            except Exception as exc:
                self.get_logger().error(
                    f'Error del worker: {exc}'
                )
                try:
                    pedido.goal_handle.abort()
                except Exception:
                    pass
                pedido.fin.set()

            with self.lock:
                self.ejecutando = None

            self.politica.atendido(pedido)

    def execute_callback(self, goal_handle):
        with self.lock:
            pedido = self.ejecutando

        resultado = ProcesarObjeto.Result()

        if pedido is None or pedido.goal_handle is not goal_handle:
            resultado.success = False
            resultado.message = 'Pedido no seleccionado por el worker'
            goal_handle.abort()
            return resultado

        inicio = time.time()

        try:
            self.get_logger().info(
                f'VISION SIMULADA DESPUES DE DESENCOLAR: '
                f'{pedido.color}'
            )

            self.get_logger().info(
                f'IK Y MOVEIT 2: PENDIENTES DE INTEGRACION '
                f'para {pedido.objeto}'
            )

            while time.time() - inicio < self.duracion:
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    resultado.success = False
                    resultado.message = 'Cancelado'
                    resultado.wait_time_s = pedido.espera_s
                    resultado.exec_time_s = time.time() - inicio
                    return resultado

                feedback = ProcesarObjeto.Feedback()
                feedback.state = 'SIMULATING'
                feedback.queue_position = 0
                feedback.elapsed_s = time.time() - inicio
                goal_handle.publish_feedback(feedback)

                time.sleep(0.1)

            goal_handle.succeed()

            # Exito exclusivamente en el procesamiento simulado.
            # No equivale a un agarre fisico satisfactorio.
            resultado.success = True
            resultado.message = (
                'Simulacion logica completada. '
                'Vision, IK, MoveIt 2 y agarre fisico pendientes.'
            )
            resultado.wait_time_s = pedido.espera_s
            resultado.exec_time_s = time.time() - inicio

            return resultado

        finally:
            pedido.fin.set()


def main(args=None):
    rclpy.init(args=args)
    nodo = BrokerP2Sim()
    ejecutor = MultiThreadedExecutor(num_threads=4)
    ejecutor.add_node(nodo)

    try:
        ejecutor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        nodo.detener.set()
        nodo.worker.join(timeout=3.0)
        ejecutor.shutdown()
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
