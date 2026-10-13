"""P1: servicio ROS 2 con LAYA y clasificador de respaldo.
No publica comandos al brazo, los movimientos dependen del broker RB-2.
"""

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

def rechazar(motivo): #Respuesta de rechazo: sin accion, sin colores y sin prioridad
    return ("", "cubo", "", "", 0, False, motivo)

def color_exacto(palabras, i): #El color no debe ir seguido de algo que lo cambie (rojo fuerte, azul marino...)
    if i + 1 >= len(palabras):
        return True
    siguiente = palabras[i + 1]
    if siguiente in DESPUES_DE_COLOR or re.fullmatch(VERBOS, siguiente):
        return True
    return siguiente == "de" and palabras[i + 2:i + 3] in (["la"], ["el"], ["las"], ["los"])

def color_del_sustantivo(palabras, i): #Color de "cubo rojo", "cubo de color rojo" o "cubo color rojo"; None si no tiene
    resto = palabras[i + 1:i + 4]
    if resto[:1] in (["de"], ["del"]):
        resto = resto[1:]
    if resto[:1] == ["color"]:
        resto = resto[1:]
    return COLORES.get(resto[0]) if resto else None

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
        return rechazar("Orden no reconocida: solo se permite recoger y colocar cubos")

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

    return ("trasladar", "cubo", color, destino, 1, True, "Prueba sin LAYA")

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

            permitido = bool(decision.permitido)
            causa = decision.motivo  # Mismo concepto de 'causa' del companero.
            if permitido and bool(self.get_parameter('validacion_estricta').value):
                reglas = clasificar_orden(request.frase)
                if not reglas[5]:
                    permitido = False
                    causa = 'Veto por reglas locales: ' + reglas[6]
                elif (decision.color, decision.destino) != (reglas[2], reglas[3]):
                    permitido = False
                    causa = 'Veto: color o destino de LAYA difiere de los identificados en la frase'

            datos = {
                'accion': decision.accion if permitido else '',
                'objeto': 'cubo',
                'color': decision.color if permitido else '',
                'destino': decision.destino if permitido else '',
                'prioridad': decision.prioridad if permitido else 0,
                'permitido': permitido,
                'degradado': False,  # Respuesta real, valida, recibida de LAYA.
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
