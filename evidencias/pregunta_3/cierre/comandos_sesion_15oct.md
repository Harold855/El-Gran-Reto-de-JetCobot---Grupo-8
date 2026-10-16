# Comandos de la sesión del 15 de octubre de 2026

Comandos que aparecen en el informe y en las capturas de [`capturas/`](capturas/). Se listan por equipo y objetivo. Rutas y nombres son los de los equipos del laboratorio (no los del repositorio). No se registra el valor de ninguna clave.

## Raspberry `rpi-12` (P3 y P1): entorno ROS 2

```bash
source /opt/ros/humble/setup.bash
source ~/gran_reto_g8_actualizado/install/local_setup.bash
source ~/pruebas_p2_interfaz/install/local_setup.bash     # interfaz de P2 compilada aparte

export ROS_DOMAIN_ID=92
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER=172.51.1.20:11811
export FASTRTPS_DEFAULT_PROFILES_FILE="$HOME/super_client_rpi.xml"
```

Perfil *super client* de Fast DDS (`~/super_client_rpi.xml`), apuntando al discovery server del Jetson:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<dds>
  <profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
    <participant profile_name="super_client_rpi" is_default_profile="true">
      <rtps>
        <builtin>
          <discovery_config>
            <discoveryProtocol>SUPER_CLIENT</discoveryProtocol>
            <discoveryServersList>
              <RemoteServer prefix="44.53.00.5f.45.50.52.4f.53.49.4d.41">
                <metatrafficUnicastLocatorList>
                  <locator>
                    <udpv4>
                      <address>172.51.1.20</address>
                      <port>11811</port>
                    </udpv4>
                  </locator>
                </metatrafficUnicastLocatorList>
              </RemoteServer>
            </discoveryServersList>
          </discovery_config>
        </builtin>
      </rtps>
    </participant>
  </profiles>
</dds>
```

Verificación del entorno y del grafo:

```bash
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID:-0}"
echo "RMW: ${RMW_IMPLEMENTATION:-predeterminado}"
echo "ROS_LOCALHOST_ONLY: ${ROS_LOCALHOST_ONLY:-0}"
ros2 service list | grep interpretar_orden
ros2 action list -t | grep move_arm
ros2 node list
ros2 service type /interpretar_orden_p1_actualizado
```

## P1: actualización y diagnóstico de LAYA

```bash
python -m py_compile interprete_ordenes.py                 # sintaxis del código actualizado

# 1) Servidor LAYA anterior (172.51.1.13): sin respuesta
curl -v --max-time 5 http://172.51.1.13:8000/
curl -v --max-time 5 http://172.51.1.13:8000/v1/systemone
ros2 param get /interprete_p1_actualizado laya_url          # String value is: http://127.0.0.1:8765

# 2) Equipos de la red y PC real del laboratorio (172.51.1.27)
ping -c 3 -W 2 172.51.1.20
ip neigh show dev wlan0
ping -c 3 -W 2 172.51.1.27
curl -v --max-time 5 http://172.51.1.27:8000/               # 404 Not Found (servidor uvicorn activo)
curl -v --max-time 5 http://172.51.1.27:8000/v1/systemone   # 405 Method Not Allowed, Allow: POST

# 3) Corrección de la URL en el nodo ya iniciado
ros2 param set /interprete_p1_actualizado laya_url http://172.51.1.27:8000
```

Consulta directa al cliente de LAYA con la URL correcta:

```bash
PYTHONPATH="$HOME/gran_reto_g8/src/interprete_ordenes/interprete_ordenes" \
LAYA_URL=http://172.51.1.27:8000 \
python - <<'PY'
from laya_cliente import consultar_laya_tipado

frase = "Recoge el cubo rojo y muévelo a la zona verde."

decision = consultar_laya_tipado(
    frase,
    url="http://172.51.1.27:8000",
    timeout=10.0
)
PY
```

El intérprete no está empaquetado como ejecutable de ROS 2: en la sesión se inició su archivo Python directamente (por ejemplo `python3 interprete_ordenes_prueba.py` con `PYTHONPATH` apuntando a `src/interprete_ordenes/interprete_ordenes`). En las capturas, los intentos de iniciar `interprete_ordenes_prueba.py` con `PYTHONPATH` fallaron con `ModuleNotFoundError: No module named 'rclpy'` hasta preparar el entorno de ROS 2 y el entorno virtual `~/pruebas_p3/.venv`.

## P3: voz, Google y entrega preparada a P2 (sin envío)

```bash
cd ~/pruebas_p3
source .venv/bin/activate
# la clave se exporta sin escribirla en el historial (ver README):
#   read -r -s -p "Introduce tu API key: " GEMINI_API_KEY; echo; export GEMINI_API_KEY

# Audio pregrabado
python transcriptor_voz.py prueba_microfono.wav \
  --ros-args \
  -p enviar_a_p2:=false \
  -p permitir_degradado:=false \
  -p timeout_transcripcion_s:=30.0

# Micrófono
python transcriptor_voz.py --microfono \
  --ros-args \
  -p enviar_a_p2:=false \
  -p permitir_degradado:=false
```

Comprobación de la configuración del P3 usado en el laboratorio:

```bash
grep -n -E 'interpretar_orden_p1_actualizado|enviar_a_p2' transcriptor_voz.py | head -15
```

Prueba del adaptador que prepara la orden `MoveArm` sin enviarla:

```bash
python - <<'PY'
from types import SimpleNamespace
from envio_move_arm_prueba import preparar_move_arm

for color in ("rojo", "verde", "azul", "amarillo"):
    decision = SimpleNamespace(
        permitido=True,
        degradado=False,
        accion="trasladar",
        objeto="cubo",
        color=color,
        destino=color,
        prioridad=1
    )

    resultado = preparar_move_arm(decision)
    print(f"{color.upper():10} | {resultado.estado:22} | {resultado.datos}")

print("\nENVIO FISICO: DESACTIVADO")
PY
```

Interfaz de P2 compilada aparte y comprobación en Python:

```bash
export AMENT_PREFIX_PATH="$HOME/pruebas_p2_interfaz/install/arm_broker_interfaces_g3:$AMENT_PREFIX_PATH"
export PYTHONPATH="$HOME/pruebas_p2_interfaz/install/arm_broker_interfaces_g3/lib/python3.10/site-packages:$PYTHONPATH"
python -c "from arm_broker_interfaces_g3.action import PickPlace; print('INTERFAZ P2 DISPONIBLE EN PYTHON')"
```

## P3–P2: conexión y registro de cierre

```bash
ping -c 2 -W 2 172.51.1.20
ros2 action list -t | grep move_arm
python conexion_p3_p2.py                                   # CONEXION CORRECTA; no envía ningún objetivo

mkdir -p evidencias/pregunta_3/cierre
{
  echo "INTEGRACION GRUPO 8"
  echo "Fecha: $(date)"
  echo
  echo "P1: Interpretacion con LAYA validada"
  echo "P3: Microfono y Google GenAI validados"
  echo "P2: Conexion ROS 2 /move_arm validada"
  echo "Movimiento real: NO EJECUTADO"
  echo
  python conexion_p3_p2.py
} | tee evidencias/pregunta_3/cierre/integracion_p1_p2_p3.txt

ls -lh evidencias/pregunta_3/cierre/
```

## Jetson `yahboom` (P2): diagnóstico y modo seguro

```bash
# Procesos del broker y de MoveIt (en esta sesión: broker físico con permitir_movimiento_real:=true)
ps aux | grep -E 'pick_place_g3|arm_broker|broker_g3' | grep -v grep

ros2 action list -t
ros2 pkg prefix arm_broker                                  # /home/jetson/rb2_ws/install/arm_broker
ros2 interface show arm_broker_interfaces/action/MoveArm

# Qué archivo ejecuta realmente el comando "broker"
python3 - <<'PY'
from importlib.metadata import distribution

d = distribution("arm-broker")

for ep in d.entry_points:
    if ep.group == "console_scripts" and ep.name == "broker":
        print("BROKER INSTALADO:", ep.value)
        funcion = ep.load()
        print("ARCHIVO REAL:", funcion.__code__.co_filename)
PY

# Comprobación final con el broker en modo seguro
ros2 action list -t | grep move_arm
ros2 param get /arm_broker permitir_movimiento_real        # Boolean value is: False
```

Los dos procesos del broker físico (PID 1744249 y 1744272) se detuvieron con SIGTERM antes de levantar el broker en modo seguro.
