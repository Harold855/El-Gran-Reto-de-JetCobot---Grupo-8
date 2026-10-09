"""Servicio ROS 2 provisional para probar la conexion P3 -> P1.

IMPORTANTE: usa reglas de prueba, NO LAYA. No usar para controlar
fisicamente el brazo hasta completar y validar la Pregunta 1.
"""

import re
import unicodedata

import rclpy
from rclpy.node import Node
from interprete_ordenes_interfaces.srv import InterpretarOrden


COLORES = r"\b(rojo|roja|verde|azul|amarillo|amarilla)\b"
CANONICOS = {"roja": "rojo", "amarilla": "amarillo"}
VERBOS = r"\b(recoge|recoger|toma|tomar|agarra|agarrar|coloca|colocar|pon|mueve|mover|lleva|llevar)\b"


def normalizar(texto):
    """Quita tildes y pasa a minusculas para comparar palabras."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(letra for letra in texto if unicodedata.category(letra) != "Mn")


def interpretar_prueba(frase):
    """Devuelve accion, objeto, color, destino y permiso (solo simulacion)."""
    texto = normalizar(frase)
    resultado = ("", "cubo", "", "", 0, False, "Orden no reconocida")

    if re.search(r"\b(no|nunca|lanza|lanzar|golpea|golpear|ataca|atacar)\b", texto):
        return ("", "cubo", "", "", 0, False, "Orden negada o no permitida")

    if "zona" not in texto or not re.search(VERBOS, texto):
        return resultado

    antes, despues = texto.split("zona", 1)
    color_objeto = re.search(COLORES, antes)
    color_destino = re.search(COLORES, despues)

    if not color_objeto or not color_destino:
        return ("", "cubo", "", "", 0, False, "Falta color de objeto o destino")

    objeto = CANONICOS.get(color_objeto.group(1), color_objeto.group(1))
    destino = CANONICOS.get(color_destino.group(1), color_destino.group(1))
    return ("trasladar", "cubo", objeto, destino, 1, True,
            "Clasificacion de prueba (sin LAYA)")


class InterpreteOrdenes(Node):
    def __init__(self):
        super().__init__("interprete_ordenes")
        self.create_service(InterpretarOrden, "/interpretar_orden", self.interpretar_orden)
        self.get_logger().warn("Modo de prueba: aun NO se consulta LAYA")

    def interpretar_orden(self, solicitud, respuesta):
        (respuesta.accion, respuesta.objeto, respuesta.color,
         respuesta.destino, respuesta.prioridad, respuesta.permitido,
         respuesta.motivo) = interpretar_prueba(solicitud.frase)
        respuesta.degradado = True
        self.get_logger().info(f"Orden: {solicitud.frase} | Permitida: {respuesta.permitido}")
        return respuesta


def main():
    rclpy.init()
    nodo = InterpreteOrdenes()
    try:
        rclpy.spin(nodo)
    finally:
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
