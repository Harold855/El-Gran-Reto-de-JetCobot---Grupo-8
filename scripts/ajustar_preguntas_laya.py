#!/usr/bin/env python3
"""Ajuste conservador de las preguntas LAYA del Grupo 8.

No cambia el formato HTTP, las funciones, el nodo ROS ni el servicio .srv.
Ejecutar con --check (solo verificar) y luego --apply (respaldar y aplicar).
"""
import argparse
import ast
import datetime
import pathlib
import shutil
import sys

RUTA = pathlib.Path('src/interprete_ordenes/interprete_ordenes/laya_cliente.py')

CAMBIOS = [
    (
        '"instructions": "Clasifica la accion. Solo trasladar significa recoger exactamente un cubo y colocarlo en una sola zona. Lanzar, caminar, apilar, modificar parametros, negar, repetir o combinar acciones no es trasladar valido.",',
        '"instructions": "Clasifica SOLO la accion principal solicitada, no evalúes si la orden completa es válida. Trasladar incluye recoger, tomar, agarrar, coger, mover, llevar, transportar, depositar o colocar un cubo en una zona. Recoge el cubo rojo y colócalo en la zona verde = trasladar. Traslada el cubo azul a la zona roja = trasladar. Lanza o golpea el cubo = otra. Caminar, girar o apilar = otra.",',
    ),
    (
        '"trasladar": "Un unico pick-and-place afirmativo completo",',
        '"trasladar": "La accion es recoger/colocar o mover/trasladar un cubo a una zona; sin evaluar aqui negaciones, colores ni urgencia",',
    ),
    (
        '"otra": "Otra accion, accion extra, cambio de parametros, negacion u orden compuesta",',
        '"otra": "Accion fisica diferente del traslado: lanzar, golpear, caminar, girar, apilar, destruir, etc.",',
    ),
    (
        '"ninguna": "No se reconoce una accion completa",',
        '"ninguna": "No se identifica ningun verbo o accion reconocible en la frase",',
    ),
    (
        '"instructions": "Asigna prioridad a la solicitud, segun el contenido: 1 normal, 2 alta, 3 urgente; no inventes urgencia. Para orden invalida indica ninguna.",',
        '"instructions": "Evalúa SOLO la urgencia expresada, independiente de que la orden sea válida o no. Si no dice urgente ni prioridad alta, elige SIEMPRE 1 (normal). Elige 2 solo si solicita explícitamente prioridad alta. Elige 3 solo si solicita explícitamente prioridad urgente o inmediata. Usa ninguna solo para texto vacío o ininteligible; no rechaces aquí órdenes por acciones o colores.",',
    ),
    (
        '"1": "Prioridad normal, sin urgencia explicita",',
        '"1": "Por defecto para toda frase comprensible sin urgencia ni prioridad alta explícita, incluso si la acción es inválida",',
    ),
    (
        '"2": "Se justifica prioridad alta",',
        '"2": "Solo si la solicitud indica expresamente prioridad alta",',
    ),
    (
        '"3": "Urgencia explicita y justificada",',
        '"3": "Solo si la solicitud contiene urgencia explícita: urgente, inmediatamente o emergencia",',
    ),
    (
        '"ninguna": "Orden invalida o no evaluable",',
        '"ninguna": "No hay texto o el texto no es interpretable; NO significa que otra pregunta haya marcado la orden como inválida",',
    ),
    (
        '"instructions": "¿Se permite exactamente UNA orden afirmativa, completa e inequivoca de recoger UN cubo rojo, verde, azul o amarillo y colocarlo en UNA zona de esos cuatro colores? Rechaza negaciones, cualquier otro objeto/color/tonalidad, instrucciones incompletas, acciones extra, cambios de fuerza o velocidad, plurales, apilamiento, multiples zonas o cubos.",',
        '"instructions": "Responde SI solo si toda la frase solicita UNA operación de recoger/mover un cubo rojo, verde, azul o amarillo y depositarlo en UNA zona roja, verde, azul o amarilla. Ejemplo SI: Recoge el cubo rojo y colócalo en la zona verde. Ejemplo SI: Traslada el cubo azul a la zona roja. Responde NO para lanzar, golpear, caminar, apilar, negaciones, otro objeto, colores fuera de los cuatro o con tonalidades, destino faltante, varios cubos/zonas y cambios de velocidad/fuerza. Ejemplo NO: Lanza el cubo rojo hacia la zona azul. Ejemplo NO: Recoge el cubo amarillo (no indica zona).",',
    ),
    (
        '"si": "Cumple todos los requisitos del pick-and-place definido",',
        '"si": "Frase completa de un único cubo admitido hacia una única zona admitida, con acción de recogida y colocación",',
    ),
    (
        '"no": "Incumple al menos uno de los requisitos",',
        '"no": "Cualquier prohibición, acción distinta de trasladar, objeto o color no admitido, falta de información o varias operaciones",',
    ),
]


def ejecutar():
    parser = argparse.ArgumentParser(description='Ajustar SOLO los criterios LAYA de P1 conservando el código existente.')
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true', help='Verificar compatibilidad sin cambiar nada')
    g.add_argument('--apply', action='store_true', help='Crear respaldo fuera del repositorio y aplicar')
    a = parser.parse_args()
    if not RUTA.is_file():
        raise SystemExit(f'ERROR: ruta no encontrada: {RUTA}. Ejecuta desde ~/gran_reto_g8.')
    actual = RUTA.read_text(encoding='utf-8')
    nuevo = actual
    for viejo, reemplazo in CAMBIOS:
        if nuevo.count(viejo) != 1:
            raise SystemExit('ERROR: no coincide la versión actual. Ningún archivo fue modificado. Fragmento:\n' + viejo[:150])
        nuevo = nuevo.replace(viejo, reemplazo)
    # Validar sintaxis ANTES de guardar y no alterar preguntas ni firmas.
    ast.parse(nuevo, filename=str(RUTA))
    if a.check:
        print(f'OK: {len(CAMBIOS)} ajustes preparados; el archivo actual es compatible. Sin cambios.')
        return
    respaldo_dir = pathlib.Path.home() / 'respaldo_p1'
    respaldo_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    respaldo = respaldo_dir / ('laya_cliente_antes_ajuste_' + timestamp + '.py')
    if respaldo.exists():
        raise SystemExit('ERROR: ya existe el archivo de respaldo. Reintenta.')
    shutil.copy2(RUTA, respaldo)
    RUTA.write_text(nuevo, encoding='utf-8')
    print('OK: solo se ajustaron las instrucciones y criterios de accion, prioridad y permitido.')
    print('Respaldo original:', respaldo)
    print('Archivo actualizado:', RUTA)
    print('Revisa: git diff -- src/interprete_ordenes/interprete_ordenes/laya_cliente.py')

if __name__ == '__main__':
    ejecutar()
