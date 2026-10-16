"""Diagnostico de la lentitud de Google en la Pregunta 3.

Responde a: ¿por que la transcripcion supera el tiempo limite? Mide por separado
  1) el audio: duracion y tamano que se sube (un audio largo o con ruido sube mas bytes);
  2) la red hacia Google: DNS, conexion TCP y TLS, por IPv4 y por IPv6
     (un IPv6 roto hace esperar varios segundos antes de pasar a IPv4);
  3) la transcripcion: N llamadas con el MISMO audio y un limite generoso, para ver
     cuanto tarda de verdad y si la lentitud es constante o intermitente.
Al final sugiere un valor para timeout_transcripcion_s.

Uso (desde la raiz del repositorio, con GEMINI_API_KEY exportada):
    python3 scripts/p3_diagnostico_google.py evidencias/pregunta_3/audios/mic_XXXX.wav
    python3 scripts/p3_diagnostico_google.py audio.wav --veces 5 --timeout 60
    python3 scripts/p3_diagnostico_google.py --solo-red          # sin audio ni clave

No escribe en el repositorio y no imprime la clave.
"""

import argparse
import math
import socket
import ssl
import statistics
import sys
import time
import wave
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
HOST = "generativelanguage.googleapis.com"


def info_audio(ruta):
    """Duracion (si es WAV) y tamano del audio; el tamano real subido es ~4/3 por el base64."""
    ruta = Path(ruta)
    kb = ruta.stat().st_size / 1024
    duracion = None
    if ruta.suffix.lower() == ".wav":
        with wave.open(str(ruta), "rb") as w:
            duracion = w.getnframes() / w.getframerate()
    return duracion, kb


def medir_red(host, familia, puerto=443, espera=5.0):
    """Devuelve (familia, dns_ms, tcp_ms, tls_ms, error); error queda vacio si todo salio bien."""
    nombre = "IPv4" if familia == socket.AF_INET else "IPv6"
    try:
        t0 = time.perf_counter()
        info = socket.getaddrinfo(host, puerto, familia, socket.SOCK_STREAM)
        dns = (time.perf_counter() - t0) * 1000
    except OSError as error:
        return nombre, None, None, None, f"sin direccion ({error})"
    direccion = info[0][4]
    try:
        t0 = time.perf_counter()
        sock = socket.socket(familia, socket.SOCK_STREAM)
        sock.settimeout(espera)
        sock.connect(direccion)
        tcp = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        with ssl.create_default_context().wrap_socket(sock, server_hostname=host):
            tls = (time.perf_counter() - t0) * 1000
        return nombre, dns, tcp, tls, ""
    except (OSError, ssl.SSLError) as error:
        try:
            sock.close()
        except Exception:
            pass
        return nombre, dns, None, None, f"{type(error).__name__}: {error}"


def sugerir_timeout(tiempos):
    """Margen de 1,5 veces el peor caso medido, redondeado a 5 s y nunca menor de 20 s."""
    if not tiempos:
        return None
    return max(20, 5 * math.ceil(1.5 * max(tiempos) / 5))


def main(argv=None):
    p = argparse.ArgumentParser(description="Diagnostico de la lentitud de Google (P3).")
    p.add_argument("audio", nargs="?", help="audio a transcribir (wav, aac, mp3...)")
    p.add_argument("--veces", type=int, default=3, help="transcripciones a medir (por defecto 3)")
    p.add_argument("--timeout", type=float, default=60.0, help="limite por llamada para el diagnostico (por defecto 60 s)")
    p.add_argument("--solo-red", action="store_true", help="medir solo la red, sin audio ni clave")
    args = p.parse_args(argv)

    print("== 1) Red hacia Google ==")
    for familia in (socket.AF_INET, socket.AF_INET6):
        nombre, dns, tcp, tls, error = medir_red(HOST, familia)
        if error:
            print(f"  {nombre}: {error}" + (f" (DNS {dns:.0f} ms)" if dns is not None else ""))
        else:
            print(f"  {nombre}: DNS {dns:.0f} ms | TCP {tcp:.0f} ms | TLS {tls:.0f} ms")
    if args.solo_red:
        return 0

    if not args.audio:
        p.error("indica el audio o usa --solo-red")
    ruta = Path(args.audio)
    if not ruta.is_file():
        p.error(f"no existe el audio: {ruta}")

    duracion, kb = info_audio(ruta)
    print("\n== 2) Audio ==")
    print(f"  {ruta.name}: " + (f"{duracion:.1f} s, " if duracion is not None else "") + f"{kb:.0f} KB (se suben ~{kb * 4 / 3:.0f} KB)")
    if duracion is not None and duracion > 8:
        print("  AVISO: el audio dura mas de 8 s. Si dijiste una frase corta, la grabacion arrastra ruido o silencio: "
              "revisa mic_umbral/silencio_fin_s y el aviso 'Audio capturado' del nodo.")

    sys.path.insert(0, str(RAIZ / "src" / "transcriptor_voz"))
    try:
        from transcripcion_google import transcribir_audio, TranscripcionError
    except ImportError as error:
        print(f"\nNo se puede importar el cliente de Google: {error}")
        return 1

    print(f"\n== 3) Transcripcion ({args.veces} llamadas, limite {args.timeout:g} s cada una) ==")
    tiempos = []
    for i in range(1, args.veces + 1):
        t0 = time.perf_counter()
        try:
            texto = transcribir_audio(ruta, timeout=args.timeout)
            ms = (time.perf_counter() - t0) * 1000
            tiempos.append(ms / 1000)
            print(f"  {i}: {ms:8.0f} ms  OK  «{texto[:60]}»")
        except TranscripcionError as error:
            print(f"  {i}: {(time.perf_counter() - t0) * 1000:8.0f} ms  FALLO  {str(error)[:90]}")

    print("\n== Resumen ==")
    if not tiempos:
        print("  Ninguna llamada termino bien: revisa la clave, la red y el modelo antes de ajustar tiempos.")
        return 1
    print(f"  Transcripcion: mediana {statistics.median(tiempos):.1f} s | peor {max(tiempos):.1f} s")
    if duracion:
        print(f"  Relacion tiempo/audio: {statistics.median(tiempos) / duracion:.2f} s de espera por cada segundo de audio")
    print(f"  Sugerencia: --ros-args -p timeout_transcripcion_s:={sugerir_timeout(tiempos):g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
