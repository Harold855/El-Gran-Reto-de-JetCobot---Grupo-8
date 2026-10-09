"""Transcripción de audio a español - pregunta 3 del Gran Reto del JetCobot"""

import os
import base64
from pathlib import Path

from google import genai
from google.genai import types


MODELO = os.getenv("GEMINI_MODELO_TRANSCRIPCION", "gemini-3.5-transcribe")
MAX_BYTES_AUDIO = 10 * 1024 * 1024

MIME_POR_EXTENSION = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".m4a": "audio/m4a",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".webm": "audio/webm",
}

class TranscripcionError(Exception): #Esto indica que debe activarse el modo teclado

def transcribir_audio(ruta_audio, timeout=15.0): #Se le envia un audio a Google y este devuelve la transcripcion 

    cliente = None

    try:
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

        audio_b64 = base64.b64encode(
            ruta.read_bytes()
        ).decode("ascii")

        cliente = genai.Client(
            http_options=types.HttpOptions(
                timeout=int(timeout * 1000)
            )
        )

        respuesta = cliente.interactions.create(
            model=MODELO,
            input=[{
                "type": "audio",
                "data": audio_b64,
                "mime_type": mime
            }],
            timeout=timeout
        )

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
        if cliente is not None:
            cliente.close()
