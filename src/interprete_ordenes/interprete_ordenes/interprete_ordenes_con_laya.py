"""Nodo P1 para pruebas con LAYA y respaldo keyword. NO publica comandos de brazo.

Ejecutar en lugar del nodo provisional, NUNCA en paralelo con el mismo servicio.
"""
import os
import time

import rclpy
from rclpy.node import Node
from interprete_ordenes_interfaces.srv import InterpretarOrden

from interprete_ordenes import clasificar_orden  # reutilizar 50/50 reglas, sin sustituirlas
from laya_cliente import ErrorLaya, consultar_laya_tipado


class InterpreteOrdenesConLaya(Node):
    def __init__(self):
        super().__init__("interprete_ordenes")
        self.declare_parameter("laya_url", os.getenv("LAYA_URL", "http://172.51.1.13:8000"))
        self.declare_parameter("laya_timeout_s", 4.0)
        self.declare_parameter("validacion_estricta", True)
        self.create_service(InterpretarOrden, "/interpretar_orden", self.atender)
        self.get_logger().info("P1: LAYA HTTP con respaldo por reglas, sin control fisico")

    def atender(self, solicitud, respuesta):
        t_inicio = time.perf_counter()
        try:
            decision = consultar_laya_tipado(
                solicitud.frase,
                url=self.get_parameter("laya_url").value,
                timeout=float(self.get_parameter("laya_timeout_s").value),
            )
            aprobado = decision.permitido
            motivo = decision.motivo
            # La decision original LAYA se registra independiente: no presentar
            # `aprobado` como exactitud pura del modelo cuando hay veto.
            if aprobado and bool(self.get_parameter("validacion_estricta").value):
                local = clasificar_orden(solicitud.frase)
                if not local[5]:
                    aprobado = False
                    motivo = "Veto del clasificador local: " + local[6]

            respuesta.accion = decision.accion if aprobado else ""
            respuesta.objeto = "cubo"
            respuesta.color = decision.color if aprobado else ""
            respuesta.destino = decision.destino if aprobado else ""
            respuesta.prioridad = decision.prioridad if aprobado else 0
            respuesta.permitido = aprobado
            respuesta.degradado = False  # hubo una respuesta LAYA valida
            respuesta.motivo = motivo
            # 0.0 significa inferencia no informada, no inferencia real de 0 ms.
            respuesta.tiempo_servidor_ms = float(decision.tiempo_servidor_ms or 0.0)
            self.get_logger().info(
                f"LAYA: permiso_bruto={decision.permitido_modelo}, "
                f"permiso_consistente={decision.permitido}, permiso_final={aprobado}; "
                f"modelo={decision.modelo_usado}; http_ms={decision.tiempo_http_ms:.2f}; "
                f"inferencia_ms={decision.tiempo_servidor_ms}"
            )
        except (ErrorLaya, ValueError) as exc:
            # Degradado significa respaldo, no autorizacion fisica.
            (respuesta.accion, respuesta.objeto, respuesta.color, respuesta.destino,
             respuesta.prioridad, respuesta.permitido, razon_local) = clasificar_orden(solicitud.frase)
            respuesta.degradado = True
            respuesta.motivo = f"Respaldo local por fallo LAYA: {exc}; {razon_local}"
            respuesta.tiempo_servidor_ms = 0.0
            self.get_logger().warn(f"No disponible LAYA; fallback keyword: {exc}")
        self.get_logger().info(
            f"P1: permitido={respuesta.permitido}, degradado={respuesta.degradado}, "
            f"tiempo_total_nodo_ms={(time.perf_counter()-t_inicio)*1000:.2f}"
        )
        return respuesta


def main():
    rclpy.init()
    nodo = InterpreteOrdenesConLaya()
    try:
        rclpy.spin(nodo)
    finally:
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()




