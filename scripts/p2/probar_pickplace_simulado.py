#!/usr/bin/env python3
"""Cliente de prueba de /pick_place: envía tareas al broker y tabula aceptación, feedback y resultado.

Con el broker en modo simulado (scripts/iniciar.sh), sin hardware:

    python3 scripts/p2/probar_pickplace_simulado.py --escenario valida
    python3 scripts/p2/probar_pickplace_simulado.py --escenario cuatro
    python3 scripts/p2/probar_pickplace_simulado.py --escenario cancelacion
    python3 scripts/p2/probar_pickplace_simulado.py --escenario invalida
    python3 scripts/p2/probar_pickplace_simulado.py --escenario ausente   # broker con -p colores_ausentes_sim:=verde

Escribe evidencias/pregunta_2/mediciones/pickplace_<escenario>_<hora>.csv. Todo lo que devuelve un
broker simulado va marcado simulado=True: no cuenta como intento de agarre físico ni como latencia real.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from jetcobot.rutas import MEDICIONES

# (id_solicitud, color, destino, prioridad, cancelar_tras_aceptar)
ESCENARIOS = {
    "valida": [("p3-001", "rojo", "verde", 1, False)],
    "otra": [("p3-002", "azul", "amarillo", 2, False)],
    "invalida": [("p3-003", "rojo", "derecha", 1, False), ("p3-004", "morado", "azul", 1, False)],
    "ausente": [("p3-005", "verde", "rojo", 1, False)],
    "cuatro": [("p3-010", "rojo", "verde", 1, False), ("p3-011", "azul", "amarillo", 3, False),
               ("p3-012", "verde", "azul", 2, False), ("p3-013", "amarillo", "rojo", 3, False)],
    "cancelacion": [("p3-020", "rojo", "verde", 1, False), ("p3-021", "azul", "rojo", 1, True)],
}
COLUMNAS = ["simulado", "id_solicitud", "color", "destino", "prioridad", "aceptado", "estado",
            "codigo_resultado", "mensaje", "espera_s", "ejecucion_s", "etapas"]


def main():
    ap = argparse.ArgumentParser(description="Prueba /pick_place sin hardware.")
    ap.add_argument("--escenario", choices=sorted(ESCENARIOS), default="valida")
    ap.add_argument("--espera", type=float, default=60.0, help="segundos máximos por resultado")
    args = ap.parse_args()

    import rclpy
    from action_msgs.msg import GoalStatus
    from arm_broker_interfaces.action import PickPlace
    from rclpy.action import ActionClient
    from rclpy.node import Node

    rclpy.init()
    nodo = Node("probar_pickplace_simulado")
    cliente = ActionClient(nodo, PickPlace, "pick_place")
    if not cliente.wait_for_server(timeout_sec=5.0):
        print("No hay servidor /pick_place: inicia el broker con scripts/iniciar.sh")
        rclpy.shutdown()
        return 1

    envios = []
    for idr, color, destino, prioridad, cancelar in ESCENARIOS[args.escenario]:
        meta = PickPlace.Goal(id_solicitud=idr, color_objetivo=color, destino=destino, priority=prioridad)
        registro = {"id": idr, "color": color, "destino": destino, "prioridad": prioridad,
                    "cancelar": cancelar, "etapas": []}
        registro["futuro"] = cliente.send_goal_async(
            meta, feedback_callback=lambda fb, r=registro: r["etapas"].append(fb.feedback.etapa))
        envios.append(registro)

    for r in envios:
        rclpy.spin_until_future_complete(nodo, r["futuro"], timeout_sec=10.0)
        r["handle"] = r["futuro"].result() if r["futuro"].done() else None
        r["aceptado"] = bool(r["handle"] and r["handle"].accepted)
        if r["aceptado"] and r["cancelar"]:
            r["handle"].cancel_goal_async()

    filas = []
    for r in envios:
        fila = {"simulado": "", "id_solicitud": r["id"], "color": r["color"], "destino": r["destino"],
                "prioridad": r["prioridad"], "aceptado": r["aceptado"], "estado": "RECHAZADO",
                "codigo_resultado": "", "mensaje": "", "espera_s": "", "ejecucion_s": "",
                "etapas": ">".join(dict.fromkeys(r["etapas"]))}
        if r["aceptado"]:
            futuro = r["handle"].get_result_async()
            rclpy.spin_until_future_complete(nodo, futuro, timeout_sec=args.espera)
            if futuro.done():
                envio = futuro.result()
                res = envio.result
                nombres = {GoalStatus.STATUS_SUCCEEDED: "EXITO", GoalStatus.STATUS_ABORTED: "ABORTADO",
                           GoalStatus.STATUS_CANCELED: "CANCELADO"}
                fila.update(estado=nombres.get(envio.status, str(envio.status)),
                            codigo_resultado=res.codigo_resultado, mensaje=res.message,
                            espera_s=f"{res.wait_time_s:.3f}", ejecucion_s=f"{res.exec_time_s:.3f}",
                            simulado="SIMULADO" in res.message)
            else:
                fila["estado"] = "SIN_RESULTADO"
        filas.append(fila)
    rclpy.shutdown()

    MEDICIONES.mkdir(parents=True, exist_ok=True)
    ruta = MEDICIONES / f"pickplace_{args.escenario}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)

    print(f"{'id':8} {'color':9} {'destino':9} {'p':>2} {'estado':10} {'codigo':18} {'espera':>7} etapas")
    for f in filas:
        print(f"{f['id_solicitud']:8} {f['color']:9} {f['destino']:9} {f['prioridad']:>2} {f['estado']:10} "
              f"{f['codigo_resultado']:18} {f['espera_s']:>7} {f['etapas']}")
    print(f"\nCSV: {ruta}\nLos resultados del broker simulado están marcados simulado=True.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
