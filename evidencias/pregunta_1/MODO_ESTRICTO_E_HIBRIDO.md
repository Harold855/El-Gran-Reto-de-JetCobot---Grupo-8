# Pregunta 1 — Modo estricto frente a modo híbrido

Las 50 frases (`frases_50.csv`) y los resultados de sus mediciones no se modificaron. Este documento explica por qué el comportamiento de las pruebas históricas no coincide con el valor por defecto actual.

| Modo | Parámetro | Qué hace ante una discrepancia entre LAYA y las reglas locales |
|---|---|---|
| **Estricto** (valor por defecto actual) | `validacion_estricta:=true` | Rechaza la orden. Es la opción segura. |
| **Híbrido** (usado en pruebas históricas) | `validacion_estricta:=false` | Mantiene la decisión de LAYA. |

En la primera prueba del laboratorio, una discrepancia de destino fue **aceptada con `degradado=False`**. Eso corresponde al modo híbrido, no al valor por defecto que hoy hay en GitHub. En la verificación posterior del servicio oficial (`VERIFICACION_SERVICIO_OFICIAL.md`) una discrepancia de destino sí se rechazó, como corresponde al modo estricto.

El modo estricto se conserva como opción segura. Las mediciones históricas se leen sabiendo con qué modo se hicieron.

## Sesión de laboratorio del 15 de octubre

Con el P1 actualizado (`/interpretar_orden_p1_actualizado`, commit `ca846f6`), el primer llamado devolvió `permitido=True` pero `degradado=True`, porque `laya_url` seguía en `http://127.0.0.1:8765` y no había servidor local. La IP 172.51.1.13 no era alcanzable; LAYA estaba en 172.51.1.27:8000 (`GET /` → 404 y `GET /v1/systemone` → 405 con `Allow: POST`). Tras `ros2 param set /interprete_p1_actualizado laya_url http://172.51.1.27:8000`, la orden de ejemplo se autorizó sin degradación. Capturas y comandos: [`cierre/capturas/p1_*`](../pregunta_3/cierre/capturas/) y [`cierre/comandos_sesion_15oct.md`](../pregunta_3/cierre/comandos_sesion_15oct.md).

## Nombres y direcciones por defecto

| Programa del repositorio | Servicio por defecto | Parámetro para cambiarlo |
|---|---|---|
| P1 · `interprete_ordenes.py` | `/interpretar_orden_p1_prueba` | `nombre_servicio` |
| P3 · `transcriptor_voz.py` | `/interpretar_orden` | `servicio_interpretar` |

Con los valores por defecto los nombres **no coinciden**: para conectar P3 con P1 hay que igualar uno de los dos (por ejemplo `-p servicio_interpretar:=/interpretar_orden_p1_prueba` en P3, o `-p nombre_servicio:=/interpretar_orden` en P1). Las pruebas de la Raspberry se ejecutaron con éxito con esos nombres por defecto, cada programa con el suyo.

Direcciones de LAYA: P1 apunta por defecto a `http://127.0.0.1:8765` (parámetro `laya_url` o variable `LAYA_URL`); `laya_cliente.py` conserva como referencia histórica `http://172.51.1.13:8000`, que ya no era alcanzable. En el laboratorio LAYA estaba en `http://172.51.1.27:8000` y hay que indicarlo con `laya_url` o `LAYA_URL`; sin eso P1 responde con el respaldo local (`degradado=true`).

## Cómo se ejecuta el intérprete

`interprete_ordenes` no está registrado como paquete ejecutable de ROS 2: en las pruebas se inició directamente su archivo Python. Procedimiento:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash          # contiene interprete_ordenes_interfaces
export ROS_DOMAIN_ID=92
python3 src/interprete_ordenes/interprete_ordenes/interprete_ordenes.py
# modo híbrido, solo para reproducir pruebas históricas:
python3 src/interprete_ordenes/interprete_ordenes/interprete_ordenes.py --ros-args -p validacion_estricta:=false
```

Si en el dominio ya hay otro intérprete (por ejemplo `/interpretar_orden_propio`), el cliente de P3 elige el servicio con el parámetro `servicio_interpretar`.
