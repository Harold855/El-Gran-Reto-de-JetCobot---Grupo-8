"""P1: servicio ROS 2 con LAYA y clasificador de respaldo.
No publica comandos al brazo, los movimientos dependen del broker RB-2.
"""

import json
import os
import re
import time
import uuid
import unicodedata

import rclpy
from rclpy.node import Node
from interprete_ordenes_interfaces.srv import InterpretarOrden
from laya_cliente import ErrorLaya, consultar_laya_tipado


# Clasificador por reglas (respaldo de LAYA). Acepta una orden BASICA de pick and place: un verbo de
# recoger/colocar, "cubo <color>" y "zona <color>" con rojo, verde, azul o amarillo. Se compara en
# minusculas y sin tildes. Ante la duda se RECHAZA. Los cubos en plural, otros objetos y otros colores
# se rechazan solos: no hay "cubo <color>" ni "zona <color>" validos.

COLORES = {
    "rojo": "rojo", "roja": "rojo",
    "verde": "verde",
    "azul": "azul",
    "amarillo": "amarillo", "amarilla": "amarillo",
}

# Verbos de recoger y colocar (con "lo"/"la" pegado: colocalo, ponlo...)
VERBOS = r"(?:recoge|recoger|toma|tomar|agarra|agarrar|coloca|colocar|pon|poner|mueve|mover|lleva|llevar|traslada|trasladar)(?:lo|la)?"

# Negaciones y acciones que el brazo no puede o no debe hacer
PROHIBIDAS = r"no|nunca|ni|evita|lanza|lanzar|golpea|golpear|ataca|atacar|tira|tirar|camina|caminar|salta|saltar|gira|girar|apila|apilar"

# Lo que convierte un color en otro ("rojo fuerte", "azul marino"): no se acepta
VARIANTES = {"claro", "oscuro", "fuerte", "marino", "lima", "pastel", "cielo", "brillante"}


def normalizar_texto(frase): #Convierte frases a minusculas y elimina tildes
    texto = unicodedata.normalize("NFD", frase.lower())
    return "".join(
        letra for letra in texto
        if unicodedata.category(letra) != "Mn"
    )

def rechazar(motivo): #Respuesta de rechazo: sin accion, sin colores y sin prioridad
    return ("", "cubo", "", "", 0, False, motivo)

def color_de(palabras, sustantivo): #Color que sigue a "cubo" o "zona" ("cubo rojo", "zona de color verde"); None si no hay
    if sustantivo not in palabras:
        return None
    resto = palabras[palabras.index(sustantivo) + 1:][:4]
    if resto[:2] == ["de", "color"]:
        resto = resto[2:]
    if not resto or resto[0] not in COLORES or resto[1:2] and resto[1] in VARIANTES:
        return None
    return COLORES[resto[0]]

def clasificar_orden(frase):#Clasifica frases con reglas: orden basica de recoger UN cubo y colocarlo en UNA zona
    palabras = re.findall(r"[a-z]+", normalizar_texto(frase))

    if any(re.fullmatch(PROHIBIDAS, p) for p in palabras):
        return rechazar("Orden negada o accion no permitida")

    if not any(re.fullmatch(VERBOS, p) for p in palabras):
        return rechazar("Orden no reconocida: solo se permite recoger y colocar cubos")

    color = color_de(palabras, "cubo")
    if color is None:
        return rechazar("Falta el cubo o su color (rojo, verde, azul o amarillo)")

    destino = color_de(palabras, "zona")
    if destino is None:
        return rechazar("Falta la zona de destino o su color (rojo, verde, azul o amarillo)")

    return ("trasladar", "cubo", color, destino, 1, True, "Prueba sin LAYA")

def decidir_con_laya(frase, decision, validacion_estricta=True, corregir_con_reglas=True):
    """Combina la decision de LAYA con las reglas. Devuelve (permitido, accion, color, destino, prioridad, degradado, causa).

    validacion_estricta=False  -> se usa tal cual la decision de LAYA.
    corregir_con_reglas=False  -> las reglas solo pueden VETAR (comportamiento original).
    corregir_con_reglas=True   -> ademas corrigen los falsos negativos de LAYA: si se equivoca de color o
                                  destino se usan los de la frase, y si niega una orden que las reglas validan se acepta.
    Cuando la respuesta final ya no es pura de LAYA, degradado=True. Lo que LAYA dijo queda en decision.respuestas_crudas.
    """
    permitido, causa = bool(decision.permitido), decision.motivo
    accion, color, destino, prioridad = decision.accion, decision.color, decision.destino, decision.prioridad
    degradado = False

    if validacion_estricta:
        reglas = clasificar_orden(frase)
        if permitido and not reglas[5]:                        # LAYA acepta y las reglas rechazan: veto
            permitido, causa = False, 'Veto por reglas locales: ' + reglas[6]
        elif permitido and (color, destino) != (reglas[2], reglas[3]):  # LAYA se equivoco de color o destino
            if corregir_con_reglas:
                color, destino, degradado = reglas[2], reglas[3], True
                causa = "LAYA se equivoco de color o destino; se usan los de la frase"
            else:
                permitido, causa = False, 'Veto: color o destino de LAYA difiere de los identificados en la frase'
        elif not permitido and reglas[5] and corregir_con_reglas:       # LAYA niega y las reglas validan
            elegida = decision.respuestas_crudas.get("prioridad", {}).get("choice")
            permitido, accion, color, destino, degradado = True, "trasladar", reglas[2], reglas[3], True
            prioridad = int(elegida) if elegida in ("1", "2", "3") else 1
            causa = f"La decision de LAYA no es utilizable; las reglas validan la orden ({decision.motivo})"

    if not permitido:
        accion, color, destino, prioridad = "", "", "", 0
    return permitido, accion, color, destino, prioridad, degradado, causa

class InterpreteOrdenes(Node):
    """P1 del Grupo 8: servicio unico, LAYA HTTP y fallback de reglas.

    def __init__(self):
        super().__init__('interprete_ordenes')
        # Mantener los nombres de parametros que ya usa el integrante P1.
        # No fijar la IP del laboratorio en codigo: exportar LAYA_URL en la terminal.
        self.declare_parameter('laya_url', os.getenv('LAYA_URL', 'http://127.0.0.1:8765'))
        self.declare_parameter('laya_timeout', 4.0)
        self.declare_parameter('validacion_estricta', True)
        # True: las reglas tambien CORRIGEN errores de LAYA (falsos negativos). False: solo vetan, como antes.
        # Para medir la exactitud pura de LAYA usar False y revisar las respuestas crudas del registro.
        self.declare_parameter('corregir_con_reglas', True)
        self.servicio = self.create_service(
            InterpretarOrden,
            '/interpretar_orden',
            self.procesar,
        )
        self.get_logger().info('Servicio listo: LAYA principal y palabras clave de respaldo')

    def procesar(self, request, response):
        # El UUID se mantiene en logs sin alterar el .srv usado por P3.
        request_id = str(uuid.uuid4())
        inicio = time.perf_counter()
        try:
            decision = consultar_laya_tipado(
                request.frase,
                url=self.get_parameter('laya_url').value,
                timeout=float(self.get_parameter('laya_timeout').value),
            )

            permitido, accion, color, destino, prioridad, degradado, causa = decidir_con_laya(
                request.frase,
                decision,
                validacion_estricta=bool(self.get_parameter('validacion_estricta').value),
                corregir_con_reglas=bool(self.get_parameter('corregir_con_reglas').value),
            )
            datos = {
                'accion': accion,
                'objeto': 'cubo',
                'color': color,
                'destino': destino,
                'prioridad': prioridad,
                'permitido': permitido,
                'degradado': degradado,  # False = respuesta de LAYA tal cual; True = corregida por las reglas.
                'causa': causa,
                'tiempo_servidor_ms': float(decision.tiempo_servidor_ms or 0.0),
            }
            self.get_logger().info(
                f'[{request_id}] LAYA respondio en {decision.tiempo_http_ms:.2f} ms; '
                f'modelo={decision.modelo_usado}; '
                f'permitido_modelo={decision.permitido_modelo}; '
                f'permitido_final={permitido}; '
                f'inferencia_ms={decision.tiempo_servidor_ms}'
            )
            self.get_logger().info(
                f'[{request_id}] respuestas_laya='
                + json.dumps({k: v.get('choice') for k, v in decision.respuestas_crudas.items()
                              if isinstance(v, dict)}, ensure_ascii=False)
            )
            # Importante para el informe: permitido_modelo y respuestas_crudas son
            # del modelo; permitido_final puede incluir veto local. No mezclarlos.

        except (ErrorLaya, ValueError) as e:
            accion, objeto, color, destino, prioridad, permitido, causa_local = clasificar_orden(request.frase)
            datos = {
                'accion': accion,
                'objeto': objeto,
                'color': color,
                'destino': destino,
                'prioridad': prioridad,
                'permitido': permitido,
                'degradado': True,
                'causa': f'Respaldo local por fallo de LAYA: {e}; {causa_local}',
                # 0.0 = no informado por LAYA; NO es medicion de 0 ms.
                'tiempo_servidor_ms': 0.0,
            }
            self.get_logger().warn(f'[{request_id}] LAYA fallo, usando fallback: {e}')

        # Mantener el .srv real de P3: motivo (no causa), sin request_id.
        response.accion = datos['accion']
        response.objeto = datos['objeto']
        response.color = datos['color']
        response.destino = datos['destino']
        response.prioridad = datos['prioridad']
        response.permitido = datos['permitido']
        response.degradado = datos['degradado']
        response.motivo = datos['causa']
        response.tiempo_servidor_ms = datos['tiempo_servidor_ms']

        self.get_logger().info(
            f'[{request_id}] Orden recibida: {request.frase!r}; '
            f'permitido={response.permitido}, degradado={response.degradado}, '
            f'duracion_nodo_ms={(time.perf_counter() - inicio) * 1000:.2f}'
        )
        return response

    # Alias de compatibilidad para llamadas de prueba anteriores (atender_orden = procesar)

def main(args=None):
    rclpy.init(args=args)
    nodo = InterpreteOrdenes()
    try:
        rclpy.spin(nodo)
    finally:
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
