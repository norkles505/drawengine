"""
Stroke Stabilizer — suavizado de trazos en tiempo real.

Algoritmo: Moving Average ponderado.
El punto de dibujo "persigue" al cursor con inercia.
Nivel 0 = sin stabilizer (directo)
Nivel 1-10 = suavizado creciente
"""

from collections import deque
from PyQt6.QtCore import QPoint
import math


class Stabilizer:
    def __init__(self, level: int = 0):
        self._level   = 0
        self._buffer: deque = deque()
        self._last_committed: QPoint | None = None
        self.set_level(level)

    def set_level(self, level: int):
        """0 = off, 1-10 = suavizado."""
        self._level = max(0, min(10, level))
        # Tamaño del buffer: más nivel = más puntos promediar
        size = max(1, self._level * 3)
        self._buffer = deque(maxlen=size)

    @property
    def level(self) -> int:
        return self._level

    @property
    def active(self) -> bool:
        return self._level > 0

    def reset(self):
        """Llamar al inicio de cada trazo."""
        self._buffer.clear()
        self._last_committed = None

    def add_point(self, p: QPoint) -> QPoint | None:
        """
        Recibe el punto del cursor y devuelve el punto suavizado
        que se debe dibujar. Devuelve None si aún no hay suficientes
        puntos para estabilizar.
        """
        if not self.active:
            return p

        self._buffer.append(p)

        if len(self._buffer) < 2:
            return None   # esperar más puntos

        # Weighted average: puntos más recientes pesan más
        total_w = 0.0
        sum_x   = 0.0
        sum_y   = 0.0
        n       = len(self._buffer)

        for i, pt in enumerate(self._buffer):
            w      = (i + 1) ** 1.5   # peso creciente
            sum_x += pt.x() * w
            sum_y += pt.y() * w
            total_w += w

        smoothed = QPoint(int(sum_x / total_w), int(sum_y / total_w))

        # Solo dibujar si el punto suavizado se movió lo suficiente
        if self._last_committed is not None:
            dx = smoothed.x() - self._last_committed.x()
            dy = smoothed.y() - self._last_committed.y()
            if math.sqrt(dx*dx + dy*dy) < 0.5:
                return None   # sin movimiento significativo

        self._last_committed = smoothed
        return smoothed

    def flush(self, last_target: QPoint) -> list[QPoint]:
        """
        Al soltar el mouse, devuelve los puntos finales para
        cerrar el trazo suavizado hasta el cursor real.
        """
        if not self.active or self._last_committed is None:
            return []

        points = []
        lc     = self._last_committed
        steps  = max(1, self._level * 2)

        for i in range(1, steps + 1):
            t  = i / steps
            px = int(lc.x() + (last_target.x() - lc.x()) * t)
            py = int(lc.y() + (last_target.y() - lc.y()) * t)
            points.append(QPoint(px, py))

        return points