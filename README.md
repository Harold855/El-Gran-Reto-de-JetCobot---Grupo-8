# El Gran Reto del JetCobot — Grupo 8

| Integrante | Pregunta | Trabajo realizado |
|---|---|---|
| **Integrante 1** | **P1** — Servicio de interpretación de órdenes (LAYA) | Servicio ROS 2 `/interpretar_orden` con interfaz `InterpretarOrden.srv`; cliente HTTP de LAYA con preguntas de opción única; clasificador por palabras clave de respaldo y reconciliación con la decisión de LAYA; 50 frases de práctica con su decisión esperada y script de medición de latencia y exactitud. |
| **Integrante 2** | **P2** — Agarre autónomo con acceso exclusivo al brazo | Broker ROS 2 de acceso exclusivo (admisión, cola y *worker* único) con políticas `fifo`, `round_robin` y prioridad con envejecimiento; cinemática directa DH contrastada con el URDF y con un modelo PoE; visión por color de los cuatro cubos; calibración, mapa visual y métricas de la cola. |
| **Integrante 3** | **P3** — De la voz al movimiento | Transcripción de audio y micrófono con Google AI Studio, límite de espera propio y respaldo por teclado; conexión con `/interpretar_orden`; registro CSV de cada orden con sus tiempos y evidencias de 10 audios. |

Sistema para controlar el **JetCobot** con órdenes en lenguaje natural: el operador **habla o escribe** una frase en español, el sistema la convierte en texto, decide si es una orden de *pick and place* permitida y gobierna el brazo mediante una cola de acceso exclusivo, con cinemática y visión por color.

Proyecto del curso de Robótica. Todo el software corre sobre **ROS 2 Humble** (Ubuntu 22.04).

---

## Arquitectura

El sistema vive en tres máquinas. El grafo ROS 2 está en el Jetson de cada equipo; la transcripción se resuelve en Google AI Studio y el modelo LAYA corre en la computadora del laboratorio. Ninguno de los dos es un nodo ROS 2.

```text
 Micrófono / archivo de audio
            │
            ▼
   ┌─────────────────┐   HTTPS    ┌────────────────────┐
   │ transcriptor_voz│ ─────────► │  Google AI Studio  │  audio → texto        (P3)
   └────────┬────────┘            └────────────────────┘
            │  (si falla o no hay Internet: modo teclado)
            ▼   servicio ROS 2 /interpretar_orden
   ┌──────────────────┐   HTTP    ┌────────────────────┐
   │interprete_ordenes│ ────────► │        LAYA        │  decisión             (P1)
   └────────┬─────────┘           └────────────────────┘
            │  decisión tipada: acción, objeto, color,
            │  destino, prioridad, permitido, degradado, motivo
            ▼
   ┌─────────────────┐
   │   arm_broker    │  cola con políticas, único publicador hacia el brazo   (P2)
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
│   ├── transcriptor_voz/            P3 · Voz → texto → /interpretar_orden → registro CSV
│   │   ├── transcriptor_voz.py        nodo ROS 2 (archivo de audio o micrófono)
│   │   ├── transcripcion_google.py    cliente de Google AI Studio
│   │   └── captura_microfono.py       grabación con detección de fin de frase
│   ├── interprete_ordenes/          P1
│   │   ├── interprete_ordenes/        servicio /interpretar_orden, cliente LAYA y clasificador por reglas
│   │   └── interprete_ordenes_interfaces/   paquete con InterpretarOrden.srv
│   ├── arm_broker/                  P2 · Broker de acceso exclusivo al brazo
│   │   ├── broker.py, fk.py, politicas.py   nodo, cinemática directa y políticas de cola
│   │   ├── cinematica_urdf.py, fk_poe.py    FK de referencia (URDF y PoE) para contrastar fk.py
│   │   ├── cliente_brazo.py                 cliente de prueba del broker
│   │   └── test/                            pruebas de FK y de políticas
│   ├── arm_broker_interfaces/       P2 · Acción MoveArm y mensaje QueueState
│   └── jetcobot/                    P2 · Visión por color, posiciones, pick and place y MoveIt 2
│       ├── rutas.py                   rutas del repositorio para los scripts de P2
│       ├── config/                    robot.yaml y zonas_trabajo.json
│       └── modelos/jetcobot.urdf      modelo del robot
├── scripts/
│   ├── ejecutar_frases_50.py        P1 · Mide latencia y exactitud sobre las frases de prueba
│   ├── ajustar_preguntas_laya.py    P1 · Ajusta las preguntas enviadas a LAYA
│   ├── p2/                          P2 · Visión, calibración, métricas del broker y tablas DH
│   │   └── calibracion_supervisada/   mueven el brazo por puerto serie: solo con el broker detenido
│   ├── iniciar.sh, cliente.sh, verificar.sh, detener.sh   P2 · operación del broker (respetan ROS_DOMAIN_ID; 57 si no hay ninguno)
│   ├── p3_genera_latencias.py       P3 · Resumen de latencias de la cadena de voz
│   ├── p3_prueba_timeout_local.py   P3 · Prueba del límite local de espera (sin llamar a Google)
│   └── p3_diagnostico_google.py     P3 · Diagnóstico de red y latencia de la transcripción
└── evidencias/
    ├── pregunta_1/                  50 frases de práctica (csv y md)
    ├── pregunta_2/                  calibracion/, camara/ y mapas/ de la visión y el brazo
    └── pregunta_3/                  Audios, capturas, transcripciones.csv y README propio
```
---

## Componentes

### 1. `transcriptor_voz` — de la voz al texto (P3)

Nodo ROS 2 (`transcriptor_voz`) que toma un archivo de audio o captura del micrófono, obtiene la transcripción en español, la envía a `/interpretar_orden` y registra cada orden en `evidencias/pregunta_3/transcripciones.csv`.

- **Google AI Studio** (`transcripcion_google.py`): envía el audio en la misma solicitud y devuelve el texto. Modelo configurable con `GEMINI_MODELO_TRANSCRIPCION` (por defecto `gemini-3.5-transcribe`). Formatos: wav, mp3, m4a, ogg, flac, aac y webm, hasta 10 MB.
- **Clave de API**: se lee de la variable de entorno `GEMINI_API_KEY` (o `GOOGLE_API_KEY`). Nunca se escribe en el código.
- **Límite de espera propio**: la llamada a Google se ejecuta con un tiempo máximo real (`timeout_transcripcion_s`). Al agotarse, no hay Internet, falta la clave o la transcripción llega vacía, el sistema activa el **modo teclado** y lo informa.
- **Micrófono** (`captura_microfono.py`): graba un WAV mono de 16 kHz. Calibra el ruido de fondo en silencio, avisa «Habla ahora», espera a que empieces a hablar y termina al detectar silencio. Usa `arecord` (alsa-utils) o `parec` (pulseaudio-utils), sin librerías de Python adicionales. Los límites son de **tiempo real**, y mide `tiempo_captura_ms` desde el **fin de habla estimado por energía** (no es el instante exacto).
- **Evidencia**: cada audio se conserva en `evidencias/pregunta_3/audios/` sin duplicar copias (nombre con hash del contenido) y cada ejecución agrega una fila al CSV con el audio, el texto, el origen (`google` o `teclado`), la decisión recibida y los tiempos.

**Parámetros ROS 2:** `timeout_transcripcion_s` (30), `timeout_servicio_s` (5), `silencio_fin_s` (0.8), `espera_inicio_s` (8), `max_duracion_s` (15). Hacia P2: `enviar_a_p2` (`true`), `permitir_degradado` (`false`), `timeout_servidor_p2_s` (3) y `timeout_resultado_p2_s` (120).

**Columnas de `transcripciones.csv`:** `fecha`, `audio_original`, `audio_copia`, `transcripcion`, `origen`, `tiempo_google_ms`, `id_solicitud`, `accion`, `objeto`, `color`, `destino`, `prioridad`, `permitido`, `degradado`, `motivo`, `resultado`, `tiempo_servicio_ms`, `tiempo_total_ms`, `tiempo_teclado_ms`, `tiempo_captura_ms`. Entrega a P2: `enviado_p2`, `aceptado_p2`, `estado_p2`, `codigo_p2`, `simulado_p2`, `mensaje_p2`, `tiempo_aceptacion_p2_ms`, `tiempo_resultado_p2_ms`, `espera_cola_p2_s`, `ejecucion_p2_s`, `etapas_p2`, `tiempo_total_p2_ms` (lo no medido queda vacío).

**Entrega a P2** (`envio_pickplace.py`): si P1 devuelve `permitido=true`, `trasladar` sobre un `cubo`, colores válidos y prioridad 1 a 3, P3 envía la tarea a la acción `/pick_place` con el mismo `id_solicitud` que usó con P1 y registra aceptación, etapas y resultado. Una decisión degradada (clasificador de respaldo) no se envía salvo `permitir_degradado:=true`. P3 nunca manda movimientos articulares ni publica en `/joint_states`: P2 valida de nuevo y es el único que mueve el brazo. Un resultado de broker simulado queda como `simulado_p2=True` y no cuenta como movimiento. El código de salida es 0 si la tarea terminó en `COMPLETADO` o no correspondía enviarla, y 2 si P2 la rechazó, falló o expiró el tiempo.

### 2. `interprete_ordenes` — del texto a una decisión (P1)

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

**Cliente de LAYA** (`laya_cliente.py`). Consulta el endpoint HTTP `/v1/systemone` de LAYA con **preguntas de opción única** y valida seis decisiones: acción, objeto, color, destino, prioridad y si la orden está permitida. Las preguntas son criterios fijos de evaluación: no entrenan al modelo. La dirección se toma de `LAYA_URL` (o del parámetro `laya_url`) y el tiempo máximo de `laya_timeout` (4 s). `scripts/ajustar_preguntas_laya.py` aplica los ajustes de redacción de esas preguntas con verificación previa y respaldo.

**Clasificador por palabras clave.** Acepta una **orden básica de *pick and place***: un verbo de recoger o colocar (*recoge, toma, agarra, coloca, pon, mueve, lleva, traslada*), «cubo» seguido de su color y «zona» seguida de su color, con los cuatro colores exactos (**rojo, verde, azul, amarillo**). Rechaza, con su motivo:

| Se rechaza | Ejemplos |
|---|---|
| Negaciones y acciones que el brazo no hace | «No recojas…», «Lanza…», «Camina…», «Golpea…», «Apila…» |
| Falta el cubo o su color | «Recoge el cubo morado…», «Recoge los cubos…» |
| Falta la zona o su color | «Recoge el cubo amarillo» |
| Variantes de color frecuentes | «rojo fuerte», «azul marino», «verde lima» |
| Frases sin verbo de recoger o colocar | «¿Qué hora es?» |

Es el respaldo cuando LAYA no responde: resuelve las órdenes básicas; las órdenes complejas (velocidad, varios cubos, órdenes compuestas, sinónimos poco comunes) quedan para LAYA.

**Combinación con LAYA.** Cuando LAYA responde, el nodo contrasta su decisión con el clasificador (`validacion_estricta`): si LAYA acepta algo que las reglas rechazan, se veta. Con `corregir_con_reglas` (por defecto `false`) las reglas además **corrigen** los errores de LAYA: si se equivoca de color o destino se usan los de la frase, y si niega una orden que las reglas validan se acepta; en esos casos `degradado=true`. Se activa con `--ros-args -p corregir_con_reglas:=true`. El nodo registra en el log lo que respondió LAYA campo a campo.

**Parámetros ROS 2:** `laya_url`, `laya_timeout` (4.0), `validacion_estricta` (`true`) y `corregir_con_reglas` (`false`).

### 3. `arm_broker` — acceso exclusivo al brazo (P2)

Nodo `ArmBroker`: es el **único** que publica en `/joint_states`; los clientes solo envían *goals* a un servidor de acciones (`MoveArm`, del paquete `arm_broker_interfaces`).

- Un goal pasa por **admisión → cola → ejecución exclusiva** (un *worker* único).
- **Políticas de cola**: `fifo`, `round_robin` y `prioridad` (prioridad con envejecimiento: puntaje `priority + espera/tau`, así ningún cliente queda sin atención). Prioridad de 0 a 255 (mayor número, más urgente).
- **Admisión**: rechaza con causa y motivo si el objetivo excede los límites articulares, sale del espacio de trabajo, supera el paso articular máximo o la cola está llena; cada rechazo se registra en `rechazos.csv`.
- Publica el estado de la cola en `/arm/queue_state`.
- **`/pick_place`** (`arm_broker_interfaces/action/PickPlace`): recibe una tarea ya autorizada por P1 (`id_solicitud`, `color_objetivo`, `destino`, `priority` 1 a 3) y la encola en la **misma cola y worker** que `/move_arm`, de modo que nunca hay dos movimientos a la vez. Rechaza antes de encolar los colores, destinos (solo rojo, verde, azul y amarillo del tablero izquierdo), prioridades e identificadores inválidos o repetidos. Devuelve feedback por etapas (`EN_COLA`, `PERCEPCION`, `APROXIMACION`, `AGARRE`, `TRASLADO`, `DEPOSITO`, `RETIRADA`) y un `codigo_resultado` (`COMPLETADO`, `OBJETO_AUSENTE`, `NO_CONFIGURADO`, `ERROR_AGARRE`, `CANCELADO`…).
- **Modos de ejecución** (`modo_ejecucion`): `simulado` (por defecto) corre la secuencia real con percepción, movimiento y pinza falsos y marca todo como SIMULADO; `real` exige `permitir_movimiento_real:=true` y falla cerrado (`NO_CONFIGURADO`) mientras no haya respaldos de hardware.
- **Registro por tarea** (`registro_tareas.csv`): eventos y tiempos por `id_solicitud` (solicitud, admisión, cola, inicio del worker, etapas y fin), con la marca `simulado`. La columna `registro` separa `tarea` de `rechazo`: una solicitud rechazada (por ejemplo con un `id_solicitud` repetido) no altera los eventos de la tarea activa con ese id.
- **Parámetros:** `politica` (`fifo`), `tau_envejecimiento_s` (8.0, solo para `prioridad`), `cola_max` (20), `paso_max_rad` (1.2), `duracion_movimiento_s` (3.0), `pasos_interpolacion` (10), `archivo_rechazos` (`rechazos.csv`), `modo_ejecucion` (`simulado`), `permitir_movimiento_real` (`false`), `archivo_registro_tareas` (`registro_tareas.csv`).
- `fk.py`: cinemática directa del JetCobot con tabla Denavit-Hartenberg, verificación de límites articulares y de espacio de trabajo, y paso articular máximo.
- `cinematica_urdf.py` y `fk_poe.py`: cinemática de referencia (desde el URDF y con producto de exponenciales) para contrastar `fk.py`; el broker no las usa.
- Pruebas sin ROS ni hardware: `python3 -m unittest discover -s src/arm_broker/test` (FK, referencia PoE, políticas, admisión, cola compartida, cancelación y trazabilidad de `/pick_place`; el broker se prueba contra un ROS 2 falso y `test_fk_poe.py` requiere numpy y scipy) y `python3 -m unittest discover -s src/jetcobot/test` (configuración, secuencia de pick and place, visión sobre las imágenes del repositorio y planificación de MoveIt).

### 4. `jetcobot` — visión y *pick and place* (P2)

- `vision_colores.py`: detección de los cuatro colores por rangos HSV con cámara de 640×480, filtrando por área y relación de aspecto. `detectar_cubos` devuelve el centro, el área y el rectángulo de cada cubo; `dibujar_detecciones` los marca en la imagen. Es la única implementación de visión: los scripts de `scripts/p2/` la llaman.
- `rutas.py`, `config/` y `modelos/`: rutas del repositorio, configuración del robot (`ROS_DOMAIN_ID` 57), zonas de trabajo y URDF.
- `posiciones.py`: pose de escaneo, destinos por color (posición, alturas de aproximación y de dejada, orientación) y validación de poses.
- `pick_and_place.py`: control de la pinza, `recoger_cubo`, `entregar_cubo` y `ejecutar_pick_and_place` para un color objetivo y un destino.
- `integration_moveit.py`: conversión de orientación (Rx, Ry, Rz) a cuaternión, validación de trayectorias de MoveIt 2 y cálculo del error entre la pose solicitada y la alcanzada con la cinemática directa.

---

## Frases de práctica

`evidencias/pregunta_1/frases_50.{csv,md}` contiene **50 frases** con la decisión esperada para cada una: **23 a aceptar y 27 a rechazar**, repartidas en 14 categorías (órdenes directas, variaciones de verbo, de cubo y de zona, colores no reconocidos y degradados, objetos que no son cubos, negativas, acciones no permitidas, incompletas, ambiguas y cambios de parámetros). Las frases 1 a 10 son los audios grabados por el tercer integrante del equipo.

Con estas frases, el clasificador por palabras clave acierta **40 de 50**: resuelve las órdenes básicas (incluidos los 10 audios del equipo) y falla las categorías complejas (cambios de velocidad, órdenes compuestas, «o», sinónimos poco comunes y verbos menos usuales). Esas son las frases que resuelve LAYA.

---

## Scripts

### `scripts/ejecutar_frases_50.py` (P1)

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

### `scripts/p2/` (P2)

Se ejecutan desde la raíz del repositorio (`python3 scripts/p2/<script>.py`); las rutas salen de `src/jetcobot/rutas.py`.

- **Visión y mapas**: `probar_reconocimiento.py` (captura y detecta; guarda en `evidencias/pregunta_2/camara/`), `calibrar_camara.py`, `crear_mapa_visual.py` (`mapas/`), `analizar_perspectiva.py` e `inspeccionar_contornos.py`.
- **Broker**: `generar_carga.py` (poses reproducibles para los cuatro clientes), `exportar_csv.py` (rosbag → `queue_state.csv` y `joint_states.csv`) y `metricas.py` (espera media y p95, inanición y equidad de Jain; escribe en `evidencias/pregunta_2/mediciones/`).
- **Cinemática**: `ajustar_dh.py`, `generar_dh.py`, `validar_dh_profesor.py`, `probar_cola_real.py` y `importar_coordenadas.py`.
- **`calibracion_supervisada/`**: `inicializar_brazo.py`, `ir_escaneo.py`, `escaneo_eje_y.py`, `verificar_fk.py` y similares abren el puerto serie y mueven el brazo sin pasar por el broker. Se usan solo con el broker detenido y con alguien junto al robot; no se ejecutan durante la demostración ni junto a la Pregunta 3.

### Operación del broker (P2)

`scripts/iniciar.sh` (variable `POLITICA` para elegir la política), `scripts/cliente.sh <cliente> <prioridad>`, `scripts/verificar.sh` y `scripts/detener.sh`. Respetan el `ROS_DOMAIN_ID` de la terminal y usan 57 solo si no hay ninguno; lo muestran al iniciar. `MODO=simulado` (por defecto) no toca hardware; `MODO=real` exige además `PERMITIR_MOVIMIENTO_REAL=si`.

### `scripts/p3_*.py` (P3)

- `p3_genera_latencias.py`: lee `transcripciones.csv` (sin modificarlo) y produce `latencias_resumen.csv` y `tabla_solicitudes_p3.csv` en `evidencias/pregunta_3/`.
- `p3_prueba_timeout_local.py`: prueba controlada del límite local de espera, sin llamar a Google, sin clave y sin escribir el CSV.
- `p3_diagnostico_google.py`: mide por separado el audio (duración y tamaño), la red hacia Google (DNS, TCP y TLS por IPv4 e IPv6) y varias transcripciones con el mismo audio, y sugiere un valor para `timeout_transcripcion_s`. No escribe en el repositorio ni imprime la clave.

---

## Instalación

**Requisitos:** Ubuntu 22.04, ROS 2 Humble, `colcon` y Python 3.10. Los scripts de visión y calibración de P2 usan además `numpy`, `scipy`, `opencv-python` y `pymycobot`.

```bash
# 1) Interfaces y broker (desde la raíz del repositorio)
source /opt/ros/humble/setup.bash
colcon build --packages-select interprete_ordenes_interfaces arm_broker_interfaces arm_broker
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

**Broker del brazo (P2)**

```bash
scripts/iniciar.sh                    # broker; POLITICA=fifo|round_robin|prioridad
scripts/cliente.sh alumno_1 5         # un cliente con su prioridad (0-255)
scripts/verificar.sh                  # acciones, publicador y estado de la cola
```
---

## Evidencias

### Pregunta 1

`evidencias/pregunta_1/frases_50.{csv,md}`: las 50 frases con su categoría y decisión esperada. `scripts/ejecutar_frases_50.py` escribe las mediciones en `evidencias/pregunta_1/mediciones/`.

### Pregunta 2 — `evidencias/pregunta_2/`

- **`calibracion/`**: escaneo inicial y desplazamientos en X e Y desde la postura de escaneo, con las detecciones de los cuatro cubos marcadas en cada comparación (`comparacion_movimiento_x.png`, `encuadres/`, `escaneo_y_*/`); postura de escaneo preferida; validación del modelo visual (`validacion_modelo_*/`, con perspectiva y superposición); recuperación del escaneo; modelo visual preliminar (relación entre los movimientos del robot en el plano y el desplazamiento en la imagen); y `referencias_urdf.npz`, las 100 poses de referencia del URDF con las que se ajusta y valida la tabla DH.
- **`camara/`**: capturas de la cámara con los cuatro colores y su detección.
- **`mapas/`**: mapa visual con los centros de los cuatro cubos y las distancias entre ellos en píxeles.
- **Pruebas automáticas**: `src/arm_broker/test/` comprueba la FK contra el URDF (posición cero, matrices homogéneas y rechazo de entradas inválidas), el modelo PoE contra las poses de validación y las tres políticas de cola (orden FIFO, prioridad, envejecimiento, desempate, rotación entre clientes y `tau` inválido).

### Pregunta 3

El detalle está en [`evidencias/pregunta_3/README.md`](evidencias/pregunta_3/README.md). Resumen de lo comprobado:

- **Transcripción de 10 audios** `.aac` grabados con un teléfono: las 10 conservaron el significado de la orden y 8 coincidieron literalmente con lo dictado. Tiempo habitual de Google: **3–4 s** por archivo.
- **Dato atípico conservado:** el primer intento del audio 8 tardó 35,72 s y al repetirlo 2,96 s. Ambos quedaron en el CSV.
- **Respaldo por teclado:** comprobado con una ruta inexistente, sin Internet y con un tiempo de espera agotado. En todos los casos se registró `origen=teclado` y la orden continuó hasta `/interpretar_orden`.
- **Integración con `/interpretar_orden`:** audio → Google → decisión estructurada, con órdenes permitidas y con órdenes rechazadas («Lanza…», «No recojas…»), probada en Ubuntu 22.04 sobre WSL2 con ROS 2 Humble.

## Seguridad

- La clave de la API se lee **solo** de una variable de entorno y no aparece en el código ni en el historial del repositorio.
- El movimiento directo del brazo por puerto serie queda confinado a `scripts/p2/calibracion_supervisada/` y se usa únicamente con el broker detenido; el broker es el único publicador hacia el brazo.
- `.gitignore` excluye `__pycache__/` y `*.pyc`. No se publican `build/`, `install/` ni `log/`.
