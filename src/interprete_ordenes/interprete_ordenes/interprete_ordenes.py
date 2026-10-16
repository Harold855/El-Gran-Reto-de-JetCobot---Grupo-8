"""P1 Grupo 8: servicio ROS 2 de interpretación con LAYA y respaldo local.

No envía movimientos al brazo. El cliente P3 debe exigir:
permitido=True, degradado=False y una orden compatible con P2.
"""

import json
import os
import re
import time
import unicodedata
import uuid

import rclpy
from rclpy.node import Node
from interprete_ordenes_interfaces.srv import InterpretarOrden

try:
    from interprete_ordenes.laya_cliente import ErrorLaya, consultar_laya_tipado
except ModuleNotFoundError as exc:
    if exc.name not in ("interprete_ordenes", "interprete_ordenes.laya_cliente"):
        raise
    from laya_cliente import ErrorLaya, consultar_laya_tipado

COLORES = {
    "rojo": "rojo", "roja": "rojo", "verde": "verde",
    "azul": "azul", "amarillo": "amarillo", "amarilla": "amarillo",
}
CUBOS = {"cubo", "cubito", "bloque"}
ZONAS = {"zona", "area", "sector", "seccion", "region", "cuadrante"}
VERBOS = set("""
    recoge recoger recoja recojas coge coger coja cojas toma tomar tome tomes
    agarra agarrar agarre agarres mueve mover mueva muevas lleva llevar lleve lleves
    traslada trasladar traslade transporta transportar transporte coloca colocar
    coloque coloques pon poner ponga pongas deja dejar deje dejes deposita
    depositar deposite ubica ubicar ubique situa situar situe reubica reubicar
    reubique levanta levantar levante levantes sujeta sujetar sujete
""".split())
PROHIBIDAS = set("""
    no nunca jamas ni sin evita evitar evite detente alto stop cancela cancelar
    prohibido prohibida tampoco lanza lanzar tira tirar golpea golpear ataca atacar
    empuja empujar arrastra arrastrar rompe romper camina caminar salta saltar
    gira girar apila apilar enciende apaga abre cierra
""".split())
PARAMETROS = set("""
    mas menos rapido rapida rapidamente despacio lento lenta lentamente velocidad
    fuerza acelera frena aumenta reduce ajusta configura modifica cambia deprisa aprisa
""".split())
AMBIGUAS = set("""
    o otro otra otros otras varios varias todos todas ambos ambas cualquier cualquiera
    algun alguna dos tres cuatro 2 3 4 luego despues ademas tambien primero segundo
    cubos cubitos bloques zonas areas sectores secciones regiones cuadrantes
""".split())
INVALIDOS = set("""
    esfera esferas bola bolas pelota pelotas piramide piramides cilindro cilindros
    lapiz lapices marcador marcadores botella morado morada violeta naranja
    blanco blanca negro negra gris rosa marron celeste turquesa cian
    fuerte marino lima claro clara oscuro oscura pastel brillante militar neon fluorescente
""".split())


def normalizar_texto(frase):
    texto = unicodedata.normalize("NFD", (frase or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def rechazar(motivo):
    return ("", "cubo", "", "", 0, False, motivo)


def es_verbo(palabra):
    if palabra in VERBOS:
        return True
    return any(palabra.endswith(sufijo) and palabra[:-len(sufijo)] in VERBOS
               for sufijo in ("lo", "la"))


def extraer_color(palabras, indice):
    """Admite 'cubo rojo', 'cubo de color rojo', 'zona de color verde'."""
    resto = palabras[indice + 1:indice + 5]
    if resto and resto[0] in ("de", "del"):
        resto = resto[1:]
    if resto and resto[0] == "color":
        resto = resto[1:]
    return COLORES.get(resto[0]) if resto else None


def clasificar_orden(frase):
    palabras = re.findall(r"[a-z]+|[0-9]+", normalizar_texto(frase))
    if not palabras:
        return rechazar("Orden vacia")

    texto = " ".join(palabras)
    if re.search(r"\b(?:deja|dejar|deje|para|pare|deten) de\b", texto):
        return rechazar("Orden negada")
    if any(p in PROHIBIDAS for p in palabras):
        return rechazar("Orden negada o accion no permitida")
    if any(p in PARAMETROS for p in palabras):
        return rechazar("No se permite modificar parametros por voz")
    if any(p in AMBIGUAS for p in palabras):
        return rechazar("Orden ambigua o multiple")
    if any(p in INVALIDOS for p in palabras):
        return rechazar("Objeto o color no admitido")

    indices_cubo = [i for i, p in enumerate(palabras) if p in CUBOS]
    indices_zona = [i for i, p in enumerate(palabras) if p in ZONAS]
    if len(indices_cubo) != 1 or len(indices_zona) != 1:
        return rechazar("Se requiere exactamente un cubo y una zona")
    if not 1 <= sum(es_verbo(p) for p in palabras) <= 2:
        return rechazar("Orden no reconocida o con acciones adicionales")

    color = extraer_color(palabras, indices_cubo[0])
    destino = extraer_color(palabras, indices_zona[0])
    if not color or not destino:
        return rechazar("Falta color exacto del cubo o de la zona")
    if sum(p in COLORES for p in palabras) != 2:
        return rechazar("Orden ambigua: debe haber solo dos colores")

    return ("trasladar", "cubo", color, destino, 1, True, "Reglas locales")



def decidir_con_laya(frase, decision, validacion_estricta=True,
                      corregir_con_reglas=False):
    """
    Integracion segura de LAYA con validacion local.

    LAYA:
      - Autoriza o rechaza
      - Clasifica la accion
      - Determina prioridad

    Reglas:
      - Verifican la frase
      - Identifican color del cubo y zona de entrega
      - Rechazan ambiguedades y colores invalidos

    Las respuestas originales de LAYA permanecen disponibles
    en decision.respuestas_crudas para la evaluacion de exactitud.
    """

    reglas = clasificar_orden(frase)

    accion_local, objeto_local, color_local, destino_local,         _, permiso_local, motivo_local = reglas

    crudas = decision.respuestas_crudas

    def opcion(nombre):
        entrada = crudas.get(nombre, {})
        return entrada.get("choice") if isinstance(entrada, dict) else None

    permiso_modelo = bool(decision.permitido_modelo)
    accion_modelo = opcion("accion")
    prioridad_modelo = opcion("prioridad")

    # Una denegacion de LAYA nunca se convierte en autorizacion.
    if not permiso_modelo:
        return (
            False, "", "", "", 0, False,
            "LAYA rechazo la orden"
        )

    # Las reglas locales tienen poder de veto.
    if not permiso_local:
        return (
            False, "", "", "", 0, False,
            "Orden rechazada por validacion local: " + motivo_local
        )

    # La accion debe estar autorizada tambien por LAYA.
    if accion_modelo != "trasladar":
        return (
            False, "", "", "", 0, False,
            "LAYA no identifico una accion de traslado valida"
        )

    # La prioridad procede exclusivamente de LAYA.
    if prioridad_modelo not in ("1", "2", "3"):
        return (
            False, "", "", "", 0, False,
            "Prioridad de LAYA invalida"
        )

    prioridad = int(prioridad_modelo)

    # Extraemos los parametros fisicos de la frase validada.
    # Nunca se deja que un destino contradictorio mueva el brazo.
    discrepancias = []

    if opcion("objeto") != objeto_local:
        discrepancias.append("objeto")

    if opcion("color") != color_local:
        discrepancias.append("color")

    if opcion("destino") != destino_local:
        discrepancias.append("destino")

    if discrepancias:
        if validacion_estricta:
            return (
                False, "", "", "", 0, False,
                "Orden rechazada por discrepancia LAYA: "
                + ", ".join(discrepancias)
            )

        causa = (
            "LAYA autorizo; parametros verificados mediante "
            "clasificador local. Discrepancias LAYA: "
            + ", ".join(discrepancias)
        )
    else:
        causa = "LAYA y clasificador local coinciden"

    return (
        True,
        accion_local,
        color_local,
        destino_local,
        prioridad,
        False,
        causa
    )


class InterpreteOrdenes(Node):
    def __init__(self):
        super().__init__("interprete_ordenes")
        self.declare_parameter("laya_url", os.getenv("LAYA_URL", "http://127.0.0.1:8765"))
        self.declare_parameter("laya_timeout", 4.0)
        self.declare_parameter("validacion_estricta", True)
        self.declare_parameter("corregir_con_reglas", False)  # Compatibilidad; sin elevación de permisos.
        self.declare_parameter(
            "nombre_servicio",
            "/interpretar_orden_p1_prueba"
        )

        nombre_servicio = self.get_parameter(
            "nombre_servicio"
        ).value

        self.servicio = self.create_service(
            InterpretarOrden,
            nombre_servicio,
            self.procesar
        )
        self.get_logger().info("P1 listo: LAYA principal; respaldo local identificado como degradado")

    def procesar(self, request, response):
        request_id = str(uuid.uuid4())
        inicio = time.perf_counter()
        try:
            decision = consultar_laya_tipado(
                request.frase,
                url=self.get_parameter("laya_url").value,
                timeout=float(self.get_parameter("laya_timeout").value),
            )
            permitido, accion, color, destino, prioridad, degradado, causa = decidir_con_laya(
                request.frase, decision,
                validacion_estricta=bool(self.get_parameter("validacion_estricta").value),
                corregir_con_reglas=bool(self.get_parameter("corregir_con_reglas").value),
            )
            objeto = "cubo"
            tiempo_servidor_ms = float(decision.tiempo_servidor_ms or 0.0)
            self.get_logger().info(
                f"[{request_id}] LAYA http_ms={decision.tiempo_http_ms:.2f}; "
                f"modelo={decision.modelo_usado}; "
                f"permitido_modelo={decision.permitido_modelo}; "
                f"permitido_final={permitido}; inferencia_ms={decision.tiempo_servidor_ms}"
            )
            self.get_logger().info(
                f"[{request_id}] respuestas_laya=" + json.dumps(
                    {k: v.get("choice") for k, v in decision.respuestas_crudas.items()
                     if isinstance(v, dict)}, ensure_ascii=False
                )
            )
        except (ErrorLaya, ValueError, TimeoutError, OSError) as exc:
            accion, objeto, color, destino, prioridad, permitido, causa_local = clasificar_orden(request.frase)
            degradado = True
            causa = f"Respaldo local por fallo de LAYA: {exc}; {causa_local}"
            tiempo_servidor_ms = 0.0  # No medido, NO equivale a 0 ms.
            self.get_logger().warning(f"[{request_id}] LAYA no disponible: {exc}")

        response.accion = accion
        response.objeto = objeto
        response.color = color
        response.destino = destino
        response.prioridad = int(prioridad)
        response.permitido = bool(permitido)
        response.degradado = bool(degradado)
        response.motivo = str(causa)
        response.tiempo_servidor_ms = float(tiempo_servidor_ms)
        self.get_logger().info(
            f"[{request_id}] frase={request.frase!r}; permitido={response.permitido}; "
            f"degradado={response.degradado}; "
            f"duracion_nodo_ms={(time.perf_counter() - inicio) * 1000:.2f}"
        )
        return response


def main(args=None):
    rclpy.init(args=args)
    nodo = InterpreteOrdenes()
    try:
        rclpy.spin(nodo)
    finally:
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
