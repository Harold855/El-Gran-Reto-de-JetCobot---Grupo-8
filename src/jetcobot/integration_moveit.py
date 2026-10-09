import math

if __package__:
    from .posiciones import validar_pose
else:
    from posiciones import validar_pose


# Se tiene que convertir Rx, Ry, Rz a cuaternion usando la convencion asumida: roll-pitch-yaw (XYZ).
def convertir_orientacion(rx, ry, rz):
    r = math.radians(rx) / 2
    p = math.radians(ry) / 2
    y = math.radians(rz) / 2

    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)

    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    qw = cr * cp * cy + sr * sp * sy

    return (qx, qy, qz, qw)

class IntegracionMoveIt:

    def __init__(
        self,
        planificador,
        ejecutar_trayectoria,
        frame_id,
        target_link
    ):
        self.planificador = planificador
        self.ejecutar_trayectoria = ejecutar_trayectoria
        self.frame_id = frame_id
        self.target_link = target_link

    def mover_a_pose(self, pose):

        if not validar_pose(pose):
            print("[MOVEIT] Pose invalida")
            return False

        x, y, z, rx, ry, rz = pose

        # MyCobot(en mm) irá hacia MoveIt2 (en metros)
        posicion = (
            x / 1000.0,
            y / 1000.0,
            z / 1000.0
        )

        orientacion = convertir_orientacion(
            rx, ry, rz
        )

        # 1. Se planifica con MoveIt2
        try:
            trayectoria = self.planificador.plan(
                position=posicion,
                quat_xyzw=orientacion,
                frame_id=self.frame_id,
                target_link=self.target_link,
                timeout_sec=10.0
            )

        except Exception as error:
            print(f"[MOVEIT] Error: {error}")
            return False

        if trayectoria is None or not trayectoria.points:
            print("[MOVEIT] No encontre trayectoria")
            return False

        print("[MOVEIT] Trayectoria planificada")

        # 2. Después, el worker ejecuta la trayectoria
        try:
            resultado = self.ejecutar_trayectoria(
                trayectoria
            )

        except Exception as error:
            print(f"[MOVEIT] Error de ejecucion: {error}")
            return False

        if resultado is not True:
            print("[MOVEIT] Movimiento no confirmado")
            return False

        print("[MOVEIT] Movimiento completado")
        return True
