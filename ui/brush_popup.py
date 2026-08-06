"""
Popup flotante de herramientas de pincel.
"""

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QPushButton, QVBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QIcon

from ui.icon_paths import (
    PEN_ICON, FILL_ICON, ERASER_ICON, SMUDGE_ICON, HAND_ICON, TEXT_ICON, EYEDROP_ICON
)


class _ToolCard(QPushButton):
    """Botón cuadrado con ícono (SVG o emoji) centrado. El nombre de
    la herramienta se muestra como tooltip al pasar el mouse, no
    como texto fijo debajo del ícono."""

    def __init__(self, icon_or_emoji: str, label: str, parent=None):
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

        if icon_or_emoji.lower().endswith((".svg", ".png")):
            pix = QIcon(icon_or_emoji).pixmap(QSize(19, 19))
            icon_lbl.setPixmap(pix)
        else:
            icon_lbl.setText(icon_or_emoji)
            icon_lbl.setStyleSheet(
                "background: transparent; border: none; font-size: 15px;")

        layout.addWidget(icon_lbl)

    def _style(self):
        return """
            _ToolCard {
                background: #202020;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
            }
            _ToolCard:hover {
                background: #3a2a15;
                border: 1px solid #f2801a;
            }
            _ToolCard:pressed { background: #f2801a; }
        """


class BrushPopup(QWidget):
    pen_selected      = pyqtSignal()
    eraser_selected   = pyqtSignal()
    fill_selected     = pyqtSignal()
    eyedrop_selected  = pyqtSignal()
    text_selected     = pyqtSignal()
    hand_selected     = pyqtSignal()
    smudge_selected   = pyqtSignal()

    # (ícono SVG/PNG o emoji, etiqueta)
    TOOLS = [
        (PEN_ICON,    "Lápiz"),
        (ERASER_ICON, "Borrador"),
        (FILL_ICON,   "Rellenar"),
        (EYEDROP_ICON, "Gotero"),
        (TEXT_ICON,   "Texto"),
        (HAND_ICON,   "Mano"),
        (SMUDGE_ICON, "Difuminar"),
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
            self.pen_selected,
            self.eraser_selected,
            self.fill_selected,
            self.eyedrop_selected,
            self.text_selected,
            self.hand_selected,
            self.smudge_selected,
        ]

        for i, ((icon_or_emoji, label), sig) in enumerate(
                zip(self.TOOLS, signals)):
            btn = _ToolCard(icon_or_emoji, label)
            btn.clicked.connect(sig.emit)
            btn.clicked.connect(self.hide)
            grid.addWidget(btn, i // 4, i % 4)

    def show_at(self, pos: QPoint):
        self.adjustSize()
        self.move(pos)
        self.show()
