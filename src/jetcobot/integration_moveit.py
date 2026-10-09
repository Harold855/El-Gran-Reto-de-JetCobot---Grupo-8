"""Planificación de poses con MoveIt2, ejecución exclusiva por el worker"""
import math
from numbers import Integral, Real

if __package__:
    from .posiciones import validar_pose
else:
    from posiciones import validar_pose

# Se tiene que convertir Rx, Ry, Rz a cuaternion usando la convencion: roll-pitch-yaw (XYZ), pero se tendria que verificar si esto es cierto.
def convertir_orientacion(rx, ry, rz):
    if not validar_pose([0, 0, 0, rx, ry, rz]):
        raise ValueError("¡Esta orientación no es válida!")
    r, p, y = (math.radians(v) / 2 for v in (rx, ry, rz))
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )

# Error XYZ estan en mm, que se uso en fk.py del Reto 2
# q_medidas debe estar en radianes
def calcular_error_fk(pose_solicitada, q_medidas, cinematica):
    if not validar_pose(pose_solicitada) or not validar_pose(q_medidas):
        raise ValueError("Las poses o articulaciones medidas no son válidas")
    alcanzada = cinematica.fk(list(q_medidas))
    if (len(alcanzada) != 3 or
            not validar_pose(list(alcanzada) + [0, 0, 0])):
        raise ValueError("¡Error! FK devolvió una posición no válida")
    return math.dist(pose_solicitada[:3], alcanzada)

# pymoveit2.plan retorna JointTrajectory; otros adaptadores la envuelven.
def _validar_trayectoria(resultado, cinematica=None):
    trayectoria = getattr(resultado, "joint_trajectory", resultado)
    if trayectoria is None or not getattr(trayectoria, "points", None):
        raise ValueError("No se pudo encontrar una trayectoria")

    nombres = list(trayectoria.joint_names)
    if (len(nombres) != 6 or
            any(not isinstance(n, str) or not n for n in nombres) or
            len(set(nombres)) != 6):
        raise ValueError("Es necesario que la trayectoria deba identificar seis articulaciones")

    if cinematica is not None:
        if set(nombres) != set(cinematica.JOINT_NAMES):
            raise ValueError("Las articulaciones no corresponden a la FK del RB-2")
        indices_fk = [nombres.index(n) for n in cinematica.JOINT_NAMES]

    tiempo_anterior = None
    for punto in trayectoria.points:
        q = list(punto.positions)
        if not validar_pose(q):
            raise ValueError("Punto articular incompleto o no finito")

        sec = punto.time_from_start.sec
        nano = punto.time_from_start.nanosec
        if (any(not isinstance(v, Integral) or isinstance(v, bool)
                for v in (sec, nano)) or
                sec < 0 or not 0 <= nano < 1_000_000_000):
            raise ValueError("Tiempo de trayectoria no válido")
        tiempo = sec * 1_000_000_000 + nano
        if tiempo_anterior is not None and tiempo <= tiempo_anterior:
            raise ValueError("Los tiempos deben ser estrictamente crecientes")
        tiempo_anterior = tiempo

        if cinematica is not None:
            q_fk = [q[i] for i in indices_fk]
            ok, motivo = cinematica.dentro_de_limites(q_fk)
            if not ok:
                raise ValueError(motivo)
            ok, motivo = cinematica.dentro_del_workspace(q_fk)
            if not ok:
                raise ValueError(motivo)

    return trayectoria

class IntegracionMoveIt:
    def __init__(self, planificador, ejecutar_trayectoria, frame_id,
                 target_link, timeout_planificacion=10.0, cinematica=None):
        if not callable(getattr(planificador, "plan", None)):
            raise ValueError("El planificador debe proporcionar el plan()")
        if not callable(ejecutar_trayectoria):
            raise ValueError("Aún falta el ejecutor de trayectorias del worker")
        if any(not isinstance(v, str) or not v.strip()
               for v in (frame_id, target_link)):
            raise ValueError("Se debe indicar el frame_id y el target_link usando el robot")
        if (not isinstance(timeout_planificacion, Real) or
                isinstance(timeout_planificacion, bool) or
                not math.isfinite(timeout_planificacion) or
                timeout_planificacion <= 0):
            raise ValueError("El timeout de planificación no es válido")

        self.planificador = planificador
        self.ejecutar_trayectoria = ejecutar_trayectoria
        self.frame_id = frame_id
        self.target_link = target_link
        self.timeout_planificacion = float(timeout_planificacion)
        self.cinematica = cinematica

    def mover_a_pose(self, pose):
        if not validar_pose(pose):
            print("[MOVEIT] Pose no válida")
            return False

        x, y, z, rx, ry, rz = pose
        try:
            resultado = self.planificador.plan(
                position=(x / 1000.0, y / 1000.0, z / 1000.0),
                quat_xyzw=convertir_orientacion(rx, ry, rz),
                frame_id=self.frame_id,
                target_link=self.target_link,
                timeout_sec=self.timeout_planificacion,
            )
            trayectoria = _validar_trayectoria(resultado, self.cinematica)
        except Exception as error:
            print(f"¡[MOVEIT] Ocurrio un error al planificar o validar!: {error}")
            return False

        try:
            confirmado = self.ejecutar_trayectoria(trayectoria)
        except Exception as error:
            print(f"[MOVEIT] Ocurrio un error de ejecución: {error}")
            return False

        if confirmado is not True:
            print("[MOVEIT] Este movimiento no está confirmado")
            return False
        print("[MOVEIT] Este movimiento si está confirmado por el worker")
        return True
