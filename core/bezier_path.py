"""
Modelo de datos para paths de Bézier cúbico.
Cada segmento: P0 --(CP1)--(CP2)-- P1
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class AnchorPoint:
    """Punto ancla con dos handles (control points)."""
    x: float
    y: float
    # Handle de salida (hacia el siguiente segmento)
    cx1: float = 0.0
    cy1: float = 0.0
    # Handle de entrada (desde el segmento anterior)
    cx2: float = 0.0
    cy2: float = 0.0
    # Modo de handles
    smooth: bool = True   # True = simétrico, False = independiente

    def set_handles_from_drag(self, drag_x: float, drag_y: float):
        """
        Al arrastrar al colocar el punto, define los handles
        simétricamente alrededor del ancla.
        """
        dx = drag_x - self.x
        dy = drag_y - self.y
        self.cx1 =  dx
        self.cy1 =  dy
        self.cx2 = -dx
        self.cy2 = -dy

    @property
    def handle_out(self) -> Tuple[float, float]:
        """Coordenada absoluta del handle de salida."""
        return (self.x + self.cx1, self.y + self.cy1)

    @property
    def handle_in(self) -> Tuple[float, float]:
        """Coordenada absoluta del handle de entrada."""
        return (self.x + self.cx2, self.y + self.cy2)


class BezierPath:
    """
    Path compuesto por puntos ancla con handles cúbicos.
    Soporta paths abiertos y cerrados.
    """

    HIT_RADIUS = 10   # píxeles de tolerancia para hit-test

    def __init__(self):
        self.points: List[AnchorPoint] = []
        self.closed: bool = False
        self._stroke_width: int = 3   # tamaño propio de la Bézier

    # ── Construcción ──────────────────────────────────────────────────

    def add_point(self, x: float, y: float) -> AnchorPoint:
        pt = AnchorPoint(x, y, 0, 0, 0, 0)
        self.points.append(pt)
        return pt

    def close(self):
        """Cierra el path conectando el último punto con el primero."""
        if len(self.points) >= 2:
            self.closed = True

    def can_close(self) -> bool:
        return len(self.points) >= 2

    # ── Evaluación ────────────────────────────────────────────────────

    def _cubic(self, p0, p1, p2, p3, t: float) -> float:
        """Fórmula cúbica de Bézier para una dimensión."""
        mt = 1 - t
        return (mt**3 * p0 +
                3 * mt**2 * t * p1 +
                3 * mt * t**2 * p2 +
                t**3 * p3)

    def sample_segment(self, i: int, steps: int = 60
                       ) -> List[Tuple[float, float]]:
        """
        Muestrea el segmento entre points[i] y points[i+1].
        Devuelve lista de (x, y).
        """
        n = len(self.points)
        j = (i + 1) % n
        a = self.points[i]
        b = self.points[j]

        # Control points absolutos
        cx1, cy1 = a.handle_out
        cx2, cy2 = b.handle_in

        pts = []
        for k in range(steps + 1):
            t = k / steps
            x = self._cubic(a.x, cx1, cx2, b.x, t)
            y = self._cubic(a.y, cy1, cy2, b.y, t)
            pts.append((x, y))
        return pts

    def all_segments(self) -> List[Tuple[int, int]]:
        """
        Devuelve los índices de segmentos (i, j) que existen.
        """
        n = len(self.points)
        if n < 2:
            return []
        if self.closed:
            return [(i, (i+1) % n) for i in range(n)]
        else:
            return [(i, i+1) for i in range(n-1)]

    def sample_all(self, steps: int = 60
                   ) -> List[List[Tuple[float, float]]]:
        """Devuelve todos los segmentos muestreados."""
        result = []
        for i, _ in self.all_segments():
            result.append(self.sample_segment(i, steps))
        return result

    # ── Hit-test ──────────────────────────────────────────────────────

    def hit_anchor(self, x: float, y: float
                   ) -> Optional[int]:
        """Devuelve índice del ancla tocada, o None."""
        for i, pt in enumerate(self.points):
            if math.hypot(x - pt.x, y - pt.y) < self.HIT_RADIUS:
                return i
        return None

    def hit_handle_out(self, x: float, y: float
                       ) -> Optional[int]:
        """Devuelve índice del punto cuyo handle de salida fue tocado."""
        for i, pt in enumerate(self.points):
            hx, hy = pt.handle_out
            if math.hypot(x - hx, y - hy) < self.HIT_RADIUS:
                return i
        return None

    def hit_handle_in(self, x: float, y: float
                      ) -> Optional[int]:
        """Devuelve índice del punto cuyo handle de entrada fue tocado."""
        for i, pt in enumerate(self.points):
            hx, hy = pt.handle_in
            if math.hypot(x - hx, y - hy) < self.HIT_RADIUS:
                return i
        return None

    def hit_first_anchor(self, x: float, y: float) -> bool:
        """True si (x,y) está cerca del primer punto (para cerrar)."""
        if not self.points:
            return False
        pt = self.points[0]
        return math.hypot(x - pt.x, y - pt.y) < self.HIT_RADIUS * 1.5

    # ── Utilidades ────────────────────────────────────────────────────

    def move_anchor(self, index: int, dx: float, dy: float):
        """Mueve un ancla (y sus handles con ella)."""
        pt = self.points[index]
        pt.x += dx
        pt.y += dy

    def move_handle_out(self, index: int, x: float, y: float):
        """Mueve el handle de salida; si smooth, refleja el de entrada."""
        pt = self.points[index]
        pt.cx1 = x - pt.x
        pt.cy1 = y - pt.y
        if pt.smooth:
            # Reflejo simétrico
            dist = math.hypot(pt.cx2, pt.cy2)
            if dist > 0:
                pt.cx2 = -pt.cx1
                pt.cy2 = -pt.cy1
            else:
                pt.cx2 = -pt.cx1
                pt.cy2 = -pt.cy1

    def move_handle_in(self, index: int, x: float, y: float):
        """Mueve el handle de entrada; si smooth, refleja el de salida."""
        pt = self.points[index]
        pt.cx2 = x - pt.x
        pt.cy2 = y - pt.y
        if pt.smooth:
            pt.cx1 = -pt.cx2
            pt.cy1 = -pt.cy2
