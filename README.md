# El Gran Reto del JetCobot — Grupo 8

| Integrante | Pregunta Realizada | Trabajo encargado |
|---|---|---|
| **Sebastian Escobar** | **P1** — Servicio de interpretación de órdenes (LAYA) | Servicio ROS 2 `/interpretar_orden` con la interfaz `InterpretarOrden.srv`; cliente HTTP de LAYA con preguntas de opción única; clasificador por palabras clave de respaldo y validación estricta de las decisiones de LAYA; 50 frases de práctica con su decisión esperada; scripts de medición de latencia y de exactitud; informe final con la comparación LAYA frente a reglas. |
| **Jorge Rivera** | **P2** — Agarre autónomo con acceso exclusivo al brazo | Broker ROS 2 de acceso exclusivo (admisión, cola y *worker* único) con las acciones `/move_arm` y `/pick_place`; políticas de cola `fifo`, `round_robin` y prioridad con envejecimiento; ejecutor simulado y ejecutor real que falla cerrado; cinemática directa DH contrastada con el URDF y con un modelo PoE; visión por color de los cuatro cubos; calibración, mapa visual y métricas de la cola. |
| **Harold Payco** | **P3** — De la voz al movimiento | Captura por micrófono y transcripción con Google AI Studio, con límite de espera propio y respaldo por teclado; consulta al servicio de P1; entrega a P2 de la orden autorizada mediante `/pick_place`; registro CSV de cada orden con sus tiempos y su resultado; evidencias de 10 audios y de la sesión de laboratorio del 15 de octubre. |

## Descripción general

Repositorio que contiene el sistema del Grupo 8 para el *Gran Reto del JetCobot*, que usa un brazo **JetCobot**.

El trabajo se reparte en tres capas que se comunican por interfaces ROS 2 definidas y que pueden probarse por separado:

- **P3 — de la voz al texto.** Obtiene la frase a partir de un micrófono o de un archivo de audio. La transcripción depende de Google AI Studio y de Internet; si falla, hay un tiempo máximo real de espera y un **modo teclado**, de modo que la orden siempre puede continuar.
- **P1 — del texto a una decisión.** Un servicio ROS 2 consulta a LAYA (el modelo del laboratorio) con preguntas de opción única y devuelve una **decisión tipada** (acción, objeto, color, destino, prioridad, permitido y motivo), nunca texto libre. Un clasificador propio por palabras clave actúa como respaldo y como control: con la validación estricta, si LAYA y las reglas discrepan, la orden se rechaza.
- **P2 — de la decisión al brazo.** Un broker es el **único** que controla el brazo. Admite, encola y ejecuta las solicitudes una a una, con políticas de cola configurables, validación de límites articulares y de espacio de trabajo, y un ejecutor simulado que permite probar toda la cadena sin hardware.

Tres decisiones de diseño recorren el proyecto:

1. **Seguridad primero.** Ninguna capa mueve el brazo por su cuenta. P3 solo entrega la *tarea* (color, destino y prioridad), nunca movimientos articulares; P2 vuelve a validar todo antes de aceptar; y el ejecutor real **falla cerrado** (`NO_CONFIGURADO`) mientras no tenga percepción, movimiento y pinza respaldados por hardware.
2. **Degradación controlada.** Cada dependencia externa tiene un respaldo: Google → teclado; LAYA → clasificador local; broker real → ejecutor simulado.
3. **Trazabilidad.** Un `id_solicitud` enlaza el audio, la transcripción, la decisión de P1, la cola y el resultado de P2 en los CSV de P3 y de P2. Todo resultado de un ejecutor simulado queda marcado como tal para que no se confunda con movimiento real.

El software corre sobre **ROS 2 Humble** (Ubuntu 22.04). El estado real de cada parte —qué está implementado, qué se probó con pruebas automáticas y qué se comprobó en el laboratorio— está en [Estado final y alcance de las pruebas](#estado-final-y-alcance-de-las-pruebas).

---

## Arquitectura

### Vista general

```text
 Micrófono / archivo de audio
            │
            ▼
 ┌────────────────────────┐   HTTPS   ┌────────────────────┐
 │  P3 · transcriptor_voz │ ────────► │  Google AI Studio  │   audio → texto
 └───────────┬────────────┘           └────────────────────┘
             │ si falla o no hay Internet: modo teclado
             ▼   servicio ROS 2 · InterpretarOrden
 ┌────────────────────────┐   HTTP    ┌────────────────────┐
 │ P1 · interprete_ordenes│ ────────► │        LAYA        │   decisión tipada
 └───────────┬────────────┘           └────────────────────┘
             │ permitido = true (y no degradado)
             ▼   acción ROS 2 · PickPlace   (solo la tarea)
 ┌────────────────────────────────────────────────────┐
 │ P2 · arm_broker                                    │
 │   cola compartida con /move_arm · un solo worker   │
 │   ejecutor simulado | ejecutor real (falla cerrado)│
 └───────────┬────────────────────────────────────────┘
             ▼
          JetCobot  ◄── visión por color · cinemática · pick and place (src/jetcobot)
```

### Contratos entre las capas

| De → a | Interfaz | Contenido | Qué garantiza |
|---|---|---|---|
| P3 → P1 | Servicio `InterpretarOrden` | `frase` → `accion`, `objeto`, `color`, `destino`, `prioridad`, `permitido`, `degradado`, `motivo`, `tiempo_servidor_ms` | La decisión es tipada; si LAYA no responde, responde el respaldo local con `degradado=true` |
| P3 → P2 | Acción `PickPlace` (`/pick_place`) | `id_solicitud`, `color_objetivo`, `destino`, `priority` (1–3) → `success`, `codigo_resultado`, tiempos; feedback por etapas | P3 nunca envía movimientos; P2 valida y rechaza antes de encolar |
| Clientes → P2 | Acción `MoveArm` (`/move_arm`) | `joint_positions` (6 rad), `client_id`, `priority` (0–255) | Misma cola y worker que `/pick_place`: nunca dos movimientos a la vez |
| P2 → todos | Tópico `/arm/queue_state` | Estado de la cola, ejecución actual y contadores | Visibilidad de la cola para cualquier cliente |

### P1 — decisión

```text
 frase ──► consulta a LAYA (/v1/systemone, 6 preguntas de opción única)
              │ respuesta                          │ sin respuesta (conexión rechazada o tiempo agotado)
              ▼                                    ▼
      contraste con el clasificador local     clasificador local ──► degradado = true
              │
   coinciden ─┴─ discrepan
      │            └─► validacion_estricta=true: se rechaza con su motivo
      ▼
 decisión tipada (permitido, acción, objeto, color, destino, prioridad)
```

### P2 — broker

```text
 /move_arm ──┐                                      ┌─► ejecutor simulado ─► etapas y resultado SIMULADO
             ├─► admisión ─► cola con política ─► worker único ─┤
 /pick_place ┘   (límites,    (fifo | round_robin |             └─► ejecutor real ─► percepción · movimiento · pinza
                  workspace,   prioridad con envejecimiento)        (sin los tres respaldos: NO_CONFIGURADO)
                  paso máx.,
                  cola llena,
                  id repetido)
```

### P3 — voz

```text
 micrófono (detección de voz por energía) ─┐
                                           ├─► Google (límite real) ──► texto ──► P1 ──► ¿permitido? ──► P2 (/pick_place)
 archivo de audio ─────────────────────────┘        │ falla / sin Internet / sin clave
                                                    └──► teclado ──────────┘
                                                                  └─► transcripciones.csv (una fila por orden)
```

### Despliegue en el laboratorio

| Componente | Equipo | Dirección | Función |
|---|---|---|---|
| P3 | Raspberry Pi `rpi-12` | 172.51.1.23 | Micrófono, Google AI Studio, cliente de P1 y entrega a P2 |
| P1 | Servicio ROS 2 en la Raspberry; LAYA en una PC del laboratorio | LAYA: 172.51.1.27:8000 | Interpretar, validar y autorizar |
| P2 | Jetson `yahboom` | 172.51.1.20 | Broker, MoveIt 2 y control del brazo (`/dev/ttyUSB0`) |
| ROS 2 | Humble · `ROS_DOMAIN_ID=92` | Discovery server 172.51.1.20:11811 | Comunicación entre equipos |

Ni Google AI Studio ni LAYA son nodos ROS 2: se acceden por HTTP(S).

---

## Estructura del repositorio

```text
.
├── src/                              Paquetes y módulos del sistema
│   ├── transcriptor_voz/               P3
│   │   ├── transcriptor_voz.py           nodo: audio o micrófono → Google/teclado → P1 → P2 → CSV
│   │   ├── transcripcion_google.py       cliente de Google AI Studio con límite de espera
│   │   ├── captura_microfono.py          grabación con calibración de ruido y fin de frase
│   │   ├── envio_pickplace.py            validación de la decisión y cliente de /pick_place
│   │   └── test/                         pruebas (cliente de acción falso y CSV)
│   ├── interprete_ordenes/             P1
│   │   ├── interprete_ordenes/           servicio, cliente LAYA y clasificador por reglas
│   │   └── interprete_ordenes_interfaces/  paquete con InterpretarOrden.srv
│   ├── arm_broker/                     P2 · broker de acceso exclusivo
│   │   ├── broker.py                     nodo: /move_arm, /pick_place, cola y worker
│   │   ├── politicas.py                  fifo, round_robin y prioridad con envejecimiento
│   │   ├── tarea_pickplace.py            contrato y validación de las tareas
│   │   ├── ejecutor_simulado.py          ejecución sin hardware (resultados marcados SIMULADO)
│   │   ├── ejecutor_real.py              falla cerrado sin respaldos de hardware
│   │   ├── registro_tarea.py             eventos y tiempos por id_solicitud (CSV)
│   │   ├── fk.py                         cinemática directa DH, límites y espacio de trabajo
│   │   ├── cinematica_urdf.py, fk_poe.py referencias para contrastar fk.py
│   │   ├── cliente_brazo.py              cliente de prueba de /move_arm
│   │   └── test/                         pruebas (incluye un ROS 2 falso para el broker)
│   ├── arm_broker_interfaces/          P2 · acciones MoveArm y PickPlace, mensaje QueueState
│   └── jetcobot/                       P2 · visión, posiciones y pick and place
│       ├── vision_colores.py             detección HSV de los cuatro cubos
│       ├── posiciones.py                 lectura y validación de zonas_trabajo.json
│       ├── pick_and_place.py             secuencia por etapas con dispositivos inyectables
│       ├── integration_moveit.py         planificación y ejecución de trayectorias separadas
│       ├── rutas.py                      rutas del repositorio para los scripts
│       ├── config/                       robot.yaml y zonas_trabajo.json
│       ├── modelos/jetcobot.urdf         modelo del robot
│       └── test/                         pruebas
├── scripts/
│   ├── ejecutar_frases_50.py, ejecutar_frases_50_p1_g8.py, evaluar_laya_vs_palabras.py,
│   │   ajustar_preguntas_laya.py       P1 · medición y evaluación sobre las 50 frases
│   ├── p2/                             P2 · visión, calibración, métricas de la cola y cinemática
│   │   └── calibracion_supervisada/      mueven el brazo por puerto serie: solo con el broker detenido
│   ├── iniciar.sh, cliente.sh, verificar.sh, detener.sh   P2 · operación del broker
│   └── p3_genera_latencias.py, p3_prueba_timeout_local.py, p3_diagnostico_google.py   P3
└── evidencias/
    ├── pregunta_1/                     frases, mediciones, informes y verificación del servicio
    ├── pregunta_2/                     calibración, cámara, mapas y estado final
    └── pregunta_3/                     audios, capturas, CSV y cierre de la sesión de laboratorio
```

---

## Componentes

### P1 — `interprete_ordenes`: del texto a una decisión

Nodo ROS 2 que expone el servicio de interpretación y devuelve una **decisión tipada**.

```text
string frase
---
string accion
string objeto
string color
string destino
int32 prioridad
bool permitido
bool degradado               # true = respondió el clasificador por palabras clave
string motivo                # causa cuando la orden se rechaza
float32 tiempo_servidor_ms   # lo que tardó el servidor en decidir (sin la red)
```

- **Cliente de LAYA** (`laya_cliente.py`): consulta el endpoint HTTP `/v1/systemone` con **preguntas de opción única** y valida seis decisiones: acción, objeto, color, destino, prioridad y si la orden está permitida. Las preguntas son criterios fijos de evaluación: no entrenan al modelo. La dirección se toma de `LAYA_URL` o del parámetro `laya_url`.
- **Clasificador por palabras clave**: acepta una orden básica de *pick and place* (un verbo de recoger o colocar, «cubo» con su color y «zona» con su color, entre rojo, verde, azul y amarillo) y rechaza con su motivo las negaciones, las acciones que el brazo no hace, los colores o variantes no admitidos, los objetos que no son cubos y las órdenes incompletas o con varios cubos o zonas.
- **Validación estricta** (`validacion_estricta`, por defecto `true`): si LAYA decide algo distinto de lo que identifican las reglas locales (por ejemplo, otro destino), la orden se **rechaza**. Es la opción segura. El modo híbrido, usado en las primeras pruebas del laboratorio, está documentado por separado en [`MODO_ESTRICTO_E_HIBRIDO.md`](evidencias/pregunta_1/MODO_ESTRICTO_E_HIBRIDO.md).
- **Respaldo**: si LAYA no responde (conexión rechazada o tiempo agotado), responde el clasificador local con `degradado=true`.
- **Nombres y direcciones por defecto**: el servicio de P1 se llama `/interpretar_orden_p1_prueba` (parámetro `nombre_servicio`) y el de P3 busca `/interpretar_orden` (`servicio_interpretar`); `laya_url` apunta a `http://127.0.0.1:8765`, y `laya_cliente.py` conserva `http://172.51.1.13:8000` como referencia histórica. En el laboratorio LAYA estaba en `http://172.51.1.27:8000`. Detalle en [`MODO_ESTRICTO_E_HIBRIDO.md`](evidencias/pregunta_1/MODO_ESTRICTO_E_HIBRIDO.md).
- **Parámetros**: `laya_url`, `laya_timeout` (4 s), `validacion_estricta` (`true`) y `corregir_con_reglas` (`false`, solo por compatibilidad).
- **Ejecución**: `interprete_ordenes` no está registrado como paquete ejecutable de ROS 2; se inicia su archivo Python directamente (procedimiento en el documento anterior). Solo `interprete_ordenes_interfaces` se compila con `colcon`.
- **Frases de práctica**: [`evidencias/pregunta_1/frases_50.md`](evidencias/pregunta_1/frases_50.md) contiene 50 frases con su decisión esperada (23 a aceptar y 27 a rechazar), repartidas en 14 categorías: órdenes directas, variaciones de verbo, de cubo y de zona, colores no reconocidos y degradados, objetos que no son cubos, negativas, acciones no permitidas, incompletas, ambiguas y cambios de parámetros.

### P2 — `arm_broker`: acceso exclusivo al brazo

Nodo `ArmBroker`: el único que publica en `/joint_states`. Los clientes solo envían *goals*.

- **Flujo**: admisión → cola → ejecución exclusiva con un *worker* único. Las dos acciones, `/move_arm` y `/pick_place`, comparten cola, política y worker.
- **Admisión**: rechaza con causa y motivo los objetivos fuera de los límites articulares o del espacio de trabajo, los pasos articulares excesivos, las colas llenas y, en `/pick_place`, los colores, destinos (solo las cuatro zonas de color del tablero izquierdo), prioridades e identificadores inválidos o repetidos. Los rechazos quedan en `rechazos.csv` y en el registro de tareas.
- **Políticas de cola**: `fifo`, `round_robin` y `prioridad` con envejecimiento (puntaje `priority + espera/tau`; mayor número, más urgente; ningún cliente queda sin atención).
- **`/pick_place`** (`PickPlace.action`): recibe `id_solicitud`, `color_objetivo`, `destino` y `priority` (1 a 3). Devuelve feedback por etapas (`EN_COLA`, `PERCEPCION`, `APROXIMACION`, `AGARRE`, `TRASLADO`, `DEPOSITO`, `RETIRADA`) y un `codigo_resultado` (`COMPLETADO`, `OBJETO_AUSENTE`, `NO_CONFIGURADO`, `ERROR_AGARRE`, `CANCELADO`…). Si se cancela con el cubo sujeto, no lo suelta solo.
- **Modos** (`modo_ejecucion`): `simulado` (por defecto) corre la secuencia real con percepción, movimiento y pinza falsos y lo marca SIMULADO; `real` exige `permitir_movimiento_real:=true` y falla cerrado (`NO_CONFIGURADO`) mientras falten los respaldos de hardware.
- **Registro por tarea** (`registro_tareas.csv`): eventos y tiempos por `id_solicitud` con la marca `simulado`; la columna `registro` separa `tarea` de `rechazo`.
- **Cinemática**: `fk.py` implementa la cinemática directa con tabla Denavit-Hartenberg; `cinematica_urdf.py` y `fk_poe.py` son referencias (URDF y producto de exponenciales) para contrastarla, y el broker no las usa.
- **Parámetros**: `politica` (`fifo`), `tau_envejecimiento_s` (8), `cola_max` (20), `paso_max_rad` (1,2), `duracion_movimiento_s` (3), `pasos_interpolacion` (10), `modo_ejecucion` (`simulado`), `permitir_movimiento_real` (`false`), `archivo_rechazos` y `archivo_registro_tareas`.

### P2 — `jetcobot`: visión y *pick and place*

- `vision_colores.py`: detección de los cuatro colores por rangos HSV (640×480), con filtros de área y relación de aspecto; `detectar_cubos` y `buscar_color_en_frame` devuelven centro, área y rectángulo en píxeles. No hay calibración métrica: los píxeles no son coordenadas del robot.
- `posiciones.py` y `config/zonas_trabajo.json`: **única fuente** de poses de trabajo, con validación de esquema. Los destinos son las casillas B/G/R/Y del tablero izquierdo (heredados del código original, con `validada: false`); las poses de recogida están en `null` y devuelven `NO_CONFIGURADO`.
- `pick_and_place.py`: `ejecutar_secuencia` recibe la percepción, el movimiento y la pinza por parámetro, devuelve un resultado estructurado y no da por bueno un agarre que no se confirmó.
- `integration_moveit.py`: planificación y ejecución de trayectorias como pasos separados, con validación de nombres, límites y tiempos.
- Los datos y el modelo viajan con el paquete: `config/`, `modelos/jetcobot.urdf` y `rutas.py`.

### P3 — `transcriptor_voz`: de la voz al movimiento

- **Google AI Studio** (`transcripcion_google.py`): envía el audio en la misma solicitud. Modelo configurable con `GEMINI_MODELO_TRANSCRIPCION` (por defecto `gemini-3.5-transcribe`); formatos wav, mp3, m4a, ogg, flac, aac y webm hasta 10 MB. La clave sale **solo** de `GEMINI_API_KEY` (o `GOOGLE_API_KEY`).
- **Límite de espera propio**: la llamada se ejecuta con un tiempo máximo real (`timeout_transcripcion_s`, 30 s). Al agotarse, sin Internet, sin clave o con una transcripción vacía, se activa el **modo teclado**.
- **Micrófono** (`captura_microfono.py`): WAV mono de 16 kHz; calibra el ruido de fondo, avisa «Habla ahora» y termina al detectar silencio. Usa `arecord` o `parec`. Mide `tiempo_captura_ms` desde el **fin de habla estimado por energía**, no desde el instante exacto.
- **Entrega a P2** (`envio_pickplace.py`): solo si P1 devuelve `permitido=true`, `trasladar` sobre un `cubo`, colores válidos y prioridad 1 a 3, y la decisión **no** es degradada (salvo `permitir_degradado:=true`). Envía la tarea con el mismo `id_solicitud` y registra aceptación, etapas y resultado. Nunca manda movimientos articulares.
- **Registro**: cada ejecución agrega una fila a `evidencias/pregunta_3/transcripciones.csv` con audio, texto, origen (`google` o `teclado`), decisión de P1, resultado de P2 y tiempos; lo no medido queda vacío. Los audios se conservan sin duplicar copias.
- **Parámetros**: `timeout_transcripcion_s` (30), `timeout_servicio_s` (5), `silencio_fin_s` (0,8), `espera_inicio_s` (8), `max_duracion_s` (15), `servicio_interpretar` (`/interpretar_orden`), `enviar_a_p2` (`true`), `permitir_degradado` (`false`), `timeout_servidor_p2_s` (3) y `timeout_resultado_p2_s` (120).
- **Código de salida**: 0 si la tarea terminó en `COMPLETADO` o no correspondía enviarla; 2 si P2 la rechazó, falló o expiró el tiempo.

---

## Scripts

Se ejecutan desde la raíz del repositorio.

| Grupo | Scripts | Para qué sirven |
|---|---|---|
| **P1** | `ejecutar_frases_50.py`, `ejecutar_frases_50_p1_g8.py` | Envían las 50 frases al servicio, miden la latencia de ida y vuelta (mediana y percentil 95) y comparan cada decisión con la esperada. Exigen escribir una **predicción antes de medir**; los nombres de los resultados llevan la hora y no se sobrescriben |
| | `evaluar_laya_vs_palabras.py` | Compara la exactitud de LAYA con la del clasificador local, sin sustituir las decisiones de LAYA |
| | `ajustar_preguntas_laya.py` | Aplica los ajustes de redacción de las preguntas de LAYA con verificación previa y respaldo |
| **P2** | `p2/probar_pickplace_simulado.py` | Cliente de `/pick_place` con escenarios (válida, inválida, cubo ausente, cuatro clientes, cancelación); tabula aceptación, etapas y resultado |
| | `p2/generar_carga.py`, `p2/exportar_csv.py`, `p2/metricas.py` | Poses reproducibles para los clientes, rosbag → CSV y métricas de la cola (espera media y p95, inanición, equidad de Jain) |
| | `p2/probar_reconocimiento.py`, `p2/calibrar_camara.py`, `p2/crear_mapa_visual.py`, `p2/analizar_perspectiva.py`, `p2/inspeccionar_contornos.py` | Visión, calibración y mapas |
| | `p2/ajustar_dh.py`, `p2/generar_dh.py`, `p2/validar_dh_profesor.py` | Ajuste y validación de la tabla DH |
| | `p2/calibracion_supervisada/` | **Mueven el brazo por puerto serie sin pasar por el broker.** Solo con el broker detenido y con alguien junto al robot; nunca durante la demostración ni junto a P3 |
| | `iniciar.sh`, `cliente.sh`, `verificar.sh`, `detener.sh` | Operación del broker. Respetan el `ROS_DOMAIN_ID` de la terminal (92 por defecto); `MODO=simulado` por defecto, `MODO=real` exige además `PERMITIR_MOVIMIENTO_REAL=si` |
| **P3** | `p3_genera_latencias.py` | Resumen de latencias y tabla de solicitudes a partir de `transcripciones.csv`, con las métricas de P2 separadas en simulado y real |
| | `p3_prueba_timeout_local.py` | Prueba controlada del límite de espera, sin llamar a Google |
| | `p3_diagnostico_google.py` | Mide por separado el audio, la red hacia Google (DNS, TCP y TLS por IPv4 e IPv6) y varias transcripciones, y sugiere un valor para el límite de espera |

---

## Estado final y alcance de las pruebas

El código publicado y lo probado en el laboratorio **no son una única versión validada**. Esta sección distingue tres niveles: lo implementado en el repositorio, lo comprobado con pruebas automáticas (sin ROS real ni hardware) y lo comprobado en los equipos del laboratorio (ROS 2 Humble, dominio 92).

### ¿Qué hay en cada capa?

| Capa | Implementado en el repositorio | Pruebas automáticas | Comprobado en el laboratorio |
|---|---|---|---|
| **P1** · servicio con LAYA, respaldo local y validación estricta | Sí | Evaluación sobre las 50 frases (LAYA 15/50; palabras clave 50/50) y verificación del servicio oficial | LAYA real alcanzado en 172.51.1.27:8000; orden válida autorizada sin degradación; discrepancia de destino rechazada en modo estricto |
| **P1** · paquete ejecutable ROS 2 de `interprete_ordenes` | No: solo se compila la interfaz | — | Se inició el archivo Python directamente |
| **P2** · `/move_arm` | Sí | Admisión, cola, cancelación y exclusión mutua contra un ROS 2 falso | Detectada y conectada en el Jetson |
| **P2** · `/pick_place` | Sí | Admisión, políticas, cola compartida, cancelación y trazabilidad contra un ROS 2 falso | **No confirmada** en el broker usado en el Jetson |
| **P2** · ejecución simulada | Sí | Sí | Se inició un broker sin movimiento real |
| **P2** · pick and place real | Exige respaldos de hardware; sin ellos `NO_CONFIGURADO` | La secuencia se prueba con dispositivos falsos | **No completado**: la recogida no tenía una trayectoria segura validada |
| **P2** · cinemática y visión | `fk.py`, referencias URDF y PoE, detección HSV | FK frente al URDF, modelo PoE, visión sobre las imágenes guardadas | Imágenes y lecturas de posición tomadas con el robot en calibración supervisada |
| **P3** · voz, Google, teclado y CSV | Sí | Cliente de acción falso y CSV en carpeta temporal | Audios y micrófono con Google; respaldo por teclado; transcripción exitosa en la Raspberry |
| **P3** · entrega a P2 | `ActionClient` de `/pick_place` | Cliente de acción falso | **Distinta en el laboratorio**: adaptador de preparación para `/move_arm`, con el envío desactivado |

Pruebas automáticas incluidas: **109** (55 en `arm_broker`, 38 en `jetcobot` y 16 en `transcriptor_voz`). Se ejecutan sin ROS ni hardware; el broker se prueba contra un ROS 2 falso y la prueba del modelo PoE requiere numpy y scipy.

### Versiones: repositorio frente a laboratorio

| | Código publicado | Versión usada en el laboratorio |
|---|---|---|
| Servicio de P1 | P1 publica `/interpretar_orden_p1_prueba` y P3 busca `/interpretar_orden` (por defecto no coinciden) | Pruebas con los nombres por defecto, cada programa con el suyo; la última configuración de P3 usó `/interpretar_orden_p1_actualizado` |
| Dirección de LAYA | `laya_url` = `http://127.0.0.1:8765`; `laya_cliente.py` guarda `http://172.51.1.13:8000` como referencia histórica | `http://172.51.1.27:8000` |
| Entrega a P2 | `/pick_place`; `enviar_a_p2=true` por defecto | Adaptador de preparación para `/move_arm`; `enviar_a_p2=false` |
| Broker de P2 | `src/arm_broker` de este repositorio | Instalación del Jetson en `rb2_ws`: es **otra implementación**, y no debe sustituirse la de este repositorio sin obtener antes una copia de esa versión |
| `validacion_estricta` | `true` por defecto | Las primeras pruebas usaron el modo híbrido |

### Resultados de la sesión del 15 de octubre

| Resultado | Estado |
|---|---|
| Voz → transcripción (micrófono y Google) | **Demostrado** |
| Transcripción → P1 con LAYA real, autorización no degradada | **Demostrado** |
| P1 → orden `MoveArm` preparada sin envío (`orden_rojo`) | **Demostrado** |
| Raspberry → acción `/move_arm` del Jetson | **Demostrado** (descubrimiento y conexión) |
| Jetson P2 en modo seguro (`permitir_movimiento_real=False`) | **Demostrado** |
| Recepción y ejecución de un goal por P2 desde P3 | **No demostrado** |
| Movimiento, agarre y depósito de un cubo | **No ejecutado** |

### Lo que este estado no demuestra

- Que `/pick_place` existiera o funcionara en el Jetson: es código del repositorio verificado con un ROS 2 falso, no con ROS 2 real.
- Que un resultado `COMPLETADO (SIMULADO)` signifique movimiento: solo indica que el software simulado terminó.
- Que las poses de trabajo sean físicas: las recogidas están en `null`, los destinos están sin validar y los píxeles de la cámara no son coordenadas del robot.
- Que las latencias medidas sean un estudio estadístico: son salidas de terminal de pruebas puntuales; el escenario llamado «carga» no acredita concurrencia real de otros equipos.
- Que la exactitud del 100 % del clasificador local se mantenga con frases nuevas: corresponde únicamente a las 50 frases evaluadas.

---

## Evidencias Presentadas

### Pregunta 1 — `evidencias/pregunta_1/`

| Archivo | Qué contiene |
|---|---|
| [`frases_50.csv`](evidencias/pregunta_1/frases_50.csv), [`frases_50.md`](evidencias/pregunta_1/frases_50.md) | Las 50 frases con su categoría y decisión esperada. No se reescribieron ni se alteraron sus resultados |
| [`INFORME_FINAL_P1.md`](evidencias/pregunta_1/INFORME_FINAL_P1.md) | Implementación, exactitud (**LAYA 15/50 frente a 50/50 del clasificador local**), latencias (mediana 298,95 ms en calma y 318,00 ms en el escenario etiquetado como carga), análisis de errores y limitaciones |
| [`VERIFICACION_SERVICIO_OFICIAL.md`](evidencias/pregunta_1/VERIFICACION_SERVICIO_OFICIAL.md) | Verificación del servicio oficial: una orden válida autorizada y otra rechazada por discrepancia, sin movimiento físico |
| [`MODO_ESTRICTO_E_HIBRIDO.md`](evidencias/pregunta_1/MODO_ESTRICTO_E_HIBRIDO.md) | Por qué las primeras pruebas usaron el modo híbrido, el diagnóstico de LAYA del 15 de octubre y cómo ejecutar el intérprete |
| `mediciones/`, `resultados_p1_g8/` | Mediciones por escenario, comparación independiente de LAYA, predicción previa y resultados históricos del servicio híbrido |

### Pregunta 2 — `evidencias/pregunta_2/`

| Archivo o carpeta | Qué contiene |
|---|---|
| [`ESTADO_FINAL_P2.md`](evidencias/pregunta_2/ESTADO_FINAL_P2.md) | Separa simulación, validación estática, calibración con el robot y movimiento real; compara el repositorio con lo observado en el Jetson |
| `calibracion/` | Escaneo inicial y desplazamientos en X e Y desde la postura de escaneo, con las detecciones de los cuatro cubos marcadas; postura de escaneo preferida; validación del modelo visual; recuperación del escaneo; modelo visual preliminar; y `referencias_urdf.npz` con las 100 poses de referencia del URDF |
| `camara/` | Capturas de la cámara con los cuatro colores y su detección |
| `mapas/` | Mapa visual con los centros de los cuatro cubos y las distancias entre ellos, en píxeles |
| Pruebas | `src/arm_broker/test/` y `src/jetcobot/test/` (FK, modelo PoE, políticas, admisión, cola compartida, secuencia, visión sobre las imágenes guardadas) |

### Pregunta 3 — `evidencias/pregunta_3/`

| Archivo o carpeta | Qué contiene |
|---|---|
| [`README.md`](evidencias/pregunta_3/README.md) | Pruebas con 10 audios `.aac` (las 10 conservaron el significado y 8 coincidieron literalmente; Google tarda 3–4 s, con un atípico de 35,72 s conservado), respaldo por teclado y primera integración con P1 |
| `audios/`, `transcripciones.csv`, `capturas/` | Grabaciones, registro de cada orden con sus tiempos y capturas de las pruebas |
| [`cierre/informe_avances_15oct.md`](evidencias/pregunta_3/cierre/informe_avances_15oct.md) | Informe de la sesión de laboratorio del 15 de octubre (también en [Word](evidencias/pregunta_3/cierre/Informe_Avances_JetCobot_P1_P2_P3_15Oct2026.docx)) |
| [`cierre/comandos_sesion_15oct.md`](evidencias/pregunta_3/cierre/comandos_sesion_15oct.md) | Comandos usados en la Raspberry y en el Jetson |
| [`cierre/capturas/`](evidencias/pregunta_3/cierre/capturas/) | 12 capturas que respaldan el informe (prefijos `p1_`, `p2_` y `p3_`) |
| [`cierre/informe_cierre_P3.md`](evidencias/pregunta_3/cierre/informe_cierre_P3.md) | Comparación entre el código publicado y la versión del laboratorio, lo logrado y lo no conseguido |
| [`cierre/integracion_p1_p2_p3.txt`](evidencias/pregunta_3/cierre/integracion_p1_p2_p3.txt) | Registro de cierre generado en la Raspberry |

---

## Seguridad

- La clave de la API se lee **solo** de una variable de entorno y no aparece en el código ni en el historial del repositorio.
- P3 nunca publica en `/joint_states` ni envía movimientos articulares; el broker es el único publicador hacia el brazo.
- El movimiento directo del brazo por puerto serie queda confinado a `scripts/p2/calibracion_supervisada/` y se usa únicamente con el broker detenido.
- El ejecutor real falla cerrado y `permitir_movimiento_real` es `false` por defecto; el modo `real` exige un permiso explícito en el broker y en `iniciar.sh`.
- Las decisiones degradadas (clasificador de respaldo) no se envían a P2 salvo permiso explícito.
- `.gitignore` excluye `__pycache__/` y `*.pyc`. No se publican `build/`, `install/` ni `log/`.
