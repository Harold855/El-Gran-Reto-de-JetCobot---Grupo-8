# Pregunta 3 — Informe de cierre

## Dos versiones que no deben tratarse como una sola

| | Código publicado en GitHub | Versión funcional en el laboratorio |
|---|---|---|
| Servicio de P1 | P1 publica `/interpretar_orden_p1_prueba` y P3 busca `/interpretar_orden` (por defecto no coinciden; P3 lo cambia con `servicio_interpretar`) | Pruebas con los nombres por defecto, cada programa con el suyo; la última configuración de P3 usó `/interpretar_orden_p1_actualizado` |
| Dirección de LAYA | `laya_url` = `http://127.0.0.1:8765`; `laya_cliente.py` guarda `http://172.51.1.13:8000` como referencia histórica | `http://172.51.1.27:8000` |
| Entrega a P2 | `ActionClient` de `/pick_place` (`enviar_a_p2=true` por defecto) | Adaptador de preparación para `/move_arm` (`envio_move_arm_prueba.preparar_move_arm`), con `enviar_a_p2=false` por defecto y el envío físico desactivado |
| Alcance | Entrega la tarea a `/pick_place` y registra aceptación, etapas y resultado | No se envió ninguna orden de movimiento real |

Ninguna de las dos se describe aquí como la versión validada de extremo a extremo. El parámetro `servicio_interpretar` permite que el código publicado apunte al servicio usado en el laboratorio sin cambiar nada más.

## Las dos interfaces consideradas

- **`/pick_place`** (repositorio): una tarea completa (`id_solicitud`, color, destino, prioridad) que el broker valida, encola y ejecuta. P3 solo la entrega; nunca manda movimientos articulares.
- **`/move_arm`** (laboratorio): objetivos articulares. Es la interfaz que se detectó y conectó en el Jetson.

## Qué se logró

- Voz o archivo de audio → Google → texto, con respaldo por teclado.
- Texto → servicio de P1 con LAYA real → decisión estructurada.
- Registro de cada orden con tiempos en `transcripciones.csv`.
- En el código publicado: entrega a `/pick_place`, probada contra un cliente de acción falso y con un broker simulado (ROS falso). Un resultado de broker simulado queda como `simulado_p2=True`.

## Qué no se consiguió

- `/pick_place` no se confirmó en el broker utilizado en el Jetson.
- No se completó un pick and place real: la recogida no tenía una trayectoria segura validada y `mover_agarre()` estaba bloqueado en el código del Jetson.
- No hay medición de voz a movimiento del brazo.
- El código publicado de P3 no se ejecutó con ROS 2 real contra `/pick_place`.

## Documentos de la sesión del 15 de octubre

- [`informe_avances_15oct.md`](informe_avances_15oct.md): informe técnico de la sesión (versión en Markdown del documento Word original, [`Informe_Avances_JetCobot_P1_P2_P3_15Oct2026.docx`](Informe_Avances_JetCobot_P1_P2_P3_15Oct2026.docx)).
- [`comandos_sesion_15oct.md`](comandos_sesion_15oct.md): comandos usados en la Raspberry y en el Jetson.
- [`capturas/`](capturas/): las capturas que respaldan el informe (prefijos `p1_`, `p2_` y `p3_` según el subsistema).
- [`integracion_p1_p2_p3.txt`](integracion_p1_p2_p3.txt): registro de cierre tal como se generó en la Raspberry.
