"""
Sistema de selección — rectángulo y lazo libre.
"""

import numpy as np
from typing import Optional
from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QImage, QPainter, QPen, QColor, QPolygon
from PyQt6.QtCore import Qt


class Selection:

    def __init__(self):
        self._rect:       Optional[QRect]       = None
        self._float:      Optional[np.ndarray]  = None
        self._float_pos:  QPoint                = QPoint(0, 0)
        # Lazo
        self._lasso_pts:  list[QPoint]          = []
        self._lasso_mask: Optional[np.ndarray]  = None
        self._is_lasso:   bool                  = False
        self._is_opacity_mask: bool = False

    # ── Estado ────────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self._rect is not None or self._lasso_mask is not None

    @property
    def has_float(self) -> bool:
        return self._float is not None

    @property
    def rect(self) -> Optional[QRect]:
        return self._rect

    @property
    def is_lasso(self) -> bool:
        return self._is_lasso

    @property
    def lasso_points(self) -> list:
        return self._lasso_pts

    # ── Rectángulo ────────────────────────────────────────────────────

    def set_rect(self, x0: int, y0: int, x1: int, y1: int):
        left   = min(x0, x1)
        top    = min(y0, y1)
        right  = max(x0, x1)
        bottom = max(y0, y1)
        if right - left < 2 or bottom - top < 2:
            return
        self._rect      = QRect(left, top, right-left, bottom-top)
        self._is_lasso  = False
        self._lasso_pts = []
        self._lasso_mask = None

    # ── Lazo ──────────────────────────────────────────────────────────

    def lasso_add_point(self, p: QPoint):
        """Agrega un punto al contorno del lazo mientras se arrastra."""
        self._lasso_pts.append(p)
        self._is_lasso = True

    def lasso_close(self, canvas_w: int, canvas_h: int):
        """
        Cierra el lazo y genera la máscara de píxeles seleccionados.
        Usa rasterización por scanline.
        """
        if len(self._lasso_pts) < 3:
            self.clear()
            return

        # Bounding box del lazo
        xs = [p.x() for p in self._lasso_pts]
        ys = [p.y() for p in self._lasso_pts]
        x0 = max(0, min(xs))
        y0 = max(0, min(ys))
        x1 = min(canvas_w, max(xs) + 1)
        y1 = min(canvas_h, max(ys) + 1)

        if x1 <= x0 or y1 <= y0:
            self.clear()
            return

        # Rasterizar el polígono en una imagen temporal
        mask_img = QImage(canvas_w, canvas_h,
                          QImage.Format.Format_Grayscale8)
        mask_img.fill(0)
        painter = QPainter(mask_img)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        poly = QPolygon([p for p in self._lasso_pts])
        painter.drawPolygon(poly)
        painter.end()

        # Convertir a máscara numpy bool
        ptr = mask_img.bits()
        ptr.setsize(mask_img.sizeInBytes())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
            canvas_h, canvas_w).copy()
        self._lasso_mask = arr > 128

        # Rect bounding box para compatibilidad
        self._rect = QRect(x0, y0, x1-x0, y1-y0)

    # ── Punto dentro ──────────────────────────────────────────────────

    def point_in_float(self, p: QPoint) -> bool:
        if self._float is None:
            return False
        fh, fw = self._float.shape[:2]
        r = QRect(self._float_pos.x(), self._float_pos.y(), fw, fh)
        return r.contains(p)

    def point_in_rect(self, p: QPoint) -> bool:
        if self._rect is None:
            return False
        return self._rect.contains(p)

    # ── Clear ─────────────────────────────────────────────────────────

    def clear(self):
        self._rect       = None
        self._float      = None
        self._float_pos  = QPoint(0, 0)
        self._lasso_pts  = []
        self._lasso_mask = None
        self._is_lasso   = False
        self._is_opacity_mask = False

    # ── Lift ──────────────────────────────────────────────────────────

    def lift(self, layer_arr: np.ndarray,
             canvas_w: int, canvas_h: int) -> np.ndarray:
        if self._rect is None:
            return layer_arr

        x0 = max(0, self._rect.left())
        y0 = max(0, self._rect.top())
        x1 = min(canvas_w, self._rect.right())
        y1 = min(canvas_h, self._rect.bottom())

        if x1 <= x0 or y1 <= y0:
            return layer_arr

        if self._is_lasso and self._lasso_mask is not None:
            # Lift solo los píxeles dentro del lazo
            region     = layer_arr[y0:y1, x0:x1].copy()
            lasso_crop = self._lasso_mask[y0:y1, x0:x1]

            # Float = región con píxeles fuera del lazo borrados
            float_arr = region.copy()
            float_arr[~lasso_crop] = 0

            self._float     = float_arr
            self._float_pos = QPoint(x0, y0)

            # Borrar solo los píxeles dentro del lazo
            layer_arr[y0:y1, x0:x1][lasso_crop] = 0
        else:
            # Lift rectangular normal
            self._float     = layer_arr[y0:y1, x0:x1].copy()
            self._float_pos = QPoint(x0, y0)
            self._rect      = QRect(x0, y0, x1-x0, y1-y0)
            layer_arr[y0:y1, x0:x1] = 0

        return layer_arr

    # ── Mover float ───────────────────────────────────────────────────

    def move_float(self, delta: QPoint):
        self._float_pos += delta
        if self._rect is not None:
            self._rect = QRect(
                self._float_pos.x(), self._float_pos.y(),
                self._rect.width(),  self._rect.height())
        # Mover puntos del lazo
        if self._lasso_pts:
            self._lasso_pts = [
                QPoint(p.x() + delta.x(), p.y() + delta.y())
                for p in self._lasso_pts]
        if self._lasso_mask is not None:
            # Desplazar la máscara
            self._lasso_mask = np.roll(
                self._lasso_mask, delta.y(), axis=0)
            self._lasso_mask = np.roll(
                self._lasso_mask, delta.x(), axis=1)

    # ── Draw overlay ──────────────────────────────────────────────────

    def draw_overlay(self, painter: QPainter, zoom: float,
                     offset: QPoint, dash_offset: float = 0.0):
        ox, oy = offset.x(), offset.y()

        def _ants_pens():
            black = QPen(QColor(0, 0, 0), 1, Qt.PenStyle.CustomDashLine)
            black.setDashPattern([4, 4])
            black.setDashOffset(dash_offset)
            white = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.CustomDashLine)
            white.setDashPattern([4, 4])
            white.setDashOffset(dash_offset + 4)
            return black, white

        # Float content
        if self._float is not None:
            fh, fw = self._float.shape[:2]
            img = QImage(self._float.tobytes(), fw, fh,
                         QImage.Format.Format_ARGB32_Premultiplied)
            dx = int(self._float_pos.x() * zoom + ox)
            dy = int(self._float_pos.y() * zoom + oy)
            painter.drawImage(QRect(dx, dy,
                                    int(fw*zoom), int(fh*zoom)), img)


       # Elipse — solo si es selección circular, no máscara de opacidad
        if (self._is_lasso and self._lasso_mask is not None
                and not self._lasso_pts
                and not self._is_opacity_mask):
            r  = self._rect
            sx = int(r.left()  * zoom + ox)
            sy = int(r.top()   * zoom + oy)
            sw = int(r.width() * zoom)
            sh = int(r.height()* zoom)
            black, white = _ants_pens()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(black)
            painter.drawEllipse(QRect(sx, sy, sw, sh))
            painter.setPen(white)
            painter.drawEllipse(QRect(sx, sy, sw, sh))

        # Lazo en progreso o cerrado
        if self._is_lasso and self._lasso_pts:
            pts_widget = [
                QPoint(int(p.x()*zoom + ox), int(p.y()*zoom + oy))
                for p in self._lasso_pts]

            # Contorno del lazo (marching ants)
            black, white = _ants_pens()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for pen in (black, white):
                painter.setPen(pen)
                for i in range(len(pts_widget) - 1):
                    painter.drawLine(pts_widget[i], pts_widget[i+1])
                if self._float is not None and len(pts_widget) > 2:
                    painter.drawLine(pts_widget[-1], pts_widget[0])

        # Rect punteado (selección rectangular) — estilo "hormigas" Photoshop
        elif self._rect is not None and not self._is_lasso:
            r  = self._rect
            sx = int(r.left()  * zoom + ox)
            sy = int(r.top()   * zoom + oy)
            sw = int(r.width() * zoom)
            sh = int(r.height()* zoom)

            black, white = _ants_pens()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(black)
            painter.drawRect(QRect(sx, sy, sw, sh))
            painter.setPen(white)
            painter.drawRect(QRect(sx, sy, sw, sh))

    # ── Stamp ─────────────────────────────────────────────────────────

    def stamp(self, layer_arr: np.ndarray,
              canvas_w: int, canvas_h: int) -> np.ndarray:
        if self._float is None:
            return layer_arr

        fh, fw  = self._float.shape[:2]
        fx, fy  = self._float_pos.x(), self._float_pos.y()

        src_x0  = max(0, -fx)
        src_y0  = max(0, -fy)
        dst_x0  = max(0,  fx)
        dst_y0  = max(0,  fy)
        copy_w  = min(fw - src_x0, canvas_w - dst_x0)
        copy_h  = min(fh - src_y0, canvas_h - dst_y0)

        if copy_w <= 0 or copy_h <= 0:
            self._float     = None
            self._float_pos = QPoint(0, 0)
            self._rect      = None
            return layer_arr

        src = self._float[src_y0:src_y0+copy_h,
                          src_x0:src_x0+copy_w].astype(float)
        dst = layer_arr[dst_y0:dst_y0+copy_h,
                        dst_x0:dst_x0+copy_w].astype(float)

        sa    = src[:, :, 3:4] / 255.0
        da    = dst[:, :, 3:4] / 255.0
        out_a = sa + da * (1.0 - sa)

        with np.errstate(invalid='ignore', divide='ignore'):
            out_rgb = np.where(
                out_a > 0,
                (src[:,:,:3]*sa + dst[:,:,:3]*da*(1-sa)) / out_a,
                0)

        result = np.zeros_like(src)
        result[:, :, :3] = np.clip(out_rgb, 0, 255)
        result[:, :,  3] = np.clip(out_a[:,:,0]*255, 0, 255)

        layer_arr[dst_y0:dst_y0+copy_h,
                  dst_x0:dst_x0+copy_w] = result.astype(np.uint8)

        self._float      = None
        self._float_pos  = QPoint(0, 0)
        self._rect       = None
        self._lasso_pts  = []
        self._lasso_mask = None
        return layer_arr
    
    def set_ellipse(self, x0: int, y0: int, x1: int, y1: int,
                canvas_w: int, canvas_h: int):
        """
        Crea una selección elíptica y genera su máscara.
        """
        left   = min(x0, x1)
        top    = min(y0, y1)
        right  = max(x0, x1)
        bottom = max(y0, y1)

        if right - left < 2 or bottom - top < 2:
            return

        self._rect = QRect(left, top, right-left, bottom-top)

        self._is_lasso = True
        self.mode = "ellipse"     # 🔥 IMPORTANTE


        # Rasterizar la elipse como máscara
        mask_img = QImage(canvas_w, canvas_h,
                        QImage.Format.Format_Grayscale8)
        mask_img.fill(0)

        painter = QPainter(mask_img)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(left, top,
                                right-left, bottom-top))
        painter.end()

        ptr = mask_img.bits()
        ptr.setsize(mask_img.sizeInBytes())

        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
            canvas_h, canvas_w).copy()

        self._lasso_mask = arr > 128
        self._lasso_pts  = []
        self._is_opacity_mask = False

    def clear(self):
        self._rect       = None
        self._float      = None
        self._float_pos  = QPoint(0, 0)
        self._lasso_pts  = []
        self._lasso_mask = None
        self._is_lasso   = False
        # Notificar al canvas que limpie la máscara de pintura
        # (se hace desde MainWindow via _sel_deselect)
