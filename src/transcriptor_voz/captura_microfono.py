"""Captura de voz desde el microfono"""

"""Graba un .wav de 16 kHz y 16 bits. Primero calibra el ruido de fondo en silencio, despues avisa con una frase "Habla ahora", espera a que el operador empiece a
hablar y termina cuando detecta silencio.

Fin de habla ESTIMADO (importante para la resolución de la parte C):
`t_fin_habla_estimado` no es el instante exacto en que el operador terminó de hablar. Es la hora de llegada (time.monotonic(), tomada al leer el pipe) del
ultimo bloque de 20 ms cuya energia (RMS) supero el umbral. 
Por eso:
  - Se incluye el retraso de los buffers del dispositivo y del sistema de audio;
  - Un ruido fuerte puede contarse como voz y retrasar el fin estimado;
  - Una voz muy baja o un final suave de una palabra pueden no superar el umbral y adelantarlo.
Es un fin de habla estimado por energia

Atencion: aun está pendiente de validar con grabaciones reales (comparandolo con el fin visible en la forma de onda).
          `tiempo_captura_ms` mide desde ese instante estimado hasta tener el WAV
          escrito; incluye la espera de silencio (`silencio_fin_s`).

Limites en tiempo REAL (time.monotonic), no en cantidad de audio recibido:
  - calibracion de ruido:  CALIBRACION_MAX_S
  - esperar a que hables:  espera_inicio_s (desde el aviso "Habla ahora")
  - duracion de la frase:  max_duracion_s (desde que se detecta el inicio)
Asi, aunque el audio llegue lento, la captura nunca excede esos tiempos.

Tampoco nunca espera indefinidamente: si no hay microfono, no hay voz o el
dispositivo se bloquea, entonces lanza CapturaError y el nodo pasa al modo teclado.
"""

# ---------------------------------------------------------------------------------------------
# GUÍA RÁPIDA
#   Objetivo : grabar UNA frase hablada del micrófono y guardarla como archivo .wav.
#   Recibe   : carpeta de salida y los tiempos límite (silencio final, espera, duración máxima).
#   Devuelve : un objeto Captura (ruta del WAV, duración, motivo de fin y tiempos) o lanza
#              CapturaError (sin micrófono, sin voz...), caso en que el nodo pasa al modo teclado.
#   Flujo    : abrir micrófono -> calibrar el ruido de fondo (silencio) -> avisar "Habla ahora"
#              -> esperar a que empieces -> grabar hasta detectar silencio -> escribir el WAV.
#   Piezas   : _Fuente lee el audio del programa externo (arecord/parec) en un hilo;
#              DetectorVoz decide cuándo empieza y termina la frase; capturar_voz las une.
# ---------------------------------------------------------------------------------------------
import array
import math
import queue
import shutil
import statistics
import subprocess
import tempfile
import threading
import time
import uuid
import wave
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


FRECUENCIA = 16000         # muestras por segundo (16 kHz basta para reconocer voz)
MS_BLOQUE = 20             # el audio se analiza en bloques de 20 ms
BYTES_BLOQUE = FRECUENCIA * MS_BLOQUE // 1000 * 2  # 16 bits, mono

BLOQUES_CALIBRACION = 15   # 300 ms de silencio para medir el ruido de fondo
CALIBRACION_MAX_S = 3.0    # tiempo real maximo para completar la calibracion
BLOQUES_INICIO = 5         # 100 ms seguidos con voz para considerar que empezo
BLOQUES_PRE_ROLL = 15      # 300 ms previos que se conservan para no cortar la primera silaba (pre-roll = audio anterior al inicio)
BLOQUES_COLA_FINAL = 10    # 200 ms de silencio que se conservan al final
UMBRAL_MINIMO = 350.0      # el umbral (nivel RMS que separa voz de ruido) nunca baja de este valor...
UMBRAL_MAXIMO = 2500.0     # ...ni sube de este
ESPERA_DATOS_S = 2.0       # Si el dispositivo no entrega audio en este tiempo entonces se descarta

# Programas de captura, según en orden de preferencia: nombre, comando, opcion de dispositivo
# (arecord = ALSA, el sistema de audio de Linux; parec = PulseAudio, el servidor de sonido; "raw" = audio sin cabecera)
PROGRAMAS = (
    ("arecord",
     ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(FRECUENCIA), "-c", "1"],
     "-D"),
    ("parec",
     ["parec", "--format=s16le", f"--rate={FRECUENCIA}", "--channels=1", "--raw"],
     "--device"),
)

class CapturaError(Exception):
    """Revisa si no se pudo capturar la voz, para que el nodo pase al modo teclado."""

@dataclass   # dataclass: clase que solo guarda datos; Python le genera el constructor
class Captura:
    """Resultado de capturar_voz: lo que recibe transcriptor_voz.py."""
    ruta: Path
    duracion_s: float
    programa: str
    umbral_rms: float                # nivel que separo voz de ruido en esta captura
    motivo_fin: str                  # "silencio" o "limite_duracion"
    t_fin_habla_estimado: float      # time.monotonic(); ver nota en el docstring del modulo
    tiempo_captura_ms: float         # desde el fin de habla estimado hasta tener el WAV listo


def calcular_rms(bloque):
    # RMS (raíz de la media de los cuadrados): mide la "fuerza" o volumen de un bloque; más alto = más sonido
    muestras = array.array("h")
    muestras.frombytes(bloque[: len(bloque) // 2 * 2])
    if not muestras:
        return 0.0
    return math.sqrt(sum(m * m for m in muestras) / len(muestras))


class DetectorVoz:
    """Decide cuando empieza y cuando termina la frase, bloque a bloque (20 ms).

    Recibe cada bloque con procesar(). Etapas: calibrando (mide el ruido) -> esperando voz ->
    hablando (guarda el audio) -> terminado (por silencio o por límite de duración).
    Es una detección de voz simple por energía (VAD): no entiende palabras, solo volumen.
    """

    def __init__(self, silencio_fin_s=0.8, max_duracion_s=15.0, umbral_rms=None):
        self.bloques_silencio_fin = max(1, round(silencio_fin_s * 1000 / MS_BLOQUE))
        self.max_bloques = round(max_duracion_s * 1000 / MS_BLOQUE)
        self.umbral = umbral_rms
        self._calibracion = []
        self._pre_roll = deque(maxlen=BLOQUES_PRE_ROLL)
        self._seguidos_con_voz = 0
        self.bloques = []             # audio de la frase
        self.hablando = False
        self.terminado = False
        self.motivo_fin = ""
        self.t_inicio_habla = None    # llegada del bloque en que se confirmo el inicio
        self.t_fin_habla = None       # llegada del ultimo bloque con energia sobre el umbral
        self._silencio = 0
        self._ultimo_con_voz = -1

    @property
    def calibrado(self):
        return self.umbral is not None

    def _fijar_umbral(self):
        # el umbral es 3 veces el ruido típico (mediana, que ignora picos aislados), dentro de los límites
        ruido = statistics.median(self._calibracion)
        self.umbral = min(UMBRAL_MAXIMO, max(UMBRAL_MINIMO, 3.0 * ruido))

    def _terminar(self, motivo):
        self.terminado = True
        self.motivo_fin = motivo
        # se recorta el silencio sobrante del final
        self.bloques = self.bloques[: self._ultimo_con_voz + 1 + BLOQUES_COLA_FINAL]

    def forzar_fin(self):
        """Termina por limite de tiempo real, conservando lo grabado hasta ahora."""
        if self.hablando and not self.terminado:
            self._terminar("limite_duracion")

    def procesar(self, bloque, ahora):
        """Procesa un bloque de 20 ms. `ahora` es la hora de llegada (time.monotonic())."""
        if self.terminado:
            return

        nivel = calcular_rms(bloque)

        if self.umbral is None:
            self._calibracion.append(nivel)
            self._pre_roll.append(bloque)
            if len(self._calibracion) >= BLOQUES_CALIBRACION:
                self._fijar_umbral()
            return

        con_voz = nivel >= self.umbral

        if not self.hablando:
            self._pre_roll.append(bloque)
            self._seguidos_con_voz = self._seguidos_con_voz + 1 if con_voz else 0
            if self._seguidos_con_voz >= BLOQUES_INICIO:
                self.hablando = True
                self.bloques = list(self._pre_roll)
                self._ultimo_con_voz = len(self.bloques) - 1
                self.t_inicio_habla = ahora
                self.t_fin_habla = ahora
                self._silencio = 0
            return

        self.bloques.append(bloque)
        if con_voz:
            self._silencio = 0
            self._ultimo_con_voz = len(self.bloques) - 1
            self.t_fin_habla = ahora
        else:
            self._silencio += 1

        if self._silencio >= self.bloques_silencio_fin:
            self._terminar("silencio")
        elif len(self.bloques) >= self.max_bloques:
            self._terminar("limite_duracion")

    def audio(self):
        return b"".join(self.bloques)


class _Fuente:
    """Programa de captura en ejecucion, su tarea es leer su stdout en un hilo y se limpiarlo por completo.

    Lanza arecord/parec como proceso aparte, que escribe el audio por su salida estándar (stdout,
    un "pipe" o tubería entre procesos). Un hilo lo lee en bloques de 20 ms y los deja en una cola
    junto con la hora de llegada; capturar_voz los toma de esa cola.
    """

    def __init__(self, nombre, orden):
        self.nombre = nombre
        # stderr va a un archivo temporal: si el programa escribe mucho (avisos de ALSA o
        # PulseAudio) nunca se llena un pipe ni se bloquea la captura.
        self.errores = tempfile.TemporaryFile()
        self.proceso = subprocess.Popen(
            orden, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=self.errores
        )
        self.cola = queue.Queue()   # cola segura entre hilos: aquí llegan (hora, bloque) o None si el programa terminó
        self.hilo = threading.Thread(target=self._leer, daemon=True)   # daemon: no impide cerrar el programa
        self.hilo.start()

    def _leer(self):
        try:
            while True:
                # bufsize por defecto: read(n) espera el bloque completo, no devuelve parciales
                datos = self.proceso.stdout.read(BYTES_BLOQUE)
                if not datos:
                    break
                # la hora se toma AL LEER el pipe, sin esperar a que el consumidor procese
                self.cola.put((time.monotonic(), datos))
        except (OSError, ValueError):
            pass
        finally:
            self.cola.put(None)

    def detalle_error(self):
        try:
            self.errores.seek(0)
            return self.errores.read()[-300:].decode(errors="replace").strip()
        except (OSError, ValueError):
            return ""

    def cerrar(self):
        """Su tarea es terminar el proceso, esperar su salida y cerrar pipes y archivos."""
        proceso = self.proceso
        if proceso.poll() is None:      # poll() es None mientras el proceso sigue vivo
            proceso.terminate()         # terminate = pedirle que termine; kill = obligarlo
            try:
                proceso.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proceso.kill()
                try:
                    proceso.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    pass

        self.hilo.join(timeout=1.0)
        
        # Si el hilo sigue leyendo (el pipe lo retiene otro proceso) 
        # Se debe cerrar stdout, para que se quede esperando el candado de lectura, asi se deja al hilo daemon.
        if not self.hilo.is_alive():
            try:
                proceso.stdout.close()
            except OSError:
                pass
        try:
            self.errores.close()
        except OSError:
            pass

def _abrir_microfono(dispositivo):
    """Función que devuelve (fuente, primer_bloque) del primer programa que entregue audio

    Prueba arecord y luego parec; el primero que entregue un bloque de audio en ESPERA_DATOS_S se usa.
    Si ninguno sirve lanza CapturaError con el motivo de cada uno. `dispositivo` vacío = el predeterminado."""
    errores = []
    for nombre, comando, opcion in PROGRAMAS:
        if shutil.which(comando[0]) is None:
            errores.append(f"¡{nombre}: no esta instalado!")
            continue

        orden = list(comando)
        if dispositivo:
            orden += [opcion, dispositivo]
        try:
            fuente = _Fuente(nombre, orden)
        except OSError as error:
            errores.append(f"{nombre}: {error}")
            continue

        try:
            primero = fuente.cola.get(timeout=ESPERA_DATOS_S)
        except queue.Empty:
            primero = None

        if primero:
            return fuente, primero

        fuente.cerrar()
        errores.append(f"{nombre}: sin audio {fuente.detalle_error()}".strip())

    raise CapturaError("¡Error!¡No se pudo abrir el microfono (" + "; ".join(errores) + ")!")


def capturar_voz(carpeta_salida, dispositivo="", silencio_fin_s=0.8,
                 espera_inicio_s=8.0, max_duracion_s=15.0, umbral_rms=None,
                 informar=print):
                   
    """Graba una frase del microfono y la guarda como WAV en carpeta_salida.

    Recibe: carpeta_salida, dispositivo (opcional), silencio_fin_s (silencio que da por terminada la
    frase), espera_inicio_s (cuánto esperar a que empieces), max_duracion_s e informar (función para
    mostrar mensajes). Devuelve una Captura o lanza CapturaError. Todos los límites son de tiempo real.
    """
    carpeta = Path(carpeta_salida)
    carpeta.mkdir(parents=True, exist_ok=True)

    if umbral_rms is None:
        informar("[VOZ] Calibrando el ruido de fondo. Guarda silencio un momento...")
    fuente, primero = _abrir_microfono(dispositivo)
    detector = DetectorVoz(silencio_fin_s, max_duracion_s, umbral_rms)

    # time.monotonic(): reloj que solo avanza (no cambia si se ajusta la hora del sistema); sirve para medir duraciones
    t_calibracion = time.monotonic() + CALIBRACION_MAX_S
    t_espera = None  # limite para empezar a hablar; se fija al avisar "Habla ahora"
    pendiente = primero
    avisado = False

    try:
        while not detector.terminado:
            
            # El aviso solo se muestra cuando el umbral ya esta fijado (calibracion terminada)
            if detector.calibrado and not avisado:
                avisado = True
                t_espera = time.monotonic() + espera_inicio_s
                informar("[VOZ] Microfono listo. Habla ahora...")

            # Cada vuelta: ¿en qué etapa estoy? -> su límite de tiempo -> tomar un bloque -> dárselo al detector
            ahora = time.monotonic()
            if not detector.calibrado:
                limite = t_calibracion
            elif not detector.hablando:
                limite = t_espera
            else:
                limite = detector.t_inicio_habla + max_duracion_s

            restante = limite - ahora
            if restante <= 0:
                if not detector.calibrado:
                    raise CapturaError("¡No se pudo calibrar el ruido de fondo a tiempo!")
                if not detector.hablando:
                    raise CapturaError(f"¡No se detecto voz en {espera_inicio_s:g} s!")
                detector.forzar_fin()
                break

            if pendiente is not None:
                elemento, pendiente = pendiente, None
            else:
                try:
                    elemento = fuente.cola.get(timeout=min(ESPERA_DATOS_S, restante))
                except queue.Empty:
                    if restante <= ESPERA_DATOS_S:
                        continue  # se cumplio el limite de tiempo: lo resuelve la vuelta siguiente
                    raise CapturaError("¡El micrófono dejo de entregar audio!")

            if elemento is None:
                raise CapturaError("¡El programa de captura se cerró inesperadamente!")
            llegada, bloque = elemento
            detector.procesar(bloque, llegada)
    finally:
        fuente.cerrar()

    # Guardado: WAV (archivo de audio sin compresión) mono, 16 bits (2 bytes por muestra), a 16 kHz
    audio = detector.audio()
    nombre = f"mic_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}.wav"
    ruta = carpeta / nombre
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(FRECUENCIA)
        archivo.writeframes(audio)

    return Captura(
        ruta=ruta,
        duracion_s=len(audio) / (FRECUENCIA * 2),
        programa=fuente.nombre,
        umbral_rms=detector.umbral,
        motivo_fin=detector.motivo_fin,
        t_fin_habla_estimado=detector.t_fin_habla,
        tiempo_captura_ms=(time.monotonic() - detector.t_fin_habla) * 1000,
    )
