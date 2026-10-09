"""Nodo transcriptor_voz para la Pregunta 3 del Gran Reto.

Recibe un archivo de audio, solicita la transcripcion a Google (si falla,
modo teclado), envia el texto al servicio ROS 2 /interpretar_orden y
registra evidencia CSV.

Uso:
    python3 transcriptor_voz.py archivo.wav
    python3 transcriptor_voz.py archivo.wav --ros-args -p timeout_transcripcion_s:=10.0

Pendiente: enviar la decision a la cola del broker (Pregunta 2).
"""

import csv
import hashlib
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args
from interprete_ordenes_interfaces.srv import InterpretarOrden

if __package__:
    from .transcripcion_google import transcribir_audio, TranscripcionError
else:
    from transcripcion_google import transcribir_audio, TranscripcionError


RAIZ = Path(__file__).resolve().parents[2]
CARPETA_EVIDENCIA = RAIZ / "evidencias/pregunta_3"
CARPETA_AUDIOS = CARPETA_EVIDENCIA / "audios"
REGISTRO = CARPETA_EVIDENCIA / "transcripciones.csv"

COLUMNAS = [
    "fecha", "audio_original", "audio_copia", "transcripcion", "origen",
    "tiempo_google_ms", "accion", "objeto", "color", "destino",
    "prioridad", "permitido", "degradado", "motivo", "tiempo_servicio_ms",
]


def obtener_orden(ruta_audio, timeout=15.0, avisar=print, informar=print):
    """Obtiene texto con Google o activa el respaldo por teclado.

    Cualquier falla de la transcripcion (sin clave, sin internet, timeout,
    audio inexistente o ilegible) pasa a modo teclado: el sistema no se cae.
    """
    inicio = time.monotonic()

    try:
        informar("Transcribiendo audio...")
        texto = transcribir_audio(ruta_audio, timeout=timeout)
        tiempo_google_ms = (time.monotonic() - inicio) * 1000
        origen = "google"
    except (TranscripcionError, OSError) as error:  # OSError incluye FileNotFoundError
        tiempo_google_ms = (time.monotonic() - inicio) * 1000
        avisar(f"Transcripcion fallida ({error}). Activando modo teclado")
        try:
            texto = input("Escribe la orden: ").strip()
        except EOFError:  # no hay teclado disponible (entrada estandar cerrada)
            avisar("No hay teclado disponible")
            texto = ""
        origen = "teclado"

    return texto, origen, tiempo_google_ms


def _huella(ruta):
    """Hash corto del contenido del archivo."""
    sha = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            sha.update(bloque)
    return sha.hexdigest()[:10]


def _relativa_a_raiz(ruta):
    try:
        return str(ruta.relative_to(RAIZ))
    except ValueError:
        return str(ruta)


def copiar_audio(ruta_audio):
    """Guarda el audio en la evidencia sin duplicarlo; devuelve su ruta relativa a la raiz.

    - Si el audio ya esta dentro de la carpeta de evidencia, no se copia.
    - El nombre de la copia lleva un hash del contenido: el mismo audio
      repetido reutiliza su copia, y dos audios distintos con el mismo
      nombre nunca se pisan.
    """
    origen = Path(ruta_audio).resolve()
    if not origen.is_file():
        return ""

    carpeta = CARPETA_AUDIOS.resolve()
    if carpeta in origen.parents:
        return _relativa_a_raiz(origen)

    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{origen.stem}_{_huella(origen)}{origen.suffix}"

    if not destino.exists():
        temporal = destino.with_name(destino.name + ".tmp")
        shutil.copy2(origen, temporal)
        temporal.replace(destino)  # evita dejar una copia a medias

    return _relativa_a_raiz(destino)


def guardar_evidencia(ruta_audio, texto, origen, tiempo_google_ms,
                      decision=None, tiempo_servicio_ms=None):
    """Registra la transcripcion, el audio original, la decision y las latencias."""
    CARPETA_EVIDENCIA.mkdir(parents=True, exist_ok=True)
    audio_original = str(Path(ruta_audio).resolve())

    try:
        audio_copia = copiar_audio(ruta_audio)
    except OSError as error:
        print(f"[VOZ] No se pudo copiar el audio: {error}")
        audio_copia = ""

    nuevo = not REGISTRO.exists() or REGISTRO.stat().st_size == 0

    if decision is None:
        campos_decision = ["", "", "", "", "", "", "", "sin decision"]
    else:
        campos_decision = [
            decision.accion, decision.objeto, decision.color, decision.destino,
            decision.prioridad, decision.permitido, decision.degradado,
            decision.motivo,
        ]

    with REGISTRO.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        if nuevo:
            escritor.writerow(COLUMNAS)
        escritor.writerow([
            datetime.now().isoformat(timespec="seconds"),
            audio_original,
            audio_copia,
            texto,
            origen,
            round(tiempo_google_ms, 2),
            *campos_decision,
            "" if tiempo_servicio_ms is None else round(tiempo_servicio_ms, 2),
        ])


class TranscriptorVoz(Node):
    def __init__(self):
        super().__init__("transcriptor_voz")
        self.declare_parameter("timeout_transcripcion_s", 15.0)
        self.declare_parameter("timeout_servicio_s", 5.0)
        self.cliente = self.create_client(InterpretarOrden, "/interpretar_orden")

    def _parametro(self, nombre):
        return self.get_parameter(nombre).value

    def obtener_orden(self, ruta_audio):
        return obtener_orden(
            ruta_audio,
            timeout=self._parametro("timeout_transcripcion_s"),
            avisar=self.get_logger().warn,
            informar=self.get_logger().info,
        )

    def interpretar(self, texto):
        """Envia la frase a /interpretar_orden. Devuelve (respuesta, ms) o (None, ms)."""
        limite = self._parametro("timeout_servicio_s")
        inicio = time.monotonic()

        if not self.cliente.wait_for_service(timeout_sec=limite):
            self.get_logger().error(f"/interpretar_orden no disponible tras {limite} s")
            return None, (time.monotonic() - inicio) * 1000

        solicitud = InterpretarOrden.Request()
        solicitud.frase = texto
        futuro = self.cliente.call_async(solicitud)
        rclpy.spin_until_future_complete(self, futuro, timeout_sec=limite)
        milisegundos = (time.monotonic() - inicio) * 1000

        if not futuro.done():
            futuro.cancel()
            self.get_logger().error(f"/interpretar_orden no respondio en {limite} s")
            return None, milisegundos

        return futuro.result(), milisegundos


def main():
    argumentos = remove_ros_args(sys.argv)
    if len(argumentos) != 2:
        print("Uso: python3 transcriptor_voz.py archivo.wav [--ros-args -p timeout_transcripcion_s:=10.0]")
        return 1
    ruta_audio = argumentos[1]

    rclpy.init()
    nodo = TranscriptorVoz()
    try:
        texto, origen, tiempo_google_ms = nodo.obtener_orden(ruta_audio)

        decision, tiempo_servicio_ms = (None, None)
        if texto:
            decision, tiempo_servicio_ms = nodo.interpretar(texto)

        guardar_evidencia(ruta_audio, texto, origen, tiempo_google_ms,
                          decision, tiempo_servicio_ms)

        if not texto:
            nodo.get_logger().error("No se obtuvo ninguna orden")
            return 1

        nodo.get_logger().info(f"Orden: {texto} (origen: {origen}, intento Google: {tiempo_google_ms:.1f} ms)")

        if decision is None:
            nodo.get_logger().error("Sin decision del interprete: no se ejecuta nada")
            return 1

        if not decision.permitido:
            nodo.get_logger().warn(f"Orden RECHAZADA: {decision.motivo}")
            return 0

        nodo.get_logger().info(
            f"Decision: {decision.accion} {decision.objeto} {decision.color} -> "
            f"{decision.destino} (prioridad {decision.prioridad}, "
            f"degradado={decision.degradado}, servicio {tiempo_servicio_ms:.1f} ms)")
        nodo.get_logger().info("Pendiente enviar a la cola del broker")
        return 0
    finally:
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
