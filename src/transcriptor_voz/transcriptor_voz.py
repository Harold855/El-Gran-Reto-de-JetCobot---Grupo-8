"""Coordinador de voz para la Pregunta 3 del Gran Reto.

Recibe un archivo de audio, solicita la transcripcion a Google,
activa el modo teclado si Google falla y registra evidencia CSV.
Pendiente: integracion con el servicio ROS 2 /interpretar_orden.
"""

import csv
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
CARPETA_EVIDENCIA = RAIZ / "evidencias/pregunta_3"
CARPETA_AUDIOS = CARPETA_EVIDENCIA / "audios"
REGISTRO = CARPETA_EVIDENCIA / "transcripciones.csv"


def obtener_orden(ruta_audio, timeout=15.0):
    """Obtiene texto con Google o activa el respaldo por teclado.

    Cualquier falla de la transcripcion (sin clave, sin internet, timeout,
    audio inexistente o ilegible) pasa a modo teclado: el sistema no se cae.
    """
    inicio = time.monotonic()

    try:
        print("[VOZ] Transcribiendo audio...")
        texto = transcribir_audio(ruta_audio, timeout=timeout)
        tiempo_google_ms = (time.monotonic() - inicio) * 1000
        origen = "google"
    except (TranscripcionError, OSError) as error:  # OSError incluye FileNotFoundError
        tiempo_google_ms = (time.monotonic() - inicio) * 1000
        print(f"[VOZ] Error: {error}")
        print("[VOZ] Activando modo teclado")
        try:
            texto = input("Escribe la orden: ").strip()
        except EOFError:  # no hay teclado disponible (entrada estandar cerrada)
            print("[VOZ] No hay teclado disponible")
            texto = ""
        origen = "teclado"

    return texto, origen, tiempo_google_ms


def copiar_audio(ruta_audio):
    """Guarda una copia del audio en la evidencia; devuelve su ruta relativa a la raiz."""
    origen = Path(ruta_audio)
    if not origen.is_file():
        return ""

    CARPETA_AUDIOS.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = CARPETA_AUDIOS / f"{marca}_{origen.name}"
    shutil.copy2(origen, destino)
    return str(destino.relative_to(RAIZ))


def guardar_evidencia(ruta_audio, texto, origen, tiempo_ms):
    """Registra la transcripcion, el audio original y la latencia con Google."""
    CARPETA_EVIDENCIA.mkdir(parents=True, exist_ok=True)
    audio_original = str(Path(ruta_audio).resolve())

    try:
        audio_copia = copiar_audio(ruta_audio)
    except OSError as error:
        print(f"[VOZ] No se pudo copiar el audio: {error}")
        audio_copia = ""

    nuevo = not REGISTRO.exists() or REGISTRO.stat().st_size == 0

    with REGISTRO.open("a", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        if nuevo:
            escritor.writerow([
                "fecha", "audio_original", "audio_copia",
                "transcripcion", "origen", "tiempo_google_ms"
            ])
        escritor.writerow([
            datetime.now().isoformat(timespec="seconds"),
            audio_original,
            audio_copia,
            texto,
            origen,
            round(tiempo_ms, 2),
        ])


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 transcriptor_voz.py archivo.wav")
        return 1

    ruta_audio = sys.argv[1]
    texto, origen, tiempo_ms = obtener_orden(ruta_audio)
    guardar_evidencia(ruta_audio, texto, origen, tiempo_ms)

    if not texto:
        print("[VOZ] No se obtuvo ninguna orden")
        return 1

    print(f"[VOZ] Orden: {texto}")
    print(f"[VOZ] Origen: {origen}")
    print(f"[VOZ] Tiempo intento Google: {tiempo_ms:.1f} ms")
    print("[VOZ] Pendiente enviar a /interpretar_orden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
