"""Transcripción de audio a español con Google AI Studio - primer eslabón de P3 (voz -> texto -> P1 -> P2)."""

# ---------------------------------------------------------------------------------------------
# GUÍA RÁPIDA
#   Objetivo : convertir un archivo de audio en texto en español usando Google AI Studio.
#   Recibe   : la ruta del audio y un tiempo máximo (timeout). Necesita la clave GEMINI_API_KEY
#              (o GOOGLE_API_KEY) en una variable de entorno; nunca se escribe en el código.
#   Devuelve : el texto transcrito, o lanza TranscripcionError (archivo inválido, sin clave,
#              error o tiempo agotado de Google, texto vacío). transcriptor_voz.py lo captura
#              y pasa al modo teclado.
#   Flujo    : comprobar archivo, formato, tamaño, clave y timeout -> codificar el audio en base64
#              -> enviarlo a Google en una sola petición -> leer el texto de la respuesta.
# Términos: base64 = forma de escribir bytes como texto para enviarlos en una petición web;
#   MIME = nombre estándar del tipo de archivo (audio/wav); Interactions API = servicio de Google que recibe el audio.
# ---------------------------------------------------------------------------------------------
import os
import base64
from pathlib import Path

from google import genai
from google.genai import types


# Modelo de Google; se puede cambiar con la variable de entorno GEMINI_MODELO_TRANSCRIPCION
MODELO = os.getenv("GEMINI_MODELO_TRANSCRIPCION", "gemini-3.5-transcribe")
MAX_BYTES_AUDIO = 10 * 1024 * 1024   # tamaño máximo aceptado: 10 MB

MIME_POR_EXTENSION = {   # extensión del archivo -> tipo MIME que se le dice a Google
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".m4a": "audio/m4a",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".webm": "audio/webm",
}

class TranscripcionError(Exception):   # error propio: así el nodo distingue un fallo de transcripción de otros 
    """Error durante la transcripción con Google."""
    pass

def transcribir_audio(ruta_audio, timeout=30.0): #Se le envia un audio a Google y este devuelve la transcripcion 

    # Si algo sale mal se lanza TranscripcionError; todo error de Google se convierte en ese mismo tipo
    cliente = None

    try:
        # 1) Validaciones previas (barato y sin Internet): archivo, formato, tamaño, clave y timeout
        ruta = Path(ruta_audio)

        if not ruta.is_file():
            raise TranscripcionError(f"¡No existe el audio en esa ruta!: {ruta}")

        mime = MIME_POR_EXTENSION.get(ruta.suffix.lower())
        if mime is None:
            raise TranscripcionError("¡Error! Formato de audio no soportado.")

        tamano = ruta.stat().st_size
        if tamano == 0 or tamano > MAX_BYTES_AUDIO:
            raise TranscripcionError("¡El audio está vacío o es demasiado grande!")

        if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
            raise TranscripcionError("¡No se pudo encontrar la API key!")

        if timeout <= 0:
            raise TranscripcionError("¡El timeout es inválido!")

        # 2) El audio se codifica en base64 para enviarlo dentro de la petición
        audio_b64 = base64.b64encode(
            ruta.read_bytes()
        ).decode("ascii")

        # 3) Cliente de Google con el timeout en milisegundos (la clave se toma sola del entorno)
        cliente = genai.Client(
            http_options=types.HttpOptions(
                timeout=int(timeout * 1000)
            )
        )

        # 4) Una sola petición con el audio; Google devuelve el texto
        respuesta = cliente.interactions.create(
            model=MODELO,
            input=[{
                "type": "audio",
                "data": audio_b64,
                "mime_type": mime
            }],
            timeout=timeout
        )

        # 5) Texto de la respuesta; si viene vacío se considera fallo
        texto = (respuesta.output_text or "").strip()

        if not texto:
            raise TranscripcionError("¡La transcripción está vacía!")

        return texto

    except TranscripcionError:
        raise

    except Exception as error:
        raise TranscripcionError(
            f"Error de Google: {type(error).__name__}: {error}"
        ) from error

    finally:
        # siempre se cierra el cliente para liberar la conexión
        if cliente is not None:
            cliente.close()
