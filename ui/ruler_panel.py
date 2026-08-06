from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
    QStackedWidget, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon
from core.ruler import RulerType
from ui.icon_paths import (
    RULER_OFF_ICON, RULER_LINE_ICON, RULER_CIRCLE_ICON,
    RULER_ELLIPSE_ICON, RULER_SYMMETRY_ICON
)


class RulerPanel(QWidget):
    ruler_type_changed   = pyqtSignal(object)
    ruler_active_changed = pyqtSignal(bool)
    ruler_config_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Reglas")
        self.setFixedWidth(260)
        from ui.dark_titlebar import apply_dark_titlebar
        apply_dark_titlebar(self)
        self.setStyleSheet("""
            QWidget   { background: #202020; color: #ddd; }
            QLabel    { color: #aaa; font-size: 11px; }
            QPushButton {
                background: #282828; color: #ddd;
                border: 1px solid #3a3a3a; border-radius: 4px;
                padding: 4px 8px; font-size: 11px;
            }
            QPushButton:hover   { background: #383838; border-color: #f2801a; }
            QPushButton:checked { background: #f2801a; border-color: #f2801a; }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 3px;
                padding: 2px 4px; font-size: 11px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── Tipo de regla ─────────────────────────────────────────────
        layout.addWidget(QLabel("Tipo de regla"))
        self.type_buttons = {}
        row = QHBoxLayout()
        row.setSpacing(4)

        # Botón OFF
        self.btn_off = QPushButton()
        self.btn_off.setIcon(QIcon(RULER_OFF_ICON))
        self.btn_off.setIconSize(QSize(20, 20))
        self.btn_off.setToolTip("Sin regla")
        self.btn_off.setCheckable(True)
        self.btn_off.setChecked(True)
        self.btn_off.setFixedHeight(30)
        self.btn_off.clicked.connect(self._on_off)
        row.addWidget(self.btn_off)

        types = [
            (RulerType.LINE,     RULER_LINE_ICON,     "Línea"),
            (RulerType.CIRCLE,   RULER_CIRCLE_ICON,   "Circular"),
            (RulerType.ELLIPSE,  RULER_ELLIPSE_ICON,  "Elíptica"),
            (RulerType.SYMMETRY, RULER_SYMMETRY_ICON, "Simétrica"),
        ]
        for rtype, icon_path, tooltip in types:
            btn = QPushButton()
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(20, 20))
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda _, t=rtype: self._select_type(t))
            row.addWidget(btn)
            self.type_buttons[rtype] = btn
        layout.addLayout(row)

        self._sep(layout)

        # ── Configuración por tipo ────────────────────────────────────
        layout.addWidget(QLabel("Configuración"))
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        layout.addWidget(self.stack)

        self._cfg_line     = self._make_line_cfg()
        self._cfg_circle   = self._make_circle_cfg()
        self._cfg_ellipse  = self._make_ellipse_cfg()
        self._cfg_symmetry = self._make_symmetry_cfg()
        self._cfg_empty    = QWidget()

        for w in [self._cfg_line, self._cfg_circle,
                  self._cfg_ellipse, self._cfg_symmetry,
                  self._cfg_empty]:
            self.stack.addWidget(w)

        self.stack.setCurrentWidget(self._cfg_empty)

        self._sep(layout)

        hint = QLabel(
            "Haz clic en el canvas para posicionar.\n"
            "Arrastra el centro para mover.\n"
            "Arrastra el borde para redimensionar.")
        hint.setStyleSheet("color: #555; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()

    def _make_line_cfg(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        row = QHBoxLayout()
        row.addWidget(QLabel("Ángulo"))
        self.line_angle = QDoubleSpinBox()
        self.line_angle.setRange(-360, 360)
        self.line_angle.setValue(0)
        self.line_angle.setSuffix("°")
        self.line_angle.setFixedWidth(90)
        self.line_angle.valueChanged.connect(self._on_config_changed)
        row.addWidget(self.line_angle)
        row.addStretch()
        lay.addLayout(row)
        return w

    def _make_circle_cfg(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        row = QHBoxLayout()
        row.addWidget(QLabel("Radio"))
        self.circle_radius = QSpinBox()
        self.circle_radius.setRange(10, 2000)
        self.circle_radius.setValue(150)
        self.circle_radius.setSuffix(" px")
        self.circle_radius.setFixedWidth(90)
        self.circle_radius.valueChanged.connect(self._on_config_changed)
        row.addWidget(self.circle_radius)
        row.addStretch()
        lay.addLayout(row)
        return w

    def _make_ellipse_cfg(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        for label, attr, val in [
            ("Radio X", "ellipse_rx", 150),
            ("Radio Y", "ellipse_ry", 80),
            ("Ángulo",  "ellipse_angle", 0),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            sp = QDoubleSpinBox()
            sp.setRange(-360 if "Ángulo" in label else 1, 2000)
            sp.setValue(val)
            sp.setFixedWidth(90)
            sp.setSuffix("°" if "Ángulo" in label else " px")
            sp.valueChanged.connect(self._on_config_changed)
            setattr(self, attr, sp)
            row.addWidget(sp)
            row.addStretch()
            lay.addLayout(row)
        return w

    def _make_symmetry_cfg(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(QLabel("Modo"))
        self.sym_mode = QComboBox()
        self.sym_mode.addItems(["Vertical", "Horizontal", "Ambos", "Radial"])
        self.sym_mode.currentIndexChanged.connect(self._on_config_changed)
        lay.addWidget(self.sym_mode)
        row = QHBoxLayout()
        row.addWidget(QLabel("Ejes radiales"))
        self.sym_radial_n = QSpinBox()
        self.sym_radial_n.setRange(2, 16)
        self.sym_radial_n.setValue(4)
        self.sym_radial_n.setFixedWidth(60)
        self.sym_radial_n.valueChanged.connect(self._on_config_changed)
        row.addWidget(self.sym_radial_n)
        row.addStretch()
        lay.addLayout(row)
        return w

    def _on_off(self):
        for btn in self.type_buttons.values():
            btn.setChecked(False)
        self.btn_off.setChecked(True)
        self.stack.setCurrentWidget(self._cfg_empty)
        self.ruler_active_changed.emit(False)

    def _select_type(self, rtype: RulerType):
        self.btn_off.setChecked(False)
        for t, btn in self.type_buttons.items():
            btn.setChecked(t == rtype)
        cfg_map = {
            RulerType.LINE:     self._cfg_line,
            RulerType.CIRCLE:   self._cfg_circle,
            RulerType.ELLIPSE:  self._cfg_ellipse,
            RulerType.SYMMETRY: self._cfg_symmetry,
        }
        self.stack.setCurrentWidget(cfg_map.get(rtype, self._cfg_empty))
        self.ruler_type_changed.emit(rtype)
        self.ruler_active_changed.emit(True)

    def _on_config_changed(self):
        self.ruler_config_changed.emit()

    def get_ruler_config(self) -> dict:
        return {
            "line_angle":    self.line_angle.value(),
            "circle_radius": self.circle_radius.value(),
            "ellipse_rx":    self.ellipse_rx.value(),
            "ellipse_ry":    self.ellipse_ry.value(),
            "ellipse_angle": self.ellipse_angle.value(),
            "sym_mode":      self.sym_mode.currentText().lower(),
            "sym_radial_n":  self.sym_radial_n.value(),
        }

    def _sep(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333333;")
        layout.addWidget(sep)
