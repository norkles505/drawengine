"""
Barra de propiedades contextual — siempre visible,
cambia según la herramienta activa.
Contiene TODAS las propiedades por herramienta: tamaño, opacidad,
estabilizador, tolerancia, etc. El toolbar lateral solo tiene
botones de herramienta y selector de color.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QStackedWidget, QFontComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from core.tools import ToolType


class ToolPropsBar(QWidget):
    """
    Barra de propiedades contextual.
    Cada herramienta tiene su propio panel dentro de un QStackedWidget.
    """

    # ── Señales — lápiz / borrador ────────────────────────────────────
    pen_size_changed     = pyqtSignal(int)
    pen_opacity_changed  = pyqtSignal(float)
    pen_hardness_changed = pyqtSignal(float)
    pen_type_changed     = pyqtSignal(str)      # "round","square","soft"
    pen_stab_changed     = pyqtSignal(int)       # estabilizador 0-10

    eraser_size_changed    = pyqtSignal(int)
    eraser_opacity_changed = pyqtSignal(float)
    eraser_soft_changed    = pyqtSignal(bool)
    eraser_stab_changed    = pyqtSignal(int)

    # ── Señales — smudge ──────────────────────────────────────────────
    smudge_size_changed    = pyqtSignal(int)
    smudge_opacity_changed = pyqtSignal(float)
    smudge_stab_changed    = pyqtSignal(int)

    # ── Señales — fill ────────────────────────────────────────────────
    fill_tolerance_changed = pyqtSignal(int)

    # ── Señales — texto ───────────────────────────────────────────────
    text_font_changed   = pyqtSignal(str)
    text_size_changed   = pyqtSignal(int)
    text_bold_changed   = pyqtSignal(bool)
    text_italic_changed = pyqtSignal(bool)

    # ── Señales — formas ──────────────────────────────────────────────
    shape_fill_changed   = pyqtSignal(bool)
    shape_stroke_changed = pyqtSignal(int)

    # ── Señales — selección ───────────────────────────────────────────
    sel_mode_changed = pyqtSignal(str)   # "new","add","subtract"

    # ── Señales — transform ───────────────────────────────────────────
    tx_x_changed     = pyqtSignal(float)
    tx_y_changed     = pyqtSignal(float)
    tx_w_changed     = pyqtSignal(float)
    tx_h_changed     = pyqtSignal(float)
    tx_angle_changed = pyqtSignal(float)
    tx_lock_toggled  = pyqtSignal(bool)
    tx_pivot_toggled = pyqtSignal(bool)
    tx_unit_toggled  = pyqtSignal(bool)
    tx_rotate_left   = pyqtSignal()
    tx_rotate_right  = pyqtSignal()
    tx_flip_h        = pyqtSignal()
    tx_flip_v        = pyqtSignal()
    tx_cancelled     = pyqtSignal()
    tx_committed     = pyqtSignal()



    bezier_stroke_changed = pyqtSignal(int)
    bezier_confirm        = pyqtSignal()
    bezier_cancel         = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tx_lock        = False
        self._tx_use_percent = False
        self._tx_orig_ratio  = 1.0
        self.setFixedHeight(36)
        self.setStyleSheet("""
            QWidget {
                background: #202020;
                border-bottom: 1px solid #333333;
            }
            QLabel {
                color: #888; font-size: 10px;
                background: transparent; border: none;
            }
            QSpinBox, QDoubleSpinBox, QComboBox, QFontComboBox {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 3px;
                padding: 1px 4px; font-size: 11px;
                max-height: 22px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid #f2801a;
            }
            QCheckBox {
                color: #aaa; font-size: 10px;
                background: transparent; border: none;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(8, 0, 8, 0)
        main.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(
            "QStackedWidget { background: transparent; border: none; }")
        main.addWidget(self.stack)

        self._panels = {}
        self._panels[ToolType.PEN]       = self._make_pen_panel()
        self._panels[ToolType.ERASER]    = self._make_eraser_panel()
        self._panels[ToolType.SMUDGE]    = self._make_smudge_panel()
        self._panels[ToolType.FILL]      = self._make_fill_panel()
        self._panels[ToolType.TEXT]      = self._make_text_panel()
        self._panels[ToolType.LINE]      = self._make_shape_panel("Line")
        self._panels[ToolType.RECT]      = self._make_shape_panel("Rectangle")
        self._panels[ToolType.ELLIPSE]   = self._make_shape_panel("Ellipse")
        self._panels[ToolType.TRIANGLE]  = self._make_shape_panel("Triangle")
        self._panels[ToolType.SELECT]    = self._make_sel_panel("Marquee")
        self._panels[ToolType.LASSO]     = self._make_sel_panel("Lasso")
        self._panels[ToolType.EYEDROP]   = self._make_eyedrop_panel()
        self._panels[ToolType.TRANSFORM] = self._make_transform_panel()

        self._panels[ToolType.BEZIER] = self._make_bezier_panel()

        empty = QWidget()
        empty.setStyleSheet("background: transparent;")
        self._panels["empty"] = empty

        for panel in self._panels.values():
            self.stack.addWidget(panel)
        self.stack.addWidget(empty)

        self.switch_tool(ToolType.PEN)

    # ── Cambiar panel ─────────────────────────────────────────────────

    def switch_tool(self, tool: ToolType):
        panel = self._panels.get(tool, self._panels.get("empty"))
        if panel:
            self.stack.setCurrentWidget(panel)

    # ── Panels ────────────────────────────────────────────────────────

    def _make_pen_panel(self) -> QWidget:
        w, lay = self._row()

        # Tamaño
        lay.addWidget(self._lbl("Size"))
        self.pen_size = QSpinBox()
        self.pen_size.setRange(1, 200)
        self.pen_size.setValue(8)
        self.pen_size.setFixedWidth(52)
        self.pen_size.valueChanged.connect(self.pen_size_changed)
        lay.addWidget(self.pen_size)

        self._vsep(lay)

        # Opacidad
        lay.addWidget(self._lbl("Opacity"))
        self.pen_opacity = QSpinBox()
        self.pen_opacity.setRange(1, 100)
        self.pen_opacity.setValue(100)
        self.pen_opacity.setSuffix("%")
        self.pen_opacity.setFixedWidth(58)
        self.pen_opacity.valueChanged.connect(
            lambda v: self.pen_opacity_changed.emit(v / 100.0))
        lay.addWidget(self.pen_opacity)

        self._vsep(lay)

        # Dureza
        lay.addWidget(self._lbl("Hardness"))
        self.pen_hardness = QSpinBox()
        self.pen_hardness.setRange(0, 100)
        self.pen_hardness.setValue(100)
        self.pen_hardness.setSuffix("%")
        self.pen_hardness.setFixedWidth(58)
        self.pen_hardness.valueChanged.connect(
            lambda v: self.pen_hardness_changed.emit(v / 100.0))
        lay.addWidget(self.pen_hardness)

        self._vsep(lay)

        # Punta
        lay.addWidget(self._lbl("Tip"))
        self.pen_type = QComboBox()
        self.pen_type.addItems(["Round", "Square", "Soft"])
        self.pen_type.setFixedWidth(70)
        self.pen_type.currentTextChanged.connect(self.pen_type_changed)
        lay.addWidget(self.pen_type)

        self._vsep(lay)

        # Estabilizador
        lay.addWidget(self._lbl("Stabilizer"))
        self.pen_stab = QSpinBox()
        self.pen_stab.setRange(0, 10)
        self.pen_stab.setValue(0)
        self.pen_stab.setFixedWidth(46)
        self.pen_stab.setToolTip("Stroke stabilizer (0=off, 10=max)")
        self.pen_stab.valueChanged.connect(self.pen_stab_changed)
        lay.addWidget(self.pen_stab)

        lay.addStretch()
        return w

    def _make_eraser_panel(self) -> QWidget:
        w, lay = self._row()

        # Tamaño
        lay.addWidget(self._lbl("Size"))
        self.eraser_size = QSpinBox()
        self.eraser_size.setRange(1, 200)
        self.eraser_size.setValue(24)
        self.eraser_size.setFixedWidth(52)
        self.eraser_size.valueChanged.connect(self.eraser_size_changed)
        lay.addWidget(self.eraser_size)

        self._vsep(lay)

        # Opacidad
        lay.addWidget(self._lbl("Opacity"))
        self.eraser_opacity = QSpinBox()
        self.eraser_opacity.setRange(1, 100)
        self.eraser_opacity.setValue(100)
        self.eraser_opacity.setSuffix("%")
        self.eraser_opacity.setFixedWidth(58)
        self.eraser_opacity.valueChanged.connect(
            lambda v: self.eraser_opacity_changed.emit(v / 100.0))
        lay.addWidget(self.eraser_opacity)

        self._vsep(lay)

        # Soft eraser (antes era "~ERA" en el toolbar)
        lay.addWidget(self._lbl("Mode"))
        self.eraser_soft_combo = QComboBox()
        self.eraser_soft_combo.addItems(["Hard", "Soft"])
        self.eraser_soft_combo.setFixedWidth(64)
        self.eraser_soft_combo.currentIndexChanged.connect(
            lambda i: self.eraser_soft_changed.emit(i == 1))
        lay.addWidget(self.eraser_soft_combo)

        self._vsep(lay)

        # Estabilizador
        lay.addWidget(self._lbl("Stabilizer"))
        self.eraser_stab = QSpinBox()
        self.eraser_stab.setRange(0, 10)
        self.eraser_stab.setValue(0)
        self.eraser_stab.setFixedWidth(46)
        self.eraser_stab.setToolTip("Stroke stabilizer (0=off, 10=max)")
        self.eraser_stab.valueChanged.connect(self.eraser_stab_changed)
        lay.addWidget(self.eraser_stab)

        lay.addStretch()
        return w

    def _make_smudge_panel(self) -> QWidget:
        w, lay = self._row()

        lay.addWidget(self._lbl("Size"))
        self.smudge_size = QSpinBox()
        self.smudge_size.setRange(1, 200)
        self.smudge_size.setValue(20)
        self.smudge_size.setFixedWidth(52)
        self.smudge_size.valueChanged.connect(self.smudge_size_changed)
        lay.addWidget(self.smudge_size)

        self._vsep(lay)

        lay.addWidget(self._lbl("Strength"))
        self.smudge_opacity = QSpinBox()
        self.smudge_opacity.setRange(1, 100)
        self.smudge_opacity.setValue(80)
        self.smudge_opacity.setSuffix("%")
        self.smudge_opacity.setFixedWidth(58)
        self.smudge_opacity.valueChanged.connect(
            lambda v: self.smudge_opacity_changed.emit(v / 100.0))
        lay.addWidget(self.smudge_opacity)

        self._vsep(lay)

        lay.addWidget(self._lbl("Stabilizer"))
        self.smudge_stab = QSpinBox()
        self.smudge_stab.setRange(0, 10)
        self.smudge_stab.setValue(0)
        self.smudge_stab.setFixedWidth(46)
        self.smudge_stab.valueChanged.connect(self.smudge_stab_changed)
        lay.addWidget(self.smudge_stab)

        lay.addStretch()
        return w

    def _make_fill_panel(self) -> QWidget:
        w, lay = self._row()

        lay.addWidget(self._lbl("Tolerance"))
        self.fill_tol = QSpinBox()
        self.fill_tol.setRange(0, 255)
        self.fill_tol.setValue(15)
        self.fill_tol.setFixedWidth(52)
        self.fill_tol.valueChanged.connect(self.fill_tolerance_changed)
        lay.addWidget(self.fill_tol)

        self._vsep(lay)

        lay.addWidget(self._lbl("Sample"))
        self.fill_sample = QComboBox()
        self.fill_sample.addItems(["All layers", "Active layer"])
        self.fill_sample.setFixedWidth(90)
        lay.addWidget(self.fill_sample)

        lay.addStretch()
        return w

    def _make_text_panel(self) -> QWidget:
        w, lay = self._row()

        lay.addWidget(self._lbl("Font"))
        self.text_font = QFontComboBox()
        self.text_font.setFixedWidth(150)
        self.text_font.currentFontChanged.connect(
            lambda f: self.text_font_changed.emit(f.family()))
        lay.addWidget(self.text_font)

        self._vsep(lay)

        lay.addWidget(self._lbl("Size"))
        self.text_size = QSpinBox()
        self.text_size.setRange(6, 300)
        self.text_size.setValue(24)
        self.text_size.setFixedWidth(52)
        self.text_size.valueChanged.connect(self.text_size_changed)
        lay.addWidget(self.text_size)

        self._vsep(lay)

        self.text_bold = QPushButton("B")
        self.text_bold.setCheckable(True)
        self.text_bold.setFixedSize(24, 24)
        self.text_bold.setStyleSheet(self._toggle_btn_style("bold"))
        self.text_bold.toggled.connect(self.text_bold_changed)
        lay.addWidget(self.text_bold)

        self.text_italic = QPushButton("I")
        self.text_italic.setCheckable(True)
        self.text_italic.setFixedSize(24, 24)
        self.text_italic.setStyleSheet(self._toggle_btn_style("italic"))
        self.text_italic.toggled.connect(self.text_italic_changed)
        lay.addWidget(self.text_italic)

        lay.addStretch()
        return w

    def _make_shape_panel(self, name: str) -> QWidget:
        w, lay = self._row()

        lay.addWidget(self._lbl(f"{name} —"))
        self._vsep(lay)

        lay.addWidget(self._lbl("Stroke"))
        sp = QSpinBox()
        sp.setRange(1, 100)
        sp.setValue(2)
        sp.setFixedWidth(48)
        sp.valueChanged.connect(self.shape_stroke_changed)
        lay.addWidget(sp)

        self._vsep(lay)

        self.shape_filled = QCheckBox("Filled")
        self.shape_filled.toggled.connect(self.shape_fill_changed)
        lay.addWidget(self.shape_filled)

        lay.addStretch()
        return w

    def _make_sel_panel(self, name: str) -> QWidget:
        w, lay = self._row()

        lay.addWidget(self._lbl(f"{name} —"))
        self._vsep(lay)
        lay.addWidget(self._lbl("Mode"))

        for label, mode in [("New", "new"),
                             ("+ Add", "add"),
                             ("− Sub", "subtract")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setStyleSheet(self._toggle_btn_style())
            btn.clicked.connect(
                lambda _, m=mode: self.sel_mode_changed.emit(m))
            lay.addWidget(btn)
            if mode == "new":
                btn.setChecked(True)

        lay.addStretch()
        return w

    def _make_eyedrop_panel(self) -> QWidget:
        w, lay = self._row()

        lay.addWidget(self._lbl("Eyedropper —"))
        self._vsep(lay)
        lay.addWidget(self._lbl("Color:"))

        self.eye_color_preview = QLabel("          ")
        self.eye_color_preview.setFixedSize(40, 22)
        self.eye_color_preview.setStyleSheet(
            "background: #000; border: 1px solid #444; border-radius: 3px;")
        lay.addWidget(self.eye_color_preview)

        self.eye_color_hex = QLabel("#000000")
        self.eye_color_hex.setStyleSheet(
            "color: #aaa; font-size: 11px; font-family: monospace;"
            "background: transparent; border: none;")
        lay.addWidget(self.eye_color_hex)

        self._vsep(lay)

        lay.addWidget(self._lbl("Sample"))
        self.eye_sample = QComboBox()
        self.eye_sample.addItems(["All layers", "Active layer"])
        self.eye_sample.setFixedWidth(90)
        lay.addWidget(self.eye_sample)

        lay.addStretch()
        return w

    def update_eyedrop_color(self, color: QColor):
        self.eye_color_preview.setStyleSheet(
            f"background: {color.name()};"
            f"border: 1px solid #444; border-radius: 3px;")
        self.eye_color_hex.setText(
            f"{color.name()}  "
            f"R:{color.red()} G:{color.green()} B:{color.blue()}")

    def _make_transform_panel(self) -> QWidget:
        w, lay = self._row()

        # Pivot
        self.tx_btn_pivot = QPushButton("⊹")
        self.tx_btn_pivot.setCheckable(True)
        self.tx_btn_pivot.setFixedSize(26, 26)
        self.tx_btn_pivot.setToolTip("Pivot: top-left ↔ center")
        self.tx_btn_pivot.setStyleSheet(self._toggle_btn_style())
        self.tx_btn_pivot.toggled.connect(self.tx_pivot_toggled)
        lay.addWidget(self.tx_btn_pivot)

        self._vsep(lay)

        # X, Y
        lay.addWidget(self._lbl("X"))
        self.tx_x = self._dspin(-99999, 99999, 0)
        self.tx_x.valueChanged.connect(self.tx_x_changed)
        lay.addWidget(self.tx_x)

        lay.addWidget(self._lbl("Y"))
        self.tx_y = self._dspin(-99999, 99999, 0)
        self.tx_y.valueChanged.connect(self.tx_y_changed)
        lay.addWidget(self.tx_y)

        self._vsep(lay)

        # Unit px/%
        self.tx_btn_unit = QPushButton("px")
        self.tx_btn_unit.setCheckable(True)
        self.tx_btn_unit.setFixedSize(28, 22)
        self.tx_btn_unit.setToolTip("px / %")
        self.tx_btn_unit.setStyleSheet(self._toggle_btn_style())
        self.tx_btn_unit.toggled.connect(self._on_tx_unit)
        lay.addWidget(self.tx_btn_unit)

        # W, lock, H
        lay.addWidget(self._lbl("W"))
        self.tx_w = self._dspin(0.1, 99999, 0)
        self.tx_w.valueChanged.connect(self._on_tx_w)
        lay.addWidget(self.tx_w)

        self.tx_btn_lock = QPushButton("🔓")
        self.tx_btn_lock.setCheckable(True)
        self.tx_btn_lock.setFixedSize(26, 26)
        self.tx_btn_lock.setToolTip("Lock aspect ratio")
        self.tx_btn_lock.setStyleSheet(self._toggle_btn_style())
        self.tx_btn_lock.toggled.connect(self._on_tx_lock)
        lay.addWidget(self.tx_btn_lock)

        lay.addWidget(self._lbl("H"))
        self.tx_h = self._dspin(0.1, 99999, 0)
        self.tx_h.valueChanged.connect(self._on_tx_h)
        lay.addWidget(self.tx_h)

        self._vsep(lay)

        # Ángulo
        lay.addWidget(self._lbl("∠"))
        self.tx_angle = self._dspin(-360, 360, 0)
        self.tx_angle.setFixedWidth(64)
        self.tx_angle.setSuffix("°")
        self.tx_angle.valueChanged.connect(self.tx_angle_changed)
        lay.addWidget(self.tx_angle)

        self._vsep(lay)

        # Acciones rápidas
        for icon, tip, sig in [
            ("↺", "Rotate left 90°",  self.tx_rotate_left),
            ("↻", "Rotate right 90°", self.tx_rotate_right),
            ("↔", "Flip horizontal",  self.tx_flip_h),
            ("↕", "Flip vertical",    self.tx_flip_v),
        ]:
            btn = QPushButton(icon)
            btn.setFixedSize(26, 26)
            btn.setToolTip(tip)
            btn.setStyleSheet(self._action_btn_style())
            btn.clicked.connect(sig.emit)
            lay.addWidget(btn)

        self._vsep(lay)
        lay.addStretch()

        # Cancelar / Hecho
        self.tx_btn_cancel = QPushButton("Cancelar")
        self.tx_btn_cancel.setFixedHeight(26)
        self.tx_btn_cancel.setStyleSheet("""
            QPushButton {
                background: #333; color: #aaa;
                border: none; border-radius: 4px;
                padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background: #444; color: white; }
        """)
        self.tx_btn_cancel.clicked.connect(self.tx_cancelled.emit)

        self.tx_btn_done = QPushButton("✓ Hecho")
        self.tx_btn_done.setFixedHeight(26)
        self.tx_btn_done.setStyleSheet("""
            QPushButton {
                background: #f2801a; color: white;
                border: none; border-radius: 4px;
                padding: 0 10px; font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background: #ff9d40; }
        """)
        self.tx_btn_done.clicked.connect(self.tx_committed.emit)

        lay.addWidget(self.tx_btn_cancel)
        lay.addWidget(self.tx_btn_done)

        return w

    # ── Transform helpers ─────────────────────────────────────────────

    def _on_tx_lock(self, checked: bool):
        self._tx_lock = checked
        self.tx_btn_lock.setText("🔒" if checked else "🔓")
        self.tx_lock_toggled.emit(checked)

    def _on_tx_unit(self, checked: bool):
        self._tx_use_percent = checked
        self.tx_btn_unit.setText("%" if checked else "px")
        self.tx_unit_toggled.emit(checked)

    def _on_tx_w(self, v: float):
        self.tx_w_changed.emit(v)
        if self._tx_lock:
            new_h = v / max(0.001, self._tx_orig_ratio)
            self.tx_h.blockSignals(True)
            self.tx_h.setValue(new_h)
            self.tx_h.blockSignals(False)
            self.tx_h_changed.emit(new_h)

    def _on_tx_h(self, v: float):
        self.tx_h_changed.emit(v)
        if self._tx_lock:
            new_w = v * self._tx_orig_ratio
            self.tx_w.blockSignals(True)
            self.tx_w.setValue(new_w)
            self.tx_w.blockSignals(False)
            self.tx_w_changed.emit(new_w)

    def update_transform(self, tb):
        if tb is None:
            return
        if tb._orig_h > 0:
            self._tx_orig_ratio = tb._orig_w / tb._orig_h

        use_center = self.tx_btn_pivot.isChecked()

        self.tx_x.blockSignals(True)
        self.tx_y.blockSignals(True)
        if use_center:
            self.tx_x.setValue(round(tb.x + tb.w / 2, 2))
            self.tx_y.setValue(round(tb.y + tb.h / 2, 2))
        else:
            self.tx_x.setValue(round(tb.x, 2))
            self.tx_y.setValue(round(tb.y, 2))
        self.tx_x.blockSignals(False)
        self.tx_y.blockSignals(False)

        self.tx_w.blockSignals(True)
        self.tx_h.blockSignals(True)
        if self._tx_use_percent:
            self.tx_w.setValue(round(abs(tb.scale_x) * 100, 2))
            self.tx_h.setValue(round(abs(tb.scale_y) * 100, 2))
        else:
            self.tx_w.setValue(round(tb.w, 2))
            self.tx_h.setValue(round(tb.h, 2))
        self.tx_w.blockSignals(False)
        self.tx_h.blockSignals(False)

        self.tx_angle.blockSignals(True)
        self.tx_angle.setValue(round(tb.angle, 2))
        self.tx_angle.blockSignals(False)

    # ── Sincronización de valores iniciales ───────────────────────────

    def set_pen_values(self, size: int, opacity: int,
                       hardness: int, stab: int):
        """Inicializa el panel del lápiz con los valores actuales del canvas."""
        self.pen_size.blockSignals(True)
        self.pen_opacity.blockSignals(True)
        self.pen_hardness.blockSignals(True)
        self.pen_stab.blockSignals(True)
        self.pen_size.setValue(size)
        self.pen_opacity.setValue(opacity)
        self.pen_hardness.setValue(hardness)
        self.pen_stab.setValue(stab)
        self.pen_size.blockSignals(False)
        self.pen_opacity.blockSignals(False)
        self.pen_hardness.blockSignals(False)
        self.pen_stab.blockSignals(False)

    def set_eraser_values(self, size: int, opacity: int,
                          soft: bool, stab: int):
        """Inicializa el panel del borrador."""
        self.eraser_size.blockSignals(True)
        self.eraser_opacity.blockSignals(True)
        self.eraser_stab.blockSignals(True)
        self.eraser_size.setValue(size)
        self.eraser_opacity.setValue(opacity)
        self.eraser_stab.setValue(stab)
        self.eraser_soft_combo.setCurrentIndex(1 if soft else 0)
        self.eraser_size.blockSignals(False)
        self.eraser_opacity.blockSignals(False)
        self.eraser_stab.blockSignals(False)

    # ── Helpers de UI ─────────────────────────────────────────────────

    def _row(self):
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(5)
        return w, lay

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            "color: #777; font-size: 10px;"
            "background: transparent; border: none;")
        return l

    def _vsep(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(20)
        sep.setStyleSheet("color: #333333; background: transparent;")
        layout.addWidget(sep)

    def _dspin(self, mn, mx, val) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(mn, mx)
        sp.setValue(val)
        sp.setDecimals(2)
        sp.setFixedWidth(70)
        sp.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        sp.setKeyboardTracking(True)
        return sp

    def _toggle_btn_style(self, style=""):
        weight = "bold" if style == "bold" else "normal"
        fstyle = "italic" if style == "italic" else "normal"
        return f"""
            QPushButton {{
                background: #282828; color: #888;
                border: 1px solid #3a3a3a; border-radius: 4px;
                font-size: 12px; font-weight: {weight};
                font-style: {fstyle};
            }}
            QPushButton:checked {{
                background: #3a2a15; color: #f2801a;
                border: 1px solid #f2801a;
            }}
            QPushButton:hover {{ border: 1px solid #f2801a; }}
        """

    def _action_btn_style(self):
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
    

    def _make_bezier_panel(self) -> QWidget:
        w, lay = self._row()

        lay.addWidget(self._lbl("Bézier —"))
        self._vsep(lay)

        lay.addWidget(self._lbl("Stroke"))
        self.bezier_stroke = QSpinBox()
        self.bezier_stroke.setRange(1, 100)
        self.bezier_stroke.setValue(3)
        self.bezier_stroke.setFixedWidth(52)
        self.bezier_stroke.setToolTip("Grosor del trazo Bézier")
        self.bezier_stroke.valueChanged.connect(self.bezier_stroke_changed)
        lay.addWidget(self.bezier_stroke)

        self._vsep(lay)

        # Botón confirmar
        self.bezier_btn_confirm = QPushButton("✓ Aplicar")
        self.bezier_btn_confirm.setFixedHeight(26)
        self.bezier_btn_confirm.setStyleSheet("""
            QPushButton {
                background: #f2801a; color: white;
                border: none; border-radius: 4px;
                padding: 0 10px; font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background: #ff9d40; }
        """)
        self.bezier_btn_confirm.clicked.connect(self.bezier_confirm.emit)
        lay.addWidget(self.bezier_btn_confirm)

        # Botón cancelar
        self.bezier_btn_cancel = QPushButton("Cancelar")
        self.bezier_btn_cancel.setFixedHeight(26)
        self.bezier_btn_cancel.setStyleSheet("""
            QPushButton {
                background: #333; color: #aaa;
                border: none; border-radius: 4px;
                padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background: #444; color: white; }
        """)
        self.bezier_btn_cancel.clicked.connect(self.bezier_cancel.emit)
        lay.addWidget(self.bezier_btn_cancel)

        self._vsep(lay)
        lay.addWidget(self._lbl("Tip: Click=ancla  Arrastrar=handles  Enter=aplicar  Esc=cancelar"))

        lay.addStretch()
        return w
