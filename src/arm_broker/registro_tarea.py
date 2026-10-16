"""Registro de eventos y tiempos por id_solicitud, exportado a CSV.

Las duraciones salen del reloj monótono; t_sistema_unix permite comparar con otras máquinas solo
si sus relojes están sincronizados (no se restan marcas de máquinas distintas sin avisar).
Los registros de un ejecutor simulado llevan simulado=True: no son latencias físicas.

Un rechazo se anota aparte (registro='rechazo') y nunca toca los eventos de una tarea con el mismo
id_solicitud que siga activa (registro='tarea').
"""

import csv
import os
import threading
import time

COLUMNAS = ["id_solicitud", "registro", "evento", "t_monotonic_s", "t_sistema_unix", "simulado", "detalle"]
MAX_CERRADAS = 500


class RegistroTareas:
    def __init__(self, ruta_csv="", simulado=False, reloj=time.monotonic, reloj_sistema=time.time):
        self.ruta_csv = ruta_csv
        self.simulado = bool(simulado)
        self._reloj = reloj
        self._reloj_sistema = reloj_sistema
        self._lock = threading.Lock()
        self._abiertas = {}
        self._cerradas = {}
        self._rechazos = []

    def marca(self):
        """Instante actual (monótono, sistema): se toma al recibir y se usa si luego se admite."""
        return self._reloj(), self._reloj_sistema()

    def _fila(self, id_solicitud, registro, nombre, detalle, marca=None):
        mono, sistema = marca or self.marca()
        return {"id_solicitud": id_solicitud, "registro": registro, "evento": nombre,
                "t_monotonic_s": f"{mono:.6f}", "t_sistema_unix": f"{sistema:.6f}",
                "simulado": self.simulado, "detalle": detalle}

    def evento(self, id_solicitud, nombre, detalle="", marca=None):
        fila = self._fila(id_solicitud, "tarea", nombre, detalle, marca)
        with self._lock:
            self._abiertas.setdefault(id_solicitud, []).append(fila)

    def rechazar(self, id_solicitud, codigo, motivo, detalle_solicitud="", marca=None):
        """Anota una solicitud rechazada sin tocar ninguna tarea abierta o cerrada con ese id."""
        filas = [
            self._fila(id_solicitud, "rechazo", "solicitud_recibida", detalle_solicitud, marca),
            self._fila(id_solicitud, "rechazo", "admitida_o_rechazada", f"rechazada: {codigo}"),
            self._fila(id_solicitud, "rechazo", "fin_tarea", f"{codigo} | success=False | {motivo}"),
        ]
        with self._lock:
            self._rechazos.append(filas)
            del self._rechazos[:-MAX_CERRADAS]
        self._escribir(filas)

    def rechazos(self):
        with self._lock:
            return [list(filas) for filas in self._rechazos]

    def cerrar(self, id_solicitud, codigo, success, mensaje=""):
        """Añade fin_tarea y escribe todos los eventos de la tarea en el CSV."""
        self.evento(id_solicitud, "fin_tarea", f"{codigo} | success={success} | {mensaje}")
        with self._lock:
            filas = self._abiertas.pop(id_solicitud, [])
            self._cerradas[id_solicitud] = filas
            while len(self._cerradas) > MAX_CERRADAS:
                self._cerradas.pop(next(iter(self._cerradas)))
        self._escribir(filas)

    def eventos(self, id_solicitud):
        with self._lock:
            return list(self._abiertas.get(id_solicitud) or self._cerradas.get(id_solicitud) or [])

    def nombres(self, id_solicitud):
        return [fila["evento"] for fila in self.eventos(id_solicitud)]

    def duracion_s(self, id_solicitud, desde, hasta):
        """Segundos (reloj monótono) entre dos eventos de la misma tarea, o None si falta alguno."""
        marcas = {fila["evento"]: float(fila["t_monotonic_s"]) for fila in self.eventos(id_solicitud)}
        if desde in marcas and hasta in marcas:
            return marcas[hasta] - marcas[desde]
        return None

    def _escribir(self, filas):
        if not self.ruta_csv or not filas:
            return
        try:
            carpeta = os.path.dirname(self.ruta_csv)
            if carpeta:
                os.makedirs(carpeta, exist_ok=True)
            with self._lock:   # una sola escritura a la vez
                nuevo = not os.path.exists(self.ruta_csv)
                with open(self.ruta_csv, "a", newline="", encoding="utf-8") as archivo:
                    escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
                    if nuevo:
                        escritor.writeheader()
                    escritor.writerows(filas)
        except OSError:
            pass   # el registro nunca debe tumbar al broker
