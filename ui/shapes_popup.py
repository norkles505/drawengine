"""
Popup flotante de herramientas de formas.
"""

from PyQt6.QtWidgets import QWidget, QGridLayout, QPushButton, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QIcon

from ui.icon_paths import (
    LINE_ICON, RECT_ICON, ELLIPSE_ICON, TRIANGLE_ICON, BEZIER_ICON
)


class _ShapeCard(QPushButton):
    """Botón cuadrado con ícono centrado. El nombre de la forma se
    muestra como tooltip al pasar el mouse, no como texto fijo
    debajo del ícono."""

    def __init__(self, icon_path: str, label: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(label)
        self.setStyleSheet(self._style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        icon_lbl.setPixmap(QIcon(icon_path).pixmap(QSize(19, 19)))

        layout.addWidget(icon_lbl)

    def _style(self):
        return """
            _ShapeCard {
                background: #202020;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
            }
            _ShapeCard:hover {
                background: #3a2a15;
                border: 1px solid #f2801a;
            }
            _ShapeCard:pressed { background: #f2801a; }
        """


class ShapesPopup(QWidget):
    line_selected     = pyqtSignal()
    rect_selected     = pyqtSignal()
    ellipse_selected  = pyqtSignal()
    triangle_selected = pyqtSignal()
    bezier_selected   = pyqtSignal()

    TOOLS = [
        (LINE_ICON,     "Línea"),
        (RECT_ICON,     "Rectángulo"),
        (ELLIPSE_ICON,  "Elipse"),
        (TRIANGLE_ICON, "Triángulo"),
        (BEZIER_ICON,   "Bézier"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setStyleSheet("""
            QWidget {
                background: #202020;
                border: 1px solid #444;
                border-radius: 6px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(6)

        signals = [
            self.line_selected,
            self.rect_selected,
            self.ellipse_selected,
            self.triangle_selected,
            self.bezier_selected,
        ]

        for i, ((icon_path, label), sig) in enumerate(
                zip(self.TOOLS, signals)):
            btn = _ShapeCard(icon_path, label)
            btn.clicked.connect(sig.emit)
            btn.clicked.connect(self.hide)
            grid.addWidget(btn, i // 2, i % 2)

    def show_at(self, pos: QPoint):
        self.adjustSize()
        self.move(pos)
        self.show()
