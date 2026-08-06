from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QPen


# ── Conversiones de color ──────────────────────────────────────────

def rgb_to_lab(r, g, b):
    def _lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    rl, gl, bl = _lin(r), _lin(g), _lin(b)
    x = rl * 0.4124 + gl * 0.3576 + bl * 0.1805
    y = rl * 0.2126 + gl * 0.7152 + bl * 0.0722
    z = rl * 0.0193 + gl * 0.1192 + bl * 0.9505

    x /= 0.95047
    z /= 1.08883

    def _f(t):
        return t ** (1/3) if t > 0.008856 else (7.787 * t) + (16/116)

    fx, fy, fz = _f(x), _f(y), _f(z)
    L = max(0.0, (116 * fy) - 16)
    a = (fx - fy) * 500
    bb = (fy - fz) * 200
    return L, a, bb


def lab_to_rgb(L, a, b):
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200

    def _finv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16/116) / 7.787

    x = _finv(fx) * 0.95047
    y = _finv(fy)
    z = _finv(fz) * 1.08883

    rl =  x * 3.2406 + y * -1.5372 + z * -0.4986
    gl = -x * 0.9689 + y * 1.8758  + z * 0.0415
    bl =  x * 0.0557 + y * -0.2040 + z * 1.0570

    def _gamma(c):
        c = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1/2.4)) - 0.055
        return max(0, min(255, round(c * 255)))

    return _gamma(rl), _gamma(gl), _gamma(bl)


def rgb_to_cmyk(r, g, b):
    if r == 0 and g == 0 and b == 0:
        return 0, 0, 0, 100
    rf, gf, bf = r/255, g/255, b/255
    k = 1 - max(rf, gf, bf)
    c = (1 - rf - k) / (1 - k) if k < 1 else 0
    m = (1 - gf - k) / (1 - k) if k < 1 else 0
    y = (1 - bf - k) / (1 - k) if k < 1 else 0
    return round(c*100), round(m*100), round(y*100), round(k*100)


def cmyk_to_rgb(c, m, y, k):
    c, m, y, k = c/100, m/100, y/100, k/100
    r = 255 * (1-c) * (1-k)
    g = 255 * (1-m) * (1-k)
    b = 255 * (1-y) * (1-k)
    return round(r), round(g), round(b)


def snap_websafe(v: int) -> int:
    steps = [0, 51, 102, 153, 204, 255]
    return min(steps, key=lambda s: abs(s - v))


# ── Widgets de selección ────────────────────────────────────────────

class SVSquare(QWidget):
    sv_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(256, 256)
        self._hue = 0
        self._sat = 255
        self._val = 255
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_hue(self, hue: int):
        self._hue = hue
        self.update()

    def set_sv(self, s: int, v: int):
        self._sat = s
        self._val = v
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        grad_h = QLinearGradient(0, 0, w, 0)
        grad_h.setColorAt(0, QColor(255, 255, 255))
        grad_h.setColorAt(1, QColor.fromHsv(self._hue, 255, 255))
        painter.fillRect(0, 0, w, h, grad_h)

        grad_v = QLinearGradient(0, 0, 0, h)
        grad_v.setColorAt(0, QColor(0, 0, 0, 0))
        grad_v.setColorAt(1, QColor(0, 0, 0, 255))
        painter.fillRect(0, 0, w, h, grad_v)

        painter.setPen(QPen(QColor("#3a3a3a"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        ix = int(self._sat / 255 * (w - 1))
        iy = int((1 - self._val / 255) * (h - 1))

        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ix - 5, iy - 5, 10, 10)
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawEllipse(ix - 4, iy - 4, 8, 8)
        painter.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._update_from_pos(e.pos())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._update_from_pos(e.pos())

    def _update_from_pos(self, pos: QPoint):
        w, h = self.width(), self.height()
        x = max(0, min(w, pos.x()))
        y = max(0, min(h, pos.y()))
        s = max(0, min(255, int(x / w * 255)))
        v = max(0, min(255, int((1 - y / h) * 255)))
        self._sat, self._val = s, v
        self.sv_changed.emit(s, v)
        self.update()


class HueBar(QWidget):
    hue_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 256)
        self._hue = 0
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_hue(self, hue: int):
        self._hue = hue % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bar_x, bar_w = 7, 16

        grad = QLinearGradient(0, 0, 0, h)
        colors = [
            QColor(255, 0, 0), QColor(255, 0, 255), QColor(0, 0, 255),
            QColor(0, 255, 255), QColor(0, 255, 0), QColor(255, 255, 0), QColor(255, 0, 0)
        ]
        for i, col in enumerate(colors):
            grad.setColorAt(i / 6, col)

        painter.fillRect(bar_x, 0, bar_w, h, grad)
        painter.setPen(QPen(QColor("#555"), 1))
        painter.drawRect(bar_x, 0, bar_w - 1, h - 1)

        y = int(self._hue / 359 * (h - 1))

        painter.setPen(QPen(QColor("#111"), 1))
        painter.setBrush(QColor("#eee"))

        left_arrow = [QPoint(1, y - 4), QPoint(bar_x - 1, y), QPoint(1, y + 4)]
        painter.drawPolygon(left_arrow)

        right_x = bar_x + bar_w
        right_arrow = [QPoint(w - 2, y - 4), QPoint(right_x, y), QPoint(w - 2, y + 4)]
        painter.drawPolygon(right_arrow)
        painter.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._update_from_pos(e.pos())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._update_from_pos(e.pos())

    def _update_from_pos(self, pos: QPoint):
        h = self.height()
        y = max(0, min(h, pos.y()))
        hue = max(0, min(359, int(y / h * 359)))
        self._hue = hue
        self.hue_changed.emit(hue)
        self.update()


class SwatchPreview(QWidget):
    revert_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 68)
        self._new_color  = QColor(0, 0, 0)
        self._old_color  = QColor(0, 0, 0)

    def set_colors(self, new_c: QColor, old_c: QColor):
        self._new_color = new_c
        self._old_color = old_c
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor("#111"), 1))
        painter.setBrush(self._new_color)
        painter.drawRect(0, 0, 59, 33)

        painter.setBrush(self._old_color)
        painter.drawRect(0, 33, 59, 33)

        painter.end()

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if e.pos().x() < 60 and e.pos().y() > 33:
            self.revert_clicked.emit()


# ── Diálogo Principal ────────────────────────────────────────────────
#
# Reconstruido desde cero con QGridLayout para los campos (mucho más
# predecible que layouts anidados a mano) y TODO el espaciado/tamaño
# controlado por las constantes de la clase, abajo. El diálogo NO usa
# tamaño fijo de antemano: se construye primero y al final se ajusta
# exactamente a lo que ocupa su contenido (self.sizeHint()), así que
# tocar cualquier constante de aquí abajo NUNCA corta ni aplasta nada
# — el diálogo simplemente crece o se achica solo.
#
# IMPORTANTE: cada vez que un sub-layout (grid, HBox, VBox) se agrega
# a otro con addLayout(), Qt lo estira para llenar TODO el espacio
# disponible en el eje perpendicular a menos que se fije la alineación
# explícitamente. Por eso cada addLayout() de acá abajo va seguido de
# un setAlignment(..., AlignTop): así cada bloque ocupa solo su alto
# natural y no aparecen huecos gigantes o desparejos entre filas.
#
# Para editar la interfaz: cambia solo los números de esta sección.

class ColorPickerDialog(QDialog):
    color_selected = pyqtSignal(QColor)

    # ── Márgenes exteriores del diálogo ─────────────────────────
    MARGIN_LEFT    = 10
    MARGIN_TOP     = 16
    MARGIN_RIGHT   = 18
    MARGIN_BOTTOM  = 16

    # ── Título ────────────────────────────────────────────────────
    GAP_TITLE_TO_CONTENT = 6    # texto "Seleccione el color frontal:" ↔ contenido

    # ── Espaciados entre bloques grandes ─────────────────────────
    GAP_SV_TO_HUE      = 14   # cuadrado SV        ↔  barra de matiz
    GAP_HUE_TO_PANEL   = 4    # barra de matiz      ↔  panel derecho
    GAP_SWATCH_TO_BTNS = 16   # swatch              ↔  columna de botones
    GAP_TOP_TO_FIELDS  = 15   # swatch/botones      ↔  fila de campos
    GAP_FIELDS_TO_HEX  = 12   # fila R/G/B          ↔  fila hexadecimal (dentro de la misma columna)
    GAP_COLUMNS        = 40   # columna HSB/RGB     ↔  columna Lab/CMYK

    # ── Botones (OK / Cancelar / Añadir a muestras / Bibliotecas) ──
    BTN_WIDTH        = 130
    BTN_HEIGHT       = 22
    BTN_GAP          = 8    # espacio entre botones del mismo grupo
    BTN_GROUP_GAP    = 14   # espacio entre grupo OK/Cancelar y grupo Muestras/Bibliotecas

    # ── Filas de campos (H,S,B / R,G,B / L,a,b / C,M,Y,K / Hex) ──
    FIELD_LABEL_W    = 18
    FIELD_INPUT_W    = 52
    FIELD_INPUT_H    = 24
    FIELD_SUFFIX_W   = 16
    FIELD_H_SPACING  = 6    # espacio horizontal entre label/input/sufijo
    FIELD_ROW_GAP    = 4    # espacio vertical entre filas del mismo grupo
    FIELD_GROUP_GAP  = 12   # espacio vertical entre grupos (H/S/B → R/G/B, etc.)

    # ── Campo hexadecimal (usa el mismo ancho de columna que R/G/B) ─
    HEX_INPUT_W = 74
    HEX_INPUT_H = 24

    def __init__(self, initial: QColor = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selector de color (color frontal)")
        self.setModal(True)
        self.setObjectName("colorPickerDialog")
        self.setSizeGripEnabled(False)
        try:
            from ui.dark_titlebar import apply_dark_titlebar
            apply_dark_titlebar(self)
        except ImportError:
            pass
        self.setStyleSheet(self._style())

        c          = initial or QColor(0, 0, 0, 255)
        h, s, v, _ = c.getHsv()
        self._h    = max(0, h)
        self._s    = s
        self._v    = v
        self._a    = c.alpha()
        self._old  = QColor(c)
        self._updating = False
        self._fields = {}
        self._build_ui()
        self._update_all()

        # El diálogo se ajusta exactamente al contenido recién armado.
        # Cambiar cualquier constante de arriba nunca corta nada: el
        # diálogo simplemente sale más grande o más chico.
        self.setFixedSize(self.sizeHint())

    # ── Helper: una fila de campo dentro de un QGridLayout ─────────

    def _field_row(self, grid: QGridLayout, row: int,
                    field_key: str, label_text: str,
                    suffix_text: str = ""):
        col = 0

        lbl = QLabel(label_text)
        lbl.setFixedWidth(self.FIELD_LABEL_W)
        grid.addWidget(lbl, row, col)
        col += 1

        inp = QLineEdit()
        inp.setFixedSize(self.FIELD_INPUT_W, self.FIELD_INPUT_H)
        inp.setStyleSheet(self._input_style())
        grid.addWidget(inp, row, col)
        self._fields[field_key] = inp
        col += 1

        suf = QLabel(suffix_text)
        suf.setFixedWidth(self.FIELD_SUFFIX_W)
        grid.addWidget(suf, row, col)

    def _build_field_column(self, first_group, second_group) -> QGridLayout:
        """Arma una columna de campos con dos grupos separados por
        FIELD_GROUP_GAP de espacio vertical. Cada grupo es una lista
        de (field_key, label, suffix)."""
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(self.FIELD_H_SPACING)
        grid.setVerticalSpacing(self.FIELD_ROW_GAP)
        grid.setSizeConstraint(QGridLayout.SizeConstraint.SetFixedSize)

        row = 0
        for key, label, suffix in first_group:
            self._field_row(grid, row, key, label, suffix)
            row += 1

        grid.setRowMinimumHeight(row, self.FIELD_GROUP_GAP)
        row += 1

        for key, label, suffix in second_group:
            self._field_row(grid, row, key, label, suffix)
            row += 1

        return grid

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            self.MARGIN_LEFT, self.MARGIN_TOP,
            self.MARGIN_RIGHT, self.MARGIN_BOTTOM)
        main_layout.setSpacing(0)

        # ── Título ────────────────────────────────────────────────
        lbl_title = QLabel("Seleccione el color frontal:")
        main_layout.addWidget(lbl_title)
        main_layout.addSpacing(self.GAP_TITLE_TO_CONTENT)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # ── Visualizadores (Cuadrado SV + Barra H) ──────────────────
        self.sv_square = SVSquare()
        self.sv_square.sv_changed.connect(self._on_sv)
        content_layout.addWidget(self.sv_square)
        content_layout.addSpacing(self.GAP_SV_TO_HUE)

        self.hue_bar = HueBar()
        self.hue_bar.hue_changed.connect(self._on_hue)
        content_layout.addWidget(self.hue_bar)
        content_layout.addSpacing(self.GAP_HUE_TO_PANEL)

        # ── Panel Medio/Derecho ─────────────────────────────────────
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(0, 0, 0, 0)
        right_panel.setSpacing(0)

        # Swatch + Botones Superiores
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)

        self.swatches = SwatchPreview()
        self.swatches.revert_clicked.connect(self._on_revert)
        top_row.addWidget(self.swatches)
        top_row.addSpacing(self.GAP_SWATCH_TO_BTNS)

        btn_box = QVBoxLayout()
        btn_box.setContentsMargins(0, 0, 0, 0)
        btn_box.setSpacing(self.BTN_GAP)

        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self._accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_swatch = QPushButton("Añadir a muestras")
        btn_lib = QPushButton("Bibliotecas de colores")

        for b in (btn_ok, btn_cancel, btn_swatch, btn_lib):
            b.setFixedSize(self.BTN_WIDTH, self.BTN_HEIGHT)

        btn_ok.setStyleSheet(self._btn_style("#f2801a", "#ff9d40", bold=True))
        btn_cancel.setStyleSheet(self._btn_style("#333", "#444"))
        btn_swatch.setStyleSheet(self._btn_style("#333", "#444"))
        btn_lib.setStyleSheet(self._btn_style("#333", "#444"))

        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        btn_box.addSpacing(self.BTN_GROUP_GAP)
        btn_box.addWidget(btn_swatch)
        btn_box.addWidget(btn_lib)
        btn_box.addStretch()

        top_row.addLayout(btn_box)
        top_row.setAlignment(btn_box, Qt.AlignmentFlag.AlignTop)
        top_row.addStretch()
        right_panel.addLayout(top_row)
        right_panel.setAlignment(top_row, Qt.AlignmentFlag.AlignTop)
        right_panel.addSpacing(self.GAP_TOP_TO_FIELDS)

        # ── Campos de color: dos columnas (HSB/RGB/Hex | Lab/CMYK) ───
        fields_row = QHBoxLayout()
        fields_row.setContentsMargins(0, 0, 0, 0)
        fields_row.setSpacing(self.GAP_COLUMNS)

        left_grid = self._build_field_column(
            first_group=[
                ("h", "H:", "°"),
                ("s", "S:", "%"),
                ("v", "B:", "%"),
            ],
            second_group=[
                ("r",     "R:", ""),
                ("g",     "G:", ""),
                ("b_rgb", "B:", ""),
            ],
        )

        # Fila hexadecimal: va debajo de R/G/B, en la misma columna,
        # así queda alineada igual que en el selector de referencia.
        hex_row = left_grid.rowCount()
        left_grid.setRowMinimumHeight(hex_row, self.GAP_FIELDS_TO_HEX)
        hex_row += 1

        lbl_hex = QLabel("#")
        lbl_hex.setFixedWidth(self.FIELD_LABEL_W)
        left_grid.addWidget(lbl_hex, hex_row, 0)

        self.hex_edit = QLineEdit()
        self.hex_edit.setMaxLength(6)
        self.hex_edit.setFixedSize(self.HEX_INPUT_W, self.HEX_INPUT_H)
        self.hex_edit.setStyleSheet(self._input_style())
        self.hex_edit.editingFinished.connect(self._on_hex)
        left_grid.addWidget(self.hex_edit, hex_row, 1)

        right_grid = self._build_field_column(
            first_group=[
                ("L", "L:", ""),
                ("a", "a:", ""),
                ("b", "b:", ""),
            ],
            second_group=[
                ("c", "C:", "%"),
                ("m", "M:", "%"),
                ("y", "Y:", "%"),
                ("k", "K:", "%"),
            ],
        )

        fields_row.addLayout(left_grid)
        fields_row.setAlignment(left_grid, Qt.AlignmentFlag.AlignTop)
        fields_row.addLayout(right_grid)
        fields_row.setAlignment(right_grid, Qt.AlignmentFlag.AlignTop)
        fields_row.addStretch()
        right_panel.addLayout(fields_row)
        right_panel.setAlignment(fields_row, Qt.AlignmentFlag.AlignTop)
        right_panel.addStretch()

        content_layout.addLayout(right_panel)
        content_layout.setAlignment(right_panel, Qt.AlignmentFlag.AlignTop)
        main_layout.addLayout(content_layout)

        # Conexiones de Edición en Entradas
        for k in ("h", "s", "v"):
            self._fields[k].editingFinished.connect(self._on_field_hsv)
        for k in ("L", "a", "b"):
            self._fields[k].editingFinished.connect(self._on_field_lab)
        for k in ("r", "g", "b_rgb"):
            self._fields[k].editingFinished.connect(self._on_field_rgb)
        for k in ("c", "m", "y", "k"):
            self._fields[k].editingFinished.connect(self._on_field_cmyk)

    # ── Manejo de Eventos ────────────────────────────────────────────

    def _on_hue(self, h: int):
        self._h = h
        self.sv_square.set_hue(h)
        self._update_all()

    def _on_sv(self, s: int, v: int):
        self._s = s
        self._v = v
        self._update_all()

    def _on_revert(self):
        h, s, v, _ = self._old.getHsv()
        self._h, self._s, self._v = max(0, h), s, v
        self._a = self._old.alpha()
        self._update_all()

    def _on_field_hsv(self):
        if self._updating: return
        try:
            h = int(self._fields["h"].text() or 0) % 360
            s = int(self._fields["s"].text() or 0)
            v = int(self._fields["v"].text() or 0)
            self._h = h
            self._s = int(max(0, min(100, s)) / 100 * 255)
            self._v = int(max(0, min(100, v)) / 100 * 255)
            self._update_all(skip="hsv")
        except ValueError:
            pass

    def _on_field_lab(self):
        if self._updating: return
        try:
            L = float(self._fields["L"].text() or 0)
            a = float(self._fields["a"].text() or 0)
            b = float(self._fields["b"].text() or 0)
            r, g, bch = lab_to_rgb(L, a, b)
            c = QColor(r, g, bch)
            h, s, v, _ = c.getHsv()
            self._h, self._s, self._v = max(0, h), s, v
            self._update_all(skip="lab")
        except ValueError:
            pass

    def _on_field_rgb(self):
        if self._updating: return
        try:
            r = int(self._fields["r"].text() or 0)
            g = int(self._fields["g"].text() or 0)
            b = int(self._fields["b_rgb"].text() or 0)
            c = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
            h, s, v, _ = c.getHsv()
            self._h, self._s, self._v = max(0, h), s, v
            self._update_all(skip="rgb")
        except ValueError:
            pass

    def _on_field_cmyk(self):
        if self._updating: return
        try:
            c_ = int(self._fields["c"].text() or 0)
            m_ = int(self._fields["m"].text() or 0)
            y_ = int(self._fields["y"].text() or 0)
            k_ = int(self._fields["k"].text() or 0)
            r, g, b = cmyk_to_rgb(c_, m_, y_, k_)
            c = QColor(r, g, b)
            h, s, v, _ = c.getHsv()
            self._h, self._s, self._v = max(0, h), s, v
            self._update_all(skip="cmyk")
        except ValueError:
            pass

    def _on_hex(self):
        txt = self.hex_edit.text().strip().lstrip("#")
        try:
            if len(txt) == 6:
                c = QColor(f"#{txt}")
                h, s, v, _ = c.getHsv()
                self._h, self._s, self._v = max(0, h), s, v
                self._update_all(skip="hex")
        except Exception:
            pass

    def _accept(self):
        self.color_selected.emit(self.current_color())
        self.accept()

    def current_color(self) -> QColor:
        return QColor.fromHsv(self._h, self._s, self._v, self._a)

    def _update_all(self, skip: str = ""):
        self._updating = True
        c = self.current_color()

        self.swatches.set_colors(c, self._old)
        self.hue_bar.set_hue(self._h)
        self.sv_square.set_hue(self._h)
        self.sv_square.set_sv(self._s, self._v)

        if skip != "hsv":
            self._fields["h"].setText(str(self._h))
            self._fields["s"].setText(str(round(self._s / 255 * 100)))
            self._fields["v"].setText(str(round(self._v / 255 * 100)))

        if skip != "rgb":
            self._fields["r"].setText(str(c.red()))
            self._fields["g"].setText(str(c.green()))
            self._fields["b_rgb"].setText(str(c.blue()))

        if skip != "lab":
            L, a, b = rgb_to_lab(c.red(), c.green(), c.blue())
            self._fields["L"].setText(str(round(L)))
            self._fields["a"].setText(str(round(a)))
            self._fields["b"].setText(str(round(b)))

        if skip != "cmyk":
            cc, mm, yy, kk = rgb_to_cmyk(c.red(), c.green(), c.blue())
            self._fields["c"].setText(str(cc))
            self._fields["m"].setText(str(mm))
            self._fields["y"].setText(str(yy))
            self._fields["k"].setText(str(kk))

        if skip != "hex":
            self.hex_edit.setText(f"{c.red():02x}{c.green():02x}{c.blue():02x}")

        self._updating = False

    # ── Estilos Oscuros ────────────────────────────────────────────────

    def _btn_style(self, bg, hover, bold=False):
        weight = "bold" if bold else "normal"
        return f"""
            QPushButton {{
                background: {bg}; color: white;
                border: none; border-radius: 4px;
                font-size: 11px; font-weight: {weight};
                padding: 0 8px;
            }}
            QPushButton:hover {{ background: {hover}; }}
        """

    def _input_style(self):
        return """
            QLineEdit {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 3px;
                padding: 1px 3px; font-size: 11px;
                font-family: monospace;
            }
            QLineEdit:focus {
                border: 1px solid #0078d7;
            }
        """

    def _style(self):
        return """
            #colorPickerDialog { background: #202020; }
            #colorPickerDialog QLabel   { color: #ccc; font-size: 11px; background: transparent; }
        """
