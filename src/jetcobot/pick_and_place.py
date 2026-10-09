import math
import time
from numbers import Real

if __package__:
    from .vision_colores import abrir_camara, cerrar_camara, buscar_color_objetivo
    from .posiciones import (POS_ESCANEO, obtener_poses_objeto, obtener_poses_destino, validar_pose, validar_aproximacion)
else:
    from vision_colores import abrir_camara, cerrar_camara, buscar_color_objetivo
    from posiciones import (POS_ESCANEO, obtener_poses_objeto, obtener_poses_destino, validar_pose, validar_aproximacion)

PINZA_ABIERTA = 100
PINZA_CERRADA = 14

VEL_PINZA_ABRIR = 50
VEL_PINZA_CERRAR = 50

TOLERANCIA_PINZA = 5
TIMEOUT_PINZA = 4
ESPERA_INICIO_PINZA = 0.2

# -------------------------Pinza----------------------------------
def esperar_pinza(mc, timeout=TIMEOUT_PINZA):
    limite = time.monotonic() + timeout
    time.sleep(min(ESPERA_INICIO_PINZA, max(0, timeout)))
    try:
        while time.monotonic() < limite:
            estado = mc.is_gripper_moving()
            if estado == 0:
                return True
            if estado != 1:
                print("¡[PICK] este estado de la pinza no esta disponible!")
                return False
            time.sleep(0.1)
    except Exception as error:
        print(f"¡[PICK] ocurrio un error al esperar la pinza!: {error}")
        return False
    print("¡[PICK] ocurrio un timeout esperando la pinza!")
    return False

def leer_valor_pinza(mc):
    try:
        valor = mc.get_gripper_value()
    except Exception as error:
        print(f"¡[PICK] ocurrio un error al leer la pinza!: {error}")
        return None
    if (not isinstance(valor, Real) or isinstance(valor, bool)
            or not math.isfinite(valor) or not 0 <= valor <= 100):
        print("¡[PICK] ¡Error! La lectura de pinza no es válida!")
        return None
    return valor

def accionar_pinza(mc, valor, velocidad):
    try:
        mc.set_gripper_value(valor, velocidad)
    except Exception as error:
        print(f"¡[PICK] ocurrió un error al accionar la pinza!: {error}")
        return False
    return esperar_pinza(mc)
    
def abrir_pinza(mc):
    if not accionar_pinza(mc, PINZA_ABIERTA, VEL_PINZA_ABRIR):
        return False
    valor = leer_valor_pinza(mc)
    return valor is not None and abs(valor - PINZA_ABIERTA) <= TOLERANCIA_PINZA

def cerrar_pinza(mc):
    if not accionar_pinza(mc, PINZA_CERRADA, VEL_PINZA_CERRAR):
        return False
    valor = leer_valor_pinza(mc)
    if valor is None:
        return False
        
    # Heuristica del Nivel 5(Reto 1 del JetCobot)
    if valor <= PINZA_CERRADA + TOLERANCIA_PINZA:
        print("¡[PICK] ocurrio un posible cierre sin objetos, verifica el objeto")
    if valor >= PINZA_ABIERTA - TOLERANCIA_PINZA:
        print("¡[PICK] la pinza aun sigue abierta!")
        return False
    print("¡[PICK] He completado el cierre!")
    return True

# ------------------------------Movimiento------------------------------------
def mover_seguro(mover_a_pose, pose):
    if not validar_pose(pose):
        print("¡[PICK] ¡Error! La pose quedo incompleta o no es valida!")
        return False
    try:
        if mover_a_pose(list(pose)) is True:
            return True
    except Exception as error:
        print(f"¡[PICK] ocurrio un error de movimiento!: {error}")
        return False
    print("¡[PICK] no pude confirmar que se alcanzara la pose!")
    return False

# -----------------------------Pick(Recogida)---------------------------------
def recoger_cubo(mc, mover_a_pose, pose_alta, pose_agarre):
    print("¡[PICK] me estoy aproximando al objeto!")
  
    if not validar_aproximacion(pose_alta, pose_agarre):
        return False
    if not mover_seguro(mover_a_pose, pose_alta):
        return False
    if not abrir_pinza(mc):
        return False
    if not mover_seguro(mover_a_pose, pose_agarre):
        return False
    if not cerrar_pinza(mc):
        return False
    return mover_seguro(mover_a_pose, pose_alta)

# ------------------------Place(Entrega)--------------------------------
def entregar_cubo(mc, mover_a_pose, destino):
    try:
        alta, dejar = obtener_poses_destino(destino)
    except ValueError as error:
        print(f"[PICK] {error}")
        return False
    if not mover_seguro(mover_a_pose, alta):
        return False
    if not mover_seguro(mover_a_pose, dejar):
        return False
    if not abrir_pinza(mc):
        return False
    return mover_seguro(mover_a_pose, alta)

# --------------------------Ciclo Completo-------------------------------
def ejecutar_pick_and_place(mc, mover_a_pose, color_objetivo, destino):
    if not isinstance(color_objetivo, str) or not isinstance(destino, str):
        return False
    color_objetivo = color_objetivo.strip().lower()
    destino = destino.strip().lower()
    try:
        pose_alta, pose_agarre = obtener_poses_objeto(color_objetivo)
        obtener_poses_destino(destino)
    except ValueError as error:
        print(f"[PICK] {error}")
        return False

    if usar_pose_escaneo and not mover_seguro(mover_a_pose, POS_ESCANEO):
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

