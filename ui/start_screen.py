"""
Pantalla de inicio estilo Photoshop:
- Columna izquierda: proyectos recientes (doble click para abrir)
- Columna derecha: plantillas rápidas de tamaño de canvas + "Personalizado…"
- Botón para abrir cualquier otro archivo .dwe desde disco
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QWidget, QGridLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.user_config import UserConfig


class _TemplateCard(QPushButton):
    """Botón-tarjeta para una plantilla rápida de canvas."""

    def __init__(self, name: str, w: int, h: int, parent=None):
        super().__init__(parent)
        self.width_px  = w
        self.height_px = h
        self.setFixedSize(134, 80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(f"{name}\n{w} × {h} px")
        self.setStyleSheet("""
            QPushButton {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 6px;
                font-size: 12px; text-align: center;
                padding: 6px;
            }
            QPushButton:hover {
                background: #333333; border: 1px solid #f2801a;
            }
            QPushButton:pressed { background: #1c1c1c; }
        """)


class StartScreen(QDialog):
    """
    Pantalla de bienvenida mostrada antes de abrir la ventana principal.

    Resultado tras exec() == Accepted, en los atributos:
      result_action: "new" | "open"
      result_width, result_height, result_fps  (si action == "new")
      result_path                              (si action == "open")
    """

    TEMPLATES = [
        ("HD",       1280, 720),
        ("Full HD",  1920, 1080),
        ("2K",       2560, 1440),
        ("Cuadrado", 1080, 1080),
        ("Banner",   1500, 500),
        ("A4 (300dpi)", 2480, 3508),
    ]

    # Margen/espaciado únicos, reutilizados en todo el diálogo para que
    # todo quede alineado y con el mismo "aire" alrededor.
    MARGIN  = 26
    SPACING = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DrawEngine")
        self.setFixedSize(860, 540)
        self.setModal(True)
        from ui.dark_titlebar import apply_dark_titlebar
        apply_dark_titlebar(self)
        self.setStyleSheet(self._style())

        self._config = UserConfig()

        self.result_action = None
        self.result_width  = 1920
        self.result_height = 1080
        self.result_fps    = 24
        self.result_path   = ""

        self._build_ui()
        self._load_recent()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        M, S = self.MARGIN, self.SPACING

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Encabezado ───────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(68)
        header.setObjectName("header")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(M, 10, M, 10)
        h_layout.setSpacing(2)
        title = QLabel("DrawEngine")
        title.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #f2801a;")
        sub = QLabel("Elige un proyecto reciente o crea uno nuevo")
        sub.setStyleSheet("font-size: 11px; color: #888;")
        h_layout.addWidget(title)
        h_layout.addWidget(sub)
        root.addWidget(header)

        # Línea separadora del encabezado, con el mismo margen lateral
        # que el resto del contenido (en vez de ir de borde a borde).
        head_sep_wrap = QWidget()
        head_sep_wrap.setFixedHeight(1)
        hs_layout = QHBoxLayout(head_sep_wrap)
        hs_layout.setContentsMargins(M, 0, M, 0)
        head_sep = QFrame()
        head_sep.setFrameShape(QFrame.Shape.HLine)
        head_sep.setStyleSheet("color: #303030; background: #303030;")
        head_sep.setFixedHeight(1)
        hs_layout.addWidget(head_sep)
        root.addWidget(head_sep_wrap)

        # ── Cuerpo ───────────────────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(M, M, M, M)
        body.setSpacing(S)

        # -- Columna izquierda: recientes --
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(self._section_label("Recientes"))

        self.list_recent = QListWidget()
        self.list_recent.setFixedWidth(258)
        self.list_recent.itemDoubleClicked.connect(
            self._on_recent_double_clicked)
        left.addWidget(self.list_recent, stretch=1)

        btn_open_other = QPushButton("Abrir otro archivo…")
        btn_open_other.setFixedHeight(34)
        btn_open_other.setStyleSheet(self._secondary_btn_style())
        btn_open_other.clicked.connect(self._on_open_other)
        left.addWidget(btn_open_other)

        body.addLayout(left)

        # Separador vertical, centrado entre ambas columnas
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("color: #303030; background: #303030;")
        body.addWidget(sep)

        # -- Columna derecha: plantillas --
        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(self._section_label("Nuevo proyecto"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for i, (name, w, h) in enumerate(self.TEMPLATES):
            card = _TemplateCard(name, w, h)
            card.clicked.connect(
                lambda _=False, c=card: self._on_template_clicked(c))
            grid.addWidget(card, i // 3, i % 3)
        right.addLayout(grid)

        right.addStretch()

        btn_custom = QPushButton("Personalizado…")
        btn_custom.setFixedHeight(38)
        btn_custom.setStyleSheet(self._primary_btn_style())
        btn_custom.clicked.connect(self._on_custom)
        right.addWidget(btn_custom)

        body.addLayout(right, stretch=1)

        root.addLayout(body)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #ccc; font-size: 12px; font-weight: bold;")
        return lbl

    # ── Recientes ─────────────────────────────────────────────────────

    def _load_recent(self):
        self.list_recent.clear()
        for path in self._config.get_recent_projects():
            name = os.path.basename(path)
            exists = os.path.isfile(path)
            item = QListWidgetItem(
                name if exists else f"{name}  (no encontrado)")
            item.setData(Qt.ItemDataRole.UserRole, path)
            if not exists:
                item.setForeground(Qt.GlobalColor.darkGray)
            item.setToolTip(path)
            self.list_recent.addItem(item)

        if self.list_recent.count() == 0:
            placeholder = QListWidgetItem("Sin proyectos recientes")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(Qt.GlobalColor.darkGray)
            self.list_recent.addItem(placeholder)

    def _on_recent_double_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        if not os.path.isfile(path):
            QMessageBox.warning(
                self, "Archivo no encontrado",
                f"No se encontró el proyecto en:\n{path}")
            self._config.remove_recent_project(path)
            self._config.save()
            self._load_recent()
            return
        self.result_action = "open"
        self.result_path   = path
        self.accept()

    def _on_open_other(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir proyecto", "",
            "DrawEngine Project (*.dwe)")
        if not path:
            return
        self.result_action = "open"
        self.result_path   = path
        self.accept()

    # ── Nuevo proyecto ────────────────────────────────────────────────

    def _on_template_clicked(self, card: _TemplateCard):
        self.result_action = "new"
        self.result_width  = card.width_px
        self.result_height = card.height_px
        self.result_fps    = 24
        self.accept()

    def _on_custom(self):
        from ui.startup_dialog import StartupDialog
        dlg = StartupDialog(self)
        if dlg.exec() == StartupDialog.DialogCode.Accepted:
            self.result_action = "new"
            self.result_width  = dlg.result_width
            self.result_height = dlg.result_height
            self.result_fps    = dlg.result_fps
            self.accept()

    # ── Estilos ───────────────────────────────────────────────────────

    def _primary_btn_style(self):
        return """
            QPushButton {
                background: #f2801a; color: white;
                border: none; border-radius: 6px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: #ff9d40; }
            QPushButton:pressed { background: #c96812; }
        """

    def _secondary_btn_style(self):
        return """
            QPushButton {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover { background: #333333; border: 1px solid #f2801a; }
        """

    def _style(self):
        return """
            QDialog { background: #202020; }
            QLabel  { color: #ddd; }
            QWidget#header { background: #181818; }
            QListWidget {
                background: #181818; border: 1px solid #333;
                border-radius: 6px; color: #eee; font-size: 12px;
                padding: 4px;
            }
            QListWidget::item { padding: 6px; border-radius: 4px; }
            QListWidget::item:selected { background: #f2801a; color: white; }
            QListWidget::item:hover    { background: #2a2a2a; }
        """
