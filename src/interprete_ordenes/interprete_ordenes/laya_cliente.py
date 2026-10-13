"""
Cliente HTTP de LAYA . 
Dos interfaces sobre la misma peticion:
- consultar_laya(frase, url, timeout) -> (json_crudo, tiempo_http_ms)
- consultar_laya_tipado(...) -> DecisionLaya
  Valida seis decisiones para /interpretar_orden sin controlar el robot.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import sys
import time
from typing import Any
from urllib import error, request
from urllib.parse import urlsplit

COLORES = frozenset({"rojo", "verde", "azul", "amarillo"})

# Criterios fijos de evaluacion P1, NO entrenan LAYA.
PREGUNTAS = {
    "accion": {
        "type": "choice",
        "instructions": "Clasifica la accion. Solo trasladar significa recoger exactamente un cubo y colocarlo en una sola zona. Lanzar, caminar, apilar, modificar parametros, negar, repetir o combinar acciones no es trasladar valido.",
        "criteria": {
            "trasladar": "Un unico pick-and-place afirmativo completo",
            "otra": "Otra accion, accion extra, cambio de parametros, negacion u orden compuesta",
            "ninguna": "No se reconoce una accion completa",
        },
    },
    "objeto": {
        "type": "choice",
        "instructions": "Identifica el objeto pedido. Cubo, cubito y bloque designan un cubo en esta practica. Prohibidos esferas, piramides, lapices, marcadores y varios objetos.",
        "criteria": {
            "cubo": "Exactamente un cubo, cubito o bloque",
            "otro": "Objeto que no es un cubo, o multiples objetos",
            "ninguno": "Objeto ausente o ambiguo",
        },
    },
    "color": {
        "type": "choice",
        "instructions": "Color exacto del CUBO, no el de la zona. Solo rojo, verde, azul o amarillo simples. Morado, blanco, verde lima, rojo fuerte, azul marino y cualquier variante son invalidos.",
        "criteria": {
            "rojo": "El cubo es rojo exacto", "verde": "El cubo es verde exacto",
            "azul": "El cubo es azul exacto", "amarillo": "El cubo es amarillo exacto",
            "ninguno": "Color ausente, desconocido, compuesto o ambiguo",
        },
    },
    "destino": {
        "type": "choice",
        "instructions": "Color exacto de la UNICA zona de deposito; no confundir con color del cubo. Aceptar area, sector o seccion como zona. No admitir dos zonas o colores modificados.",
        "criteria": {
            "rojo": "Zona roja", "verde": "Zona verde", "azul": "Zona azul",
            "amarillo": "Zona amarilla", "ninguno": "Sin destino valido o univoco",
        },
    },
    "prioridad": {
        "type": "choice",
        "instructions": "Asigna prioridad a la solicitud, segun el contenido: 1 normal, 2 alta, 3 urgente; no inventes urgencia. Para orden invalida indica ninguna.",
        "criteria": {
            "1": "Prioridad normal, sin urgencia explicita",
            "2": "Se justifica prioridad alta",
            "3": "Urgencia explicita y justificada",
            "ninguna": "Orden invalida o no evaluable",
        },
    },
    "permitido": {
        "type": "choice",
        "instructions": "¿Se permite exactamente UNA orden afirmativa, completa e inequivoca de recoger UN cubo rojo, verde, azul o amarillo y colocarlo en UNA zona de esos cuatro colores? Rechaza negaciones, cualquier otro objeto/color/tonalidad, instrucciones incompletas, acciones extra, cambios de fuerza o velocidad, plurales, apilamiento, multiples zonas o cubos.",
        "criteria": {
            "si": "Cumple todos los requisitos del pick-and-place definido",
            "no": "Incumple al menos uno de los requisitos",
        },
    },
}

class ErrorLaya(RuntimeError):
    """Conexion, HTTP, formato o respuesta no fiable, el nodo activa respaldo"""

@dataclass(frozen=True)
class DecisionLaya:
    accion: str
    objeto: str
    color: str
    destino: str
    prioridad: int
    permitido: bool  # validacion interna de consistencia de campos del propio LAYA
    permitido_modelo: bool  # resultado bruto de answers.permitido.choice
    motivo: str
    tiempo_http_ms: float
    tiempo_servidor_ms: float | None  # SOLO cabecera informada por LAYA
    modelo_usado: str | None
    respuestas_crudas: dict[str, Any]  # necesario para exactitud pura de P1

@dataclass(frozen=True)
class _RespuestaHTTP:
    cuerpo: dict[str, Any]
    tiempo_http_ms: float
    tiempo_servidor_ms: float | None

def _url_endpoint(url: str | None) -> str:
    base = (url or os.getenv("LAYA_URL") or "http://172.51.1.13:8000").strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise ErrorLaya("URL de LAYA invalida (debe ser http(s)://host:puerto)")
    if parsed.query or parsed.fragment:
        raise ErrorLaya("LAYA_URL no admite query ni fragmento")
    if base.endswith("/v1/systemone"):
        return base
    return base + "/v1/systemone"

def _ms_servidor(headers: Any) -> float | None:
    valor = headers.get("X-Inference-Time-Ms")
    if valor is None:
        mat = re.search(r"(?:^|,)\s*inference\s*;\s*dur\s*=\s*([\d.]+)", headers.get("Server-Timing", ""), re.I)
        valor = mat.group(1) if mat else None
    try:
        resultado = float(valor)
    except (ValueError, TypeError):
        return None
    return resultado if 0 < resultado < 1e8 else None

def _pedir(frase: str, url: str | None, timeout: float, modelo: str | None) -> _RespuestaHTTP:
    if not isinstance(frase, str) or not frase.strip():
        raise ErrorLaya("Frase vacia")
    if not 0 < timeout <= 120:
        raise ValueError("timeout debe estar entre 0 y 120 segundos")

    cuerpo = {"state": frase, "lang": "es", "questions": PREGUNTAS}
    elegido = modelo if modelo is not None else os.getenv("LAYA_MODEL", "").strip()
    if elegido:  # no fijar modelo a espaldas del preset del docente
        cuerpo["model"] = elegido
    credencial = os.getenv("LAYA_API_KEY", "").strip()
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if credencial:
        headers["Authorization"] = "Bearer " + credencial
    peticion = request.Request(
        _url_endpoint(url),
        data=json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    inicio = time.perf_counter()
    try:
        with request.urlopen(peticion, timeout=timeout) as respuesta:
            bytes_recibidos = respuesta.read(1024 * 1024 + 1)
            ms_inferencia = _ms_servidor(respuesta.headers)
    except (error.HTTPError, error.URLError, OSError, TimeoutError) as exc:
        raise ErrorLaya(f"Consulta HTTP LAYA fallida: {exc}") from exc
    tiempo_http = (time.perf_counter() - inicio) * 1000
    if len(bytes_recibidos) > 1024 * 1024:
        raise ErrorLaya("Respuesta demasiado extensa")
    try:
        datos = json.loads(bytes_recibidos.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErrorLaya("LAYA no devolvio JSON valido") from exc
    if not isinstance(datos, dict) or not isinstance(datos.get("answers"), dict):
        raise ErrorLaya("Respuesta LAYA sin campo answers")
    return _RespuestaHTTP(datos, tiempo_http, ms_inferencia)


def consultar_laya(frase: str, url: str | None = None, timeout: float = 4.0, *, modelo: str | None = None) -> tuple[dict[str, Any], float]:
    """API del integrante P1: devuelve (JSON de LAYA, HTTP_ms).

    Los campos de inferencia estan en CABECERAS, por tanto no se incluyen en el
    diccionario JSON de esta interfaz simple. Usar consultar_laya_tipado para eso.
    """
    resultado = _pedir(frase, url, timeout, modelo)
    return resultado.cuerpo, resultado.tiempo_http_ms

def _choice(answers: dict[str, Any], campo: str, validos: set[str]) -> str:
    entrada = answers.get(campo)
    if not isinstance(entrada, dict) or entrada.get("type") != "choice":
        raise ErrorLaya(f"Falta decision choice para {campo}")
    valor = entrada.get("choice")
    if not isinstance(valor, str) or valor not in validos:
        raise ErrorLaya(f"Opcion invalida para {campo}: {valor!r}")
    if entrada.get("low_confidence") is True or entrada.get("abstention") == "abstained":
        raise ErrorLaya(f"LAYA se abstuvo en {campo}")
    return valor

def consultar_laya_tipado(frase: str, url: str | None = None, timeout: float = 4.0, *, modelo: str | None = None) -> DecisionLaya:
    """Convierte seis respuestas choice de LAYA a valores seguros para el srv.
    Para evaluar exactitud del modelo, guardar respuestas_crudas aparte;
    `permitido` aqui implica consistencia, NO es una orden de mover el brazo.
    """
    resp = _pedir(frase, url, timeout, modelo)
    uso = resp.cuerpo.get("usage")
    if isinstance(uso, dict) and (uso.get("truncated") is True or uso.get("state_tokens_dropped", 0) or uso.get("truncated_questions")):
        raise ErrorLaya("LAYA proceso entrada truncada")
    respuestas = resp.cuerpo["answers"]
    accion = _choice(respuestas, "accion", {"trasladar", "otra", "ninguna"})
    objeto = _choice(respuestas, "objeto", {"cubo", "otro", "ninguno"})
    color = _choice(respuestas, "color", set(COLORES) | {"ninguno"})
    destino = _choice(respuestas, "destino", set(COLORES) | {"ninguno"})
    prioridad = _choice(respuestas, "prioridad", {"1", "2", "3", "ninguna"})
    permitir = _choice(respuestas, "permitido", {"si", "no"})
    completo = (accion == "trasladar" and objeto == "cubo" and color in COLORES
                and destino in COLORES and prioridad in {"1", "2", "3"})
    seguro = permitir == "si" and completo
    router = resp.cuerpo.get("routing")
    nombre_modelo = router.get("model") if isinstance(router, dict) else None
    return DecisionLaya(
        accion="trasladar" if seguro else "",
        objeto="cubo",
        color=color if seguro else "",
        destino=destino if seguro else "",
        prioridad=int(prioridad) if seguro else 0,
        permitido=seguro,
        permitido_modelo=(permitir == "si"),
        motivo="LAYA: orden validada" if seguro else "LAYA: denegada o decisiones incompatibles",
        tiempo_http_ms=resp.tiempo_http_ms,
        tiempo_servidor_ms=resp.tiempo_servidor_ms,
        modelo_usado=nombre_modelo,
        respuestas_crudas=respuestas,
    )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: laya_cliente.py "Recoge el cubo rojo y colócalo en la zona verde"')
        raise SystemExit(2)
    from dataclasses import asdict
    try:
        decision = consultar_laya_tipado(" ".join(sys.argv[1:]))
        print(json.dumps(asdict(decision), ensure_ascii=False, indent=2))
    except (ErrorLaya, ValueError) as exc:
        print(f"Error LAYA: {exc}", file=sys.stderr)
        raise SystemExit(1)

