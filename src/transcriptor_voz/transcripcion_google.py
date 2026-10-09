"""Transcripcion de audio en espanol con Google AI Studio (Gemini).

Pregunta 3, Parte A del Gran Reto. Este modulo solo habla con la nube; el nodo
ROS 2 transcriptor_voz lo invoca y decide que hacer si falla.

- La clave se lee de la variable de entorno GEMINI_API_KEY (o GOOGLE_API_KEY).
  Nunca se escribe en el codigo ni se sube al repositorio.
- Toda falla (sin clave, sin internet, timeout, respuesta vacia) se informa con
  TranscripcionError. El nodo la captura y pasa a modo texto por teclado.
"""

import base64
import os
import time
from pathlib import Path

from google import genai
from google.genai import types

MODELO_PRINCIPAL = os.environ.get("GEMINI_MODELO_TRANSCRIPCION", "gemini-3.5-transcribe")
MODELO_RESPALDO = os.environ.get("GEMINI_MODELO_RESPALDO", "gemini-flash-latest")

# Solicitud en linea (sin subir el archivo): limite de Gemini ~20 MB y base64
# agrega ~33 %, por eso se acepta un audio de hasta 14 MB.
MAX_BYTES_AUDIO = 14 * 1024 * 1024

MIME_POR_EXTENSION = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".aiff": "audio/aiff",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".m4a": "audio/m4a",
    ".opus": "audio/opus",
    ".webm": "audio/webm",
}

INSTRUCCION_RESPALDO = (
    "Transcribe literalmente el audio en espanol. Responde solo con el texto "
    "dicho, sin comillas, comentarios ni traduccion. Si no hay voz, no respondas nada."
)


class TranscripcionError(Exception):
    """La transcripcion no se pudo obtener; el nodo debe pasar a modo teclado."""


def _hay_clave():
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def _pedir_transcripcion(cliente, modelo, audio_b64, mime, timeout_restante):
    """Una sola llamada a la Interactions API; devuelve el texto (puede ser vacio)."""
    argumentos = {
        "model": modelo,
        "input": [{"type": "audio", "data": audio_b64, "mime_type": mime}],
        "timeout": timeout_restante,
    }
    if "transcribe" in modelo:
        argumentos["generation_config"] = {
            "transcription_config": {"language_codes": ["es"]}
        }
    else:
        argumentos["system_instruction"] = INSTRUCCION_RESPALDO

    respuesta = cliente.interactions.create(**argumentos)
    return (respuesta.output_text or "").strip()


def transcribir_audio(ruta_audio, timeout=10.0):
    """Devuelve la transcripcion en espanol del audio.

    `timeout` es el limite TOTAL en segundos (incluye el intento de respaldo).
    Lanza TranscripcionError si no se obtiene texto a tiempo.
    """
    ruta = Path(ruta_audio)

    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el audio: {ruta}")

    mime = MIME_POR_EXTENSION.get(ruta.suffix.lower())
    if mime is None:
        raise TranscripcionError(
            f"Formato no soportado '{ruta.suffix}'. Usa: {', '.join(MIME_POR_EXTENSION)}"
        )

    if ruta.stat().st_size > MAX_BYTES_AUDIO:
        raise TranscripcionError(
            f"Audio demasiado grande ({ruta.stat().st_size / 1e6:.1f} MB); maximo 14 MB"
        )

    if not _hay_clave():
        raise TranscripcionError(
            "Falta la variable de entorno GEMINI_API_KEY (o GOOGLE_API_KEY)"
        )

    audio_b64 = base64.b64encode(ruta.read_bytes()).decode("ascii")
    limite = time.monotonic() + timeout

    # El timeout del cliente (en milisegundos) es el techo de cada solicitud.
    cliente = genai.Client(
        http_options=types.HttpOptions(timeout=int(timeout * 1000))
    )

    ultimo_error = None
    try:
        for modelo in (MODELO_PRINCIPAL, MODELO_RESPALDO):
            restante = limite - time.monotonic()
            if restante <= 0.5:
                break
            try:
                texto = _pedir_transcripcion(cliente, modelo, audio_b64, mime, restante)
            except Exception as exc:  # red caida, timeout, modelo no disponible, etc.
                ultimo_error = f"{modelo}: {type(exc).__name__}: {exc}"
                continue
            if texto:
                return texto
            ultimo_error = f"{modelo}: transcripcion vacia"
    finally:
        cliente.close()

    raise TranscripcionError(ultimo_error or f"Sin respuesta en {timeout} s")
