from pathlib import Path
from google import genai
from google.genai import types

def transcribir_audio(ruta_audio, timeout=30):

    ruta = Path(ruta_audio)

    if not ruta.is_file():
        raise FileNotFoundError(
            f"No existe el audio: {ruta}"
        )

    cliente = genai.Client(
        http_options=types.HttpOptions(
            timeout=int(timeout * 1000)
        )
    )

    try:
        archivo = cliente.files.upload(
            file=str(ruta)
        )

        respuesta = cliente.interactions.create(
            model="gemini-3.5-transcribe",
            input=[{
                "type": "audio",
                "uri": archivo.uri,
                "mime_type": archivo.mime_type
            }],
            timeout=timeout
        )

        texto = (respuesta.output_text or "").strip()

        if not texto:
            raise ValueError("Transcripcion vacia")

        return texto

    finally:
        cliente.close()











