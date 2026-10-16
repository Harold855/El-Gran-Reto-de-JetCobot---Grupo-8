"""Envío de P3 a /pick_place con un cliente de acción falso (sin ROS ni hardware)."""

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/transcriptor_voz

from envio_pickplace import COLUMNAS_P2, decision_apta, enviar_pick_place


def decision(**cambios):
    base = dict(accion="trasladar", objeto="cubo", color="rojo", destino="verde", prioridad=1,
                permitido=True, degradado=False, motivo="")
    base.update(cambios)
    return types.SimpleNamespace(**base)


class Futuro:
    def __init__(self, valor, listo=True):
        self._valor, self._listo = valor, listo

    def done(self):
        return self._listo

    def result(self):
        return self._valor


class Meta:
    def __init__(self, **kw):
        self.__dict__.update(kw)


Accion = types.SimpleNamespace(Goal=Meta)


class Handle:
    def __init__(self, aceptado=True, resultado=None, resultado_listo=True):
        self.accepted = aceptado
        self._resultado = resultado
        self._listo = resultado_listo
        self.cancelado = False

    def get_result_async(self):
        return Futuro(self._resultado, self._listo)

    def cancel_goal_async(self):
        self.cancelado = True


class Cliente:
    def __init__(self, servidor=True, handle=None, etapas=()):
        self.servidor, self.handle, self.etapas = servidor, handle, etapas
        self.enviadas = []

    def wait_for_server(self, timeout_sec):
        return self.servidor

    def send_goal_async(self, meta, feedback_callback):
        self.enviadas.append(meta)
        for etapa in self.etapas:
            feedback_callback(types.SimpleNamespace(feedback=types.SimpleNamespace(etapa=etapa)))
        return Futuro(self.handle)


def esperar(futuro, segundos):
    return futuro.done()


def resultado_p2(codigo="COMPLETADO", status=4, mensaje="COMPLETADO (SIMULADO): completado"):
    res = types.SimpleNamespace(codigo_resultado=codigo, message=mensaje, wait_time_s=0.25, exec_time_s=1.5)
    return types.SimpleNamespace(status=status, result=res)


class TestDecisionApta(unittest.TestCase):

    def test_valida(self):
        self.assertEqual(decision_apta(decision()), (True, ""))

    def test_casos_no_aptos(self):
        for d in (None, decision(permitido=False), decision(accion="lanzar"), decision(objeto="esfera"),
                  decision(color="morado"), decision(destino="derecha"), decision(prioridad=0),
                  decision(prioridad=4)):
            self.assertFalse(decision_apta(d)[0])

    def test_degradada_solo_con_permiso_explicito(self):
        self.assertFalse(decision_apta(decision(degradado=True))[0])
        self.assertTrue(decision_apta(decision(degradado=True), permitir_degradado=True)[0])


class TestEnvio(unittest.TestCase):

    def enviar(self, cliente, d=None, **extra):
        return enviar_pick_place(cliente, Accion, "a1b2c3d4", d or decision(), esperar,
                                 mostrar=lambda *_: None, **extra)

    def test_camino_feliz_simulado(self):
        cliente = Cliente(handle=Handle(resultado=resultado_p2()), etapas=["EN_COLA", "PERCEPCION", "PERCEPCION", "DEPOSITO"])
        r = self.enviar(cliente)
        self.assertTrue(r.completado)
        self.assertTrue(r.simulado)
        self.assertEqual(r.etapas, ["EN_COLA", "PERCEPCION", "PERCEPCION", "DEPOSITO"])
        meta = cliente.enviadas[0]
        self.assertEqual((meta.id_solicitud, meta.color_objetivo, meta.destino, meta.priority),
                         ("a1b2c3d4", "rojo", "verde", 1))
        columnas = r.a_columnas(t_parcial_ms=1000.0)
        self.assertEqual(len(columnas), len(COLUMNAS_P2))
        self.assertEqual(columnas[COLUMNAS_P2.index("etapas_p2")], "EN_COLA>PERCEPCION>DEPOSITO")
        self.assertGreater(columnas[COLUMNAS_P2.index("tiempo_total_p2_ms")], 1000.0)

    def test_orden_no_apta_no_toca_el_cliente(self):
        cliente = Cliente(handle=Handle())
        r = self.enviar(cliente, decision(permitido=False))
        self.assertEqual(r.estado, "NO_ENVIADO")
        self.assertFalse(r.enviado)
        self.assertEqual(cliente.enviadas, [])

    def test_sin_servidor(self):
        r = self.enviar(Cliente(servidor=False))
        self.assertEqual(r.estado, "SIN_SERVIDOR")
        self.assertFalse(r.enviado)

    def test_rechazo_del_broker(self):
        r = self.enviar(Cliente(handle=Handle(aceptado=False)))
        self.assertEqual(r.estado, "RECHAZADO")
        self.assertTrue(r.enviado)
        self.assertFalse(r.aceptado)
        self.assertEqual(r.codigo, "")

    def test_objeto_ausente(self):
        r = self.enviar(Cliente(handle=Handle(resultado=resultado_p2("OBJETO_AUSENTE", 6, "OBJETO_AUSENTE (SIMULADO): x"))))
        self.assertEqual((r.estado, r.codigo), ("ABORTADO", "OBJETO_AUSENTE"))
        self.assertFalse(r.completado)

    def test_timeout_pide_cancelar(self):
        handle = Handle(resultado_listo=False)
        r = self.enviar(Cliente(handle=handle))
        self.assertEqual(r.estado, "TIMEOUT_CLIENTE")
        self.assertTrue(handle.cancelado)

    def test_id_invalido(self):
        r = enviar_pick_place(Cliente(handle=Handle()), Accion, "con espacios", decision(), esperar)
        self.assertEqual(r.estado, "NO_ENVIADO")

    def test_excepcion_no_se_propaga(self):
        class Roto(Cliente):
            def wait_for_server(self, timeout_sec):
                raise RuntimeError("fallo")
        self.assertEqual(self.enviar(Roto()).estado, "ERROR_CLIENTE")

    def test_no_enviado_deja_columnas_vacias(self):
        columnas = self.enviar(Cliente(), decision(permitido=False)).a_columnas(500.0)
        self.assertEqual(columnas[COLUMNAS_P2.index("aceptado_p2")], "")
        self.assertEqual(columnas[COLUMNAS_P2.index("tiempo_total_p2_ms")], "")


if __name__ == "__main__":
    unittest.main()
