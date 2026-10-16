# Pregunta 3 — Evidencias de la cadena de voz

## Objetivo

Comprobar que una orden hablada se transcribe con Google AI Studio, que existe respaldo por teclado cuando Google o Internet fallan, y que la orden llega al servicio de P1 y, cuando P1 la autoriza, queda lista para P2.

## Prueba 1 — Archivos de audio

- **Entrada:** 10 grabaciones `.aac` en `audios/`.
- **Resultado:** las 10 órdenes conservaron su significado en la transcripción de Google.
- **Registro:** `transcripciones.csv` guarda el texto, el origen (`google` o `teclado`) y los tiempos.
- **Latencias:** Google tarda normalmente 3–4 s por archivo. El primer intento del audio 8 tardó **35,72 s** y al repetirlo **2,96 s**; no se conoce la causa. Ambos intentos quedaron en el CSV.
- **Observación:** en los audios 6 y 7 Google sustituyó «hacia la zona» por «a la zona», sin cambiar la intención.

## Prueba 2 — Respaldo sin Internet

Se desactivó la conexión y se probaron los audios 1 y 8. Al fallar Google, el programa pidió la orden por teclado y la registró con `origen = teclado`. También se probó una ruta de audio inexistente.

## Prueba 3 — P3 → P1 por ROS 2

Se comprobó la comunicación entre `transcriptor_voz.py` y el servicio de P1 en Ubuntu 22.04, WSL2 y ROS 2 Humble.

| Audio | Origen | Permitido | Resultado |
|---|---|---|---|
| 1 | Google | True | Trasladar rojo a verde |
| 8 | Google | False | Orden de lanzamiento rechazada |
| 9 | Google | False | Orden negativa rechazada |

Estas respuestas se obtuvieron con el clasificador de respaldo de P1 (`degradado=True`), todavía sin LAYA.

**Orden permitida:** ![Integración P3-P1](capturas/captura_integracion_p3_p1.png)

**Órdenes rechazadas:** ![Rechazo ROS 2](capturas/captura_ordenes_rechazadas_ros2.png)

## Sesión del 15 de octubre (laboratorio)

En el laboratorio P3 trabajó con el intérprete de P1 con LAYA real, en el dominio ROS 2 `92`, con micrófono y Google GenAI en una Raspberry Pi. La versión funcional del cliente usó el servicio `/interpretar_orden_p1_actualizado` y un adaptador de preparación para `MoveArm`, con el envío físico desactivado: no se movió el brazo.

- Una frase hablada («Recoge el cubo rojo y llévalo a la zona roja») se transcribió, P1 la autorizó sin degradación y el adaptador la dejó en `PREPARADO_SIN_ENVIO`.
- «Recoge el cubo rojo y muévelo a la zona verde» fue autorizada por P1 pero el adaptador no la preparó («Destino incompatible con P2»).
- `conexion_p3_p2.py` confirmó la acción `/move_arm` del Jetson sin enviar ningún objetivo.

Informe, comandos y capturas de la sesión: [`cierre/informe_avances_15oct.md`](cierre/informe_avances_15oct.md), [`cierre/comandos_sesion_15oct.md`](cierre/comandos_sesion_15oct.md) y [`cierre/capturas/`](cierre/capturas/). La comparación con el código publicado está en [`cierre/informe_cierre_P3.md`](cierre/informe_cierre_P3.md).

## Archivos

| Archivo o carpeta | Contenido |
|---|---|
| `audios/` | `audio_1.aac` a `audio_10.aac` |
| `transcripciones.csv` | Transcripciones, origen, decisión de P1 y tiempos |
| `capturas/` | Pruebas con Google, sin Internet y del CSV |
| `cierre/` | Informe de cierre, informe de la sesión del 15 de octubre, comandos, capturas y registro de la integración P1–P2–P3 |
