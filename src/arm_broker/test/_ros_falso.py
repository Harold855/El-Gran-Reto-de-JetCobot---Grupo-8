"""ROS 2 de mentira para probar la lógica del broker sin ROS ni hardware.

instalar() registra módulos falsos (rclpy, sensor_msgs, arm_broker_interfaces) solo si ROS no está
disponible y devuelve True; con ROS real devuelve False y las pruebas que lo usan se saltan.
No reemplaza una prueba con ROS 2 real: solo ejercita admisión, cola, worker y ejecución.
"""

import copy
import sys
import threading
import types
import uuid

PARAMETROS = {}   # parametros que la prueba quiere sobrescribir antes de crear el broker
_FALSO_ACTIVO = False


def _mensaje(nombre, **defectos):
    class Mensaje:
        def __init__(self, **kw):
            for clave, valor in defectos.items():
                setattr(self, clave, copy.copy(valor))
            for clave, valor in kw.items():
                setattr(self, clave, valor)
    Mensaje.__name__ = nombre
    return Mensaje


class _Logger:
    def __init__(self):
        self.mensajes = []

    def info(self, texto):
        self.mensajes.append(("info", texto))

    warn = error = info


class _Publicador:
    def __init__(self):
        self.enviados = []

    def publish(self, mensaje):
        self.enviados.append(mensaje)


class Node:
    def __init__(self, nombre):
        self._parametros = {}
        self._logger = _Logger()

    def declare_parameter(self, nombre, defecto):
        self._parametros[nombre] = PARAMETROS.get(nombre, defecto)

    def get_parameter(self, nombre):
        return types.SimpleNamespace(value=self._parametros[nombre])

    def create_publisher(self, *args, **kwargs):
        return _Publicador()

    def create_timer(self, *args, **kwargs):
        return None

    def get_logger(self):
        return self._logger

    def get_clock(self):
        reloj = types.SimpleNamespace()
        reloj.now = lambda: types.SimpleNamespace(to_msg=lambda: None)
        return reloj

    def destroy_node(self):
        return True


class ActionServer:
    def __init__(self, nodo, tipo, nombre, **kwargs):
        self.tipo, self.nombre, self.kwargs = tipo, nombre, kwargs


class GoalResponse:
    ACCEPT, REJECT = "ACCEPT", "REJECT"


class CancelResponse:
    ACCEPT, REJECT = "ACCEPT", "REJECT"


def instalar():
    global _FALSO_ACTIVO
    if _FALSO_ACTIVO:
        return True
    try:
        import rclpy  # noqa: F401
        return False
    except ImportError:
        pass
    _FALSO_ACTIVO = True

    def modulo(nombre, **atributos):
        m = types.ModuleType(nombre)
        m.__dict__.update(atributos)
        sys.modules[nombre] = m
        return m

    modulo("rclpy", init=lambda *a, **k: None, ok=lambda: True, shutdown=lambda: None)
    modulo("rclpy.action", ActionServer=ActionServer, GoalResponse=GoalResponse,
           CancelResponse=CancelResponse)
    modulo("rclpy.callback_groups", ReentrantCallbackGroup=type("R", (), {}),
           MutuallyExclusiveCallbackGroup=type("M", (), {}))
    modulo("rclpy.executors", MultiThreadedExecutor=type("E", (), {}))
    modulo("rclpy.node", Node=Node)
    modulo("sensor_msgs")
    modulo("sensor_msgs.msg", JointState=_mensaje("JointState", name=[], position=[], header=types.SimpleNamespace(stamp=None, frame_id="")))

    mover = types.SimpleNamespace(
        Goal=_mensaje("Goal", joint_positions=[], client_id="", priority=0),
        Result=_mensaje("Result", success=False, message="", wait_time_s=0.0, exec_time_s=0.0),
        Feedback=_mensaje("Feedback", state="", queue_position=0, elapsed_s=0.0))
    pick = types.SimpleNamespace(
        Goal=_mensaje("Goal", id_solicitud="", color_objetivo="", destino="", priority=0),
        Result=_mensaje("Result", success=False, message="", codigo_resultado="",
                        wait_time_s=0.0, exec_time_s=0.0),
        Feedback=_mensaje("Feedback", etapa="", elapsed_s=0.0))
    modulo("arm_broker_interfaces")
    modulo("arm_broker_interfaces.action", MoveArm=mover, PickPlace=pick)
    modulo("arm_broker_interfaces.msg", QueueState=_mensaje(
        "QueueState", stamp=None, executing_client="", executing_goal_id="", executing_elapsed_s=0.0,
        queue_length=0, queued_goal_ids=[], queued_clients=[], queued_priorities=[], queued_wait_s=[],
        total_accepted=0, total_rejected=0, total_completed=0))
    return True


class GoalHandleFalso:
    """Un goal aceptado: execute() corre el execute_callback en otro hilo, como el executor de rclpy."""

    def __init__(self, solicitud, ejecutar_cb):
        self.request = solicitud
        self.goal_id = types.SimpleNamespace(uuid=uuid.uuid4().bytes)
        self.is_cancel_requested = False
        self.estado = "ACCEPTED"
        self.feedback = []
        self.resultado = None
        self.terminado = threading.Event()
        self._ejecutar_cb = ejecutar_cb
        self.al_recibir_feedback = None

    def execute(self):
        self.estado = "EXECUTING"

        def correr():
            self.resultado = self._ejecutar_cb(self)
            self.terminado.set()
        threading.Thread(target=correr, daemon=True).start()

    def publish_feedback(self, fb):
        self.feedback.append(fb)
        if self.al_recibir_feedback:
            self.al_recibir_feedback(fb)

    def succeed(self):
        self.estado = "SUCCEEDED"

    def abort(self):
        self.estado = "ABORTED"

    def canceled(self):
        self.estado = "CANCELED"


# ---- ayudas para las pruebas del broker -------------------------------------------------------
def crear_broker(**parametros):
    PARAMETROS.clear()
    PARAMETROS.update(parametros)
    from arm_broker.broker import ArmBroker
    return ArmBroker()


def enviar_pick(broker, id_solicitud, color, destino, prioridad):
    """Devuelve (respuesta, goal_handle o None) como haría rclpy con un goal de /pick_place."""
    from arm_broker_interfaces.action import PickPlace
    meta = PickPlace.Goal(id_solicitud=id_solicitud, color_objetivo=color, destino=destino,
                          priority=prioridad)
    respuesta = broker.goal_callback_pickplace(meta)
    if respuesta != GoalResponse.ACCEPT:
        return respuesta, None
    handle = GoalHandleFalso(meta, broker.execute_callback_pickplace)
    broker.handle_accepted_pickplace(handle)
    return respuesta, handle


def enviar_move(broker, q, cliente, prioridad):
    from arm_broker_interfaces.action import MoveArm
    meta = MoveArm.Goal(joint_positions=list(q), client_id=cliente, priority=prioridad)
    respuesta = broker.goal_callback(meta)
    if respuesta != GoalResponse.ACCEPT:
        return respuesta, None
    handle = GoalHandleFalso(meta, broker.execute_callback)
    broker.handle_accepted_callback(handle)
    return respuesta, handle


class WorkerEnHilo:
    """Llama a broker._worker() en bucle (lo que haría el timer de 0.02 s) hasta detenerlo."""

    def __init__(self, broker):
        self.broker = broker
        self._parar = threading.Event()
        self._hilo = threading.Thread(target=self._correr, daemon=True)

    def _correr(self):
        while not self._parar.is_set():
            self.broker._worker()
            self._parar.wait(0.005)

    def __enter__(self):
        self._hilo.start()
        return self

    def __exit__(self, *args):
        self._parar.set()
        self.broker._parar.set()
        self._hilo.join(5)


def esperar(handles, segundos=10):
    for h in handles:
        if not h.terminado.wait(segundos):
            raise AssertionError("un goal no terminó a tiempo")
