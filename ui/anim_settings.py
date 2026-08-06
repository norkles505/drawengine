"""
Panel flotante de configuración de animación:
reproducción, onion skinning, colores.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QSpinBox, QPushButton, QComboBox,
    QFrame, QColorDialog, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush


class ColorButton(QPushButton):
    color_changed = pyqtSignal(QColor)

    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 24)
        self._color = color
        self._update()
        self.clicked.connect(self._pick)

    def set_color(self, c: QColor):
        self._color = c
        self._update()

    def color(self) -> QColor:
        return self._color

    def _update(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: {self._color.name()};
                border: 1px solid #666;
                border-radius: 3px;
            }}
            QPushButton:hover {{ border: 1px solid #f2801a; }}
        """)

    def _pick(self):
        c = QColorDialog.getColor(self._color, self, "Pick Color")
        if c.isValid():
            self._color = c
            self._update()
            self.color_changed.emit(c)


class AnimSettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)

    PLAYBACK_MODES = ["Loop", "Ping-pong", "One shot"]
    ONION_MODES    = ["None", "Both", "Past only", "Future only"]

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Animation Settings")
        self.setFixedWidth(320)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(self._style())
        from ui.dark_titlebar import apply_dark_titlebar
        apply_dark_titlebar(self)
        self._s = dict(settings)   # copia local
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        layout.addWidget(self._title("Animation Settings"))

        # ── Playback ──────────────────────────────────────────────────
        pb_box = self._group("Playback")
        pb_lay = QVBoxLayout(pb_box)
        pb_lay.setSpacing(6)

        pb_lay.addWidget(self._lbl("Mode"))
        self.combo_play = QComboBox()
        self.combo_play.addItems(self.PLAYBACK_MODES)
        self.combo_play.setCurrentIndex(
            self._s.get("playback_mode", 0))
        self.combo_play.currentIndexChanged.connect(
            lambda i: self._set("playback_mode", i))
        pb_lay.addWidget(self.combo_play)
        layout.addWidget(pb_box)

        # ── Onion skin ────────────────────────────────────────────────
        on_box = self._group("Onion Skin")
        on_lay = QVBoxLayout(on_box)
        on_lay.setSpacing(8)

        on_lay.addWidget(self._lbl("Mode"))
        self.combo_onion = QComboBox()
        self.combo_onion.addItems(self.ONION_MODES)
        self.combo_onion.setCurrentIndex(
            self._s.get("onion_mode", 0))
        self.combo_onion.currentIndexChanged.connect(
            lambda i: self._set("onion_mode", i))
        on_lay.addWidget(self.combo_onion)

        on_lay.addWidget(self._lbl("Layers (1–5)"))
        self.spin_layers = QSpinBox()
        self.spin_layers.setRange(1, 5)
        self.spin_layers.setValue(self._s.get("onion_layers", 1))
        self.spin_layers.valueChanged.connect(
            lambda v: self._set("onion_layers", v))
        on_lay.addWidget(self.spin_layers)

        on_lay.addWidget(self._lbl("First layer opacity (%)"))
        self.spin_op1 = self._opacity_spin("onion_op_first", 50)
        on_lay.addWidget(self.spin_op1)

        on_lay.addWidget(self._lbl("Last layer opacity (%)"))
        self.spin_op2 = self._opacity_spin("onion_op_last", 20)
        on_lay.addWidget(self.spin_op2)

        # Colores
        color_row = QHBoxLayout()
        color_row.addWidget(self._lbl("Past color"))
        self.btn_past = ColorButton(
            QColor(self._s.get("onion_color_past", "#dc3c3c")))
        self.btn_past.color_changed.connect(
            lambda c: self._set("onion_color_past", c.name()))
        color_row.addWidget(self.btn_past)
        color_row.addSpacing(12)
        color_row.addWidget(self._lbl("Future color"))
        self.btn_future = ColorButton(
            QColor(self._s.get("onion_color_future", "#3c78dc")))
        self.btn_future.color_changed.connect(
            lambda c: self._set("onion_color_future", c.name()))
        color_row.addWidget(self.btn_future)
        color_row.addStretch()
        on_lay.addLayout(color_row)

        layout.addWidget(on_box)

        # ── Botones ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        btn_reset = QPushButton("Reset defaults")
        btn_reset.setStyleSheet(self._btn_style("#333", "#444"))
        btn_reset.clicked.connect(self._reset)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(self._btn_style("#f2801a", "#ff9d40"))
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    # ── Helpers ───────────────────────────────────────────────────────

    def _set(self, key, value):
        self._s[key] = value
        self.settings_changed.emit(dict(self._s))

    def _reset(self):
        defaults = {
            "playback_mode":     0,
            "onion_mode":        0,
            "onion_layers":      1,
            "onion_op_first":    50,
            "onion_op_last":     20,
            "onion_color_past":  "#dc3c3c",
            "onion_color_future":"#3c78dc",
        }
        self._s = defaults
        self.settings_changed.emit(dict(self._s))
        # Refrescar widgets
        self.combo_play.setCurrentIndex(0)
        self.combo_onion.setCurrentIndex(0)
        self.spin_layers.setValue(1)
        self.spin_op1.setValue(50)
        self.spin_op2.setValue(20)
        self.btn_past.set_color(QColor("#dc3c3c"))
        self.btn_future.set_color(QColor("#3c78dc"))

    def _opacity_spin(self, key: str, default: int) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(1, 100)
        sp.setValue(self._s.get(key, default))
        sp.setSuffix(" %")
        sp.valueChanged.connect(lambda v: self._set(key, v))
        return sp

    def _group(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet("""
            QGroupBox {
                color: #f2801a;
                border: 1px solid #333;
                border-radius: 5px;
                margin-top: 6px;
                font-size: 11px;
                font-weight: bold;
                padding-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
            }
        """)
        return g

    def _title(self, text):
        l = QLabel(text)
        l.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #f2801a;")
        return l

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet("color: #aaa; font-size: 11px;")
        return l

    def _btn_style(self, bg, hover):
        return f"""
            QPushButton {{
                background: {bg}; color: white;
                border: none; border-radius: 4px;
                padding: 6px 14px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """

    def _style(self):
        return """
            QDialog { background: #202020; }
            QLabel  { color: #ccc; }
            QComboBox, QSpinBox {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 4px;
                padding: 3px 6px; font-size: 11px;
            }
            QComboBox:hover, QSpinBox:hover {
                border: 1px solid #f2801a;
            }
            QComboBox QAbstractItemView {
                background: #282828; color: #eee;
                selection-background-color: #f2801a;
            }
        """
