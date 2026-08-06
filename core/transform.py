

import numpy as np
from PyQt6.QtCore import QPoint, QRect, QPointF, Qt
from PyQt6.QtGui import QImage, QPainter, QTransform, QColor, QPen
import math


class TransformHandle:
    """Un handle de transformación (esquina o borde)."""
    CORNER_TL = 0
    CORNER_TR = 1
    CORNER_BR = 2
    CORNER_BL = 3
    EDGE_T    = 4
    EDGE_R    = 5
    EDGE_B    = 6
    EDGE_L    = 7
    ROTATE    = 8   # handle de rotación encima del centro

    SIZE = 10   # píxeles del handle en pantalla


class TransformBox:
    """
    Caja de transformación interactiva.
    Guarda el estado original y aplica la transformación en preview.
    """

  

    def __init__(self, arr: np.ndarray, x: int, y: int,
                 mask: np.ndarray | None = None):
       
        self._orig_arr  = arr.copy()
        self._orig_x    = x
        self._orig_y    = y
        self._orig_w    = arr.shape[1]
        self._orig_h    = arr.shape[0]
        self._mask = mask.copy() if mask is not None else None


        # Estado actual de la transformación
        self.x:       float = float(x)
        self.y:       float = float(y)
        self.scale_x: float = 1.0
        self.scale_y: float = 1.0
        self.angle:   float = 0.0    # grados
        self.flip_h:  bool  = False
        self.flip_v:  bool  = False

        # Arrastre activo
        self._drag_handle: int | None  = None
        self._drag_start:  QPointF     = QPointF(0, 0)
        self._drag_orig:   tuple       = (0.0, 0.0, 1.0, 1.0, 0.0)

        self._last_drag_pt = None
        self._drag_axis = None

    # ── Dimensiones actuales ──────────────────────────────────────────

    @property
    def w(self) -> float:
        return self._orig_w * abs(self.scale_x)

    @property
    def h(self) -> float:
        return self._orig_h * abs(self.scale_y)

    def center(self) -> QPointF:
        return QPointF(self.x + self.w / 2, self.y + self.h / 2)

    # ── Handles en coordenadas canvas ────────────────────────────────

    def handle_positions(self) -> dict:
        pts = self.get_transformed_corners()

        tl, tr, br, bl = pts

        # centros de bordes
        top    = (tl + tr) / 2
        right  = (tr + br) / 2
        bottom = (bl + br) / 2
        left   = (tl + bl) / 2

        # centro real
        center = (tl + tr + br + bl) / 4

        # handle rotación (arriba del centro)
        dir_vec = top - center
        length = math.hypot(dir_vec.x(), dir_vec.y())
        if length != 0:
            dir_vec /= length

        rot = top + dir_vec * -20

        return {
            TransformHandle.CORNER_TL: tl,
            TransformHandle.CORNER_TR: tr,
            TransformHandle.CORNER_BR: br,
            TransformHandle.CORNER_BL: bl,
            TransformHandle.EDGE_T:    top,
            TransformHandle.EDGE_R:    right,
            TransformHandle.EDGE_B:    bottom,
            TransformHandle.EDGE_L:    left,
            TransformHandle.ROTATE:    rot,
        }

    def hit_handle(self, canvas_pt: QPointF,
                   zoom: float) -> int | None:
        """Devuelve el handle bajo canvas_pt, o None."""
        thresh = TransformHandle.SIZE / zoom * 1.5
        for hid, pos in self.handle_positions().items():
            dx = canvas_pt.x() - pos.x()
            dy = canvas_pt.y() - pos.y()
            if math.sqrt(dx*dx + dy*dy) < thresh:
                return hid
        return None

    def hit_interior(self, canvas_pt: QPointF) -> bool:
        return (self.x <= canvas_pt.x() <= self.x + self.w
                and self.y <= canvas_pt.y() <= self.y + self.h)

    # ── Arrastre ──────────────────────────────────────────────────────

    def start_drag(self, handle: int, canvas_pt: QPointF):
        self._drag_handle = handle
        self._drag_start  = canvas_pt
        self._last_drag_pt = canvas_pt   # ✅ correcto
        self._drag_orig   = (self.x, self.y,
                            self.scale_x, self.scale_y, self.angle)
        self._drag_axis = None

    def drag_to(self, canvas_pt: QPointF,
                constrain: bool = False):
        if self._drag_handle is None:
            return

        
        dx = canvas_pt.x() - self._last_drag_pt.x()
        dy = canvas_pt.y() - self._last_drag_pt.y()
        ox, oy = self.x, self.y
        osx, osy = self.scale_x, self.scale_y
        oangle = self.angle
        ow = self._orig_w * abs(osx)
        oh = self._orig_h * abs(osy)

        h = self._drag_handle

        if h == TransformHandle.ROTATE:
            # Rotación
            cx = ox + ow / 2
            cy = oy + oh / 2
            a1 = math.degrees(math.atan2(
                self._drag_start.y() - cy,
                self._drag_start.x() - cx))
            a2 = math.degrees(math.atan2(
                canvas_pt.y() - cy,
                canvas_pt.x() - cx))
            delta = a2 - a1
            if constrain:
                delta = round(delta / 15) * 15
            self.angle = oangle + delta

        if h in (TransformHandle.CORNER_TL,
                 TransformHandle.CORNER_TR,
                 TransformHandle.CORNER_BR,
                 TransformHandle.CORNER_BL):

            orig_ratio = (self._orig_w / max(1, self._orig_h))

            # 1. calcular tamaño base según handle
            if h == TransformHandle.CORNER_BR:
                nw = max(10, ow + dx)
                nh = max(10, oh + dy)

            elif h == TransformHandle.CORNER_TL:
                nw = max(10, ow - dx)
                nh = max(10, oh - dy)

            elif h == TransformHandle.CORNER_TR:
                nw = max(10, ow + dx)
                nh = max(10, oh - dy)

            elif h == TransformHandle.CORNER_BL:
                nw = max(10, ow - dx)
                nh = max(10, oh + dy)

            # 2. aplicar lock ratio (BIEN)
            if constrain:
                if self._drag_axis is None:
                    if abs(dx) > abs(dy) + 2:
                        self._drag_axis = "x"
                    elif abs(dy) > abs(dx) + 2:
                        self._drag_axis = "y"

                if self._drag_axis == "x":
                    nh = nw / orig_ratio
                elif self._drag_axis == "y":
                    nw = nh * orig_ratio

            # 3. ajustar posición según esquina
            if h == TransformHandle.CORNER_TL:
                self.x = ox + (ow - nw)
                self.y = oy + (oh - nh)

            elif h == TransformHandle.CORNER_TR:
                self.y = oy + (oh - nh)

            elif h == TransformHandle.CORNER_BL:
                self.x = ox + (ow - nw)

            # 4. aplicar escala
            self.scale_x = (nw / self._orig_w) * (
                -1 if osx < 0 else 1)
            self.scale_y = (nh / self._orig_h) * (
                -1 if osy < 0 else 1)

        elif h in (
            TransformHandle.EDGE_T,
            TransformHandle.EDGE_B,
            TransformHandle.EDGE_L,
            TransformHandle.EDGE_R
        ):
            orig_ratio = (self._orig_w / max(1, self._orig_h))

            # RIGHT
            if h == TransformHandle.EDGE_R:
                nw = max(10, ow + dx)
                if constrain:
                    nh = nw / orig_ratio
                else:
                    nh = oh

            # LEFT
            elif h == TransformHandle.EDGE_L:
                nw = max(10, ow - dx)
                if constrain:
                    nh = nw / orig_ratio
                else:
                    nh = oh
                self.x = ox + (ow - nw)

            # BOTTOM
            elif h == TransformHandle.EDGE_B:
                nh = max(10, oh + dy)
                if constrain:
                    nw = nh * orig_ratio
                else:
                    nw = ow

            # TOP
            elif h == TransformHandle.EDGE_T:
                nh = max(10, oh - dy)
                if constrain:
                    nw = nh * orig_ratio
                else:
                    nw = ow
                self.y = oy + (oh - nh)

            self.scale_x = (nw / self._orig_w) * (
                -1 if osx < 0 else 1)
            self.scale_y = (nh / self._orig_h) * (
                -1 if osy < 0 else 1)



        # Mover todo el box
        elif h == -1:
            self.x = ox + dx
            self.y = oy + dy


        self._last_drag_pt = canvas_pt

    def end_drag(self):
        self._drag_handle = None

    # ── Flip ──────────────────────────────────────────────────────────

    def do_flip_h(self):
        self.flip_h = not self.flip_h

    def do_flip_v(self):
        self.flip_v = not self.flip_v

    # ── Preview ───────────────────────────────────────────────────────

    def get_preview(self) -> QImage:
        h, w, _ = self._orig_arr.shape

        # Aplicar máscara al array original ANTES de transformar
        arr = self._orig_arr.copy()
        if self._mask is not None:
            # Píxeles fuera de la máscara → transparentes
            arr[~self._mask] = 0

        src = QImage(
            arr.data, w, h,
            4 * w,
            QImage.Format.Format_ARGB32_Premultiplied
        ).copy()

        t  = QTransform()
        cx = w / 2
        cy = h / 2
        t.translate(cx, cy)
        sx = self.scale_x * (-1 if self.flip_h else 1)
        sy = self.scale_y * (-1 if self.flip_v else 1)
        t.scale(sx, sy)
        t.rotate(self.angle)
        t.translate(-cx, -cy)

        return src.transformed(
            t, Qt.TransformationMode.SmoothTransformation)

    def _rotate_image(self, img: QImage, angle: float) -> QImage:
        t  = QTransform().rotate(angle)
        return img.transformed(t,
            Qt.TransformationMode.SmoothTransformation)

    # ── Commit ────────────────────────────────────────────────────────

    def stamp_to(self, layer_arr: np.ndarray,
                 canvas_w: int, canvas_h: int) -> np.ndarray:
        """Aplica la transformación definitivamente a la capa."""
        preview = self.get_preview()
        pw, ph  = preview.width(), preview.height()

        preview = preview.convertToFormat(
            QImage.Format.Format_ARGB32_Premultiplied)
        ptr = preview.bits()
        ptr.setsize(preview.sizeInBytes())
        src_arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
            ph, pw, 4).copy()

        # ── Mismo cálculo de posición que draw() ──────────────────────
        cx = self.x + self._orig_w / 2
        cy = self.y + self._orig_h / 2
        fx = int(cx - pw / 2)
        fy = int(cy - ph / 2)

        # Intersección con el canvas
        src_x0 = max(0, -fx)
        src_y0 = max(0, -fy)
        dst_x0 = max(0,  fx)
        dst_y0 = max(0,  fy)
        cw     = min(pw - src_x0, canvas_w - dst_x0)
        ch_    = min(ph - src_y0, canvas_h - dst_y0)

        if cw <= 0 or ch_ <= 0:
            return layer_arr

        src = src_arr[src_y0:src_y0+ch_,
                      src_x0:src_x0+cw].astype(float)
        dst = layer_arr[dst_y0:dst_y0+ch_,
                        dst_x0:dst_x0+cw].astype(float)

        sa    = src[:,:,3:4] / 255.0
        da    = dst[:,:,3:4] / 255.0
        out_a = sa + da * (1 - sa)

        with np.errstate(invalid='ignore', divide='ignore'):
            out_rgb = np.where(out_a > 0,
                (src[:,:,:3]*sa + dst[:,:,:3]*da*(1-sa)) / out_a, 0)

        result = np.zeros_like(src)
        result[:,:,:3] = np.clip(out_rgb, 0, 255)
        result[:,:, 3] = np.clip(out_a[:,:,0]*255, 0, 255)

        layer_arr[dst_y0:dst_y0+ch_,
                  dst_x0:dst_x0+cw] = result.astype(np.uint8)
        return layer_arr

    # ── Draw handles ──────────────────────────────────────────────────

    def draw(self, painter: QPainter, zoom: float, offset: QPoint):
        ox, oy = offset.x(), offset.y()

        # Preview
        preview = self.get_preview()
        pw = preview.width()
        ph = preview.height()

        # Centrar el preview en el centro real del box
        cx = self.x + self._orig_w / 2
        cy = self.y + self._orig_h / 2

        dx = int((cx - pw / 2) * zoom + ox)
        dy = int((cy - ph / 2) * zoom + oy)
        dw = int(pw * zoom)
        dh = int(ph * zoom)

        painter.drawImage(QRect(dx, dy, dw, dh), preview)

        # Handles y bordes usando esquinas transformadas
        pts_canvas = self.get_transformed_corners()
        pts_widget = [
            QPointF(p.x() * zoom + ox, p.y() * zoom + oy)
            for p in pts_canvas
        ]

        # Borde
        painter.setPen(QPen(QColor(80, 180, 255), 1,
                            Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(4):
            painter.drawLine(pts_widget[i],
                             pts_widget[(i+1) % 4])

        # Centro y handle de rotación
        center_w = QPointF(
            sum(p.x() for p in pts_widget) / 4,
            sum(p.y() for p in pts_widget) / 4)
        top_w = (pts_widget[0] + pts_widget[1]) / 2

        dir_x = top_w.x() - center_w.x()
        dir_y = top_w.y() - center_w.y()
        length = math.hypot(dir_x, dir_y)
        if length > 0:
            dir_x /= length
            dir_y /= length

        rot_w = QPointF(top_w.x() - dir_x * 20,
                        top_w.y() - dir_y * 20)

        painter.setPen(QPen(QColor(80, 180, 255), 1))
        painter.drawLine(top_w, rot_w)

        # Handles en coordenadas widget
        hs = TransformHandle.SIZE
        handle_pts = self.handle_positions()
        for hid, pos in handle_pts.items():
            wx = int(pos.x() * zoom + ox)
            wy = int(pos.y() * zoom + oy)

            if hid == TransformHandle.ROTATE:
                painter.setBrush(QColor(0, 200, 100))
                painter.setPen(QPen(Qt.GlobalColor.white, 1))
                painter.drawEllipse(wx-hs//2, wy-hs//2, hs, hs)
            else:
                painter.setBrush(QColor(255, 255, 255))
                painter.setPen(QPen(QColor(80, 180, 255), 1))
                painter.drawRect(wx-hs//2, wy-hs//2, hs, hs)
    

    



    def rotate_left_90(self):
        self.angle = (self.angle - 90) % 360

    def rotate_right_90(self):
        self.angle = (self.angle + 90) % 360

    def set_position_center(self, cx: float, cy: float):
        """Mueve la caja para que su centro esté en (cx, cy)."""
        self.x = cx - self.w / 2
        self.y = cy - self.h / 2

    def set_position_topleft(self, x: float, y: float):
        self.x = x
        self.y = y

    def set_width_px(self, w: float, lock: bool = False):
        if self._orig_w <= 0:
            return
        ratio = self._orig_h / self._orig_w
        self.scale_x = w / self._orig_w
        if lock:
            self.scale_y = self.scale_x * (
                1 if self.scale_y >= 0 else -1)

    def set_height_px(self, h: float, lock: bool = False):
        if self._orig_h <= 0:
            return
        self.scale_y = h / self._orig_h
        if lock:
            self.scale_x = self.scale_y * (
                1 if self.scale_x >= 0 else -1)

    def set_width_pct(self, pct: float, lock: bool = False):
        self.set_width_px(self._orig_w * pct / 100, lock)

    def set_height_pct(self, pct: float, lock: bool = False):
        self.set_height_px(self._orig_h * pct / 100, lock)

    def set_angle(self, angle: float):
        self.angle = angle % 360
    

    def _get_transform(self) -> QTransform:
        t = QTransform()

        cx = self._orig_w / 2
        cy = self._orig_h / 2

        t.translate(cx, cy)

        sx = self.scale_x * (-1 if self.flip_h else 1)
        sy = self.scale_y * (-1 if self.flip_v else 1)
        t.scale(sx, sy)

        t.rotate(self.angle)

        t.translate(-cx, -cy)

        return t
    
    def get_transformed_corners(self):
        t = self._get_transform()

        pts = [
            QPointF(0, 0),
            QPointF(self._orig_w, 0),
            QPointF(self._orig_w, self._orig_h),
            QPointF(0, self._orig_h),
        ]

        transformed = []
        for p in pts:
            tp = t.map(p)
            tp.setX(tp.x() + self.x)
            tp.setY(tp.y() + self.y)
            transformed.append(tp)

        return transformed