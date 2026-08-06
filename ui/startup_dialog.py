from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QFrame, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


class StartupDialog(QDialog):
    """Diálogo de configuración inicial del proyecto."""

    PRESETS = {
        "HD 1280×720":       (1280, 720),
        "Full HD 1920×1080": (1920, 1080),
        "2K 2560×1440":      (2560, 1440),
        "Square 1080×1080":  (1080, 1080),
        "Twitter 1500×500":  (1500, 500),
        "Custom":            None,
    }

    FPS_OPTIONS = [8, 12, 15, 24, 30, 60]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project — DrawEngine")
        self.setFixedSize(420, 380)
        self.setModal(True)
        from ui.dark_titlebar import apply_dark_titlebar
        apply_dark_titlebar(self)
        self.setStyleSheet(self._style())
        self._build_ui()

        # Valores resultado
        self.result_width = 1920
        self.result_height = 1080
        self.result_fps = 24

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Título
        title = QLabel("DrawEngine")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #f2801a;")
        layout.addWidget(title)

        sub = QLabel("Configure your new project")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(sub)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333;")
        layout.addWidget(sep)

        # Preset de canvas
        layout.addWidget(self._label("Canvas Size"))
        self.combo_preset = QComboBox()
        for name in self.PRESETS:
            self.combo_preset.addItem(name)
        self.combo_preset.setCurrentText("Full HD 1920×1080")
        self.combo_preset.currentTextChanged.connect(self._on_preset_changed)
        layout.addWidget(self.combo_preset)

        # Ancho / Alto custom
        wh_row = QHBoxLayout()
        wh_row.setSpacing(12)

        self.spin_w = QSpinBox()
        self.spin_w.setRange(100, 8000)
        self.spin_w.setValue(1920)
        self.spin_w.setPrefix("W: ")
        self.spin_w.setSuffix(" px")

        self.spin_h = QSpinBox()
        self.spin_h.setRange(100, 8000)
        self.spin_h.setValue(1080)
        self.spin_h.setPrefix("H: ")
        self.spin_h.setSuffix(" px")

        wh_row.addWidget(self.spin_w)
        wh_row.addWidget(self.spin_h)
        layout.addLayout(wh_row)

        self._set_custom_enabled(False)

        # FPS
        layout.addWidget(self._label("Frames per Second (FPS)"))
        self.combo_fps = QComboBox()
        for fps in self.FPS_OPTIONS:
            self.combo_fps.addItem(f"{fps} FPS", fps)
        self.combo_fps.setCurrentText("24 FPS")
        layout.addWidget(self.combo_fps)

        layout.addStretch()

        # Botón crear
        self.btn_create = QPushButton("Create Project")
        self.btn_create.setFixedHeight(40)
        self.btn_create.setStyleSheet("""
            QPushButton {
                background: #f2801a; color: white;
                border: none; border-radius: 6px;
                font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: #ff9d40; }
            QPushButton:pressed { background: #c96812; }
        """)
        self.btn_create.clicked.connect(self._on_create)
        layout.addWidget(self.btn_create)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #ccc; font-size: 12px; font-weight: bold;")
        return lbl

    def _on_preset_changed(self, text: str):
        preset = self.PRESETS.get(text)
        if preset is None:
            self._set_custom_enabled(True)
        else:
            self._set_custom_enabled(False)
            self.spin_w.setValue(preset[0])
            self.spin_h.setValue(preset[1])

    def _set_custom_enabled(self, enabled: bool):
        self.spin_w.setEnabled(enabled)
        self.spin_h.setEnabled(enabled)

    def _on_create(self):
        self.result_width = self.spin_w.value()
        self.result_height = self.spin_h.value()
        self.result_fps = self.combo_fps.currentData()
        self.accept()

    def _style(self):
        return """
            QDialog { background: #202020; }
            QLabel { color: #ddd; }
            QComboBox, QSpinBox {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 4px;
                padding: 4px 8px; font-size: 12px;
            }
            QComboBox:hover, QSpinBox:hover { border: 1px solid #f2801a; }
            QComboBox QAbstractItemView {
                background: #282828; color: #eee;
                selection-background-color: #f2801a;
            }
        """
