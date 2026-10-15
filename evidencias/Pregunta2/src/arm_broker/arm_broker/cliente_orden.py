# UNIVERSIDAD ESAN
# ROBÓTICA 08079
# EXAMEN PARCIAL - GRAN RETO JETCOBOT
# Grupo 7
# Integrantes:
# - Sebastian Pedro Aguirre Acosta
# - Anahi Cortez Chinchay
# - Ramirez Quevedo Karen Noelia
# - Vara Vargas Valentino Uziel

import sys

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from arm_broker_interfaces.srv import InterpretarOrden
from arm_broker_interfaces.action import MoveArm


class ClienteOrden(Node):

    def __init__(self):
        super().__init__('cliente_orden')

        self.interprete = self.create_client(
            InterpretarOrden,
            '/interpretar_orden'
        )

        self.move_arm = ActionClient(
            self,
            MoveArm,
            '/move_arm'
        )

    def interpretar(self, frase):
        self.get_logger().info(
            f'Orden recibida: "{frase}"'
        )

        if not self.interprete.wait_for_service(timeout_sec=5.0):
            self.get_logger().error(
                'Servicio /interpretar_orden no disponible'
            )
            return None

        request = InterpretarOrden.Request()
        request.frase = frase

        future = self.interprete.call_async(request)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is None:
            self.get_logger().error(
                'No se recibió respuesta de /interpretar_orden'
            )
            return None

        return future.result()

    def enviar_broker(self, decision):
        if not self.move_arm.wait_for_server(timeout_sec=5.0):
            self.get_logger().error(
                'Action server /move_arm no disponible'
            )
            return

        goal = MoveArm.Goal()

        # Pose pequeña usada únicamente para verificar
        # la integración P1 -> broker.
        goal.joint_positions = [
            0.1,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0
        ]

        goal.client_id = 'cliente_orden'

        # CRÍTICO:
        # La prioridad viene directamente de LAYA/P1.
        goal.priority = int(decision.prioridad)

        self.get_logger().info(
            f'Enviando al broker con prioridad={goal.priority}'
        )

        future_goal = self.move_arm.send_goal_async(
            goal,
            feedback_callback=self.feedback_callback
        )

        rclpy.spin_until_future_complete(self, future_goal)

        goal_handle = future_goal.result()

        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error(
                'El broker rechazó el goal'
            )
            return

        self.get_logger().info(
            'Goal aceptado por arm_broker'
        )

        future_resultado = goal_handle.get_result_async()

        rclpy.spin_until_future_complete(
            self,
            future_resultado
        )

        resultado = future_resultado.result().result

        self.get_logger().info(
            'Resultado broker: '
            f'success={resultado.success}, '
            f'wait={resultado.wait_time_s:.3f}s, '
            f'exec={resultado.exec_time_s:.3f}s, '
            f'mensaje="{resultado.message}"'
        )

    def feedback_callback(self, mensaje):
        fb = mensaje.feedback

        self.get_logger().info(
            f'Broker: estado={fb.state} '
            f'cola={fb.queue_position} '
            f't={fb.elapsed_s:.2f}s'
        )


def main(args=None):
    rclpy.init(args=args)

    nodo = ClienteOrden()

    try:
        if len(sys.argv) < 2:
            nodo.get_logger().error(
                'Uso: ros2 run arm_broker cliente_orden '
                '"frase de prueba"'
            )
            return

        frase = ' '.join(sys.argv[1:])

        decision = nodo.interpretar(frase)

        if decision is None:
            return

        print()
        print('========================================')
        print('DECISIÓN P1')
        print('========================================')
        print(f'Acción:     {decision.accion}')
        print(f'Objeto:     {decision.objeto}')
        print(f'Color:      {decision.color}')
        print(f'Prioridad:  {decision.prioridad}')
        print(f'Permitido:  {decision.permitido}')
        print(f'Método:     {decision.metodo}')
        print(f'Degradado:  {decision.degradado}')
        print('========================================')
        print()

        # REQUISITO CRÍTICO DE P2:
        # La orden prohibida se descarta ANTES de /move_arm.
        if not decision.permitido:
            nodo.get_logger().warn(
                'ORDEN RECHAZADA ANTES DE LA COLA. '
                'No se enviará ningún goal a /move_arm.'
            )
            return

        nodo.enviar_broker(decision)

    finally:
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
