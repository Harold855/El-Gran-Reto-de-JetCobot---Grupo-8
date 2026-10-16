# CALIBRACIÓN SUPERVISADA: abre el puerto serie del brazo directamente, sin pasar por el broker.
# Usar solo con el broker detenido y con alguien junto al robot; nunca durante P3 ni la demostración.
import time
from pymycobot.mycobot import MyCobot

PUERTO = "/dev/ttyUSB0"
VELOCIDAD = 10
ANGULOS_YAHBOOM = [42, 0, 0, -85, -7, -3]


def main():
    brazo = MyCobot(PUERTO, 1000000)

    print("Angulos actuales:", brazo.get_angles())
    print("Coordenadas actuales:", brazo.get_coords())
    print("Destino Yahboom:", ANGULOS_YAHBOOM)

    respuesta = input("Escribe MOVER para continuar: ")

    if respuesta != "MOVER":
        print("Movimiento cancelado")
        return

    brazo.send_angles(ANGULOS_YAHBOOM, VELOCIDAD)

    inicio = time.monotonic()

    while time.monotonic() - inicio < 20:
        time.sleep(0.5)

        if not brazo.is_moving():
            break

    print("Angulos finales:", brazo.get_angles())
    print("Coordenadas finales:", brazo.get_coords())


if __name__ == "__main__":
    main()
