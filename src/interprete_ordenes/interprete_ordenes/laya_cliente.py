"""
              Cliente HTTP de LAYA 
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
        "instructions": "Clasifica SOLO la accion principal solicitada, no evalúes si la orden completa es válida. Trasladar incluye recoger, tomar, agarrar, coger, mover, llevar, transportar, depositar o colocar un cubo en una zona. Recoge el cubo rojo y colócalo en la zona verde = trasladar. Traslada el cubo azul a la zona roja = trasladar. Lanza o golpea el cubo = otra. Caminar, girar o apilar = otra.",
        "criteria": {
            "trasladar": "La accion es recoger/colocar o mover/trasladar un cubo a una zona; sin evaluar aqui negaciones, colores ni urgencia",
            "otra": "Accion fisica diferente del traslado: lanzar, golpear, caminar, girar, apilar, destruir, etc.",
            "ninguna": "No se identifica ningun verbo o accion reconocible en la frase",
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
        "instructions": "Identifica EXCLUSIVAMENTE el color del objeto que se recoge (cubo, cubito o bloque). NO uses el color del destino. Ejemplos: 'cubo rojo a zona azul' = rojo; 'cubo verde a zona amarilla' = verde; 'cubo azul a zona roja' = azul; 'cubo amarillo a zona verde' = amarillo. Si falta color del objeto, responde ninguno. Solo acepta rojo, verde, azul o amarillo simples. Rechaza tonalidades y colores diferentes.",
        "criteria": {
            "rojo": "El cubo es rojo exacto", "verde": "El cubo es verde exacto",
            "azul": "El cubo es azul exacto", "amarillo": "El cubo es amarillo exacto",
            "ninguno": "Color ausente, desconocido, compuesto o ambiguo",
        },
    },
    "destino": {
        "type": "choice",
        "instructions": "Identifica EXCLUSIVAMENTE el color de la zona A LA QUE se debe llevar o depositar el cubo. NO copies el color del cubo. Ejemplos: 'cubo rojo a zona azul' = azul; 'cubo verde a zona amarilla' = amarillo; 'cubo azul a zona roja' = rojo; 'cubo amarillo a zona verde' = verde. Acepta zona, area, sector o seccion. Si no hay un destino unico y explicito, responde ninguno. No aceptes varias zonas ni tonalidades.",
        "criteria": {
            "rojo": "Zona roja", "verde": "Zona verde", "azul": "Zona azul",
            "amarillo": "Zona amarilla", "ninguno": "Sin destino valido o univoco",
        },
    },
                         
    "prioridad": {
    "type": "choice",
    "instructions": (
        "Clasifica solamente la urgencia de la solicitud. "
        "Elige 1 para una orden normal sin urgencia explícita. "
        "Elige 2 cuando se solicite prioridad alta. "
        "Elige 3 cuando se indique expresamente urgencia. "
        "No determines si la orden está permitida."
    ),
    "criteria": {
        "1": "Prioridad normal, sin urgencia explícita",
        "2": "Prioridad alta explícita",
        "3": "Urgencia explícita"
    }
},

    "permitido": {
        "type": "choice",
        "instructions": "Responde SI solo si toda la frase solicita UNA operación de recoger/mover un cubo rojo, verde, azul o amarillo y depositarlo en UNA zona roja, verde, azul o amarilla. Ejemplo SI: Recoge el cubo rojo y colócalo en la zona verde. Ejemplo SI: Traslada el cubo azul a la zona roja. Responde NO para lanzar, golpear, caminar, apilar, negaciones, otro objeto, colores fuera de los cuatro o con tonalidades, destino faltante, varios cubos/zonas y cambios de velocidad/fuerza. Ejemplo NO: Lanza el cubo rojo hacia la zona azul. Ejemplo NO: Recoge el cubo amarillo (no indica zona).",
        "criteria": {
            "si": "Frase completa de un único cubo admitido hacia una única zona admitida, con acción de recogida y colocación",
            "no": "Cualquier prohibición, acción distinta de trasladar, objeto o color no admitido, falta de información o varias operaciones",
        },
    },
}

class ErrorLaya(RuntimeError):
    """Conexion, HTTP, formato o respuesta no fiable; el nodo activa respaldo."""


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

def consultar_laya(frase: str, url: str | None = None, timeout: float = 4.0, *, modelo: str | None = None, modo: str = "oficial") -> tuple[dict[str, Any], float]:
    """Conserva la firma y el retorno del companero: (diccionario, HTTP_ms).

    modo="oficial": endpoint /v1/systemone y esquema state/questions (LAYA real).
    modo="mock": POST directo de {"frase": frase} (servidor SIMULADO anterior).
    El modo mock NO sirve para acreditar inferencia de LAYA en el examen.
    """
    if modo == "oficial":
        resultado = _pedir(frase, url, timeout, modelo)
        return resultado.cuerpo, resultado.tiempo_http_ms
    if modo != "mock":
        raise ValueError("modo debe ser 'oficial' o 'mock'")
    if not isinstance(frase, str) or not frase.strip():
        raise ErrorLaya("Frase vacia")
    if not 0 < timeout <= 120:
        raise ValueError("timeout debe estar entre 0 y 120 segundos")
    destino = (url or "http://127.0.0.1:8765").strip()
    parsed = urlsplit(destino)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise ErrorLaya("URL mock invalida")
    solicitud = request.Request(
        destino,
        data=json.dumps({"frase": frase}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    inicio = time.perf_counter()
    try:
        with request.urlopen(solicitud, timeout=timeout) as respuesta:
            crudo = respuesta.read(1024 * 1024 + 1)
    except (error.HTTPError, error.URLError, OSError, TimeoutError) as exc:
        raise ErrorLaya(f"Mock HTTP fallido: {exc}") from exc
    tiempo_ms = (time.perf_counter() - inicio) * 1000
    if len(crudo) > 1024 * 1024:
        raise ErrorLaya("Respuesta mock demasiado extensa")
    try:
        datos = json.loads(crudo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErrorLaya("Mock no devolvio JSON valido") from exc
    if not isinstance(datos, dict):
        raise ErrorLaya("Mock no devolvio objeto JSON")
    return datos, tiempo_ms


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
        print('Uso: python3 laya_cliente.py "Recoge el cubo rojo y colócalo en la zona verde"')
        raise SystemExit(2)
    from dataclasses import asdict
    try:
        decision = consultar_laya_tipado(" ".join(sys.argv[1:]))
        print(json.dumps(asdict(decision), ensure_ascii=False, indent=2))
    except (ErrorLaya, ValueError) as exc:
        print(f"Error LAYA: {exc}", file=sys.stderr)
        raise SystemExit(1)
