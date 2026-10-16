# CALIBRACIÓN SUPERVISADA: abre el puerto serie del brazo directamente, sin pasar por el broker.
# Usar solo con el broker detenido y con alguien junto al robot; nunca durante P3 ni la demostración.
import time
from pymycobot.mycobot import MyCobot

PUERTO = "/dev/ttyUSB0"
BAUDIOS = 1000000

print("=== CONEXIÓN CON JETCOBOT ===")

mc = MyCobot(PUERTO, BAUDIOS)
time.sleep(1)

print("\n=== ÁNGULOS ACTUALES ===")
angulos = mc.get_angles()
print(angulos)

print("\n=== ESTADO DE SERVOMOTORES ===")
try:
    estado = mc.is_all_servo_enable()
    print("Estado:", estado)
    print("1 = habilitados; 0 = alguno deshabilitado")
except Exception as e:
    print("No se pudo consultar el estado:", e)

print("\nConsulta terminada. No se enviaron movimientos.")
