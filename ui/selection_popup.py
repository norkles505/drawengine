"""
Popup flotante de herramientas de selección.
Se abre al hacer click en el botón SELECT de la toolbar.
"""

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QPushButton, QVBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QIcon

from ui.icon_paths import (
    SELECT_RECT_ICON, SELECT_CIRCLE_ICON, DESELECT_ICON,
    COPY_ICON, PASTE_ICON, CUT_ICON, SELECT_OPACITY_ICON, CLEAR_LAYER_ICON
)


class _ToolCard(QPushButton):
    """Botón cuadrado con ícono (SVG o emoji) centrado. El nombre de
    la acción se muestra como tooltip al pasar el mouse, no como
    texto fijo debajo del ícono."""

    def __init__(self, icon_or_emoji: str, label: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(label.replace("\n", " "))
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


class SelectionPopup(QWidget):
    # Señales
    deselect_requested        = pyqtSignal()
    select_by_opacity_requested = pyqtSignal()
    clear_layer_requested     = pyqtSignal()
    select_rect_requested     = pyqtSignal()
    select_circle_requested   = pyqtSignal()
    copy_requested            = pyqtSignal()
    cut_requested             = pyqtSignal()
    paste_requested           = pyqtSignal()

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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)

        # (ícono SVG/PNG o emoji, etiqueta, señal)
        items_row1 = [
            (DESELECT_ICON,  "Eliminar\nselección",   self.deselect_requested),
            (SELECT_OPACITY_ICON,  "Seleccionar\nopacidad", self.select_by_opacity_requested),
            (CLEAR_LAYER_ICON,  "Despejar\ncapa",        self.clear_layer_requested),
            (SELECT_RECT_ICON,  "Rect", self.select_rect_requested),
            (SELECT_CIRCLE_ICON,  "Circular",              self.select_circle_requested),
        ]
        items_row2 = [
            (COPY_ICON,  "Copiar",  self.copy_requested),
            (CUT_ICON,  "Cortar",  self.cut_requested),
            (PASTE_ICON, "Pegar",   self.paste_requested),
        ]

        for col, (icon_or_emoji, label, signal) in enumerate(items_row1):
            btn = _ToolCard(icon_or_emoji, label)
            btn.clicked.connect(signal.emit)
            btn.clicked.connect(self.hide)
            grid.addWidget(btn, 0, col)

        for col, (icon_or_emoji, label, signal) in enumerate(items_row2):
            btn = _ToolCard(icon_or_emoji, label)
            btn.clicked.connect(signal.emit)
            btn.clicked.connect(self.hide)
            grid.addWidget(btn, 1, col)

        layout.addLayout(grid)

    def show_at(self, pos: QPoint):
        self.adjustSize()
        self.move(pos)
        self.show()
