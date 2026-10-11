"""El transcriptor de voz o audio, usa teclado si falla y guarda evidencias"""

import csv
import hashlib
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

if __package__:
    from .transcripcion_google import transcribir_audio, TranscripcionError
else:
    from transcripcion_google import transcribir_audio, TranscripcionError


RAIZ = Path(__file__).resolve().parents[2]
EVIDENCIAS = RAIZ / "evidencias/pregunta_3"
AUDIOS = EVIDENCIAS / "audios"
REGISTRO = EVIDENCIAS / "transcripciones.csv"


def obtener_orden(ruta_audio, timeout=15.0): #Esta función devuelve texto, origen, tienpo del intento con Google en ms
    inicio = time.monotonic()

    try:
        print("¡[VOZ] Espere. Se está transcribiendo audio...!")
        texto = transcribir_audio(ruta_audio, timeout=timeout)
        tiempo_ms = (time.monotonic() - inicio) * 1000
        origen = "google"
    except (TranscripcionError, OSError) as error:
        tiempo_ms = (time.monotonic() - inicio) * 1000
        print(f"¡[VOZ] ¡Error! Ocurrió un falló con Google!: {error}")
        try:
            texto = input("[VOZ] Escribe la orden: ").strip()
        except EOFError:
            texto = ""
        origen = "teclado"

    return texto, origen, tiempo_ms

def calcular_hash_audio(ruta): #Funcion que identifica el contenido con el fin de no repetir copias del mismo archivo
    sha = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            sha.update(bloque)
    return sha.hexdigest()[:12]

def guardar_audio(ruta_audio): #Funcion que coserva una copia en la carpeta evidencias del repositorio y devuelve su ruta relativa
    origen = Path(ruta_audio).resolve()
    if not origen.is_file():
        return ""

    AUDIOS.mkdir(parents=True, exist_ok=True)
    if AUDIOS.resolve() in origen.parents:
        return str(origen.relative_to(RAIZ))

    nombre = f"{origen.stem}_{calcular_hash_audio(origen)}{origen.suffix}"
    destino = AUDIOS / nombre
    if not destino.exists():
        temporal = destino.with_name(destino.name + ".tmp")
        shutil.copy2(origen, temporal)
        temporal.replace(destino)
    return str(destino.relative_to(RAIZ))

def registrar_evidencia(ruta_audio, texto, origen, tiempo_ms): #Se guarda la referencia al audio, la transcripcion y el tiempo 
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    try:
        copia = guardar_audio(ruta_audio)
    except OSError as error:
        print(f"¡[VOZ] ¡Error! No se pudo guardar el audio!: {error}")
        copia = ""

    nuevo = not REGISTRO.exists() or REGISTRO.stat().st_size == 0
    with REGISTRO.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        if nuevo:
            escritor.writerow([
                "fecha", "audio_original", "audio_copia", "transcripcion", "origen", "tiempo_google_ms"
            ])
        escritor.writerow([
            datetime.now().isoformat(timespec="seconds"),
            str(Path(ruta_audio).resolve()), copia, texto, origen,
            round(tiempo_ms, 2)
        ])

def enviar_orden_ros(texto):
    """Envía la orden al servicio ROS 2 y muestra la decisión."""
    import rclpy
    from interprete_ordenes_interfaces.srv import InterpretarOrden

    rclpy.init()
    nodo = rclpy.create_node("cliente_voz")

    try:
        cliente = nodo.create_client(
            InterpretarOrden, "/interpretar_orden"
        )

        if not cliente.wait_for_service(timeout_sec=5.0):
            print("[ROS] Servicio no disponible")
            return False

        solicitud = InterpretarOrden.Request()
        solicitud.frase = texto

        futuro = cliente.call_async(solicitud)
        rclpy.spin_until_future_complete(
            nodo, futuro, timeout_sec=10.0
        )

        if not futuro.done():
            print("[ROS] Tiempo de espera agotado")
            return False

        respuesta = futuro.result()
        if respuesta is None:
            print("[ROS] No se recibió una respuesta válida")
            return False

        print(f"[ROS] Acción: {respuesta.accion}")
        print(f"[ROS] Color: {respuesta.color}")
        print(f"[ROS] Destino: {respuesta.destino}")
        print(f"[ROS] Prioridad: {respuesta.prioridad}")
        print(f"[ROS] Permitido: {respuesta.permitido}")
        print(f"[ROS] Degradado: {respuesta.degradado}")
        print(f"[ROS] Motivo: {respuesta.motivo}")

        return True

    except Exception as error:
        print(f"[ROS] Error: {error}")
        return False

    finally:
        nodo.destroy_node()
        rclpy.shutdown()


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 transcriptor_voz.py archivo.wav")
        return 1

    ruta_audio = sys.argv[1]
    texto, origen, tiempo_ms = obtener_orden(ruta_audio)
    registrar_evidencia(ruta_audio, texto, origen, tiempo_ms)

    if not texto:
        print("¡[VOZ] No se pudo obtener ninguna orden!")
        return 1

    print(f"[VOZ] Orden: {texto}")
    print(f"[VOZ] Origen: {origen}")
    print(f"[VOZ] Tiempo intento con Google: {tiempo_ms:.1f} ms")
    if not enviar_orden_ros(texto):
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())



