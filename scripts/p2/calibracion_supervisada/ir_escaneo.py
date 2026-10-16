# CALIBRACIÓN SUPERVISADA: abre el puerto serie del brazo directamente, sin pasar por el broker.
# Usar solo con el broker detenido y con alguien junto al robot; nunca durante P3 ni la demostración.
import time
from pymycobot.mycobot import MyCobot

PUERTO = "/dev/ttyUSB0"
VELOCIDAD = 10

POSTURA_ESCANEO = [
    140.4,
    -13.9,
    265,
    -171.38,
    -2.81,
    -42.55
]


def main():
    brazo = MyCobot(PUERTO, 1000000)

    actual = brazo.get_coords()
    angulos = brazo.get_angles()

    print("Coordenadas actuales:", actual)
    print("Angulos actuales:", angulos)
    print("Postura de escaneo:", POSTURA_ESCANEO)

    if not actual or len(actual) != 6:
        print("No se pudo verificar la posicion actual")
        return

    print("Verifica que el recorrido este libre de obstaculos.")
    print("Este programa NO verifica colisiones automaticamente.")

    confirmacion = input("Escribe MOVER para continuar: ")

    if confirmacion != "MOVER":
        print("Movimiento cancelado")
        return

    brazo.send_coords(POSTURA_ESCANEO, VELOCIDAD, 0)

    inicio = time.monotonic()

    while time.monotonic() - inicio < 20:
        time.sleep(0.5)

        if not brazo.is_moving():
            break

    print("Coordenadas finales:", brazo.get_coords())
    print("Angulos finales:", brazo.get_angles())


if __name__ == "__main__":
    main()
