from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QAbstractItemView,
    QSlider, QComboBox, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect
from PyQt6.QtGui import (
    QFont, QPainter, QColor, QImage, QPixmap, QBrush, QIcon
)
from core.tools import BlendMode
from ui.button_styles import ICON_BUTTON_STYLE
from ui.icon_paths import (
    LAYER_ADD_ICON, LAYER_DELETE_ICON, LAYER_UP_ICON, LAYER_DOWN_ICON
)


class LayerItemWidget(QWidget):
    """
    Widget personalizado para cada item de capa:
    - Miniatura
    - Nombre (editable con doble click)
    - Checkbox de visibilidad
    - Slider de opacidad
    - Combo de blend mode
    """
    visibility_changed = pyqtSignal(bool)
    opacity_changed    = pyqtSignal(int)    # 0-255
    blend_changed      = pyqtSignal(object) # BlendMode
    rename_requested   = pyqtSignal(str)

    def __init__(self, name: str, visible: bool,
                 opacity: int, blend_mode: BlendMode,
                 thumbnail: QImage | None = None,
                 parent=None):
        super().__init__(parent)
        self.setFixedHeight(68)
        self._build_ui(name, visible, opacity, blend_mode, thumbnail)

    def _build_ui(self, name, visible, opacity, blend_mode, thumbnail):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(4)

        # ── Miniatura ─────────────────────────────────────────────────
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(48, 48)
        self.lbl_thumb.setStyleSheet(
            "border: 1px solid #444; border-radius: 3px;"
            "background: #111;")
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if thumbnail and not thumbnail.isNull():
            self._set_thumb(thumbnail)
        else:
            self.lbl_thumb.setText("—")
        layout.addWidget(self.lbl_thumb)

        # ── Columna central ───────────────────────────────────────────
        center = QVBoxLayout()
        center.setSpacing(2)
        center.setContentsMargins(0, 0, 0, 0)

        # Fila superior: checkbox + nombre
        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        self.chk_visible = QPushButton()
        self.chk_visible.setCheckable(True)
        self.chk_visible.setChecked(visible)
        self.chk_visible.setFixedSize(18, 18)
        self.chk_visible.setToolTip("Toggle visibility")
        self.chk_visible.setStyleSheet("""
            QPushButton {
                background: #333; border: 1px solid #555;
                border-radius: 3px; font-size: 10px; color: #aaa;
            }
            QPushButton:checked {
                background: #f2801a; border: 1px solid #f2801a;
                color: white;
            }
        """)
        self.chk_visible.setText("👁" if visible else "")
        self.chk_visible.toggled.connect(self._on_visibility)
        top_row.addWidget(self.chk_visible)

        self.lbl_name = QLabel(name)
        self.lbl_name.setStyleSheet(
            "color: #ffffff; font-size: 11px; font-weight: bold;")
        self.lbl_name.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lbl_name.mouseDoubleClickEvent = self._on_double_click
        top_row.addWidget(self.lbl_name)
        center.addLayout(top_row)

        # Fila media: opacidad
        op_row = QHBoxLayout()
        op_row.setSpacing(3)
        lbl_op = QLabel("Op")
        lbl_op.setStyleSheet("color: #666; font-size: 9px;")
        lbl_op.setFixedWidth(14)
        op_row.addWidget(lbl_op)

        self.slider_op = QSlider(Qt.Orientation.Horizontal)
        self.slider_op.setRange(0, 255)
        self.slider_op.setValue(opacity)
        self.slider_op.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #333; height: 4px; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #f2801a; width: 10px; height: 10px;
                margin: -3px 0; border-radius: 5px;
            }
            QSlider::sub-page:horizontal {
                background: #f2801a; border-radius: 2px;
            }
        """)
        self.slider_op.valueChanged.connect(self._on_opacity)
        op_row.addWidget(self.slider_op)

        self.lbl_op_val = QLabel(f"{int(opacity/255*100)}%")
        self.lbl_op_val.setFixedWidth(30)
        self.lbl_op_val.setStyleSheet("color:#888; font-size:9px;")
        op_row.addWidget(self.lbl_op_val)
        center.addLayout(op_row)

        # Fila inferior: blend mode
        self.combo_blend = QComboBox()
        for mode in BlendMode:
            self.combo_blend.addItem(mode.value, mode)
        # Seleccionar el blend mode actual
        for i in range(self.combo_blend.count()):
            if self.combo_blend.itemData(i) == blend_mode:
                self.combo_blend.setCurrentIndex(i)
                break
        self.combo_blend.setFixedHeight(18)
        self.combo_blend.setStyleSheet("""
            QComboBox {
                background: #282828; color: #aaa;
                border: 1px solid #3a3a3a; border-radius: 3px;
                font-size: 9px; padding: 0 2px;
            }
            QComboBox:hover { border: 1px solid #f2801a; }
            QComboBox QAbstractItemView {
                background: #282828; color: #eee;
                selection-background-color: #f2801a;
                font-size: 10px;
            }
        """)
        self.combo_blend.currentIndexChanged.connect(self._on_blend)
        center.addWidget(self.combo_blend)

        layout.addLayout(center)

    # ── Actualizar miniatura ──────────────────────────────────────────

    def _set_thumb(self, img: QImage):
        pix = QPixmap.fromImage(img).scaled(
            46, 46,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self.lbl_thumb.setPixmap(pix)

    def update_thumbnail(self, img: QImage):
        if img and not img.isNull():
            self._set_thumb(img)

    def update_name(self, name: str):
        self.lbl_name.setText(name)

    def update_opacity(self, opacity: int):
        self.slider_op.blockSignals(True)
        self.slider_op.setValue(opacity)
        self.slider_op.blockSignals(False)
        self.lbl_op_val.setText(f"{int(opacity/255*100)}%")

    def update_visibility(self, visible: bool):
        self.chk_visible.blockSignals(True)
        self.chk_visible.setChecked(visible)
        self.chk_visible.setText("👁" if visible else "")
        self.chk_visible.blockSignals(False)

    # ── Señales ───────────────────────────────────────────────────────

    def _on_visibility(self, checked: bool):
        self.chk_visible.setText("👁" if checked else "")
        self.visibility_changed.emit(checked)

    def _on_opacity(self, val: int):
        self.lbl_op_val.setText(f"{int(val/255*100)}%")
        self.opacity_changed.emit(val)

    def _on_blend(self, _):
        self.blend_changed.emit(self.combo_blend.currentData())

    def _on_double_click(self, event):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Rename Layer", "Layer name:",
            text=self.lbl_name.text())
        if ok and name.strip():
            self.lbl_name.setText(name.strip())
            self.rename_requested.emit(name.strip())


class LayerPanel(QWidget):
    layer_selected           = pyqtSignal(int)
    layer_added              = pyqtSignal()
    layer_deleted            = pyqtSignal(int)
    layer_visibility_changed = pyqtSignal(int, bool)
    layer_opacity_changed    = pyqtSignal(int, int)   # panel_idx, 0-255
    layer_blend_changed      = pyqtSignal(int, object)
    layer_renamed            = pyqtSignal(int, str)
    layer_reordered          = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(204)
        self.setStyleSheet("background: #202020;")
        self._item_widgets: list[LayerItemWidget] = []
        self._active_index = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        # Título
        title = QLabel("Layers")
        title.setStyleSheet(
            "color: #f2801a; font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Botones
        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        self.btn_add  = self._icon_btn(LAYER_ADD_ICON,    "Add layer")
        self.btn_del  = self._icon_btn(LAYER_DELETE_ICON, "Delete layer")
        self.btn_up   = self._icon_btn(LAYER_UP_ICON,     "Move up")
        self.btn_down = self._icon_btn(LAYER_DOWN_ICON,   "Move down")
        for btn in (self.btn_add, self.btn_del,
                    self.btn_up, self.btn_down):
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.btn_add.clicked.connect(self.layer_added.emit)
        self.btn_del.clicked.connect(self._on_delete)
        self.btn_up.clicked.connect(self._on_move_up)
        self.btn_down.clicked.connect(self._on_move_down)

        # Lista de capas
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setSpacing(2)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: #202020; border: none;
            }
            QListWidget::item {
                background: #282828;
                border: 1px solid #333;
                border-radius: 4px;
                margin: 1px 0;
            }
            QListWidget::item:selected {
                background: #3a2a15;
                border: 1px solid #f2801a;
            }
        """)
        self.list_widget.currentRowChanged.connect(
            self._on_row_changed)
        self.list_widget.model().rowsMoved.connect(
            self._on_rows_moved)
        layout.addWidget(self.list_widget)

        hint = QLabel("Double-click to rename · Drag to reorder")
        hint.setStyleSheet("color: #444; font-size: 9px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    # ── Refresh ───────────────────────────────────────────────────────

    def refresh(self, layers, active_index: int):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self._item_widgets.clear()
        self._active_index = active_index

        for i, layer in enumerate(reversed(layers)):
            panel_idx = i
            real_idx  = len(layers) - 1 - i

            # Miniatura de la capa
            thumb = self._make_thumb(layer)

            item   = QListWidgetItem(self.list_widget)
            widget = LayerItemWidget(
                name       = layer.name,
                visible    = layer.visible,
                opacity    = layer.opacity,
                blend_mode = getattr(layer, 'blend_mode',
                                     BlendMode.NORMAL),
                thumbnail  = thumb,
            )

            # Conectar señales con el índice del panel
            widget.visibility_changed.connect(
                lambda v, pi=panel_idx:
                self.layer_visibility_changed.emit(pi, v))
            widget.opacity_changed.connect(
                lambda v, pi=panel_idx:
                self.layer_opacity_changed.emit(pi, v))
            widget.blend_changed.connect(
                lambda m, pi=panel_idx:
                self.layer_blend_changed.emit(pi, m))
            widget.rename_requested.connect(
                lambda n, pi=panel_idx:
                self.layer_renamed.emit(pi, n))

            item.setSizeHint(QSize(190, 72))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)
            self._item_widgets.append(widget)

        # Seleccionar capa activa
        active_panel = len(layers) - 1 - active_index
        self.list_widget.setCurrentRow(active_panel)
        self.list_widget.blockSignals(False)

    def _make_thumb(self, layer) -> QImage:
        """Genera miniatura 46×46 de la capa."""
        w, h = layer.width, layer.height
        img  = layer.image
        # Fondo tablero
        thumb_size = 46
        result = QImage(thumb_size, thumb_size,
                        QImage.Format.Format_ARGB32)
        painter = QPainter(result)
        tile = 8
        for r in range(thumb_size // tile + 1):
            for c in range(thumb_size // tile + 1):
                col = QColor(180,180,180) if (r+c)%2==0 \
                    else QColor(220,220,220)
                painter.fillRect(c*tile, r*tile, tile, tile, col)
        scaled = img.scaled(thumb_size, thumb_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        ox = (thumb_size - scaled.width())  // 2
        oy = (thumb_size - scaled.height()) // 2
        painter.drawImage(ox, oy, scaled)
        painter.end()
        return result

    # ── Botones ───────────────────────────────────────────────────────

    def _on_delete(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.layer_deleted.emit(row)

    def _on_move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            self.layer_reordered.emit(row, row - 1)

    def _on_move_down(self):
        row = self.list_widget.currentRow()
        if row >= 0 and row < self.list_widget.count() - 1:
            self.layer_reordered.emit(row, row + 1)

    def _on_row_changed(self, row: int):
        if row >= 0:
            self.layer_selected.emit(row)

    def _on_rows_moved(self, parent, start, end, dest, row):
        to = row if row <= start else row - 1
        self.layer_reordered.emit(start, to)

    def _icon_btn(self, icon_path, tooltip=""):
        btn = QPushButton()
        btn.setIcon(QIcon(icon_path))
        btn.setIconSize(QSize(14, 14))
        btn.setFixedSize(28, 28)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(ICON_BUTTON_STYLE)
        return btn
