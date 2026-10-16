# CALIBRACIÓN SUPERVISADA: abre el puerto serie del brazo directamente, sin pasar por el broker.
# Usar solo con el broker detenido y con alguien junto al robot; nunca durante P3 ni la demostración.
from pymycobot.mycobot import MyCobot

POSTURA_INICIAL = [0, 0, 0, 0, 0, -45]
VELOCIDAD_INICIAL = 10
TOLERANCIA_GRADOS = 2.0

mc = MyCobot("/dev/ttyUSB0", 1000000)

actual = mc.get_angles()
estado = mc.is_all_servo_enable()

print("=== PREPARACIÓN DEL INICIO ===")
print("Postura actual:", actual)
print("Postura inicial:", POSTURA_INICIAL)
print("Servomotores:", estado)
print("Velocidad prevista:", VELOCIDAD_INICIAL)
print("Tolerancia:", TOLERANCIA_GRADOS, "grados")

if not isinstance(actual, (list, tuple)) or len(actual) != 6:
    raise RuntimeError("No se pudieron leer los seis ángulos")

if estado != 1:
    raise RuntimeError("Los servomotores no están habilitados")

print("\nDIFERENCIAS ARTICULARES:")
for i, (a, b) in enumerate(zip(actual, POSTURA_INICIAL), 1):
    diferencia = b - a
    print(f"J{i}: {a:.2f}° -> {b:.2f}° | cambio {diferencia:+.2f}°")

print("\nSolo diagnóstico: NO se envió ningún movimiento.")
print("Pendiente: validar una trayectoria libre de colisiones.")
