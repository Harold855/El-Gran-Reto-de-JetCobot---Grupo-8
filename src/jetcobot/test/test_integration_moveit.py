"""Planificación separada de la ejecución, con trayectorias sintéticas (sin MoveIt ni robot)."""

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/

from arm_broker import fk
from jetcobot.integration_moveit import EjecutorTrayectoriaFalso, IntegracionMoveIt

NOMBRES = fk.JOINT_NAMES


def punto(q, sec):
    return types.SimpleNamespace(positions=q, time_from_start=types.SimpleNamespace(sec=sec, nanosec=0))


def trayectoria(puntos, nombres=NOMBRES):
    return types.SimpleNamespace(joint_names=list(nombres), points=puntos)


class PlanificadorFalso:
    def __init__(self, resultado=None, error=None):
        self.resultado, self.error = resultado, error

    def plan(self, **kwargs):
        if self.error:
            raise self.error
        return self.resultado


Q_OK = [0.1, -0.5, 0.5, 0.0, 0.2, 0.0]
POSE = [140.0, -14.0, 265.0, -171.0, -3.0, -43.0]


def crear(planificador, ejecutor):
    return IntegracionMoveIt(planificador, ejecutor, "base_link", "jiazhua_Link", cinematica=fk)


class TestPlanificarYEjecutar(unittest.TestCase):

    def test_plan_valido_no_ejecuta_nada(self):
        ejecutor = EjecutorTrayectoriaFalso()
        mi = crear(PlanificadorFalso(trayectoria([punto(Q_OK, 1), punto(Q_OK, 2)])), ejecutor)
        plan = mi.planificar_pose(POSE)
        self.assertTrue(plan.ok)
        self.assertEqual(ejecutor.recibidas, [])

    def test_mover_a_pose_planifica_y_ejecuta(self):
        ejecutor = EjecutorTrayectoriaFalso()
        mi = crear(PlanificadorFalso(trayectoria([punto(Q_OK, 1)])), ejecutor)
        self.assertTrue(mi.mover_a_pose(POSE))
        self.assertEqual(len(ejecutor.recibidas), 1)

    def test_articulaciones_incompletas(self):
        mi = crear(PlanificadorFalso(trayectoria([punto(Q_OK[:5], 1)])), EjecutorTrayectoriaFalso())
        self.assertFalse(mi.planificar_pose(POSE).ok)

    def test_nombres_de_articulaciones_incorrectos(self):
        mi = crear(PlanificadorFalso(trayectoria([punto(Q_OK, 1)], nombres=["a", "b", "c", "d", "e", "f"])),
                   EjecutorTrayectoriaFalso())
        self.assertFalse(mi.planificar_pose(POSE).ok)

    def test_tiempos_no_crecientes(self):
        mi = crear(PlanificadorFalso(trayectoria([punto(Q_OK, 2), punto(Q_OK, 2)])), EjecutorTrayectoriaFalso())
        self.assertFalse(mi.planificar_pose(POSE).ok)

    def test_fuera_de_limites_articulares(self):
        mi = crear(PlanificadorFalso(trayectoria([punto([3.5, 0, 0, 0, 0, 0], 1)])), EjecutorTrayectoriaFalso())
        self.assertFalse(mi.planificar_pose(POSE).ok)

    def test_fallo_del_planificador_no_ejecuta(self):
        ejecutor = EjecutorTrayectoriaFalso()
        mi = crear(PlanificadorFalso(error=RuntimeError("sin solución")), ejecutor)
        self.assertFalse(mi.mover_a_pose(POSE))
        self.assertEqual(ejecutor.recibidas, [])

    def test_ejecutor_que_no_confirma(self):
        mi = crear(PlanificadorFalso(trayectoria([punto(Q_OK, 1)])), EjecutorTrayectoriaFalso(confirmar=False))
        self.assertFalse(mi.mover_a_pose(POSE))

    def test_pose_invalida(self):
        mi = crear(PlanificadorFalso(trayectoria([punto(Q_OK, 1)])), EjecutorTrayectoriaFalso())
        self.assertFalse(mi.planificar_pose([1, 2, 3]).ok)


if __name__ == "__main__":
    unittest.main()
