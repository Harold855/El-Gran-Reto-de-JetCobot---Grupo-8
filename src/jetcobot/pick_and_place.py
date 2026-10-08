import time

from vision_colores import (abrir_camara, cerrar_camara, buscar_color_objetivo)
from posiciones import (POS_OBJETOS, DESTINOS)

PINZA_ABIERTA = 100
PINZA_CERRADA = 14

VEL_PINZA_ABRIR = 50
VEL_PINZA_CERRAR = 50

TOLERANCIA_PINZA = 5
TIMEOUT_PINZA = 4

# -------------------------Pinza----------------------------------
def esperar_pinza(mc, timeout=TIMEOUT_PINZA):
    inicio = time.time()
    while mc.is_gripper_moving():
        if time.time() - inicio > timeout:
            print("¡[PICK] ocurrió un timeout esperando la pinza!")
            return False
        time.sleep(0.1)
    return True

def abrir_pinza(mc):
     mc.set_gripper_value(
        PINZA_ABIERTA,
        VEL_PINZA_ABRIR
    )
    return esperar_pinza(mc)

def cerrar_pinza():
     mc.set_gripper_value(PINZA_CERRADA, VEL_PINZA_CERRAR)
    if not esperar_pinza(mc):
        return False
    try:
        valor = mc.get_gripper_value()
    except Exception:
        valor = None
    if valor is not None:
        if abs(valor - PINZA_CERRADA) <= TOLERANCIA_PINZA:
            print("¡[PICK] es posible de que no haya agarrado ningun objeto!")
        else:
            print("¡[PICK] he llegado a agarrar un objeto!")
    return True

# ------------------------------Movimiento------------------------------------
def mover_seguro(mover_a_pose, pose):
    if not mover_a_pose(pose):
        print("[PICK] No se pudo alcanzar la pose")
        return False

    return True

# -----------------------------Pick(Recogida)---------------------------------
def recoger_cubo(mc, mover_a_pose, pose_alta, pose_agarre):
    print("¡[PICK] aproximandome al objeto!")
  
    if not mover_seguro(mover_a_pose, pose_alta):
        return False
    print("[PICK] Bajando al objeto")
  
    if not mover_seguro(mover_a_pose, pose_agarre):
        return False
    print("[PICK] Cerrando pinza")
  
    if not cerrar_pinza(mc):
        return False
    print("[PICK] Subiendo con objeto")

    if not mover_seguro(mover_a_pose, pose_alta):
        return False
    return True

# ------------------------Place(Entrega)--------------------------------
def entregar_cubo(mc, mover_a_pose, destino):
    if destino not in DESTINY:
        print(f"¡[PICK] este destino: {destino}, NO ES VÁLIDO")
        return False

    d = DESTINY[destino]
    pose_alta = [d["xy"][0], d["xy"][1], d["z_alta"],
                 d["rx"], d["ry"], d["rz"]]
    pose_dejar = [d["xy"][0], d["xy"][1], d["z_dejar"],
                  d["rx"], d["ry"], d["rz"]]
    print(f"¡[PICK] moviendome al destino: {destino}!")
  
    if not mover_seguro(
        mover_a_pose,
        pose_alta
    ):
        return False
      
    if not mover_seguro(
        mover_a_pose,
        pose_dejar
    ):
        return False
    print("¡[PICK] abriendo la pinza!")
  
    if not abrir_pinza(mc):
        return False
    print("¡[PICK] retirando el brazo!")
  
    return mover_seguro(mover_a_pose, pose_alta)

# --------------------------Ciclo Completo-------------------------------
def ejecutar_pick_and_place(mc, mover_a_pose, color_objetivo, destino):
    color_objetivo = color_objetivo.lower()
    destino = destino.lower()
  
    if color_objetivo not in POS_OBJETOS:
        print(f"¡[PICK] este color no lo tengo configurado: {color_objetivo}!")
        return False
      
    if destino not in DESTINY:
        print(f"¡[PICK] este destino: {destino}, NO ES VÁLIDO!")
        return False

    # 1. ------------------------VISION--------------------------------------
    cap = abrir_camara()
    if cap is None:
        return False
      
    try:
        deteccion = buscar_color_objetivo(cap, color_objetivo)
    finally:
        cerrar_camara(cap)
      
    if deteccion is None:
        print(f"¡[PICK] no encontre el color: {color_objetivo}!")
        return False
    print(f"¡[PICK] he visto el objeto: {deteccion['color']}!")

    # 2. --------------------POSICIONES DEL OBJETO---------------------------
    objeto = POS_OBJETOS[color_objetivo]
    pose_alta = objeto["alta"]
    pose_agarre = objeto["agarre"]

    # 3. -------------------------RECOGER------------------------------------
    if not recoger_cubo(mc, mover_a_pose, pose_alta, pose_agarre):
        return False

    # 4. -------------------------ENTREGAR-----------------------------------
    if not entregar_cubo(mc, mover_a_pose, destino):
        return False
    print(f"¡[PICK] lo he completado, el {color_objetivo} llego a {destino}!")
    return True

