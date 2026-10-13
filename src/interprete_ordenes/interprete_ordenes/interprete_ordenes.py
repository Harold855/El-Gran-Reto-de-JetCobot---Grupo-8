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


# Clasificador por reglas (respaldo cuando LAYA no responde). Solo acepta UNA orden de pick and place de UN cubo: cubo de color + zona de color, con los 4 colores exactos. Todo se compara en minusculas y sin tildes. Ante la duda se RECHAZA.

COLORES = {
    "rojo": "rojo", "roja": "rojo",
    "verde": "verde",
    "azul": "azul",
    "amarillo": "amarillo", "amarilla": "amarillo",
}

# Otros colores y formas de "casi un color": no se aceptan.
COLORES_NO_ADMITIDOS = {
    "morado", "morada", "violeta", "purpura", "lila", "naranja", "anaranjado", "anaranjada",
    "blanco", "blanca", "negro", "negra", "gris", "rosa", "rosado", "rosada", "marron", "cafe",
    "celeste", "turquesa", "cian", "magenta", "fucsia", "dorado", "dorada", "plateado",
    "plateada", "beige", "crema", "oro", "plata", "rojizo", "rojiza", "azulado", "azulada",
    "azulino", "verdoso", "verdosa", "amarillento", "amarillenta", "granate", "vino",
}

NOMBRES_CUBO = {"cubo", "cubito", "bloque"}
NOMBRES_ZONA = {"zona", "area", "sector", "seccion", "region", "cuadrante"}
PLURALES = {"cubos", "cubitos", "bloques", "zonas", "areas", "sectores", "secciones",
            "regiones", "cuadrantes"}

OBJETOS_NO_CUBO = {
    "esfera", "esferas", "bola", "bolas", "pelota", "pelotas", "piramide", "piramides",
    "cilindro", "cilindros", "cono", "conos", "triangulo", "triangulos", "circulo",
    "rectangulo", "lapiz", "lapices", "marcador", "marcadores", "boligrafo", "lapicero",
    "plumon", "pluma", "regla", "taza", "vaso", "botella", "tornillo", "tuerca", "llave",
}


def _verbo(*formas): #Formas de un verbo, con o sin "lo"/"la" pegado (colocalo, ponlo, llevelo...)
    return r"(?:" + "|".join(formas) + r")(?:lo|la)?"


# Unicos verbos que significan "recoger y colocar"
VERBOS = _verbo(
    "recoge", "recoger", "recoja", "recojas", "toma", "tomar", "tome", "tomes",
    "agarra", "agarrar", "agarre", "agarres", "coge", "coger", "coja", "cojas",
    "levanta", "levantar", "levante", "levantes", "mueve", "mover", "mueva", "muevas",
    "lleva", "llevar", "lleve", "lleves", "coloca", "colocar", "coloque", "coloques",
    "pon", "poner", "ponga", "pongas", "traslada", "trasladar", "traslade", "trasladas",
    "transporta", "transportar", "transporte", "transportes", "deposita", "depositar",
    "deposite", "deposites", "deja", "dejar", "deje", "dejes", "ubica", "ubicar", "ubique",
    "situa", "situar", "situe", "transfiere", "transferir", "transfiera", "desplaza",
    "desplazar", "desplace", "guarda", "guardar", "guarde", "pasa", "pasar", "pase",
    "reubica", "reubicar", "reubique", "recoges", "tomas", "agarras", "coges", "levantas",
    "mueves", "llevas", "colocas", "pones", "trasladas", "transportas", "depositas", "dejas",
)

# Acciones que el robot no puede o no debe hacer
ACCIONES_NO_PERMITIDAS = _verbo(
    "lanza", "lanzar", "lance", "tira", "tirar", "tire", "golpea", "golpear", "golpee",
    "ataca", "atacar", "ataque", "patea", "patear", "empuja", "empujar", "empuje",
    "arrastra", "arrastrar", "rompe", "romper", "destruye", "destruir", "camina", "caminar",
    "corre", "correr", "salta", "saltar", "baila", "bailar", "gira", "girar", "rota",
    "rotar", "apaga", "apagar", "enciende", "encender", "abre", "abrir", "cierra", "cerrar",
    "regresa", "regresar", "vuelve", "volver", "retorna", "retornar", "descansa", "descansar",
)

# Negaciones y prohibiciones ("no", "nunca", "evita", "deja de", "detente"...)
PROHIBIDAS = (r"\b(?:no|nunca|jamas|ni|prohibido|prohibida|evita|evite|evitar|detente|"
              r"detener|cancela|cancelar|alto|stop|(?:deja|dejar|pare|para|deten\w*)\s+de)\b")

# Pedir otra cantidad, otra velocidad o cambiar un parametro: no se hace por voz
PARAMETROS = {
    "rapido", "rapida", "rapidamente", "lento", "lenta", "lentamente", "despacio", "deprisa",
    "aprisa", "velocidad", "fuerza", "suave", "suavemente", "cuidado", "cuidadosamente",
    "mas", "menos", "mayor", "menor", "aumenta", "aumentar", "reduce", "reducir", "acelera",
    "frena", "ajusta", "cambia", "configura", "modifica", "apila", "apilar", "apile",
    "suavidad", "delicadeza",
}
CANTIDADES = {"dos", "tres", "cuatro", "varios", "varias", "todos", "todas", "ambos",
              "ambas", "cada", "par"}
SECUENCIAS = {"luego", "despues", "ademas", "tambien", "posteriormente", "enseguida",
              "finalmente", "primero", "segundo", "siguiente"}
AMBIGUAS = {"o", "cualquier", "cualquiera", "algun", "alguno", "alguna", "algunos",
            "otro", "otra", "cercano", "cercana", "proximo", "proxima", "ultimo"}

# Urgencia expresada en la frase: no cambia el color y sube la prioridad (1 normal, 2 alta, 3 urgente)
URGENCIA = {"urgente", "urgentemente", "urgencia", "inmediato", "inmediata", "inmediatamente",
            "emergencia"}
PRIORIDAD_ALTA = {"prioritario", "prioritaria"}

# Palabras que pueden venir justo despues de un color sin cambiarlo
DESPUES_DE_COLOR = {"y", "e", "a", "al", "en", "hacia", "hasta", "sobre", "para", "por",
                    "favor", "ahora", "ya", "dentro", "encima", "con", "desde", "que", "el",
                    "la", "lo", "le", "un", "una", "gracias", "porfa", "porfavor", "please", "robot",
                    "jetcobot", "cobot", "ok", "vale"}


def normalizar_texto(frase): #Convierte frases a minusculas y elimina tildes
    texto = unicodedata.normalize("NFD", frase.lower())
    return "".join(
        letra for letra in texto
        if unicodedata.category(letra) != "Mn"
    )

MOTIVO_SIN_VERBO = "Orden no reconocida: solo se permite recoger y colocar cubos"

def rechazar(motivo): #Respuesta de rechazo: sin accion, sin colores y sin prioridad
    return ("", "cubo", "", "", 0, False, motivo)

def color_exacto(palabras, i): #El color no debe ir seguido de algo que lo cambie (rojo fuerte, azul marino...)
    if i + 1 >= len(palabras):
        return True
    siguiente = palabras[i + 1]
    if siguiente in DESPUES_DE_COLOR or siguiente in URGENCIA or re.fullmatch(VERBOS, siguiente):
        return True
    if siguiente == "es" and any(p in URGENCIA for p in palabras[i + 2:i + 4]): # "es urgente", "es una emergencia"
        return True
    return siguiente == "de" and palabras[i + 2:i + 3] in (["la"], ["el"], ["las"], ["los"])

def color_del_sustantivo(palabras, i): #Color de "cubo rojo", "cubo de color rojo" o "cubo color rojo"; None si no tiene
    resto = palabras[i + 1:i + 4]
    if resto[:1] in (["de"], ["del"]):
        resto = resto[1:]
    if resto[:1] == ["color"]:
        resto = resto[1:]
    return COLORES.get(resto[0]) if resto else None

def prioridad_por_palabras(palabras): #3 si pide urgencia, 2 si pide prioridad alta, 1 en cualquier otro caso
    if any(p in URGENCIA for p in palabras):
        return 3
    if any(p in PRIORIDAD_ALTA for p in palabras) or ("prioridad" in palabras and any(p in ("alta", "alto") for p in palabras)):
        return 2
    return 1

def clasificar_orden(frase):#Clasifica frases con reglas: solo acepta recoger UN cubo y colocarlo en UNA zona
    texto = normalizar_texto(frase)
    palabras = re.findall(r"[a-z]+", texto)

    if re.search(PROHIBIDAS, texto): # Se rechazan instrucciones negativas o prohibidas
        return rechazar("Orden negada o prohibida")

    if any(re.fullmatch(ACCIONES_NO_PERMITIDAS, p) for p in palabras):
        return rechazar("Acción no permitida: solo se puede recoger y colocar cubos")

    if any(p in OBJETOS_NO_CUBO for p in palabras):
        return rechazar("Objeto no admitido: solo se manipulan cubos")

    if any(p in COLORES_NO_ADMITIDOS for p in palabras):
        return rechazar("Color no reconocido: solo rojo, verde, azul o amarillo")

    for i, palabra in enumerate(palabras): # Rechaza variantes: rojo fuerte, azul marino, verde lima...
        if palabra in COLORES and not color_exacto(palabras, i):
            return rechazar("Color no reconocido: solo rojo, verde, azul o amarillo exactos")

    if (any(p in PLURALES or p in CANTIDADES or p in SECUENCIAS or p in AMBIGUAS for p in palabras)
            or sum(p in NOMBRES_CUBO for p in palabras) > 1
            or sum(p in NOMBRES_ZONA for p in palabras) > 1):
        return rechazar("Orden ambigua o con más de un cubo, zona u orden")

    if any(p in PARAMETROS for p in palabras):
        return rechazar("No se pueden cambiar parámetros por voz")

    if not any(re.fullmatch(VERBOS, p) for p in palabras):
        return rechazar(MOTIVO_SIN_VERBO)

    # Color del cubo y color de la zona (en cualquier orden de la frase)
    cubo = [i for i, p in enumerate(palabras) if p in NOMBRES_CUBO]
    zona = [i for i, p in enumerate(palabras) if p in NOMBRES_ZONA]

    if not cubo:
        return rechazar("Falta indicar el cubo")
    color = color_del_sustantivo(palabras, cubo[0])
    if color is None:
        return rechazar("Falta el color del cubo")
    if not zona:
        return rechazar("Falta la zona de destino")
    destino = color_del_sustantivo(palabras, zona[0])
    if destino is None:
        return rechazar("Falta el color de la zona")

    if sum(p in COLORES for p in palabras) != 2: # Un color para el cubo y uno para la zona, no mas
        return rechazar("Orden ambigua: debe haber un color de cubo y uno de zona")

    return ("trasladar", "cubo", color, destino, prioridad_por_palabras(palabras), True, "Prueba sin LAYA")

def colores_de_la_frase_coinciden(frase, color, destino): #Con verbos fuera del vocabulario de las reglas: comprueba que los colores de LAYA son los que la frase le asigna al cubo y a la zona
    palabras = re.findall(r"[a-z]+", normalizar_texto(frase))
    cubo = [i for i, p in enumerate(palabras) if p in NOMBRES_CUBO]
    zona = [i for i, p in enumerate(palabras) if p in NOMBRES_ZONA]
    if len(cubo) != 1 or len(zona) != 1 or sum(p in COLORES for p in palabras) != 2:
        return False
    return (color_del_sustantivo(palabras, cubo[0]), color_del_sustantivo(palabras, zona[0])) == (color, destino)

def prioridad_de_laya(decision, por_defecto=1): #Prioridad que dio LAYA (1, 2 o 3); si no dio una valida, la de las palabras (1 = normal)
    try:
        elegida = decision.respuestas_crudas["prioridad"]["choice"]
    except (KeyError, TypeError):
        return por_defecto
    return int(elegida) if elegida in ("1", "2", "3") else por_defecto

def decidir_con_laya(frase, decision, validacion_estricta=True, corregir_con_reglas=True):
    """Combina la decision de LAYA con la verificacion por reglas.

    Devuelve (permitido, accion, color, destino, prioridad, degradado, causa).

    validacion_estricta=False  -> se usa tal cual la decision de LAYA.
    corregir_con_reglas=False  -> comportamiento original: las reglas solo pueden VETAR.
    corregir_con_reglas=True   -> ademas corrigen los errores de LAYA que producian falsos negativos:
        * LAYA acepta pero se equivoca de color o destino -> se usan los de la frase;
        * LAYA deniega (dice no, prioridad "ninguna"...) y las reglas validan -> se acepta;
        * LAYA acepta y las reglas solo desconocen el verbo -> se acepta si los colores coinciden.
    Cuando la respuesta final ya no es pura de LAYA, degradado=True. Lo que LAYA respondio
    queda intacto en decision.respuestas_crudas y en el registro del nodo.
    """
    permitido = bool(decision.permitido)
    causa = decision.motivo  # Mismo concepto de 'causa' del companero.
    accion, color, destino = decision.accion, decision.color, decision.destino
    prioridad = decision.prioridad
    degradado = False

    if validacion_estricta:
        reglas = clasificar_orden(frase)
        if permitido:
            if not reglas[5]:
                if (corregir_con_reglas and reglas[6] == MOTIVO_SIN_VERBO
                        and colores_de_la_frase_coinciden(frase, color, destino)):
                    causa = "LAYA: orden validada (verbo fuera del vocabulario de las reglas)"
                else:
                    permitido = False
                    causa = 'Veto por reglas locales: ' + reglas[6]
            elif (color, destino) != (reglas[2], reglas[3]):
                if corregir_con_reglas:
                    color, destino = reglas[2], reglas[3]
                    degradado = True
                    causa = "LAYA se equivoco de color o destino; se usan los de la frase"
                else:
                    permitido = False
                    causa = 'Veto: color o destino de LAYA difiere de los identificados en la frase'
        elif corregir_con_reglas and reglas[5]:
            permitido = True
            accion, color, destino = "trasladar", reglas[2], reglas[3]
            prioridad = prioridad_de_laya(decision, reglas[4])
            degradado = True
            causa = f"La decision de LAYA no es utilizable (negada o incompleta) pero las reglas validan la orden; se usa el respaldo ({decision.motivo})"

    if not permitido:
        accion, color, destino, prioridad = "", "", "", 0
    return permitido, accion, color, destino, prioridad, degradado, causa

class InterpreteOrdenes(Node):
    """P1 del Grupo 8: servicio unico, LAYA HTTP y fallback de reglas.

    Conserva del companero:
      * clase InterpreteOrdenes, metodo procesar, atributo servicio;
      * parametros laya_url y laya_timeout;
      * UUID por solicitud y manejo try/except de LAYA.
    Conserva para P3 el contrato compilado interprete_ordenes_interfaces.
    """

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
