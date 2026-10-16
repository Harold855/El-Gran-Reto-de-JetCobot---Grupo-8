"""Secuencia de pick and place del JetCobot.

La secuencia (ejecutar_secuencia) no toca hardware por sí sola: recibe por parámetro la percepción,
el movimiento y la pinza, así que se prueba con funciones falsas. Devuelve un ResultadoPP
estructurado y nunca da por bueno un agarre que no se confirmó.
"""
import math
import time
from dataclasses import dataclass
from numbers import Real

if __package__:
    from .posiciones import (ConfiguracionError, ColorInvalido, DestinoInvalido, NoConfigurado,
                             cargar_configuracion, obtener_poses_destino, validar_pose,
                             validar_aproximacion)
else:
    from posiciones import (ConfiguracionError, ColorInvalido, DestinoInvalido, NoConfigurado,
                            cargar_configuracion, obtener_poses_destino, validar_pose,
                            validar_aproximacion)

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

# --------------------------Pinza como objeto-------------------------------
class PinzaMyCobot:
    """Adaptador de la pinza de un MyCobot a la interfaz de la secuencia (abrir y cerrar)."""

    def __init__(self, mc):
        self.mc = mc

    def abrir(self):
        return abrir_pinza(self.mc)

    def cerrar(self):
        """'agarrado', 'vacia' (cerró del todo: no hay cubo) o 'error'."""
        if not accionar_pinza(self.mc, PINZA_CERRADA, VEL_PINZA_CERRAR):
            return "error"
        valor = leer_valor_pinza(self.mc)
        if valor is None or valor >= PINZA_ABIERTA - TOLERANCIA_PINZA:
            return "error"
        if valor <= PINZA_CERRADA + TOLERANCIA_PINZA:
            return "vacia"
        return "agarrado"

# --------------------------Resultado estructurado--------------------------
@dataclass
class ResultadoPP:
    success: bool
    codigo: str          # COMPLETADO, OBJETO_AUSENTE, NO_CONFIGURADO, ERROR_AGARRE, ...
    etapa: str           # última etapa alcanzada
    motivo: str = ""

def _ok(etapa, motivo="completado"):
    return ResultadoPP(True, "COMPLETADO", etapa, motivo)

def _fallo(codigo, etapa, motivo):
    return ResultadoPP(False, codigo, etapa, motivo)

# --------------------------Ciclo Completo-------------------------------
def ejecutar_secuencia(color_objetivo, destino, *, config, percibir, mover_a_pose, pinza,
                       usar_pose_escaneo=True, on_etapa=None, cancelado=None):
    """Recoge el cubo de color_objetivo y lo deja en la zona destino.

    config: ConfigTrabajo con las poses; percibir(color) -> dict con 'presente';
    mover_a_pose(pose) -> True solo si se confirmó; pinza: abrir() -> bool y
    cerrar() -> 'agarrado' | 'vacia' | 'error'; on_etapa(nombre) avisa cada etapa;
    cancelado() -> True pide parar.
    Todo se valida antes de mover nada. Si se cancela con el cubo sujeto NO se suelta solo:
    el resultado lo dice y hace falta que una persona intervenga.
    """
    on_etapa = on_etapa or (lambda etapa: None)
    cancelado = cancelado or (lambda: False)

    # 1. Validación y poses, sin mover nada
    try:
        color = config.color_valido(color_objetivo)
        # Validamos el destino antes de consultar las poses
        alta_d, dejar_d = config.poses_destino(destino)
        
        if color != destino.strip().lower():
            raise DestinoInvalido(
                "Destino incompatible con P2: "
                "el cubo debe ir a la zona de su mismo color"
            )
        # Solo después comprobamos las poses de recogida
        alta_o, agarre_o = config.poses_objeto(color)
        escaneo = config.pose_escaneo() if usar_pose_escaneo else None
    except ColorInvalido as error:
        return _fallo("COLOR_INVALIDO", "VALIDACION", str(error))
    except DestinoInvalido as error:
        return _fallo("DESTINO_INVALIDO", "VALIDACION", str(error))
    except NoConfigurado as error:
        return _fallo("NO_CONFIGURADO", "VALIDACION", str(error))
    except ConfiguracionError as error:
        return _fallo("NO_CONFIGURADO", "VALIDACION", str(error))

    estado = {"sujeto": False}

    def parar(etapa):
        if not cancelado():
            return None
        if estado["sujeto"]:
            motivo = "cancelado con el cubo sujeto: no se suelta solo; requiere intervención"
        else:
            motivo = "cancelado antes de tomar el cubo"
        return _fallo("CANCELADO", etapa, motivo)

    def mover(pose, etapa):
        try:
            if mover_a_pose(list(pose)) is True:
                return None
        except Exception as error:
            return _fallo("ERROR_PLANIFICACION", etapa, f"error de movimiento: {error}")
        return _fallo("ERROR_PLANIFICACION", etapa, "no se confirmó que se alcanzara la pose")

    # 2. Percepción: solo detecta presencia, no confirma agarre
    on_etapa("PERCEPCION")
    fin = parar("PERCEPCION")
    if fin:
        return fin
    if escaneo is not None:
        fin = mover(escaneo, "PERCEPCION")
        if fin:
            return fin
    try:
        deteccion = percibir(color)
    except Exception as error:
        return _fallo("ERROR_INTERNO", "PERCEPCION", f"falló la percepción: {error}")
    if not deteccion or not deteccion.get("presente"):
        return _fallo("OBJETO_AUSENTE", "PERCEPCION", f"no se ve el cubo {color}")

    # 3. Aproximación y agarre
    on_etapa("APROXIMACION")
    fin = parar("APROXIMACION") or mover(alta_o, "APROXIMACION")
    if fin:
        return fin
    if not pinza.abrir():
        return _fallo("ERROR_AGARRE", "APROXIMACION", "la pinza no se abrió")
    fin = parar("APROXIMACION") or mover(agarre_o, "APROXIMACION")
    if fin:
        return fin

    on_etapa("AGARRE")
    fin = parar("AGARRE")
    if fin:
        return fin
    agarre = pinza.cerrar()
    if agarre != "agarrado":
        mover(alta_o, "AGARRE")   # intento de retirada; el fallo del agarre es lo que se informa
        motivo = "la pinza cerró sin cubo" if agarre == "vacia" else "la pinza no confirmó el cierre"
        return _fallo("ERROR_AGARRE", "AGARRE", motivo)
    estado["sujeto"] = True

    # 4. Traslado y depósito
    on_etapa("TRASLADO")
    for pose in (alta_o, alta_d):
        fin = parar("TRASLADO") or mover(pose, "TRASLADO")
        if fin:
            return fin
    on_etapa("DEPOSITO")
    fin = parar("DEPOSITO") or mover(dejar_d, "DEPOSITO")
    if fin:
        return fin
    if not pinza.abrir():
        return _fallo("ERROR_AGARRE", "DEPOSITO", "la pinza no se abrió al depositar: el cubo sigue sujeto")
    estado["sujeto"] = False

    on_etapa("RETIRADA")
    fin = mover(alta_d, "RETIRADA")
    if fin:
        return ResultadoPP(False, fin.codigo, "RETIRADA", "el cubo quedó depositado, pero falló la retirada")
    return _ok("RETIRADA")

def percibir_con_camara(color):
    """Percepción con la cámara real; importa OpenCV solo cuando se usa."""
    if __package__:
        from .vision_colores import abrir_camara, cerrar_camara, buscar_color_objetivo
    else:
        from vision_colores import abrir_camara, cerrar_camara, buscar_color_objetivo
    cap = abrir_camara()
    if cap is None:
        raise RuntimeError("no se pudo abrir la cámara")
    try:
        deteccion = buscar_color_objetivo(cap, color)
    finally:
        cerrar_camara(cap)
    return {"presente": deteccion is not None, "deteccion": deteccion}

def ejecutar_pick_and_place(mc, mover_a_pose, color_objetivo, destino, usar_pose_escaneo=True,
                            config=None, percibir=percibir_con_camara):
    """Versión que devuelve True o False; ejecutar_secuencia da el motivo completo."""
    if not isinstance(color_objetivo, str) or not isinstance(destino, str):
        return False
    resultado = ejecutar_secuencia(
        color_objetivo, destino, config=config or cargar_configuracion(), percibir=percibir,
        mover_a_pose=mover_a_pose, pinza=PinzaMyCobot(mc), usar_pose_escaneo=usar_pose_escaneo)
    if resultado.success:
        print(f"¡[PICK] lo he completado, el {color_objetivo} llego a {destino}!")
    else:
        print(f"¡[PICK] {resultado.codigo} en {resultado.etapa}: {resultado.motivo}")
    return resultado.success
