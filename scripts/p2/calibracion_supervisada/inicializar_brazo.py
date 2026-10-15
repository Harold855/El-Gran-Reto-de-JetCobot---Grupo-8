# CALIBRACIÓN SUPERVISADA: abre el puerto serie del brazo directamente, sin pasar por el broker.
# Usar solo con el broker detenido y con alguien junto al robot; nunca durante P3 ni la demostración.
import time
from pymycobot.mycobot import MyCobot

POSTURA_INICIAL = [0, 0, 0, 0, 0, -45]
VELOCIDAD = 10
TOLERANCIA = 2.0

mc = MyCobot("/dev/ttyUSB0", 1000000)

actual = mc.get_angles()
estado = mc.is_all_servo_enable()

if not isinstance(actual, (list, tuple)) or len(actual) != 6:
    raise RuntimeError("No se pudieron leer los ángulos")

if estado != 1:
    raise RuntimeError("Los servomotores no están habilitados")

print("=== MOVIMIENTO A POSTURA INICIAL ===")
print("Actual:", actual)
print("Destino:", POSTURA_INICIAL)
print("Velocidad:", VELOCIDAD)

# Evitar iniciar automáticamente desde una postura desconocida.
confirmacion = input(
    "\n¿Confirmas que el recorrido está despejado y "
    "puedes detener el robot si es necesario? (SI): "
)

if confirmacion != "SI":
    raise SystemExit("Movimiento cancelado")

print("\nEnviando movimiento...")
mc.send_angles(POSTURA_INICIAL, VELOCIDAD)

inicio = time.monotonic()
tiempo_maximo = 45

while time.monotonic() - inicio < tiempo_maximo:
    time.sleep(0.5)

    angulos = mc.get_angles()

    if not isinstance(angulos, (list, tuple)) or len(angulos) != 6:
        print("Lectura no disponible; revisar el brazo.")
        break

    error = max(
        abs(a - b)
        for a, b in zip(angulos, POSTURA_INICIAL)
    )

    print(f"Ángulos: {angulos} | Error máximo: {error:.2f}°")

    if error <= TOLERANCIA:
        print("\nPOSTURA INICIAL ALCANZADA")
        break
else:
    print("\nTiempo máximo alcanzado; revisar posición.")

print("Fin de supervisión.")
