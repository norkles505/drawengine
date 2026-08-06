"""
Ventana flotante de referencia — estilo Ibis Paint.
Zoom con rueda, pan con herramienta mano.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QWidget, QFileDialog
)
from PyQt6.QtGui import QPainter, QImage, QColor, QPen, QWheelEvent, QIcon
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal

from ui.icon_paths import (
    HAND_ICON, LOAD_IMAGE_ICON, LAYER_DELETE_ICON, FIT_ICON,
    ZOOM_IN_ICON, ZOOM_OUT_ICON
)


class ReferencePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image:   QImage | None = None
        self._zoom:    float         = 1.0
        self._offset:  QPoint        = QPoint(0, 0)
        self._pan_last: QPoint | None = None
        self._hand_active = False

        self.setMinimumSize(200, 180)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

     

    def set_image(self, img: QImage | None):
        self._image  = img
        self._zoom   = 1.0
        self._offset = QPoint(0, 0)
        if img is not None:
            self._fit()
        self.update()

    def _fit(self):
        if self._image is None:
            return
        zw = self.width()  / max(1, self._image.width())
        zh = self.height() / max(1, self._image.height())
        self._zoom = min(zw, zh) * 0.95
        self._center()

    def _center(self):
        if self._image is None:
            return
        dw = int(self._image.width()  * self._zoom)
        dh = int(self._image.height() * self._zoom)
        self._offset = QPoint(
            (self.width()  - dw) // 2,
            (self.height() - dh) // 2)

    def set_hand(self, active: bool):
        self._hand_active = active
        self.setCursor(Qt.CursorShape.OpenHandCursor
                       if active else Qt.CursorShape.ArrowCursor)

    def paintEvent(self, event):
        painter = QPainter(self)

        # Fondo a cuadros
        tile = 12
        for r in range(self.height() // tile + 1):
            for c in range(self.width() // tile + 1):
                v = 70 if (r + c) % 2 == 0 else 100
                painter.fillRect(c*tile, r*tile, tile, tile, QColor(v, v, v))

        if self._image is None:
            painter.setPen(QPen(QColor(120, 120, 120)))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Sin imagen\nUsa 'Cargar' para abrir una")
            painter.end()
            return

        dw = int(self._image.width()  * self._zoom)
        dh = int(self._image.height() * self._zoom)
        ox, oy = self._offset.x(), self._offset.y()
        painter.drawImage(QRect(ox, oy, dw, dh), self._image)

        # Borde sutil
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRect(ox, oy, dw, dh))

        painter.end()

    def wheelEvent(self, event: QWheelEvent):
        if self._image is None:
            return
        factor   = 1.15 if event.angleDelta().y() > 0 else 0.87
        mp       = event.position().toPoint()
        old_zoom = self._zoom
        self._zoom = max(0.05, min(20.0, self._zoom * factor))
        sc = self._zoom / old_zoom
        self._offset = QPoint(
            int(mp.x() - sc * (mp.x() - self._offset.x())),
            int(mp.y() - sc * (mp.y() - self._offset.y())))
        self.update()

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._hand_active):
            self._pan_last = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._pan_last is not None:
            self._offset += event.pos() - self._pan_last
            self._pan_last = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_last = None
            if self._hand_active:
                self.setCursor(Qt.CursorShape.OpenHandCursor)

    def resizeEvent(self, event):
        if self._image is not None and self._zoom == 1.0:
            self._fit()
        super().resizeEvent(event)


class ReferenceWindow(QDialog):
    image_loaded  = pyqtSignal(str)
    image_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Referencia")
        self.resize(300, 360)
        from ui.dark_titlebar import apply_dark_titlebar
        apply_dark_titlebar(self)
        self.setStyleSheet("""
            QDialog  { background: #202020; color: #ddd; }
            QLabel   { color: #ccc; font-size: 11px; }
            QPushButton {
                background: #282828; color: #ddd;
                border: 1px solid #3a3a3a; border-radius: 4px;
                padding: 4px 8px; font-size: 12px;
            }
            QPushButton:hover   { background: #383838; border-color: #f2801a; }
            QPushButton:pressed { background: #f2801a; }
            QPushButton:checked { background: #f2801a; border-color: #f2801a; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Preview ───────────────────────────────────────────────────
        self.preview = ReferencePreview()
        layout.addWidget(self.preview, stretch=1)

        # ── Controles ─────────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)

        self.btn_hand = QPushButton()
        self.btn_hand.setIcon(QIcon(HAND_ICON))
        self.btn_hand.setIconSize(QSize(18, 18))
        self.btn_hand.setToolTip("Mano — arrastrar imagen")
        self.btn_hand.setCheckable(True)
        self.btn_hand.setFixedSize(36, 32)
        self.btn_hand.toggled.connect(self.preview.set_hand)
        ctrl.addWidget(self.btn_hand)

        ctrl.addSpacing(8)

        btn_minus = QPushButton()
        btn_minus.setIcon(QIcon(ZOOM_OUT_ICON))
        btn_minus.setIconSize(QSize(16, 16))
        btn_minus.setFixedSize(32, 32)
        btn_minus.setToolTip("Alejar")
        btn_minus.clicked.connect(self._zoom_out)
        ctrl.addWidget(btn_minus)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(44)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl.addWidget(self.lbl_zoom)

        btn_plus = QPushButton()
        btn_plus.setIcon(QIcon(ZOOM_IN_ICON))
        btn_plus.setIconSize(QSize(16, 16))
        btn_plus.setFixedSize(32, 32)
        btn_plus.setToolTip("Acercar")
        btn_plus.clicked.connect(self._zoom_in)
        ctrl.addWidget(btn_plus)

        btn_fit = QPushButton()
        btn_fit.setIcon(QIcon(FIT_ICON))
        btn_fit.setIconSize(QSize(16, 16))
        btn_fit.setFixedSize(32, 32)
        btn_fit.setToolTip("Ajustar")
        btn_fit.clicked.connect(self._fit)
        ctrl.addWidget(btn_fit)

        ctrl.addStretch()

        self.btn_load = QPushButton()
        self.btn_load.setIcon(QIcon(LOAD_IMAGE_ICON))
        self.btn_load.setIconSize(QSize(18, 18))
        self.btn_load.setFixedSize(32, 32)
        self.btn_load.setToolTip("Cargar imagen")
        self.btn_load.clicked.connect(self._load)
        ctrl.addWidget(self.btn_load)

        self.btn_clear = QPushButton()
        self.btn_clear.setIcon(QIcon(LAYER_DELETE_ICON))
        self.btn_clear.setIconSize(QSize(18, 18))
        self.btn_clear.setFixedSize(32, 32)
        self.btn_clear.setToolTip("Quitar imagen")
        self.btn_clear.clicked.connect(self._clear)
        ctrl.addWidget(self.btn_clear)

        layout.addLayout(ctrl)

        # Actualizar label de zoom cuando cambia la rueda
        self.preview.wheelEvent = self._wheel_and_update(
            self.preview.wheelEvent)

    def _wheel_and_update(self, original_fn):
        def wrapped(event):
            original_fn(event)
            self._update_zoom_label()
        return wrapped

    def _zoom_in(self):
        self.preview._zoom = min(20.0, self.preview._zoom * 1.2)
        self.preview._center()
        self.preview.update()
        self._update_zoom_label()

    def _zoom_out(self):
        self.preview._zoom = max(0.05, self.preview._zoom / 1.2)
        self.preview._center()
        self.preview.update()
        self._update_zoom_label()

    def _fit(self):
        self.preview._fit()
        self.preview.update()
        self._update_zoom_label()

    def _update_zoom_label(self):
        pct = int(self.preview._zoom * 100)
        self.lbl_zoom.setText(f"{pct}%")

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar imagen de referencia", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.image_loaded.emit(path)

    def _clear(self):
        self.preview.set_image(None)
        self.image_cleared.emit()

    def update_preview(self, img: QImage | None):
        self.preview.set_image(img)
        self._update_zoom_label()
