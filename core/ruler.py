"""
Sistema de Reglas (Rulers) — guías de dibujo que modifican
los puntos del trazo en tiempo real, igual que Ibis Paint.
"""
import math
from enum import Enum, auto
from PyQt6.QtCore import QPoint, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
from PyQt6.QtCore import Qt


class RulerType(Enum):
    NONE     = auto()
    LINE     = auto()
    CIRCLE   = auto()
    ELLIPSE  = auto()
    SYMMETRY = auto()


class Ruler:
    """Clase base para todas las reglas."""

    def __init__(self):
        self.active:  bool = True
        self.editing: bool = False   # True mientras se posiciona

    def snap(self, x: float, y: float) -> list[tuple[float, float]]:
        """
        Recibe un punto y devuelve lista de puntos transformados.
        Simetría puede devolver más de uno.
        """
        return [(x, y)]

    def draw_overlay(self, painter: QPainter,
                     zoom: float, offset: QPoint):
        pass

    def handle_press(self, x: float, y: float, which: int = 0):
        pass

    def handle_drag(self, x: float, y: float, which: int = 0):
        pass

    def handle_release(self):
        pass


# ── Regla Lineal ──────────────────────────────────────────────────────

class LineRuler(Ruler):
    """
    Proyecta el trazo sobre una línea infinita.
    Definida por un punto central y un ángulo.
    """

    def __init__(self, cx: float = 0, cy: float = 0,
                 angle_deg: float = 0):
        super().__init__()
        self.cx    = cx
        self.cy    = cy
        self.angle = angle_deg   # grados
        self._drag_start: tuple | None = None

    def snap(self, x: float, y: float) -> list[tuple[float, float]]:
        rad = math.radians(self.angle)
        dx  = math.cos(rad)
        dy  = math.sin(rad)
        # Proyección sobre la línea
        t   = (x - self.cx) * dx + (y - self.cy) * dy
        return [(self.cx + t * dx, self.cy + t * dy)]

    def draw_overlay(self, painter, zoom, offset):
        ox, oy = offset.x(), offset.y()
        rad = math.radians(self.angle)
        dx  = math.cos(rad)
        dy  = math.sin(rad)
        L   = 4000
        x1  = int((self.cx - dx * L) * zoom + ox)
        y1  = int((self.cy - dy * L) * zoom + oy)
        x2  = int((self.cx + dx * L) * zoom + ox)
        y2  = int((self.cy + dy * L) * zoom + oy)

        pen = QPen(QColor(80, 200, 255, 160), 1,
                   Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(x1, y1, x2, y2)

        # Centro
        cx_s = int(self.cx * zoom + ox)
        cy_s = int(self.cy * zoom + oy)
        painter.setPen(QPen(QColor(80, 200, 255, 220), 2))
        painter.setBrush(QBrush(QColor(80, 200, 255, 80)))
        # Handle de rotación (a 80px del centro, sobre la línea)
        hx = (self.cx + dx * 80) * zoom + ox
        hy = (self.cy + dy * 80) * zoom + oy
        painter.drawEllipse(int(hx) - 5, int(hy) - 5, 10, 10)
        painter.drawEllipse(cx_s - 7, cy_s - 7, 14, 14)
        painter.drawLine(cx_s - 5, cy_s, cx_s + 5, cy_s)
        painter.drawLine(cx_s, cy_s - 5, cx_s, cy_s + 5)

    def handle_drag(self, x, y, which=0):
        if which == 0:   # mover centro
            self.cx = x
            self.cy = y
        elif which == 1:  # rotar
            self.angle = math.degrees(
                math.atan2(y - self.cy, x - self.cx))


# ── Regla Circular ────────────────────────────────────────────────────

class CircleRuler(Ruler):
    """
    Restringe el trazo al perímetro de un círculo.
    """

    def __init__(self, cx: float = 0, cy: float = 0,
                 radius: float = 100):
        super().__init__()
        self.cx     = cx
        self.cy     = cy
        self.radius = max(1.0, radius)

    def snap(self, x: float, y: float) -> list[tuple[float, float]]:
        dx   = x - self.cx
        dy   = y - self.cy
        dist = math.sqrt(dx*dx + dy*dy) or 1.0
        return [(self.cx + dx / dist * self.radius,
                 self.cy + dy / dist * self.radius)]

    def draw_overlay(self, painter, zoom, offset):
        ox, oy = offset.x(), offset.y()
        cx_s = int(self.cx * zoom + ox)
        cy_s = int(self.cy * zoom + oy)
        r_s  = int(self.radius * zoom)

        pen = QPen(QColor(255, 80, 80, 180), 1,
                   Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(cx_s - r_s, cy_s - r_s, r_s*2, r_s*2)

        # Centro
        painter.setPen(QPen(QColor(255, 80, 80, 220), 2))
        painter.setBrush(QBrush(QColor(255, 80, 80, 80)))
        painter.drawEllipse(cx_s - 6, cy_s - 6, 12, 12)
        painter.drawLine(cx_s - 4, cy_s, cx_s + 4, cy_s)
        painter.drawLine(cx_s, cy_s - 4, cx_s, cy_s + 4)

        # Handle de radio
        hx = int((self.cx + self.radius) * zoom + ox)
        hy = cy_s
        painter.setPen(QPen(QColor(255, 80, 80, 180), 1))
        painter.setBrush(QBrush(QColor(255, 80, 80, 120)))
        painter.drawEllipse(hx - 5, hy - 5, 10, 10)

    def handle_drag(self, x, y, which=0):
        if which == 0:
            self.cx = x
            self.cy = y
        elif which == 1:
            self.radius = max(
                1.0, math.sqrt((x-self.cx)**2 + (y-self.cy)**2))
            

    def snap_interpolated(self, x0: float, y0: float,
                          x1: float, y1: float) -> list[tuple[float, float]]:
        """Devuelve puntos intermedios a lo largo del arco entre dos posiciones."""
        import math
        # Ángulo de cada punto en el círculo
        a0 = math.atan2(y0 - self.cy, x0 - self.cx)
        a1 = math.atan2(y1 - self.cy, x1 - self.cx)

        # Diferencia angular más corta
        da = a1 - a0
        if da > math.pi:
            da -= 2 * math.pi
        elif da < -math.pi:
            da += 2 * math.pi

        # Número de pasos según cuánto arco hay que recorrer
        steps = max(1, int(abs(da) * self.radius / 4))
        pts = []
        for i in range(1, steps + 1):
            a = a0 + da * i / steps
            pts.append((
                self.cx + math.cos(a) * self.radius,
                self.cy + math.sin(a) * self.radius
            ))
        return pts


# ── Regla Elíptica ────────────────────────────────────────────────────

class EllipseRuler(Ruler):
    """
    Restringe el trazo al perímetro de una elipse con rotación.
    """

    def __init__(self, cx: float = 0, cy: float = 0,
                 rx: float = 150, ry: float = 80,
                 angle_deg: float = 0):
        super().__init__()
        self.cx    = cx
        self.cy    = cy
        self.rx    = max(1.0, rx)
        self.ry    = max(1.0, ry)
        self.angle = angle_deg

    def snap(self, x: float, y: float) -> list[tuple[float, float]]:
        rad  = math.radians(-self.angle)
        cos_ = math.cos(rad)
        sin_ = math.sin(rad)
        dx   = x - self.cx
        dy   = y - self.cy
        # Rotar al espacio local de la elipse
        lx   = cos_ * dx + sin_ * dy
        ly   = -sin_ * dx + cos_ * dy
        # Ángulo en el espacio local
        theta = math.atan2(ly / max(0.001, self.ry),
                            lx / max(0.001, self.rx))
        # Punto en el perímetro
        px_l = self.rx * math.cos(theta)
        py_l = self.ry * math.sin(theta)
        # Rotar de vuelta
        rad2  = math.radians(self.angle)
        cos2  = math.cos(rad2)
        sin2  = math.sin(rad2)
        px    = cos2 * px_l - sin2 * py_l + self.cx
        py    = sin2 * px_l + cos2 * py_l + self.cy
        return [(px, py)]

    def draw_overlay(self, painter, zoom, offset):
        from PyQt6.QtGui import QTransform
        ox, oy = offset.x(), offset.y()
        cx_s   = self.cx * zoom + ox
        cy_s   = self.cy * zoom + oy
        rx_s   = self.rx * zoom
        ry_s   = self.ry * zoom

        painter.save()
        t = QTransform()
        t.translate(cx_s, cy_s)
        t.rotate(self.angle)
        painter.setTransform(t, True)

        pen = QPen(QColor(255, 80, 80, 180), 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(
            int(-rx_s), int(-ry_s),
            int(rx_s*2), int(ry_s*2))

        # Handles
        painter.setPen(QPen(QColor(255, 80, 80, 200), 1))
        painter.setBrush(QBrush(QColor(255, 80, 80, 120)))
        # Centro
        painter.drawEllipse(-6, -6, 12, 12)
        painter.drawLine(-4, 0, 4, 0)
        painter.drawLine(0, -4, 0, 4)
        # Handle rx (derecha)
        painter.drawEllipse(int(rx_s)-5, -5, 10, 10)
        # Handle ry (abajo)
        painter.drawEllipse(-5, int(ry_s)-5, 10, 10)
        # Handle de rotación (un poco más allá de la punta de rx)
        painter.drawEllipse(int(rx_s + 24 * zoom) - 5, -5, 10, 10)

        painter.restore()

    def handle_drag(self, x, y, which=0):
        if which == 0:
            self.cx = x
            self.cy = y
        elif which == 1:
            # Ajustar rx — distancia horizontal rotada
            rad  = math.radians(-self.angle)
            dx   = x - self.cx
            dy   = y - self.cy
            lx   = math.cos(rad)*dx + math.sin(rad)*dy
            self.rx = max(1.0, abs(lx))
        elif which == 2:
            # Ajustar ry
            rad  = math.radians(-self.angle)
            dx   = x - self.cx
            dy   = y - self.cy
            ly   = -math.sin(rad)*dx + math.cos(rad)*dy
            self.ry = max(1.0, abs(ly))
        elif which == 3:
            # Rotar
            self.angle = math.degrees(
                math.atan2(y - self.cy, x - self.cx))
            
    def snap_interpolated(self, x0: float, y0: float,
                          x1: float, y1: float) -> list[tuple[float, float]]:
        import math
        rad  = math.radians(-self.angle)
        cos_ = math.cos(rad)
        sin_ = math.sin(rad)

        def to_angle(x, y):
            dx, dy = x - self.cx, y - self.cy
            lx =  cos_ * dx + sin_ * dy
            ly = -sin_ * dx + cos_ * dy
            return math.atan2(ly / max(0.001, self.ry),
                               lx / max(0.001, self.rx))

        a0 = to_angle(x0, y0)
        a1 = to_angle(x1, y1)
        da = a1 - a0
        if da > math.pi:  da -= 2 * math.pi
        elif da < -math.pi: da += 2 * math.pi

        steps = max(1, int(abs(da) * max(self.rx, self.ry) / 4))
        rad2  = math.radians(self.angle)
        cos2  = math.cos(rad2)
        sin2  = math.sin(rad2)
        pts   = []
        for i in range(1, steps + 1):
            a    = a0 + da * i / steps
            px_l = self.rx * math.cos(a)
            py_l = self.ry * math.sin(a)
            pts.append((
                cos2 * px_l - sin2 * py_l + self.cx,
                sin2 * px_l + cos2 * py_l + self.cy
            ))
        return pts


# ── Regla de Simetría ─────────────────────────────────────────────────

class SymmetryRuler(Ruler):
    """
    Duplica el trazo reflejado respecto a uno o más ejes.
    Modos: horizontal, vertical, radial (N ejes).
    """

    def __init__(self, cx: float = 0, cy: float = 0,
                 mode: str = "vertical", radial_n: int = 4):
        super().__init__()
        self.cx       = cx
        self.cy       = cy
        self.mode     = mode      # "horizontal","vertical","radial"
        self.radial_n = radial_n  # para modo radial

    def snap(self, x: float, y: float) -> list[tuple[float, float]]:
        pts = [(x, y)]
        dx  = x - self.cx
        dy  = y - self.cy

        if self.mode == "vertical":
            pts.append((self.cx - dx, y))
        elif self.mode == "horizontal":
            pts.append((x, self.cy - dy))
        elif self.mode == "both":
            pts.append((self.cx - dx, y))
            pts.append((x, self.cy - dy))
            pts.append((self.cx - dx, self.cy - dy))
        elif self.mode == "radial":
            base_angle = math.atan2(dy, dx)
            dist       = math.sqrt(dx*dx + dy*dy)
            for i in range(1, self.radial_n):
                a  = base_angle + 2 * math.pi * i / self.radial_n
                pts.append((self.cx + dist * math.cos(a),
                             self.cy + dist * math.sin(a)))
        return pts

    def draw_overlay(self, painter, zoom, offset):
        ox, oy = offset.x(), offset.y()
        cx_s   = int(self.cx * zoom + ox)
        cy_s   = int(self.cy * zoom + oy)
        L      = 4000

        pen = QPen(QColor(100, 220, 100, 160), 1,
                   Qt.PenStyle.DashLine)
        painter.setPen(pen)

        if self.mode in ("vertical", "both"):
            painter.drawLine(cx_s, cy_s - L, cx_s, cy_s + L)
        if self.mode in ("horizontal", "both"):
            painter.drawLine(cx_s - L, cy_s, cx_s + L, cy_s)
        if self.mode == "radial":
            for i in range(self.radial_n):
                a  = 2 * math.pi * i / self.radial_n
                x2 = int(cx_s + math.cos(a) * L * zoom)
                y2 = int(cy_s + math.sin(a) * L * zoom)
                painter.drawLine(cx_s, cy_s, x2, y2)

        # Centro
        painter.setPen(QPen(QColor(100, 220, 100, 220), 2))
        painter.setBrush(QBrush(QColor(100, 220, 100, 80)))
        painter.drawEllipse(cx_s - 7, cy_s - 7, 14, 14)
        painter.drawLine(cx_s - 5, cy_s, cx_s + 5, cy_s)
        painter.drawLine(cx_s, cy_s - 5, cx_s, cy_s + 5)

    def handle_drag(self, x, y, which=0):
        self.cx = x
        self.cy = y