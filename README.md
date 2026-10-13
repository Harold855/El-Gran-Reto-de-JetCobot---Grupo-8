# El Gran Reto del JetCobot — Grupo 8

Sistema para controlar un brazo **Yahboom JetCobot** con órdenes en lenguaje natural: el operador **habla o escribe** una frase en español, el sistema la convierte en texto, decide si es una orden de *pick and place* permitida y deja disponible el control del brazo (cola de acceso exclusivo, cinemática, visión y agarre).

Proyecto del curso de Robótica. Todo el software corre sobre **ROS 2 Humble** (Ubuntu 22.04).

---

## Arquitectura

El sistema vive en tres máquinas. El grafo ROS 2 está en el Jetson de cada equipo; la transcripción se resuelve en Google AI Studio y el modelo LAYA corre en la computadora del laboratorio. Ninguno de los dos es un nodo ROS 2.

```text
 Micrófono / archivo de audio
            │
            ▼
   ┌─────────────────┐   HTTPS    ┌────────────────────┐
   │ transcriptor_voz│ ─────────► │  Google AI Studio  │  audio → texto
   └────────┬────────┘            └────────────────────┘
            │  (si falla o no hay Internet: modo teclado)
            ▼   servicio ROS 2 /interpretar_orden
   ┌─────────────────┐
   │interprete_ordenes│  decisión tipada: acción, objeto, color,
   └────────┬────────┘  destino, prioridad, permitido, degradado, motivo
            ▼
   ┌─────────────────┐
   │   arm_broker    │  cola de prioridad, único publicador hacia el brazo
   └────────┬────────┘
            ▼
        JetCobot   ◄── visión por color, cinemática y pick and place (src/jetcobot)
```

La transcripción depende de Internet; la decisión y el movimiento no. Si falla la nube, el sistema continúa en **modo texto por teclado**.

---

## Estructura del repositorio

```text
.
├── src/
│   ├── transcriptor_voz/            Voz → texto → /interpretar_orden → registro CSV
│   │   ├── transcriptor_voz.py        nodo ROS 2 (archivo de audio o micrófono)
│   │   ├── transcripcion_google.py    cliente de Google AI Studio
│   │   └── captura_microfono.py       grabación con detección de fin de frase
│   ├── interprete_ordenes/
│   │   ├── interprete_ordenes/        servicio /interpretar_orden y clasificador por reglas
│   │   └── interprete_ordenes_interfaces/   paquete con InterpretarOrden.srv
│   ├── arm_broker/                  Broker de acceso exclusivo al brazo (cola, políticas, FK)
│   └── jetcobot/                    Visión por color, posiciones, pick and place y MoveIt 2
├── scripts/
│   ├── ejecutar_frases_50.py        Mide latencia y exactitud sobre las frases de prueba
│   ├── p3_genera_latencias.py       Resumen de latencias de la cadena de voz
│   └── p3_prueba_timeout_local.py   Prueba del límite local de espera (sin llamar a Google)
└── evidencias/
    ├── pregunta_1/                  50 frases de práctica (csv, xlsx, md)
    └── pregunta_3/                  Audios, capturas, transcripciones.csv y README propio
```

---

## Componentes

### 1. `transcriptor_voz` — de la voz al texto

Nodo ROS 2 (`transcriptor_voz`) que toma un archivo de audio o captura del micrófono, obtiene la transcripción en español, la envía a `/interpretar_orden` y registra cada orden en `evidencias/pregunta_3/transcripciones.csv`.

- **Google AI Studio** (`transcripcion_google.py`): envía el audio en la misma solicitud y devuelve el texto. Modelo configurable con `GEMINI_MODELO_TRANSCRIPCION` (por defecto `gemini-3.5-transcribe`). Formatos: wav, mp3, m4a, ogg, flac, aac y webm, hasta 10 MB.
- **Clave de API**: se lee de la variable de entorno `GEMINI_API_KEY` (o `GOOGLE_API_KEY`). Nunca se escribe en el código.
- **Límite de espera propio**: la llamada a Google se ejecuta con un tiempo máximo real (`timeout_transcripcion_s`). Al agotarse, no hay Internet, falta la clave o la transcripción llega vacía, el sistema activa el **modo teclado** y lo informa.
- **Micrófono** (`captura_microfono.py`): graba un WAV mono de 16 kHz. Calibra el ruido de fondo en silencio, avisa «Habla ahora», espera a que empieces a hablar y termina al detectar silencio. Usa `arecord` (alsa-utils) o `parec` (pulseaudio-utils), sin librerías de Python adicionales. Los límites son de **tiempo real**, y mide `tiempo_captura_ms` desde el **fin de habla estimado por energía** (no es el instante exacto).
- **Evidencia**: cada audio se conserva en `evidencias/pregunta_3/audios/` sin duplicar copias (nombre con hash del contenido) y cada ejecución agrega una fila al CSV con el audio, el texto, el origen (`google` o `teclado`), la decisión recibida y los tiempos.

**Parámetros ROS 2:** `timeout_transcripcion_s` (15), `timeout_servicio_s` (5), `silencio_fin_s` (0.8), `espera_inicio_s` (8), `max_duracion_s` (15).

**Columnas de `transcripciones.csv`:** `fecha`, `audio_original`, `audio_copia`, `transcripcion`, `origen`, `tiempo_google_ms`, `id_solicitud`, `accion`, `objeto`, `color`, `destino`, `prioridad`, `permitido`, `degradado`, `motivo`, `resultado`, `tiempo_servicio_ms`, `tiempo_total_ms`, `tiempo_teclado_ms`, `tiempo_captura_ms`.

### 2. `interprete_ordenes` — del texto a una decisión

Nodo ROS 2 que expone el servicio **`/interpretar_orden`** y devuelve una **decisión tipada**, nunca texto generado.

`InterpretarOrden.srv`:

```text
string frase
---
string accion
string objeto
string color
string destino
int32 prioridad
bool permitido
bool degradado          # true = respondió el clasificador por palabras clave
string motivo           # causa cuando la orden se rechaza
float32 tiempo_servidor_ms   # lo que tardó el servidor en decidir (sin la red)
```

**Clasificador por palabras clave.** Solo acepta **una orden de *pick and place* de un cubo**: un verbo de recoger y colocar, un cubo con color y una zona con color, con los cuatro colores exactos (**rojo, verde, azul, amarillo**). Rechaza, con su motivo:

| Se rechaza | Ejemplos |
|---|---|
| Negaciones y prohibiciones | «No recojas…», «Nunca muevas…», «Evita…», «Deja de…» |
| Acciones distintas de recoger y colocar | «Lanza…», «Camina…», «Golpea…», «Gira…» |
| Objetos que no son cubos | esfera, pirámide, lápiz, marcador |
| Otros colores y variantes | morado, naranja, «rojo fuerte», «azul marino», «verde lima» |
| Varios cubos, órdenes compuestas o ambiguas | «dos cubos», «luego…», «el rojo o el verde» |
| Cambio de parámetros | velocidad, fuerza, apilar |
| Órdenes incompletas | falta el cubo, su color, la zona o su color |

Acepta variaciones del lenguaje: otros verbos (*recoge, toma, agarra, coge, lleva, mueve, coloca, pon, traslada, transporta, deposita…*), formas de usted («recoja… colóquelo»), sinónimos de cubo (*cubito, bloque*) y de zona (*área, sector, sección, región*), el destino mencionado primero y cortesías («por favor», «gracias»).

### 3. `arm_broker` — acceso exclusivo al brazo

Nodo `ArmBroker`: es el **único** que publica en `/joint_states`; los clientes solo envían *goals* a un servidor de acciones (`MoveArm`, del paquete `arm_broker_interfaces`).

- Un goal pasa por **admisión → cola → ejecución exclusiva** (un *worker* único).
- **Políticas de cola**: `fifo` y `round_robin`. Prioridad de 0 a 255 (mayor número, más urgente).
- **Admisión**: rechaza con causa y motivo si el objetivo excede los límites articulares, sale del espacio de trabajo o la cola está llena; cada rechazo se registra en `rechazos.csv`.
- Publica el estado de la cola en `/arm/queue_state`.
- **Parámetros:** `politica` (`fifo`), `cola_max` (20), `paso_max_rad` (1.2), `duracion_movimiento_s` (3.0), `pasos_interpolacion` (10), `archivo_rechazos` (`rechazos.csv`).
- `fk.py`: cinemática directa del JetCobot con tabla Denavit-Hartenberg, verificación de límites articulares y de espacio de trabajo, y paso articular máximo.

### 4. `jetcobot` — visión y *pick and place*

- `vision_colores.py`: detección de los cuatro colores por rangos HSV con cámara de 640×480, filtrando por área y relación de aspecto.
- `posiciones.py`: pose de escaneo, destinos por color (posición, alturas de aproximación y de dejada, orientación) y validación de poses.
- `pick_and_place.py`: control de la pinza, `recoger_cubo`, `entregar_cubo` y `ejecutar_pick_and_place` para un color objetivo y un destino.
- `integration_moveit.py`: conversión de orientación (Rx, Ry, Rz) a cuaternión, validación de trayectorias de MoveIt 2 y cálculo del error entre la pose solicitada y la alcanzada con la cinemática directa.

---

## Frases de práctica

`evidencias/pregunta_1/frases_practica_50.{csv,xlsx,md}` contiene **50 frases** con la decisión esperada para cada una: **23 a aceptar y 27 a rechazar**, repartidas en 14 categorías (órdenes directas, variaciones de verbo, de cubo y de zona, colores no reconocidos y degradados, objetos que no son cubos, negativas, acciones no permitidas, incompletas, ambiguas y cambios de parámetros). Las frases 1 a 10 son los audios grabados por el equipo.

Con estas frases, el clasificador por palabras clave acierta **50 de 50**. Además se verificó con conjuntos adicionales de redacciones distintas y con pruebas combinatorias (decenas de miles de órdenes válidas y de variantes que deben rechazarse).

---

## Scripts

### `scripts/ejecutar_frases_50.py`

Envía cada frase a `/interpretar_orden`, mide la latencia de ida y vuelta (mediana y percentil 95), ejecuta también el clasificador por palabras clave en local y compara ambas decisiones con el resultado esperado.

```bash
python3 scripts/ejecutar_frases_50.py --escenario calma \
    --prediccion-mediana-ms 40 --prediccion-p95-ms 80 --justificacion "red local, servidor libre"
```

- Exige escribir la **predicción antes de medir** (`--ensayo` la omite para probar el script).
- Separa el tiempo de red del cálculo del servidor cuando la respuesta trae `tiempo_servidor_ms`.
- Separa en la exactitud las respuestas de LAYA (`degradado=False`) de las del respaldo.
- `--escenario calma|carga` y `--comparar CALMA.csv CARGA.csv` generan la tabla comparativa.
- Escribe en `evidencias/pregunta_1/mediciones/`: un CSV por frase, un resumen en Markdown y `predicciones.csv`. Los nombres llevan la hora y no se sobrescriben.

### `scripts/p3_genera_latencias.py`

Lee `transcripciones.csv` (sin modificarlo) y produce `latencias_resumen.csv` y `tabla_solicitudes_p3.csv` en `evidencias/pregunta_3/`.

### `scripts/p3_prueba_timeout_local.py`

Prueba controlada del límite local de espera, sin llamar a Google, sin clave y sin escribir el CSV.

---

## Instalación

**Requisitos:** Ubuntu 22.04, ROS 2 Humble, `colcon` y Python 3.10.

```bash
# 1) Interfaz del servicio (desde la raíz del repositorio)
source /opt/ros/humble/setup.bash
colcon build --packages-select interprete_ordenes_interfaces
source install/setup.bash
ros2 interface show interprete_ordenes_interfaces/srv/InterpretarOrden

# 2) SDK de Google en un entorno que conserve rclpy
sudo apt install -y python3-pip python3-venv
python3 -m venv --system-site-packages ~/.venvs/gran_reto_g8
source ~/.venvs/gran_reto_g8/bin/activate
python3 -m pip install -U google-genai

# 3) Captura por micrófono (uno de los dos)
sudo apt install -y alsa-utils            # arecord
sudo apt install -y pulseaudio-utils      # parec (útil en WSL2)
```

Si cambias `InterpretarOrden.srv`, vuelve a compilar el paquete y reinicia los nodos.

## Uso

**Terminal 1 — intérprete de órdenes**

```bash
cd ~/gran_reto_g8
source /opt/ros/humble/setup.bash
source install/setup.bash
python3 src/interprete_ordenes/interprete_ordenes/interprete_ordenes.py
```

**Terminal 2 — de la voz a la decisión**

```bash
cd ~/gran_reto_g8
source /opt/ros/humble/setup.bash
source install/setup.bash
source ~/.venvs/gran_reto_g8/bin/activate

# La clave se escribe sin mostrarla ni guardarla en el historial
read -r -s -p "Introduce tu API key: " GEMINI_API_KEY; echo
export GEMINI_API_KEY

# Desde un archivo de audio
python3 src/transcriptor_voz/transcriptor_voz.py evidencias/pregunta_3/audios/audio_1.aac

# Desde el micrófono
python3 src/transcriptor_voz/transcriptor_voz.py --microfono

# Cambiando un parámetro
python3 src/transcriptor_voz/transcriptor_voz.py --microfono --ros-args -p silencio_fin_s:=0.6
```

Al terminar, `unset GEMINI_API_KEY`.

---

## Evidencias de la Pregunta 3

El detalle está en [`evidencias/pregunta_3/README.md`](evidencias/pregunta_3/README.md). Resumen de lo comprobado:

- **Transcripción de 10 audios** `.aac` grabados con un teléfono: las 10 conservaron el significado de la orden y 8 coincidieron literalmente con lo dictado. Tiempo habitual de Google: **3–4 s** por archivo.
- **Dato atípico conservado:** el primer intento del audio 8 tardó 35,72 s y al repetirlo 2,96 s. Ambos quedaron en el CSV.
- **Respaldo por teclado:** comprobado con una ruta inexistente, sin Internet y con un tiempo de espera agotado. En todos los casos se registró `origen=teclado` y la orden continuó hasta `/interpretar_orden`.
- **Integración con `/interpretar_orden`:** audio → Google → decisión estructurada, con órdenes permitidas y con órdenes rechazadas («Lanza…», «No recojas…»), probada en Ubuntu 22.04 sobre WSL2 con ROS 2 Humble.

## Seguridad

- La clave de la API se lee **solo** de una variable de entorno y no aparece en el código ni en el historial del repositorio.
- `.gitignore` excluye `__pycache__/` y `*.pyc`. No se publican `build/`, `install/` ni `log/`.

