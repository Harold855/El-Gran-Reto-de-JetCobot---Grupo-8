import os
os.environ["OPENCV_VIDEOIO_PRIORITY_GSTREAMER"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

import time
import cv2 as cv
import numpy as np

# -----------------------------Configuración---------------------------------------
RES_CAMARA = (640, 480)
CAMARA_INDICE = 0

RANGOS_COLOR = {
    "rojo":     {"bandas_h": [(0, 10), (170, 179)], "s_min": 80, "v_min": 60},
    "verde":    {"bandas_h": [(35, 85)],            "s_min": 60, "v_min": 60},
    "azul":     {"bandas_h": [(95, 130)],           "s_min": 70, "v_min": 60},
    "amarillo": {"bandas_h": [(20, 34)],            "s_min": 80, "v_min": 80},
}

COLORES_DIBUJO = {  # BGR
    "rojo": (0, 0, 255), "verde": (0, 255, 0), "azul": (255, 0, 0), "amarillo": (0, 255, 255),
}

AREAS_POR_COLOR = {
    "rojo":     {"min": 13000, "max": 30000},
    "verde":    {"min": 13000, "max": 30000},
    "azul":     {"min": 13000, "max": 30000},
    "amarillo": {"min": 13000, "max": 30000},
}
ASPECTO_MIN = 0.75
ASPECTO_MAX = 1.35
KERNEL_VISION = np.ones((5, 5), np.uint8)

TIEMPO_CONFIRMACION_COLOR = 1.0
TIMEOUT_ESCANEO = 20

# ---------------------------------Vision-----------------------------------------
def mascara_color(hsv, nombre): #
    r = RANGOS_COLOR[nombre]
    total = None
    for h_min, h_max in r["bandas_h"]:
        bajo = (h_min, r["s_min"], r["v_min"])
        alto = (h_max, 255, 255)
        mascara = cv.inRange(hsv, bajo, alto)
        total = (mascara
            if total is None
            else cv.bitwise_or(total, mascara)
        )

    return total

def detectar_cubos(frame):
    """Cubo más grande de cada color: lista de diccionarios ordenada por área (de mayor a menor).

    Cada diccionario trae color, area, centro_x, centro_y y rectangulo (x, y, ancho, alto).
    """
    hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
    encontrados = []
    for nombre in RANGOS_COLOR:
        mascara = mascara_color(hsv, nombre)
        mascara = cv.morphologyEx(mascara, cv.MORPH_OPEN, KERNEL_VISION)
        mascara = cv.morphologyEx(mascara, cv.MORPH_CLOSE, KERNEL_VISION)
        contornos, _ = cv.findContours(mascara, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        if not contornos:
            continue
        contour = max(contornos, key=cv.contourArea)
        area = cv.contourArea(contour)
        limites = AREAS_POR_COLOR[nombre]
        if area < limites["min"] or area > limites["max"]:
            continue
        x, y, w, h = cv.boundingRect(contour)
        if h == 0:
            continue
        aspecto = w / h
        if aspecto < ASPECTO_MIN or aspecto > ASPECTO_MAX:
            continue
        momentos = cv.moments(contour)
        if momentos["m00"] == 0:
            continue
        encontrados.append({
            "color": nombre,
            "area": area,
            "centro_x": int(momentos["m10"] / momentos["m00"]),
            "centro_y": int(momentos["m01"] / momentos["m00"]),
            "rectangulo": (x, y, w, h),
        })
    encontrados.sort(key=lambda d: d["area"], reverse=True)
    return encontrados

def detectar_colores(frame):
    """Lo mismo que detectar_cubos, como tuplas (color, area, cx, cy)."""
    return [(d["color"], d["area"], d["centro_x"], d["centro_y"]) for d in detectar_cubos(frame)]

def buscar_color_en_frame(frame, color):
    """Busca el cubo de un color en una imagen ya capturada (sin cámara).

    Devuelve color, presente, estado (DETECTADO, AUSENTE, COLOR_INVALIDO o SIN_IMAGEN), centro_px,
    rectangulo, area y timestamp. centro_px son píxeles: no hay calibración métrica ni XYZ.
    """
    color = color.strip().lower() if isinstance(color, str) else color
    respuesta = {"color": color, "presente": False, "estado": "AUSENTE", "centro_px": None,
                 "rectangulo": None, "area": 0.0, "timestamp": time.time()}
    if color not in RANGOS_COLOR:
        respuesta["estado"] = "COLOR_INVALIDO"
        return respuesta
    if frame is None or getattr(frame, "size", 0) == 0:
        respuesta["estado"] = "SIN_IMAGEN"
        return respuesta
    for d in detectar_cubos(frame):
        if d["color"] == color:
            respuesta.update(presente=True, estado="DETECTADO", area=d["area"],
                             centro_px=(d["centro_x"], d["centro_y"]), rectangulo=d["rectangulo"])
            break
    return respuesta

def dibujar_detecciones(frame, detecciones):
    """Copia de frame con el rectángulo, el centro y la etiqueta de cada cubo de detectar_cubos."""
    salida = frame.copy()
    alto, ancho = salida.shape[:2]
    cv.circle(salida, (ancho // 2, alto // 2), 6, (255, 255, 255), 2)
    for d in detecciones:
        x, y, w, h = d["rectangulo"]
        tono = COLORES_DIBUJO[d["color"]]
        cv.rectangle(salida, (x, y), (x + w, y + h), tono, 2)
        cv.circle(salida, (d["centro_x"], d["centro_y"]), 5, (255, 255, 255), -1)
        cv.putText(salida, f'{d["color"]} ({d["centro_x"]}, {d["centro_y"]})',
                   (x, max(20, y - 10)), cv.FONT_HERSHEY_SIMPLEX, 0.6, tono, 2)
    return salida

# -------------------------Cámara--------------------------------
def abrir_camara(): #
    cap = cv.VideoCapture(CAMARA_INDICE, cv.CAP_V4L2)
    if not cap.isOpened():
        cap = cv.VideoCapture(CAMARA_INDICE)
    if not cap.isOpened():
        print("¡[VISION] no fue posible abrir mi cámara!")
        return None
    cap.set(cv.CAP_PROP_FRAME_WIDTH, RES_CAMARA[0])
    cap.set(cv.CAP_PROP_FRAME_HEIGHT, RES_CAMARA[1])
    ok, _ = cap.read()
    if not ok:
        cap.release()
        print("¡[VISION] mi camara no llego a responder!")
        return None
    print(
        f"[VISION] abri camara abierta en "
        f"{int(cap.get(cv.CAP_PROP_FRAME_WIDTH))}x"
        f"{int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))}"
    )

    return cap

def cerrar_camara(cap):
    if cap is not None:
        cap.release()
      
# --------------------Percepcion-----------------------------------
def buscar_color_objetivo(cap, color_objetivo):
    if cap is None:
        print("¡[VISION] cámara no disponible!")
        return None
    color_objetivo = color_objetivo.strip().lower()
    if color_objetivo not in RANGOS_COLOR:
        print(f"¡[VISION] el color {color_objetivo}, no existe en mi registro!")
        return None
    desde = None
    inicio = time.time()
    while time.time() - inicio < TIMEOUT_ESCANEO:
        ok, frame = cap.read()
        if not ok:
            continue
        detecciones = detectar_colores(frame)
        objetivo = None
        for nombre, area, cx, cy in detecciones:
            if nombre == color_objetivo:
                objetivo = (nombre, area, cx, cy)
                break
        if objetivo is not None:
            nombre, area, cx, cy = objetivo
            if desde is None:
                desde = time.time()
            elif time.time() - desde >= TIEMPO_CONFIRMACION_COLOR:
                return {
                    "color": nombre,
                    "area": area,
                    "cx": cx,
                    "cy": cy
                }
        else:
            desde = None
    print(f"¡[VISION] no pude encontrar el color: {color_objetivo}!")
    return None

# ---------------------------Prueba--------------------------------------
if __name__ == "__main__":
    cap = abrir_camara()
    if cap is not None:
        resultado = buscar_color_objetivo(cap, "verde")
        print("Resultado:", resultado)
    cerrar_camara(cap)







