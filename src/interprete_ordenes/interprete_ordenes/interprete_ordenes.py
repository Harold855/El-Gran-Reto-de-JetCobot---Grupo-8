"""Servicio ROS 2 de prueba para conectar P3 con P1 (sin LAYA).
No se debe utilizar para controlar físicamente el brazo.
"""

import re
import unicodedata

import rclpy
from rclpy.node import Node
from interprete_ordenes_interfaces.srv import InterpretarOrden


COLORES = r"\b(rojo|roja|verde|azul|amarillo|amarilla)\b"
VERBOS = r"\b(recoge|recoger|toma|tomar|agarra|agarrar|coloca|colocar|colocalo|pon|mueve|mover|lleva|llevar)\b"
PROHIBIDAS = r"\b(no|nunca|lanza|lanzar|golpea|golpear|ataca|atacar)\b"

COLORES_EQUIVALENTES = {
    "roja": "rojo",
    "amarilla": "amarillo"
}


def normalizar_texto(frase): #Convierte frases a minusculas y elimina tildes
    texto = unicodedata.normalize("NFD", frase.lower())
    return "".join(
        letra for letra in texto
        if unicodedata.category(letra) != "Mn"
    )

def clasificar_orden(frase):#Clasifica frases con reglas provisionales
    texto = normalizar_texto(frase)
    rechazo = ("", "cubo", "", "", 0, False, "Orden no reconocida")

    if re.search(PROHIBIDAS, texto): # Se rechazan instrucciones negativas o peligrosas
        return ("", "cubo", "", "", 0, False, "Orden negada o no permitida")

   
    zona = re.search(r"\bzona\b", texto)  #Se comprueba que exista una instrucción para mover un cubo

    if not zona or not re.search(r"\bcubos?\b", texto) or not re.search(VERBOS, texto):
        return rechazo

    #Se busca el color del cubo y el color del destino.
    objeto_encontrado = re.search(COLORES, texto[:zona.start()])
    destino_encontrado = re.search(COLORES, texto[zona.end():])

    if not objeto_encontrado or not destino_encontrado:
        return ("", "cubo", "", "", 0, False, "Falta color del cubo o destino")

    color = COLORES_EQUIVALENTES.get(
        objeto_encontrado.group(), objeto_encontrado.group()
    )

    destino = COLORES_EQUIVALENTES.get(
        destino_encontrado.group(), destino_encontrado.group()
    )

    return ("trasladar", "cubo", color, destino, 1, True, "Prueba sin LAYA")

class InterpreteOrdenes(Node):

    def __init__(self):
        super().__init__("interprete_ordenes")

        self.create_service(
            InterpretarOrden,
            "/interpretar_orden",
            self.atender_orden
        )

        self.get_logger().warn("Modo de prueba: LAYA no está conectado")

    def atender_orden(self, solicitud, respuesta):
        """Recibe una frase y devuelve la decisión."""

        (
            respuesta.accion,
            respuesta.objeto,
            respuesta.color,
            respuesta.destino,
            respuesta.prioridad,
            respuesta.permitido,
            respuesta.motivo
        ) = clasificar_orden(solicitud.frase)

        respuesta.degradado = True

        self.get_logger().info(
            f"Orden: {solicitud.frase} | Permitida: {respuesta.permitido}"
        )

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

