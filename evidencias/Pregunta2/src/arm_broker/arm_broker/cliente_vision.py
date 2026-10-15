# UNIVERSIDAD ESAN
# ROBÓTICA 08079
# EXAMEN PARCIAL - GRAN RETO JETCOBOT
# Grupo 7
# Integrantes:
# - Sebastian Pedro Aguirre Acosta
# - Anahi Cortez Chinchay
# - Ramirez Quevedo Karen Noelia
# - Vara Vargas Valentino Uziel

import os
import sys
import time
from datetime import datetime

import cv2 as cv
import numpy as np

import rclpy
from rclpy.node import Node

from arm_broker_interfaces.srv import InterpretarOrden


ANCHO_CAMARA = 640
ALTO_CAMARA = 480
AREA_MINIMA = 300.0

RANGOS_H = {
    'azul': (100, 130),
    'verde': (35, 85),
    'amarillo': (15, 35),
}

# Homografía cámara -> mesa.
# Entrada: píxeles (u, v)
# Salida: centímetros dentro de la zona de trabajo.
H_PIXEL_MESA = np.array([
    [-0.0102446220, -0.0125148108,  8.45884011],
    [-0.0079920344, -0.0073564273,  6.28700435],
    [-0.0010562924, -0.0015921233,  1.0]
], dtype=np.float64)


def pixel_a_mesa(u, v):
    punto = np.array(
        [[[float(u), float(v)]]],
        dtype=np.float32
    )

    convertido = cv.perspectiveTransform(
        punto,
        H_PIXEL_MESA
    )[0][0]

    x_cm = float(convertido[0])
    y_cm = float(convertido[1])

    # Corrección para la pose de observación definitiva.
    # Referencia medida:
    # pixel (387,259) -> centro real (65,85) mm.
    x_cm -= 0.50
    y_cm += 1.29

    return x_cm, y_cm



def mesa_a_pick_robot(x_mesa_mm, y_mesa_mm):
    """
    Convierte la posición del cubo dentro de la zona de trabajo
    a una posición cartesiana estimada para el PICK.

    IMPORTANTE:
    Estas coordenadas corresponden al sistema usado por PyMyCobot.
    Por ahora SOLO se calculan y muestran; no se envían al robot.
    """

    # Centro físico de la zona de trabajo 13 x 17 cm
    X_MESA_CENTRO = 65.0
    Y_MESA_CENTRO = 85.0

    # PICK conocido cuando el cubo está aproximadamente
    # sobre la cruz central.
    X_PICK_CENTRO = 240.1
    Y_PICK_CENTRO = 8.9
    Z_PICK = 135.7

    # Orientación probada en el código Pick & Place anterior
    RX_PICK = 173.01
    RY_PICK = 8.07
    RZ_PICK = -27.81

    dx_mesa = x_mesa_mm - X_MESA_CENTRO
    dy_mesa = y_mesa_mm - Y_MESA_CENTRO

    # En el tablero:
    # +X_robot va en sentido contrario al X usado
    # por nuestra coordenada de mesa.
    x_robot = X_PICK_CENTRO - dx_mesa

    # +Y_robot coincide provisionalmente con el
    # sentido vertical usado por la mesa.
    y_robot = Y_PICK_CENTRO + dy_mesa

    return {
        "x": x_robot,
        "y": y_robot,
        "z": Z_PICK,
        "rx": RX_PICK,
        "ry": RY_PICK,
        "rz": RZ_PICK,
    }


class ClienteVision(Node):

    def __init__(self):
        super().__init__('cliente_vision')

        self.interprete = self.create_client(
            InterpretarOrden,
            '/interpretar_orden'
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

    def crear_mascara(self, hsv, color):
        color = color.lower()

        if color == 'rojo':
            # El rojo ocupa dos extremos del espacio HSV.
            mask1 = cv.inRange(
                hsv,
                np.array([0, 80, 80]),
                np.array([10, 255, 255])
            )

            mask2 = cv.inRange(
                hsv,
                np.array([165, 80, 80]),
                np.array([179, 255, 255])
            )

            return cv.bitwise_or(mask1, mask2)

        if color not in RANGOS_H:
            return None

        h_min, h_max = RANGOS_H[color]

        return cv.inRange(
            hsv,
            np.array([h_min, 80, 80]),
            np.array([h_max, 255, 255])
        )

    def detectar_color(self, frame, color_objetivo):
        hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)

        mask = self.crear_mascara(
            hsv,
            color_objetivo
        )

        if mask is None:
            return None

        kernel = np.ones((5, 5), np.uint8)

        mask = cv.morphologyEx(
            mask,
            cv.MORPH_OPEN,
            kernel
        )

        mask = cv.morphologyEx(
            mask,
            cv.MORPH_CLOSE,
            kernel
        )

        contornos, _ = cv.findContours(
            mask,
            cv.RETR_EXTERNAL,
            cv.CHAIN_APPROX_SIMPLE
        )

        if not contornos:
            return None

        contorno = max(
            contornos,
            key=cv.contourArea
        )

        area = cv.contourArea(contorno)

        if area < AREA_MINIMA:
            return None

        momentos = cv.moments(contorno)

        if momentos['m00'] == 0:
            return None

        cx = int(
            momentos['m10'] /
            momentos['m00']
        )

        cy = int(
            momentos['m01'] /
            momentos['m00']
        )

        x, y, w, h = cv.boundingRect(contorno)

        centro_x = frame.shape[1] // 2
        centro_y = frame.shape[0] // 2

        dx_px = cx - centro_x
        dy_px = centro_y - cy

        return {
            'color': color_objetivo.lower(),
            'cx': cx,
            'cy': cy,
            'dx_px': dx_px,
            'dy_px': dy_px,
            'area': float(area),
            'x': x,
            'y': y,
            'w': w,
            'h': h,
        }

    def localizar(self, color_objetivo):
        color_objetivo = color_objetivo.lower()

        colores_validos = {
            'rojo',
            'verde',
            'azul',
            'amarillo'
        }

        if color_objetivo not in colores_validos:
            self.get_logger().error(
                f'Color no soportado para visión: '
                f'{color_objetivo}'
            )
            return None

        cap = cv.VideoCapture(
            '/dev/video0',
            cv.CAP_V4L2
        )

        cap.set(
            cv.CAP_PROP_FRAME_WIDTH,
            ANCHO_CAMARA
        )

        cap.set(
            cv.CAP_PROP_FRAME_HEIGHT,
            ALTO_CAMARA
        )

        if not cap.isOpened():
            self.get_logger().error(
                'No se pudo abrir /dev/video0'
            )
            return None

        # Descartar algunos frames iniciales para estabilizar
        # exposición y balance de la cámara.
        for _ in range(8):
            cap.read()
            time.sleep(0.03)

        mejor = None
        mejor_frame = None
        ultimo_frame = None

        # Buscar durante varios frames y conservar
        # la detección de mayor área.
        for _ in range(40):
            ok, frame = cap.read()

            if not ok:
                continue

            ultimo_frame = frame.copy()

            deteccion = self.detectar_color(
                frame,
                color_objetivo
            )

            if deteccion is not None:
                if (
                    mejor is None or
                    deteccion['area'] > mejor['area']
                ):
                    mejor = deteccion
                    mejor_frame = frame.copy()

            time.sleep(0.03)

        cap.release()

        frame_evidencia = (
            mejor_frame
            if mejor_frame is not None
            else ultimo_frame
        )

        if frame_evidencia is not None:
            if mejor is not None:
                x = mejor['x']
                y = mejor['y']
                w = mejor['w']
                h = mejor['h']
                cx = mejor['cx']
                cy = mejor['cy']

                cv.rectangle(
                    frame_evidencia,
                    (x, y),
                    (x + w, y + h),
                    (255, 255, 255),
                    2
                )

                cv.circle(
                    frame_evidencia,
                    (cx, cy),
                    6,
                    (255, 255, 255),
                    -1
                )

                texto = (
                    f"{color_objetivo.upper()} "
                    f"({cx},{cy})"
                )

                cv.putText(
                    frame_evidencia,
                    texto,
                    (20, 30),
                    cv.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )

            carpeta = os.path.expanduser(
                '~/ros2_ws/evidencias_p2'
            )

            os.makedirs(
                carpeta,
                exist_ok=True
            )

            timestamp = datetime.now().strftime(
                '%Y%m%d_%H%M%S'
            )

            ruta = os.path.join(
                carpeta,
                f'vision_{color_objetivo}_{timestamp}.jpg'
            )

            cv.imwrite(
                ruta,
                frame_evidencia
            )

            self.get_logger().info(
                f'Evidencia guardada: {ruta}'
            )

        return mejor


def main(args=None):
    rclpy.init(args=args)

    nodo = ClienteVision()

    try:
        if len(sys.argv) < 2:
            nodo.get_logger().error(
                'Uso: ros2 run arm_broker cliente_vision '
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

        # Una orden prohibida se elimina antes de realizar
        # cualquier etapa posterior del pipeline.
        if not decision.permitido:
            nodo.get_logger().warn(
                'ORDEN RECHAZADA. '
                'No se ejecutará visión ni /move_arm.'
            )
            return

        nodo.get_logger().info(
            f'Buscando específicamente color='
            f'{decision.color}'
        )

        deteccion = nodo.localizar(
            decision.color
        )

        print()
        print('========================================')
        print('LOCALIZACIÓN P2')
        print('========================================')

        if deteccion is None:
            print('Detectado:   False')
            print(f'Objetivo:    {decision.color}')
            print('========================================')

            nodo.get_logger().warn(
                'No se encontró el color solicitado.'
            )
            return

        print('Detectado:   True')
        print(f'Color:       {deteccion["color"]}')
        print(
            f'Centro px:   '
            f'({deteccion["cx"]}, '
            f'{deteccion["cy"]})'
        )
        print(
            f'Offset px:   '
            f'dx={deteccion["dx_px"]}, '
            f'dy={deteccion["dy_px"]}'
        )
        print(
            f'Área:        '
            f'{deteccion["area"]:.1f} px²'
        )

        x_cm, y_cm = pixel_a_mesa(
            deteccion["cx"],
            deteccion["cy"]
        )

        print(
            f'Posición:    '
            f'X={x_cm:.2f} cm, '
            f'Y={y_cm:.2f} cm'
        )
        x_mesa_mm = x_cm * 10.0
        y_mesa_mm = y_cm * 10.0

        print(
            f'Posición mm: '
            f'X={x_mesa_mm:.1f} mm, '
            f'Y={y_mesa_mm:.1f} mm'
        )

        pick = mesa_a_pick_robot(
            x_mesa_mm,
            y_mesa_mm
        )

        print(
            f'PICK estimado: '
            f'X={pick["x"]:.1f} mm, '
            f'Y={pick["y"]:.1f} mm, '
            f'Z={pick["z"]:.1f} mm'
        )

        print(
            f'Orientación:  '
            f'Rx={pick["rx"]:.2f}°, '
            f'Ry={pick["ry"]:.2f}°, '
            f'Rz={pick["rz"]:.2f}°'
        )

        print('========================================')
        print()

        nodo.get_logger().info(
            'MODO SOLO VISIÓN: '
            'NO se enviará ningún goal a /move_arm.'
        )

    finally:
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
