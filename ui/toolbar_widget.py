import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QIcon

from core.tools import ToolType
from ui.color_palette import RecentColorsPanel
from ui.selection_popup import SelectionPopup
from ui.shapes_popup import ShapesPopup
from ui.brush_popup import BrushPopup
from ui.icon_paths import (
    PEN_ICON, FILL_ICON, ERASER_ICON, SMUDGE_ICON, HAND_ICON, EYEDROP_ICON,
    SELECT_ICON, TEXT_ICON, LINE_ICON, RECT_ICON, ELLIPSE_ICON,
    TRIANGLE_ICON, BEZIER_ICON, LASSO_ICON, TRANSFORM_ICON
)


class ColorSwatch(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color = QColor(0, 0, 0, 255)
        self.setToolTip("Active color — click to change")

    def set_color(self, color: QColor):
        self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        tile = 8
        for r in range(self.height() // tile + 1):
            for c in range(self.width() // tile + 1):
                col = QColor("#bbb") if (r + c) % 2 == 0 else QColor("#eee")
                painter.fillRect(c * tile, r * tile, tile, tile, col)
        painter.setBrush(QBrush(self._color))
        painter.setPen(QPen(QColor("#888"), 1))
        painter.drawRoundedRect(1, 1, 38, 38, 6, 6)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class ToolButton(QPushButton):
    def __init__(self, icon_text: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(38, 38)
        self.set_display(icon_text)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(False)

    def set_display(self, value: str):
        """Muestra un ícono SVG/PNG (ruta de archivo) o texto/emoji."""
        if value.lower().endswith((".svg", ".png")):
            self.setIcon(QIcon(value))
            self.setIconSize(QSize(19, 19))
            self.setText("")
        else:
            self.setIcon(QIcon())
            self.setText(value)

    def set_active(self, active: bool):
        self.setChecked(active)
        self._apply_style(active)

    def _apply_style(self, active: bool):
        # Paleta MeshCraft: acento naranja RGB(242,128,26).
        bg     = "#f2801a" if active else "#282828"
        border = "#f2801a" if active else "#3a3a3a"
        hover  = "#ff9d40" if active else "#333333"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 7px;
                color: white;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background: {hover};
                border: 2px solid #f2801a;
            }}
        """)


class SideToolbar(QWidget):
    tool_changed   = pyqtSignal(ToolType)
    color_clicked  = pyqtSignal()
    color2_clicked = pyqtSignal()
    colors_swapped = pyqtSignal()

    TOOLS = [
        (PEN_ICON, "Pen tools",   ToolType.PEN),
        (SELECT_ICON, "Selection (S)",  ToolType.SELECT),
        (LASSO_ICON,  "Lasso (A)",      ToolType.LASSO),
        (TRANSFORM_ICON,  "Transform (W)",  ToolType.TRANSFORM),
        (LINE_ICON,  "Shapes",   ToolType.LINE),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(62)
        self.setStyleSheet("background: #202020;")
        self._tool_buttons: dict[ToolType, ToolButton] = {}
        self._current_tool  = ToolType.PEN
        self._recent_colors: list = []
        self._build_ui()

        # ── Brush popup ───────────────────────────────────────────────
        self._brush_popup = BrushPopup(self.window())
        self._brush_popup.pen_selected.connect(
            lambda: self._on_brush_selected(PEN_ICON, ToolType.PEN))
        self._brush_popup.eraser_selected.connect(
            lambda: self._on_brush_selected(ERASER_ICON, ToolType.ERASER))
        self._brush_popup.fill_selected.connect(
            lambda: self._on_brush_selected(FILL_ICON, ToolType.FILL))
        self._brush_popup.eyedrop_selected.connect(
            lambda: self._on_brush_selected(EYEDROP_ICON, ToolType.EYEDROP))
        self._brush_popup.text_selected.connect(
            lambda: self._on_brush_selected(TEXT_ICON, ToolType.TEXT))
        self._brush_popup.hand_selected.connect(
            lambda: self._on_brush_selected(HAND_ICON, ToolType.HAND))
        self._brush_popup.smudge_selected.connect(
            lambda: self._on_brush_selected(SMUDGE_ICON, ToolType.SMUDGE))

        self._tool_buttons[ToolType.PEN].clicked.connect(
            self._show_brush_popup)
        self._current_brush = ToolType.PEN

        # ── Shapes popup ──────────────────────────────────────────────
        self._shapes_popup = ShapesPopup(self.window())
        self._shapes_popup.line_selected.connect(
            lambda: self._on_shape_selected(LINE_ICON, ToolType.LINE))
        self._shapes_popup.rect_selected.connect(
            lambda: self._on_shape_selected(RECT_ICON, ToolType.RECT))
        self._shapes_popup.ellipse_selected.connect(
            lambda: self._on_shape_selected(ELLIPSE_ICON, ToolType.ELLIPSE))
        self._shapes_popup.triangle_selected.connect(
            lambda: self._on_shape_selected(TRIANGLE_ICON, ToolType.TRIANGLE))
        self._shapes_popup.bezier_selected.connect(
            lambda: self._on_shape_selected(BEZIER_ICON, ToolType.BEZIER))

        self._tool_buttons[ToolType.LINE].clicked.connect(
            self._show_shapes_popup)
        self._current_shape = ToolType.LINE

        # ── Selection popup ───────────────────────────────────────────
        self._sel_popup = SelectionPopup(self.window())
        self._tool_buttons[ToolType.SELECT].clicked.connect(
            self._show_sel_popup)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: #202020; border: none; }
            QScrollBar:vertical { width: 0px; }
        """)

        inner = QWidget()
        inner.setStyleSheet("background: #202020;")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(4)

        # ── Botones de herramienta ────────────────────────────────────
        for emoji, tooltip, tool in self.TOOLS:
            btn = ToolButton(emoji, tooltip)
            btn.clicked.connect(lambda _, t=tool: self._select_tool(t))
            layout.addWidget(btn)
            self._tool_buttons[tool] = btn

        self._tool_buttons[ToolType.PEN].set_active(True)

        self._sep(layout)

        # ── Colores primario / secundario ─────────────────────────────
        color_widget = QWidget()
        color_widget.setFixedSize(54, 44)
        color_widget.setStyleSheet("background: transparent;")

        self.swatch2 = ColorSwatch()
        self.swatch2.setFixedSize(28, 28)
        self.swatch2.setToolTip("Secondary color — click to change")
        self.swatch2._color = QColor(255, 255, 255, 255)
        self.swatch2.clicked.connect(self._color2_clicked)
        self.swatch2.setParent(color_widget)
        self.swatch2.move(14, 10)

        self.swatch = ColorSwatch()
        self.swatch.setToolTip("Primary color — click to change")
        self.swatch.clicked.connect(self.color_clicked.emit)
        self.swatch.setParent(color_widget)
        self.swatch.move(0, 0)

        self.btn_swap = QPushButton("⇄")
        self.btn_swap.setFixedSize(16, 16)
        self.btn_swap.setToolTip("Swap colors (X)")
        self.btn_swap.setStyleSheet("""
            QPushButton {
                background: #333; color: #aaa;
                border: none; border-radius: 3px;
                font-size: 10px; padding: 0;
            }
            QPushButton:hover { background: #f2801a; color: white; }
        """)
        self.btn_swap.clicked.connect(self.swap_colors)
        self.btn_swap.setParent(color_widget)
        self.btn_swap.move(38, 28)

        layout.addWidget(color_widget,
                         alignment=Qt.AlignmentFlag.AlignHCenter)

        # ── Colores recientes ─────────────────────────────────────────
        self.recent_panel = RecentColorsPanel()
        self.recent_panel.color_selected.connect(self._on_recent_selected)
        layout.addWidget(self.recent_panel,
                         alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # ── Lógica ────────────────────────────────────────────────────────

    def _select_tool(self, tool: ToolType):
        self._current_tool = tool
        for t, btn in self._tool_buttons.items():
            btn.set_active(t == tool)
        self.tool_changed.emit(tool)

    def select_tool_external(self, tool: ToolType):
        self._select_tool(tool)

    def update_swatch(self, r, g, b, a):
        self.swatch.set_color(QColor(r, g, b, a))

    def update_swatch2(self, r, g, b, a):
        self.swatch2.set_color(QColor(r, g, b, a))

    def swap_colors(self):
        c1 = self.swatch._color
        c2 = self.swatch2._color
        self.swatch.set_color(c2)
        self.swatch2.set_color(c1)
        self.colors_swapped.emit()

    def add_recent_color(self, r: int, g: int, b: int, a: int):
        color = [r, g, b, a]
        if color in self._recent_colors:
            self._recent_colors.remove(color)
        self._recent_colors.insert(0, color)
        self._recent_colors = self._recent_colors[:12]
        self.recent_panel.update_colors(self._recent_colors)

    def set_recent_colors(self, colors: list):
        self._recent_colors = list(colors)
        self.recent_panel.update_colors(self._recent_colors)

    def _on_recent_selected(self, r, g, b, a):
        self.update_swatch(r, g, b, a)
        self.color_clicked.emit()

    def _color2_clicked(self):
        self.color2_clicked.emit()

    def _show_sel_popup(self):
        btn = self._tool_buttons[ToolType.SELECT]
        pos = btn.mapToGlobal(btn.rect().bottomRight())
        self._sel_popup.show_at(pos)

    def _show_shapes_popup(self):
        btn = self._tool_buttons.get(ToolType.LINE)
        if btn:
            pos = btn.mapToGlobal(btn.rect().bottomRight())
            self._shapes_popup.show_at(pos)

    def _on_shape_selected(self, icon: str, tool):
        self._current_shape = tool
        btn = self._tool_buttons.get(ToolType.LINE)
        if btn:
            btn.set_display(icon)
        for t, b in self._tool_buttons.items():
            b.set_active(t == ToolType.LINE)
        self.tool_changed.emit(tool)

    def _show_brush_popup(self):
        btn = self._tool_buttons.get(ToolType.PEN)
        if btn:
            pos = btn.mapToGlobal(btn.rect().bottomRight())
            self._brush_popup.show_at(pos)

    def _on_brush_selected(self, icon: str, tool):
        self._current_brush = tool
        btn = self._tool_buttons.get(ToolType.PEN)
        if btn:
            btn.set_display(icon)
        for t, b in self._tool_buttons.items():
            b.set_active(t == ToolType.PEN)
        self.tool_changed.emit(tool)

    # ── Helpers ───────────────────────────────────────────────────────

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setStyleSheet(
            "color: #666; font-size: 9px; background: transparent;")
        return l

    def _sep(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333333; margin: 2px 4px;")
        layout.addWidget(sep)
