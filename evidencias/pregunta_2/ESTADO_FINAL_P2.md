# Pregunta 2 — Estado final

Este documento separa lo que **existe en el repositorio** de lo que **se probó en el Jetson** del laboratorio (dominio ROS 2 `92`). Que algo exista en GitHub no demuestra que estuviera disponible ni probado físicamente en ese equipo.

## Interfaces: repositorio frente al Jetson

| Interfaz | GitHub (esta rama) | Jetson probado |
|---|---|---|
| `/move_arm` | Disponible en el código | Detectada y conectada |
| `/pick_place` | Implementada en el código | No confirmada en el broker utilizado |
| Ejecución simulada | Implementada | Se inició un broker sin movimiento real |
| Pick and place real | Requiere respaldos físicos | No completado |

## Qué corresponde a cada tipo de evidencia

| Tipo | Qué es | Dónde está |
|---|---|---|
| **Simulación** | Broker con `/pick_place`, ejecutor simulado, secuencia con dispositivos falsos y registro por tarea. Todo resultado va marcado `SIMULADO`; no es movimiento del brazo. | `src/arm_broker/`, `src/jetcobot/`, pruebas en `src/*/test/` |
| **Validación estática** | Pruebas unitarias de cinemática (DH frente al URDF y modelo PoE), políticas de cola, admisión, configuración y visión sobre imágenes guardadas. No usan el robot. | `src/arm_broker/test/`, `src/jetcobot/test/` |
| **Calibración con el robot** | Capturas de cámara y lecturas de posición del brazo tomadas con los scripts de calibración supervisada, con el broker detenido. | `calibracion/`, `camara/`, `mapas/` y `scripts/p2/calibracion_supervisada/` |
| **Movimiento real de pick and place** | No completado. | — |

## Limitación del ejecutor real

`src/arm_broker/ejecutor_real.py` necesita tres funciones respaldadas por hardware: percepción, movimiento hacia una pose y control de pinza. Si falta alguna, devuelve `NO_CONFIGURADO` y no realiza ninguna operación física. Esto coincide con lo observado en el Jetson: la recogida no tenía una trayectoria segura validada y el código del entorno probado bloqueaba `mover_agarre()`.

Además, en `src/jetcobot/config/zonas_trabajo.json` las cuatro poses de recogida siguen en `null` y los destinos heredados están con `validada: false`.

## Lo observado en el Jetson (15 de octubre)

Capturas en [`../pregunta_3/cierre/capturas/`](../pregunta_3/cierre/capturas/) y detalle en [`../pregunta_3/cierre/informe_avances_15oct.md`](../pregunta_3/cierre/informe_avances_15oct.md).

- Había un broker físico (dos procesos iniciados con `permitir_movimiento_real:=true`) y un proceso MoveIt2. Se detuvieron los dos procesos del broker con SIGTERM y `/move_group` siguió disponible ([`p2_02`](../pregunta_3/cierre/capturas/p2_02_jetson_brokers_fisicos_y_acciones.jpg)).
- Al final se levantó un broker en modo seguro: `/move_arm` visible y `permitir_movimiento_real` en `False` ([`p2_01`](../pregunta_3/cierre/capturas/p2_01_jetson_move_arm_modo_seguro.jpg)).
- El comando `broker` instalado en el Jetson corresponde a `/home/jetson/rb2_ws/build/arm_broker/arm_broker/broker.py`, y las fuentes inspeccionadas estaban en `~/gran_reto_p2` ([`p2_03`](../pregunta_3/cierre/capturas/p2_03_jetson_broker_instalado_rb2_ws.jpg)): hay que cotejar la versión ejecutable con las fuentes.
- En ese código `paso_max_rad=1.2` y `q_actual=[0.0]*6` (una hipótesis, no una lectura del brazo), y `mover_agarre()` lanza `RuntimeError` hasta validar la aproximación con MoveIt2.
- La interfaz observada fue `MoveArm`; no se envió ninguna meta al broker desde P3.

## Dos implementaciones distintas

La versión de P2 que corre en el Jetson y la de este repositorio **no son la misma**. No se debe sustituir el P2 del repositorio por el código del Jetson sin obtener antes una copia de esa versión.

Se conservan el código de simulación, las pruebas y los registros de calibración.
