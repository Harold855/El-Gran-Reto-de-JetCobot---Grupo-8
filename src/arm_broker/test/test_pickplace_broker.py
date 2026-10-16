"""Broker con /move_arm y /pick_place sobre una sola cola y un solo worker (ROS falso, sin hardware)."""

import csv
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ros_falso as ros

HAY_FALSO = ros.instalar()
POSE_ALCANZABLE = [0.3, 0.0, 0.0, 0.0, 0.0, 0.0]


@unittest.skipUnless(HAY_FALSO, "hay ROS 2 real: estas pruebas usan el ROS falso")
class TestBrokerPickPlace(unittest.TestCase):

    def crear(self, **extra):
        parametros = dict(archivo_rechazos="", archivo_registro_tareas="", duracion_etapa_sim_s=0.01,
                          duracion_movimiento_s=0.02, pasos_interpolacion=2)
        parametros.update(extra)
        broker = ros.crear_broker(**parametros)
        self.orden = []            # orden en que el ejecutor empezó cada tarea
        self.dentro = 0            # cuántas secciones críticas hay abiertas ahora
        self.max_dentro = 0
        self._lock = threading.Lock()
        self._vigilar(broker)
        return broker

    def _vigilar(self, broker):
        """Envuelve el ejecutor y la publicación de /move_arm para detectar solapes."""
        ejecutar_original, mover_original = broker.ejecutor.ejecutar, broker.mover

        def entrar():
            with self._lock:
                self.dentro += 1
                self.max_dentro = max(self.max_dentro, self.dentro)

        def salir():
            with self._lock:
                self.dentro -= 1

        def ejecutar(tarea, ctx):
            self.orden.append(tarea.id_solicitud)
            entrar()
            try:
                return ejecutar_original(tarea, ctx)
            finally:
                salir()

        def mover(q):
            entrar()
            try:
                return mover_original(q)
            finally:
                salir()

        broker.ejecutor.ejecutar = ejecutar
        broker.mover = mover

    def test_t01_rojo_a_verde_completa_en_simulacion(self):
        broker = self.crear()
        _, h = ros.enviar_pick(broker, "p3-001", "rojo", "verde", 1)
        with ros.WorkerEnHilo(broker):
            ros.esperar([h])
            for _ in range(300):
                if broker.n_completados == 1:
                    break
                threading.Event().wait(0.01)
        self.assertEqual(h.estado, "SUCCEEDED")
        self.assertEqual(h.resultado.codigo_resultado, "COMPLETADO")
        self.assertIn("SIMULADO", h.resultado.message)
        etapas = [fb.etapa for fb in h.feedback]
        self.assertIn("PERCEPCION", etapas)
        self.assertIn("DEPOSITO", etapas)
        self.assertEqual(broker.n_completados, 1)

    def test_t05_objeto_ausente(self):
        broker = self.crear(colores_ausentes_sim="verde")
        _, h = ros.enviar_pick(broker, "p3-005", "verde", "rojo", 1)
        with ros.WorkerEnHilo(broker):
            ros.esperar([h])
        self.assertEqual(h.estado, "ABORTED")
        self.assertEqual(h.resultado.codigo_resultado, "OBJETO_AUSENTE")

    def test_t09_error_de_planificacion_libera_el_brazo(self):
        broker = self.crear(fallo_simulado="ERROR_PLANIFICACION")
        _, h1 = ros.enviar_pick(broker, "p3-009", "rojo", "verde", 1)
        with ros.WorkerEnHilo(broker):
            ros.esperar([h1])
            self.assertEqual(h1.resultado.codigo_resultado, "ERROR_PLANIFICACION")
            for _ in range(200):          # el worker libera el brazo
                if broker.ejecutando is None:
                    break
                threading.Event().wait(0.01)
        self.assertIsNone(broker.ejecutando)

    def test_t07_cuatro_clientes_orden_por_prioridad(self):
        broker = self.crear(politica="prioridad", tau_envejecimiento_s=1000.0)
        envios = [("p3-001", 1), ("p3-002", 3), ("p3-003", 2), ("p3-004", 3)]
        handles = [ros.enviar_pick(broker, i, "rojo", "verde", p)[1] for i, p in envios]
        with ros.WorkerEnHilo(broker):
            ros.esperar(handles)
        self.assertEqual(self.orden, ["p3-002", "p3-004", "p3-003", "p3-001"])
        self.assertEqual(self.max_dentro, 1)

    def test_t07_fifo_respeta_la_llegada(self):
        broker = self.crear(politica="fifo")
        handles = [ros.enviar_pick(broker, f"p3-0{i}", "rojo", "verde", 3 - i)[1] for i in range(3)]
        with ros.WorkerEnHilo(broker):
            ros.esperar(handles)
        self.assertEqual(self.orden, ["p3-00", "p3-01", "p3-02"])

    def test_t08_cancelar_pendiente_no_ejecuta(self):
        broker = self.crear()
        _, h1 = ros.enviar_pick(broker, "p3-001", "rojo", "verde", 1)
        _, h2 = ros.enviar_pick(broker, "p3-002", "azul", "amarillo", 1)
        h2.is_cancel_requested = True
        with ros.WorkerEnHilo(broker):
            ros.esperar([h1, h2])
        self.assertEqual(h2.estado, "CANCELED")
        self.assertEqual(h2.resultado.codigo_resultado, "CANCELADO")
        self.assertEqual(self.orden, ["p3-001"])

    def test_cancelar_en_ejecucion_con_cubo_sujeto(self):
        broker = self.crear()
        _, h = ros.enviar_pick(broker, "p3-003", "rojo", "verde", 1)

        def al_feedback(fb):
            if fb.etapa == "TRASLADO":
                h.is_cancel_requested = True
        h.al_recibir_feedback = al_feedback
        with ros.WorkerEnHilo(broker):
            ros.esperar([h])
        self.assertEqual(h.estado, "CANCELED")
        self.assertIn("cubo sujeto", h.resultado.message)

    def test_t11_move_arm_y_pick_place_nunca_se_solapan(self):
        broker = self.crear()
        handles = [
            ros.enviar_pick(broker, "p3-001", "rojo", "verde", 1)[1],
            ros.enviar_move(broker, POSE_ALCANZABLE, "alumno_1", 1)[1],
            ros.enviar_pick(broker, "p3-002", "azul", "amarillo", 2)[1],
            ros.enviar_move(broker, [-0.3, 0, 0, 0, 0, 0], "alumno_2", 1)[1],
        ]
        self.assertTrue(all(h is not None for h in handles))
        with ros.WorkerEnHilo(broker):
            ros.esperar(handles)
            for _ in range(300):          # el worker cuenta el último al liberar el brazo
                if broker.n_completados == 4:
                    break
                threading.Event().wait(0.01)
        self.assertEqual(self.max_dentro, 1)
        self.assertEqual(broker.n_completados, 4)
        self.assertTrue(all(h.estado == "SUCCEEDED" for h in handles))

    def test_t10_trazabilidad_en_el_csv(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = str(Path(carpeta) / "registro_tareas.csv")
            broker = self.crear(archivo_registro_tareas=ruta)
            _, h = ros.enviar_pick(broker, "p3-001", "rojo", "verde", 1)
            ros.enviar_pick(broker, "p3-002", "rojo", "derecha", 1)   # rechazada
            with ros.WorkerEnHilo(broker):
                ros.esperar([h])
            with open(ruta, newline="", encoding="utf-8") as f:
                filas = list(csv.DictReader(f))
        propios = [f["evento"] for f in filas if f["id_solicitud"] == "p3-001"]
        self.assertEqual(propios[:4], ["solicitud_recibida", "admitida_o_rechazada", "encolada", "inicio_worker"])
        self.assertEqual(propios[-1], "fin_tarea")
        rechazadas = [f for f in filas if f["id_solicitud"] == "p3-002"]
        self.assertIn("DESTINO_INVALIDO", rechazadas[-1]["detalle"])
        self.assertTrue(all(f["simulado"] == "True" for f in filas))

    def test_id_duplicado_no_toca_los_eventos_de_la_tarea_activa(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = str(Path(carpeta) / "registro_tareas.csv")
            broker = self.crear(archivo_registro_tareas=ruta)
            _, h = ros.enviar_pick(broker, "p3-001", "rojo", "verde", 1)
            antes = broker.registro.nombres("p3-001")
            respuesta, _ = ros.enviar_pick(broker, "p3-001", "azul", "amarillo", 2)   # mismo id, tarea activa
            self.assertEqual(respuesta, "REJECT")
            self.assertEqual(broker.registro.nombres("p3-001"), antes)          # nada nuevo en la activa
            self.assertNotIn("fin_tarea", broker.registro.nombres("p3-001"))     # y no se cerró
            with ros.WorkerEnHilo(broker):
                ros.esperar([h])
                for _ in range(300):
                    if broker.n_completados == 1:
                        break
                    threading.Event().wait(0.01)
            self.assertEqual(h.estado, "SUCCEEDED")
            with open(ruta, newline="", encoding="utf-8") as f:
                filas = list(csv.DictReader(f))
        tarea = [f for f in filas if f["registro"] == "tarea"]
        rechazo = [f for f in filas if f["registro"] == "rechazo"]
        self.assertEqual([f["evento"] for f in tarea].count("fin_tarea"), 1)
        self.assertIn("COMPLETADO", [f for f in tarea if f["evento"] == "fin_tarea"][0]["detalle"])
        self.assertEqual([f["evento"] for f in rechazo], ["solicitud_recibida", "admitida_o_rechazada", "fin_tarea"])
        self.assertIn("ID_DUPLICADO", rechazo[-1]["detalle"])
        self.assertTrue(all(f["id_solicitud"] == "p3-001" for f in filas))

    def test_id_se_libera_al_terminar(self):
        broker = self.crear()
        _, h = ros.enviar_pick(broker, "p3-001", "rojo", "verde", 1)
        with ros.WorkerEnHilo(broker):
            ros.esperar([h])
            for _ in range(200):
                if "p3-001" not in broker.ids_activos:
                    break
                threading.Event().wait(0.01)
        self.assertEqual(ros.enviar_pick(broker, "p3-001", "rojo", "verde", 1)[0], "ACCEPT")


if __name__ == "__main__":
    unittest.main()
