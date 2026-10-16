"""Rutas del repositorio para los scripts de la pregunta 2.

Los scripts de scripts/p2/ añaden `src` a sys.path e importan esto, de modo que no dependen
del directorio desde el que se ejecutan.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

CONFIG = Path(__file__).resolve().parent / "config"
ZONAS_TRABAJO = CONFIG / "zonas_trabajo.json"
ROBOT_YAML = CONFIG / "robot.yaml"
URDF = Path(__file__).resolve().parent / "modelos" / "jetcobot.urdf"

EVIDENCIAS_P2 = RAIZ / "evidencias" / "pregunta_2"
CALIBRACION = EVIDENCIAS_P2 / "calibracion"
CAMARA = EVIDENCIAS_P2 / "camara"
MAPAS = EVIDENCIAS_P2 / "mapas"
MEDICIONES = EVIDENCIAS_P2 / "mediciones"
