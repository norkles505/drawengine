"""
Barra de propiedades de transformación.
Se muestra debajo de la barra de menú cuando Ctrl+T está activo.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QLocale
from PyQt6.QtGui import QDoubleValidator, QIntValidator


class PropField(QWidget):
    """Campo de propiedad: label + input."""
    value_changed = pyqtSignal(float)

    def __init__(self, label: str, suffix: str = "",
                 decimals: bool = True, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        lbl = QLabel(label)
        lbl.setStyleSheet("color: #888; font-size: 10px;")
        lbl.setFixedWidth(18)
        layout.addWidget(lbl)

        self.edit = QLineEdit("0")
        self.edit.setFixedWidth(64)
        self.edit.setStyleSheet("""
            QLineEdit {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 3px;
                padding: 2px 4px; font-size: 11px;
            }
            QLineEdit:focus { border: 1px solid #f2801a; }
        """)
        if decimals:
            val = QDoubleValidator(-99999, 99999, 2)
            val.setLocale(QLocale(QLocale.Language.English))
            self.edit.setValidator(val)
        else:
            self.edit.setValidator(QIntValidator(-99999, 99999))

        layout.addWidget(self.edit)

        if suffix:
            suf = QLabel(suffix)
            suf.setStyleSheet("color: #666; font-size: 10px;")
            layout.addWidget(suf)

        self.edit.editingFinished.connect(self._on_edited)

    def set_value(self, v: float):
        self.edit.blockSignals(True)
        self.edit.setText(f"{v:.2f}" if '.' in str(v) else str(int(v)))
        self.edit.blockSignals(False)

    def get_value(self) -> float:
        try:
            return float(self.edit.text().replace(",", "."))
        except Exception:
            return 0.0

    def _on_edited(self):
        self.value_changed.emit(self.get_value())


class TransformBar(QWidget):
    """
    Barra de propiedades de transformación.
    Señales emitidas cuando el usuario edita un campo.
    """
    x_changed      = pyqtSignal(float)
    y_changed      = pyqtSignal(float)
    w_changed      = pyqtSignal(float)   # px o %
    h_changed      = pyqtSignal(float)
    angle_changed  = pyqtSignal(float)
    lock_toggled   = pyqtSignal(bool)
    pivot_toggled  = pyqtSignal(bool)    # False=top-left, True=center
    unit_toggled   = pyqtSignal(bool)    # False=px, True=%

    # Botones flotantes
    rotate_left    = pyqtSignal()
    rotate_right   = pyqtSignal()
    flip_h         = pyqtSignal()
    flip_v         = pyqtSignal()
    cancelled      = pyqtSignal()
    committed      = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setStyleSheet("""
            QWidget {
                background: #202020;
                border-bottom: 1px solid #333;
            }
        """)
        self._lock_ratio  = False
        self._use_center  = False
        self._use_percent = False
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # ── Pivot switch (esquina / centro) ───────────────────────────
        self.btn_pivot = QPushButton("⊹")
        self.btn_pivot.setCheckable(True)
        self.btn_pivot.setFixedSize(26, 26)
        self.btn_pivot.setToolTip(
            "Toggle pivot: corner ↔ center")
        self.btn_pivot.setStyleSheet(self._toggle_style())
        self.btn_pivot.toggled.connect(self._on_pivot)
        layout.addWidget(self.btn_pivot)

        self._sep(layout)

        # ── X, Y ──────────────────────────────────────────────────────
        self.f_x = PropField("X", "px")
        self.f_y = PropField("Y", "px")
        self.f_x.value_changed.connect(self.x_changed)
        self.f_y.value_changed.connect(self.y_changed)
        layout.addWidget(self.f_x)
        layout.addWidget(self.f_y)

        self._sep(layout)

        # ── Ancho, Alto, Lock ─────────────────────────────────────────
        # Switch px/%
        self.btn_unit = QPushButton("px")
        self.btn_unit.setCheckable(True)
        self.btn_unit.setFixedSize(28, 22)
        self.btn_unit.setToolTip("Toggle px / %")
        self.btn_unit.setStyleSheet(self._toggle_style())
        self.btn_unit.toggled.connect(self._on_unit)
        layout.addWidget(self.btn_unit)

        self.f_w = PropField("W", "")
        self.f_h = PropField("H", "")
        self.f_w.value_changed.connect(self._on_w_changed)
        self.f_h.value_changed.connect(self._on_h_changed)
        layout.addWidget(self.f_w)

        # Lock proporción
        self.btn_lock = QPushButton("🔓")
        self.btn_lock.setCheckable(True)
        self.btn_lock.setFixedSize(26, 26)
        self.btn_lock.setToolTip("Lock aspect ratio")
        self.btn_lock.setStyleSheet(self._toggle_style())
        self.btn_lock.toggled.connect(self._on_lock)
        layout.addWidget(self.btn_lock)

        layout.addWidget(self.f_h)

        self._sep(layout)

        # ── Ángulo ────────────────────────────────────────────────────
        self.f_angle = PropField("∠", "°")
        self.f_angle.value_changed.connect(self.angle_changed)
        layout.addWidget(self.f_angle)

        self._sep(layout)

        # ── Acciones ──────────────────────────────────────────────────
        actions = [
            ("↺",  "Rotate left 90°",   self.rotate_left),
            ("↻",  "Rotate right 90°",  self.rotate_right),
            ("↔",  "Flip horizontal",   self.flip_h),
            ("↕",  "Flip vertical",     self.flip_v),
        ]
        for icon, tip, sig in actions:
            btn = QPushButton(icon)
            btn.setFixedSize(26, 26)
            btn.setToolTip(tip)
            btn.setStyleSheet(self._action_style())
            btn.clicked.connect(sig.emit)
            layout.addWidget(btn)

        self._sep(layout)

        # ── Cancelar / Hecho ──────────────────────────────────────────
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setFixedHeight(26)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #333; color: #aaa;
                border: none; border-radius: 4px;
                padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background: #444; color: white; }
        """)
        self.btn_cancel.clicked.connect(self.cancelled.emit)

        self.btn_done = QPushButton("✓ Hecho")
        self.btn_done.setFixedHeight(26)
        self.btn_done.setStyleSheet("""
            QPushButton {
                background: #f2801a; color: white;
                border: none; border-radius: 4px;
                padding: 0 10px; font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background: #ff9d40; }
        """)
        self.btn_done.clicked.connect(self.committed.emit)

        layout.addStretch()
        layout.addWidget(self.btn_cancel)
        layout.addWidget(self.btn_done)

    # ── Actualizar campos desde el TransformBox ───────────────────────

    def update_from_box(self, tb, use_percent: bool = False):
        """Sincroniza los campos con el estado actual del TransformBox."""
        if tb is None:
            return

        cx = tb.x + tb.w / 2
        cy = tb.y + tb.h / 2

        if self._use_center:
            self.f_x.set_value(round(cx, 2))
            self.f_y.set_value(round(cy, 2))
        else:
            self.f_x.set_value(round(tb.x, 2))
            self.f_y.set_value(round(tb.y, 2))

        if self._use_percent:
            orig_w = tb._orig_w
            orig_h = tb._orig_h
            self.f_w.set_value(round(abs(tb.scale_x) * 100, 2))
            self.f_h.set_value(round(abs(tb.scale_y) * 100, 2))
        else:
            self.f_w.set_value(round(tb.w, 2))
            self.f_h.set_value(round(tb.h, 2))

        self.f_angle.set_value(round(tb.angle, 2))

    # ── Señales internas ──────────────────────────────────────────────

    def _on_lock(self, checked: bool):
        self._lock_ratio = checked
        self.btn_lock.setText("🔒" if checked else "🔓")
        self.lock_toggled.emit(checked)

    def _on_pivot(self, checked: bool):
        self._use_center = checked
        self.btn_pivot.setToolTip(
            "Pivot: CENTER" if checked else "Pivot: TOP-LEFT")
        self.pivot_toggled.emit(checked)

    def _on_unit(self, checked: bool):
        self._use_percent = checked
        self.btn_unit.setText("%" if checked else "px")
        self.unit_toggled.emit(checked)

    def _on_w_changed(self, v: float):
        self.w_changed.emit(v)
        # Si lock activo, propagar al alto
        if self._lock_ratio:
            self.f_h.set_value(v)
            self.h_changed.emit(v)

    def _on_h_changed(self, v: float):
        self.h_changed.emit(v)
        if self._lock_ratio:
            self.f_w.set_value(v)
            self.w_changed.emit(v)

    # ── Helpers de estilo ─────────────────────────────────────────────

    def _toggle_style(self):
        return """
            QPushButton {
                background: #282828; color: #888;
                border: 1px solid #3a3a3a; border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:checked {
                background: #3a2a15; color: #f2801a;
                border: 1px solid #f2801a;
            }
            QPushButton:hover { border: 1px solid #f2801a; }
        """

    def _action_style(self):
        return """
            QPushButton {
                background: #282828; color: #ccc;
                border: 1px solid #3a3a3a; border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #333; color: white;
                border: 1px solid #f2801a;
            }
        """

    def _sep(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(22)
        sep.setStyleSheet("color: #333;")
        layout.addWidget(sep)
