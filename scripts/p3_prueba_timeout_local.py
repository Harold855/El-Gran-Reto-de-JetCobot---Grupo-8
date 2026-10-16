"""Prueba CONTROLADA del límite local de espera, sin llamar Google.

Ejecutar desde raíz de repo, con ROS 2 cargado:
  python3 scripts/p3_prueba_timeout_local.py
Esta prueba no escribe el CSV de evidencias, no requiere clave ni P1.
"""

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "transcriptor_voz"))
from transcriptor_voz import ejecutar_con_limite


def prueba_lenta():
    time.sleep(3)
    return "No debería recibirse"


inicio = time.monotonic()
limite = 1.0
try:
    ejecutar_con_limite(prueba_lenta, limite)
    raise AssertionError("ERROR: no se produjo el timeout")
except TimeoutError as error:
    medido = time.monotonic() - inicio
    print(f"[PRUEBA] Timeout esperado: {limite:.2f} s")
    print(f"[PRUEBA] Espera real: {medido:.3f} s")
    print(f"[PRUEBA] Resultado: {error}")
    assert 0.8 <= medido <= 2.0, "El límite no se respetó con una tolerancia razonable"
    print("[PRUEBA] OK: el hilo principal no esperó los 3 segundos")
