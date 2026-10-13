"""Servicio ROS 2 de prueba para conectar P3 con P1 (sin LAYA).
No se debe utilizar para controlar físicamente el brazo.
"""

import re
import time
import unicodedata

import rclpy
from rclpy.node import Node
from interprete_ordenes_interfaces.srv import InterpretarOrden


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

def color_del_sustantivo(palabras, i): #Color de "cubo rojo", "cubo de color rojo" o "cubo color rojo", None si no tiene
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

        inicio = time.perf_counter()
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
        # Tiempo que tardó el servidor en decidir (sin la red). Con LAYA, informar el cálculo del propio servidor.
        respuesta.tiempo_servidor_ms = (time.perf_counter() - inicio) * 1000

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
