""" El transcriptor de voz o audio, usa teclado si falla y guarda evidencias """
""" Versión 1.4: archivo o micrófono -> Google/teclado -> /interpretar_orden -> CSV."""
""" Sin LAYA ni broker: la respuesta de P1 sigue siendo provisional. El id_solicitud solo se transmite a P1 cuando la interfaz .srv lo permite."""
import csv
import hashlib
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args
from interprete_ordenes_interfaces.srv import InterpretarOrden

if __package__:
    from .transcripcion_google import transcribir_audio, TranscripcionError
    from .captura_microfono import capturar_voz, CapturaError
else:
    from transcripcion_google import transcribir_audio, TranscripcionError
    from captura_microfono import capturar_voz, CapturaError


RAIZ = Path(__file__).resolve().parents[2]
EVIDENCIAS = RAIZ / "evidencias/pregunta_3"
AUDIOS = EVIDENCIAS / "audios"
REGISTRO = EVIDENCIAS / "transcripciones.csv"

COLUMNAS = [
    "fecha", "audio_original", "audio_copia", "transcripcion", "origen",
    "tiempo_google_ms", "id_solicitud", "accion", "objeto", "color",
    "destino", "prioridad", "permitido", "degradado", "motivo", "resultado",
    "tiempo_servicio_ms", "tiempo_total_ms", "tiempo_teclado_ms",
    "tiempo_captura_ms",  # solo se mide al usar --microfono
]

def ejecutar_con_limite(funcion, segundos): #Función que deja de esperar una llamada lenta de Google, se activa si se superan los 15 s
    datos = {}

    def tarea():
        try:
            datos["valor"] = funcion()
        except Exception as error:
            datos["error"] = error

    hilo = threading.Thread(target=tarea, daemon=True)
    hilo.start()
    hilo.join(segundos)
    if hilo.is_alive():
        raise TimeoutError(f"¡¡Error! Google superó el límite de 15s, su timeout fue de {segundos:g} segundos!")
    if "error" in datos:
        raise datos["error"]
    return datos["valor"]

def obtener_orden(ruta_audio, timeout=15.0): #Esta función devuelve texto, origen, tienpo del intento con Google en ms
    inicio = time.monotonic()
    tiempo_teclado = 0.0
    try:
        print("¡[VOZ] Espere un momento. Se está transcribiendo audio...!")
        texto = ejecutar_con_limite(
            lambda: transcribir_audio(ruta_audio, timeout=timeout), timeout
        )
        origen = "google"
    except (TranscripcionError, OSError, TimeoutError) as error:
        print(f"¡[VOZ] Error con Google!: {error}")
        print("[VOZ] Se ha activado el modo teclado")
        origen = "teclado"
        tiempo_google = (time.monotonic() - inicio) * 1000
        inicio_teclado = time.monotonic()
        try:
            texto = input("[VOZ] Por favor, escribe lo que quisiste ordenar: ").strip()
        except EOFError:
            texto = ""
        tiempo_teclado = (time.monotonic() - inicio_teclado) * 1000
        return texto, origen, tiempo_google, tiempo_teclado
        
    tiempo_google = (time.monotonic() - inicio) * 1000
    return texto, origen, tiempo_google, tiempo_teclado
    
def calcular_hash_audio(ruta): #Funcion que identifica el contenido con el fin de no repetir copias del mismo archivo
    sha = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            sha.update(bloque)
    return sha.hexdigest()[:12]

def guardar_audio(ruta_audio): #Funcion que conserva una copia en la carpeta evidencias del repositorio y devuelve su ruta relativa
    origen = Path(ruta_audio).resolve()
    if not origen.is_file():
        return ""
    AUDIOS.mkdir(parents=True, exist_ok=True)
    if AUDIOS.resolve() in origen.parents:
        return origen.relative_to(RAIZ).as_posix()
    destino = AUDIOS / f"{origen.stem}_{calcular_hash_audio(origen)}{origen.suffix}"
    if not destino.exists():
        temporal = destino.with_name(destino.name + ".tmp")
        shutil.copy2(origen, temporal)
        temporal.replace(destino)
    return destino.relative_to(RAIZ).as_posix()

def preparar_csv(): #Añade columnas al CSV antiguo
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    if not REGISTRO.exists() or REGISTRO.stat().st_size == 0:
        return
    with REGISTRO.open(newline="", encoding="utf-8-sig") as archivo:
        filas = list(csv.reader(archivo))
    encabezado = filas[0]
    if encabezado == COLUMNAS:
        return
    if encabezado != COLUMNAS[:len(encabezado)]:
        raise ValueError("El CSV contiene columnas distintas. ¡Debes revísarlo antes de modificar!")
    respaldo = REGISTRO.with_name("transcripciones.csv.bak")
    if not respaldo.exists():
        shutil.copy2(REGISTRO, respaldo)
    temporal = REGISTRO.with_name("transcripciones.csv.tmp")
    with temporal.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS)
        for fila in filas[1:]:
            if len(fila) > len(COLUMNAS):
                raise ValueError("¡Filas CSV con más columnas de las esperadas!")
            escritor.writerow(fila + [""] * (len(COLUMNAS) - len(fila)))
    temporal.replace(REGISTRO)

def registrar_evidencia(ruta_audio, texto, origen, tiempos, decision=None, id_solicitud=None): #Se guarda la referencia al audio, la transcripcion y el tiempo 
    preparar_csv()
    try:
        copia = guardar_audio(ruta_audio) if ruta_audio else ""
    except OSError as error:
        print(f"¡[VOZ] No se pudo copiar el audio!: {error}")
        copia = ""

    if decision is None:
        campos = [""] * 7 + ["Sin respuesta de P1", "sin_decision"]
    else:
        estado = "autorizada_p1" if decision.permitido else "rechazada_p1"
        campos = [
            decision.accion, decision.objeto, decision.color, decision.destino,
            decision.prioridad, decision.permitido, decision.degradado,
            decision.motivo, estado,
        ]

    def valor_ms(clave):
        valor = tiempos.get(clave)
        return "" if valor is None else round(valor, 2)

    # Por el momento: Latencia parcial hacia P1, NO latencia hasta el movimiento del brazo. Para audio pregrabado no se conoce el tiempo de captura: queda vacío.
    t_total = sum(
        t for t in (tiempos.get("captura"), tiempos.get("google"),
                  tiempos.get("teclado"), tiempos.get("servicio")) if t is not None
    )
    # Si la captura por micrófono falló, no hay referencia de fin de habla.
    total_parcial = round(t_total, 2) if ruta_audio else ""

    nuevo = not REGISTRO.exists() or REGISTRO.stat().st_size == 0
    with REGISTRO.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        if nuevo:
            escritor.writerow(COLUMNAS)
        escritor.writerow([
            datetime.now().isoformat(timespec="seconds"),
            Path(ruta_audio).resolve().as_posix() if ruta_audio else "",
            copia, texto, origen, valor_ms("google"),
            id_solicitud or uuid.uuid4().hex[:8],
            *campos,
            valor_ms("servicio"), total_parcial, valor_ms("teclado"),
            valor_ms("captura"),
        ])
        
class NodoTranscriptor(Node):
    """Nodo ROS 2 que configura los tiempos y consulta a P1."""
    def __init__(self):
        super().__init__("transcriptor_voz")
        self.declare_parameter("timeout_transcripcion_s", 15.0)
        self.declare_parameter("timeout_servicio_s", 5.0)
        self.declare_parameter("silencio_fin_s", 0.8)
        self.declare_parameter("espera_inicio_s", 8.0)
        self.declare_parameter("max_duracion_s", 15.0)
        self.cliente = self.create_client(InterpretarOrden, "/interpretar_orden")
        
def enviar_orden_ros(texto, nodo, timeout, id_solicitud=None):
    inicio = time.monotonic()

    def tiempo_ms():
        return (time.monotonic() - inicio) * 1000

    try:
        if not nodo.cliente.wait_for_service(timeout_sec=timeout):
            print("¡[ROS] /interpretar_orden no está disponible!")
            return None, tiempo_ms()

        solicitud = InterpretarOrden.Request()
        solicitud.frase = texto
        # Compatibilidad con la interfaz actual, que solo tiene 'frase'.
        # Si después se añade 'string id_solicitud' al .srv, se transmitirá.
        if hasattr(solicitud, "id_solicitud"):
            solicitud.id_solicitud = id_solicitud
        futuro = nodo.cliente.call_async(solicitud)
        restante = timeout - (time.monotonic() - inicio)
        if restante <= 0:
            futuro.cancel()
            print("¡[ROS] Se agotó el tiempo de espera!")
            return None, tiempo_ms()

        rclpy.spin_until_future_complete(nodo, futuro, timeout_sec=restante)
        if not futuro.done():
            futuro.cancel()
            print("[ROS] P1 no respondió a tiempo")
            return None, tiempo_ms()

        respuesta = futuro.result()
        if respuesta is None:
            print("[ROS] P1 no devolvió una respuesta válida")
            return None, tiempo_ms()
        print(f"[ROS] ID: {id_solicitud}")
        print(f"[ROS] Acción: {respuesta.accion}")
        print(f"[ROS] Objeto: {respuesta.objeto}")
        print(f"[ROS] Color: {respuesta.color}")
        print(f"[ROS] Destino: {respuesta.destino}")
        print(f"[ROS] Prioridad: {respuesta.prioridad}")
        print(f"[ROS] Permitido: {respuesta.permitido}")
        print(f"[ROS] Degradado: {respuesta.degradado}")
        print(f"[ROS] Motivo: {respuesta.motivo}")
        return respuesta, tiempo_ms()
    except Exception as error:
        print(f"[ROS] Error al consultar P1: {error}")
        return None, tiempo_ms()

def texto_por_teclado():
    """Respaldo ante un error de captura; mide el tiempo del operador."""
    inicio = time.monotonic()
    print("¡[VOZ] Captura no disponible!¡Pasando al modo teclado!")
    try:
        texto = input("¡[VOZ] Escribe la orden!: ").strip()
    except EOFError:
        texto = ""
    return texto, (time.monotonic() - inicio) * 1000


def mostrar_tiempo(etiqueta, valor):
    if valor is None:
        print(f"¡[VOZ] {etiqueta}: no medido!")
    else:
        print(f"[VOZ] {etiqueta}: {valor:.1f} ms")


def main():
    argumentos = remove_ros_args(args=sys.argv)
    if len(argumentos) != 2:
        print("Uso: python3 transcriptor_voz.py audio.aac | --microfono [--ros-args ...]")
        return 1

    rclpy.init(args=sys.argv)
    nodo = NodoTranscriptor()
    try:
        timeout_google = float(nodo.get_parameter("timeout_transcripcion_s").value)
        timeout_ros = float(nodo.get_parameter("timeout_servicio_s").value)
        silencio = float(nodo.get_parameter("silencio_fin_s").value)
        espera = float(nodo.get_parameter("espera_inicio_s").value)
        duracion = float(nodo.get_parameter("max_duracion_s").value)
        if min(timeout_google, timeout_ros, silencio, espera, duracion) <= 0:
            print("¡[VOZ] Todos los límites deben ser mayores que cero!")
            return 1

        id_solicitud = uuid.uuid4().hex[:8]
        print(f"[VOZ] ID solicitud: {id_solicitud}")
        modo_microfono = argumentos[1] == "--microfono"
        ruta_audio = ""
        tiempo_captura = None
        texto, origen, t_google, t_teclado = None, None, None, None

        if modo_microfono:
            try:
                grabacion = capturar_voz(
                    AUDIOS, silencio_fin_s=silencio,
                    espera_inicio_s=espera, max_duracion_s=duracion
                )
                ruta_audio = str(grabacion.ruta)
                tiempo_captura = grabacion.tiempo_captura_ms
                print(f"[VOZ] Audio guardado: {ruta_audio}")
                print(f"[VOZ] Fin de captura: {grabacion.motivo_fin}")
                mostrar_tiempo("Captura (fin de habla estimado a WAV)", tiempo_captura)
            except (CapturaError, OSError) as error:
                print(f"¡[VOZ] Error de micrófono!: {error}")
                texto, t_teclado = texto_por_teclado()
                origen = "teclado"
        else:
            ruta_audio = argumentos[1]

        if texto is None:
            texto, origen, t_google, t_teclado = obtener_orden(ruta_audio, timeout_google)

        # Mostrar la frase inmediatamente después de transcribir, antes de P1.
        print(f"[VOZ] Orden: {texto}")
        print(f"[VOZ] Origen: {origen}")

        decision, t_ros = None, None
        if texto:
            decision, t_ros = enviar_orden_ros(texto, nodo, timeout_ros, id_solicitud)

        try:
            registrar_evidencia(
                ruta_audio, texto, origen,
                {"captura": tiempo_captura, "google": t_google,
                 "teclado": t_teclado, "servicio": t_ros},
                decision, id_solicitud
            )
        except (OSError, ValueError) as error:
            print(f"¡[VOZ] No se pudo guardar el CSV!: {error}")
            return 1

        # Los tiempos que no se miden quedan vacíos en el CSV.
        if not modo_microfono:
            print("¡[VOZ] Captura: no medida (archivo pregrabado)!")
        mostrar_tiempo("Google", t_google)
        mostrar_tiempo("Teclado", t_teclado)
        mostrar_tiempo("ROS 2", t_ros)
        print(f"[VOZ] Evidencia registrada: {REGISTRO}")

        if not texto or decision is None:
            return 1
        if not decision.permitido:
            print("[ROS] Orden rechazada por P1; no se envía al broker")
        else:
            print("[ROS] P1 autorizó la orden; broker todavía no integrado")
        return 0
    finally:
        nodo.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    sys.exit(main())


