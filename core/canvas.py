from typing import List, Optional
from PyQt6.QtGui import QImage, QPainter, QColor, QPen
import numpy as np
from collections import deque

from core.layer import Layer
from core.animation import Animation, Frame
from core.selection import Selection
from core.history import HistoryManager
from core.tools import ToolType, BrushSettings, BlendMode
from PyQt6.QtCore import Qt, QRect
from core.stabilizer import Stabilizer
from core.reference import ReferenceImage
from core.transform import TransformBox
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtCore import Qt



class Canvas:
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 24):
        self.width  = width
        self.height = height
        self.brush        = BrushSettings()
        self.current_tool = ToolType.PEN
        self.fill_tolerance = 15
        self.fill_expand    = 1
        self.animation = Animation(width, height, fps)
        self.selection = Selection()
        self.history = HistoryManager(max_steps=40)
        
        self.stabilizer = Stabilizer(level=0)


        self.reference = ReferenceImage()
        
        self.transform_box: TransformBox | None = None

        self.brush_opacity: float = 1.0   # 0.0 - 1.0
        self.eraser_soft:   bool  = False  # borrador suave (gaussiano)

        # Onion skinning — configuración completa
        self.onion_enabled      = False
        self.onion_prev         = 1       # frames anteriores
        self.onion_next         = 0       # frames siguientes
        self.onion_op_first     = 50.0    # opacidad % del frame más cercano
        self.onion_op_last      = 20.0    # opacidad % del frame más lejano
        self.onion_color_past   = (220, 60,  60)
        self.onion_color_future = (60,  120, 220)

        self._onion_cache: dict = {}      # {frame_index: QImage sin tint}
        self._tinted_cache: dict = {}   # {(index, color, opacity): QImage}
        self._onion_overlay: QImage | None = None
        self._stroke_buffer: QImage | None = None  # buffer del trazo actual

        self._clipboard: np.ndarray | None = None

        # Máscara de pintura activa (limita pincel/borrador/fill)
        self.paint_mask:        np.ndarray | None = None
        self.paint_mask_active: bool              = False

    # ── Shortcuts al frame actual ─────────────────────────────────────

    @property
    def current_frame(self) -> Frame:
        return self.animation.current_frame

    @property
    def layers(self):
        return self.current_frame.layers

    @property
    def active_layer_index(self) -> int:
        return self.current_frame.active_layer_index

    @active_layer_index.setter
    def active_layer_index(self, v: int):
        self.current_frame.active_layer_index = v

    def add_layer(self, name: str = None) -> Layer:
        return self.current_frame.add_layer(name)

    def delete_layer(self, index: int):
        self.current_frame.delete_layer(index)

    @property
    def active_layer(self) -> Optional[Layer]:
        return self.current_frame.active_layer

    # ── Composición ───────────────────────────────────────────────────

    def composite(self) -> QImage:
        result = QImage(self.width, self.height,
                        QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(Qt.GlobalColor.white)
        painter = QPainter(result)

        # Onion overlay
        if self.onion_enabled and self._onion_overlay is not None:
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setOpacity(1.0)
            painter.drawImage(0, 0, self._onion_overlay)

        # Capas del frame actual
        mode_map = {
            BlendMode.NORMAL:   QPainter.CompositionMode.CompositionMode_SourceOver,
            BlendMode.MULTIPLY: QPainter.CompositionMode.CompositionMode_Multiply,
            BlendMode.SCREEN:   QPainter.CompositionMode.CompositionMode_Screen,
            BlendMode.OVERLAY:  QPainter.CompositionMode.CompositionMode_Overlay,
            BlendMode.ADD:      QPainter.CompositionMode.CompositionMode_Plus,
        }
        for layer in self.current_frame.layers:
            if not layer.visible:
                continue
            painter.setOpacity(layer.opacity / 255.0)
            painter.setCompositionMode(
                mode_map.get(layer.blend_mode,
                    QPainter.CompositionMode.CompositionMode_SourceOver))
            painter.drawImage(0, 0, layer.image)

        # Preview del stroke buffer (lo que se está dibujando ahora)
        if self._stroke_buffer is not None:
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setOpacity(self.brush_opacity)
            painter.drawImage(0, 0, self._stroke_buffer)



        # Preview del transform box
        if self.transform_box is not None:
            tb      = self.transform_box
            preview = tb.get_preview()
            pw      = preview.width()
            ph      = preview.height()
            # Centrar en el centro del box original
            cx = tb.x + tb._orig_w / 2
            cy = tb.y + tb._orig_h / 2
            tx = int(cx - pw / 2)
            ty = int(cy - ph / 2)
            painter.setOpacity(1.0)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawImage(QRect(tx, ty, pw, ph), preview)

        painter.end()
        return result
        
    def _get_onion_frame(self, index: int) -> np.ndarray:
        if index in self._onion_cache:
            return self._onion_cache[index]

        img = QImage(self.width, self.height,
                    QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver)

        for layer in self.animation.frames[index].layers:
            if layer.visible:
                painter.setOpacity(layer.opacity / 255.0)
                painter.drawImage(0, 0, layer.image)
        painter.end()

        ptr = img.bits()
        ptr.setsize(img.sizeInBytes())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
            self.height, self.width, 4).copy()

        self._onion_cache[index] = arr
        return arr


    def _get_tinted_frame(self, index: int,
                          color: tuple, opacity: float) -> QImage:
        """
        Devuelve QImage con el color aplicado al 100% de saturación.
        La opacidad se aplica al momento de dibujar, no aquí.
        Caché por (index, color).
        """
        key = (index, color)
        if key in self._tinted_cache:
            return self._tinted_cache[key]

        arr = self._get_onion_frame(index).copy()
        r, g, b = color

        has_content = arr[:, :, 3] > 10
        # Aplicar color puro — sin tocar el alpha
        arr[has_content, 0] = b   # BGRA
        arr[has_content, 1] = g
        arr[has_content, 2] = r
        # Alpha fijo alto para que el color se vea correcto
        arr[has_content, 3] = 255

        result = QImage(
            arr.tobytes(), self.width, self.height,
            QImage.Format.Format_ARGB32_Premultiplied
        )
        self._tinted_cache[key] = result
        return result


    

    # ── Para compatibilidad con _apply_anim_settings ──────────────────
    def request_onion_update(self, callback=None):
        """
        Recalcula el onion overlay en un hilo separado.
        Mientras calcula, el canvas sigue respondiendo.
        """
        self.invalidate_onion_cache()
        if not self.onion_enabled:
            self._onion_overlay = None
            if callback:
                callback()
            return

        import threading

        def _worker():
            self._build_onion_overlay()
            if callback:
                # Volver al hilo principal via QTimer
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, callback)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def invalidate_onion_cache(self):
        self._onion_cache.clear()
        self._tinted_cache.clear()
        self._onion_overlay = None

    def _composite_to_numpy(self) -> np.ndarray:
        img = self.composite()
        ptr = img.bits()
        ptr.setsize(img.sizeInBytes())
        return np.frombuffer(ptr, dtype=np.uint8).reshape(
            self.height, self.width, 4).copy()




    def begin_stroke(self):
        """Inicializa el buffer de trazo sin dibujar nada."""
        layer = self.active_layer
        if layer is None:
            return
        self.history.push(self.current_frame)
        self._stroke_buffer = QImage(
            self.width, self.height,
            QImage.Format.Format_ARGB32_Premultiplied)
        self._stroke_buffer.fill(Qt.GlobalColor.transparent)

    # ── Herramientas ──────────────────────────────────────────────────

    def stroke(self, x0: int, y0: int, x1: int, y1: int,
               first: bool = False):
        layer = self.active_layer
        if layer is None:
            return
        if first:
            self.history.push(self.current_frame)
            self._stroke_buffer = QImage(
                self.width, self.height,
                QImage.Format.Format_ARGB32_Premultiplied)
            self._stroke_buffer.fill(Qt.GlobalColor.transparent)

        # Siempre usar buffer si existe, sin importar first
        # El borrador usa buffer si existe, el smudge dibuja directo
        if self.current_tool == ToolType.PEN:
            target = self._stroke_buffer if self._stroke_buffer is not None else layer.image
        else:
            target = layer.image

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.current_tool == ToolType.PEN:
            # Dibujar en buffer con color al 100% — opacidad se aplica al final
            color = self.brush.qcolor
            color.setAlpha(255)
            pen = QPen(color, self.brush.size,
                       Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(pen)
            painter.drawLine(x0, y0, x1, y1)

        elif self.current_tool == ToolType.ERASER:
            if self.eraser_soft:
                painter.end()
                self._soft_erase(layer, x0, y0, x1, y1)
                return
            else:
                pen = QPen(Qt.GlobalColor.transparent, self.brush.size,
                           Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap,
                           Qt.PenJoinStyle.RoundJoin)
                painter.setCompositionMode(
                    QPainter.CompositionMode.CompositionMode_Clear)
                painter.setPen(pen)
                painter.drawLine(x0, y0, x1, y1)

        painter.end()

    def commit_stroke(self):
        if self._stroke_buffer is None:
            return
        layer = self.active_layer
        if layer is None:
            self._stroke_buffer = None
            return

        # Aplicar máscara de pintura al buffer si está activa
        if self.paint_mask_active and self.paint_mask is not None:
            buf = self._stroke_buffer.convertToFormat(
                QImage.Format.Format_ARGB32_Premultiplied)
            ptr = buf.bits()
            ptr.setsize(buf.sizeInBytes())
            buf_arr = np.frombuffer(
                ptr, dtype=np.uint8).reshape(
                self.height, self.width, 4).copy()
            buf_arr[~self.paint_mask] = 0
            # Escribir de vuelta al buffer
            result_img = QImage(
                buf_arr.tobytes(), self.width, self.height,
                QImage.Format.Format_ARGB32_Premultiplied)
            painter = QPainter(layer.image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setOpacity(self.brush_opacity)
            painter.drawImage(0, 0, result_img)
            painter.end()
        else:
            # Sin máscara — compositar directo con QPainter
            painter = QPainter(layer.image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setOpacity(self.brush_opacity)
            painter.drawImage(0, 0, self._stroke_buffer)
            painter.end()

        self._stroke_buffer = None
    
    def _soft_erase(self, layer, x0: int, y0: int,
                    x1: int, y1: int):
        """
        Borrador suave: borra con gradiente radial gaussiano.
        Produce bordes difuminados en lugar de corte duro.
        """
        import numpy as np

        arr = layer.get_numpy()   # BGRA
        r   = max(1, self.brush.size // 2)

        # Interpolar puntos entre (x0,y0) y (x1,y1)
        dist  = max(1, int(((x1-x0)**2 + (y1-y0)**2) ** 0.5))
        steps = max(1, dist)

        strength = self.brush_opacity   # 0.0-1.0

        for i in range(steps + 1):
            t  = i / steps
            cx = int(x0 + (x1 - x0) * t)
            cy = int(y0 + (y1 - y0) * t)

            # Región de efecto
            x_min = max(0, cx - r)
            x_max = min(layer.width,  cx + r + 1)
            y_min = max(0, cy - r)
            y_max = min(layer.height, cy + r + 1)

            if x_max <= x_min or y_max <= y_min:
                continue

            # Grid de distancias al centro
            ys, xs = np.ogrid[y_min:y_max, x_min:x_max]
            dist_sq = (xs - cx)**2 + (ys - cy)**2
            r_sq    = r * r

            # Gaussiana normalizada (1 en centro, 0 en borde)
            gauss = np.exp(-2.5 * dist_sq / max(1, r_sq))
            gauss[dist_sq > r_sq] = 0.0

            # Reducir alpha según la gaussiana
            region = arr[y_min:y_max, x_min:x_max]
            alpha  = region[:, :, 3].astype(np.float32)
            alpha  = np.clip(alpha - gauss * 255.0 * strength, 0, 255)
            arr[y_min:y_max, x_min:x_max, 3] = alpha.astype(np.uint8)

        # Aplicar máscara de pintura
        if self.paint_mask_active and self.paint_mask is not None:
            # Restaurar píxeles fuera de la máscara
            orig = layer.get_numpy()
            outside = ~self.paint_mask
            arr[outside] = orig[outside]

        layer.set_numpy(arr)
        

    def fill(self, x: int, y: int):
        self.push_history()
        if self.active_layer is None:
            return
        if not (0 <= x < self.width and 0 <= y < self.height):
            return

        ref      = self._composite_to_numpy()
        edge_map = self._build_edge_map(ref, x, y)

        visited = np.zeros((self.height, self.width), dtype=bool)
        mask    = np.zeros((self.height, self.width), dtype=bool)
        visited[y, x] = True
        queue = deque([(x, y)])
        dirs  = [(1,0),(-1,0),(0,1),(0,-1)]

        while queue:
            cx, cy = queue.popleft()
            if edge_map[cy, cx]:
                continue
            mask[cy, cx] = True
            for dx, dy in dirs:
                nx, ny = cx+dx, cy+dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if not visited[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((nx, ny))

        if self.fill_expand > 0:
            mask = self._dilate(mask, self.fill_expand)

        # Aplicar máscara de pintura si está activa
        if self.paint_mask_active and self.paint_mask is not None:
            mask = mask & self.paint_mask

        fill_color = np.array([
            self.brush.color_b, self.brush.color_g,
            self.brush.color_r, self.brush.color_a,
        ], dtype=np.uint8)

        layer_arr = self.active_layer.get_numpy()
        layer_arr[mask] = fill_color
        self.active_layer.set_numpy(layer_arr)
        self.invalidate_onion_cache()

    def lift_selection(self):
        if self.active_layer is None or not self.selection.active:
            return
        self.push_history()
        arr = self.active_layer.get_numpy()
        arr = self.selection.lift(arr, self.width, self.height)
        self.active_layer.set_numpy(arr)

    def stamp_selection(self):
        if self.active_layer is None:
            return
        self.push_history()
        arr = self.active_layer.get_numpy()
        arr = self.selection.stamp(arr, self.width, self.height)
        self.active_layer.set_numpy(arr)
        self.invalidate_onion_cache()

    def _apply_shape_to_layer(self, layer, draw_fn):
        

        # Dibujar en buffer temporal
        buf = QImage(self.width, self.height,
                    QImage.Format.Format_ARGB32_Premultiplied)
        buf.fill(Qt.GlobalColor.transparent)
        painter = QPainter(buf)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver)
        draw_fn(painter)
        painter.end()

        # Aplicar máscara de selección si está activa
        if self.selection.active or (self.paint_mask_active and self.paint_mask is not None):
            ptr = buf.bits()
            ptr.setsize(buf.sizeInBytes())
            buf_arr = np.frombuffer(
                ptr, dtype=np.uint8).reshape(
                self.height, self.width, 4).copy()

            if self.selection.active:
                if (self.selection._is_lasso
                        and self.selection._lasso_mask is not None):
                    mask = self.selection._lasso_mask
                elif self.selection.rect is not None:
                    mask = np.zeros((self.height, self.width), dtype=bool)
                    r  = self.selection.rect
                    x0 = max(0, r.left())
                    y0 = max(0, r.top())
                    x1 = min(self.width,  r.right())
                    y1 = min(self.height, r.bottom())
                    mask[y0:y1, x0:x1] = True
                else:
                    mask = None
                if mask is not None:
                    buf_arr[~mask] = 0

            if self.paint_mask_active and self.paint_mask is not None:
                buf_arr[~self.paint_mask] = 0

            # Reconstruir buf desde el array modificado
            buf = QImage(
                buf_arr.tobytes(), self.width, self.height,
                QImage.Format.Format_ARGB32_Premultiplied)

        # Compositar sobre la capa con QPainter (correcto, respeta opacidad)
        painter = QPainter(layer.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setOpacity(self.brush_opacity)
        painter.drawImage(0, 0, buf)
        painter.end()
        self.invalidate_onion_cache()

    def draw_line(self, x0, y0, x1, y1):
        layer = self.active_layer
        if layer is None:
            return
        from PyQt6.QtGui import QPen
        from PyQt6.QtCore import Qt

        def _draw(painter):
            pen = QPen(self.brush.qcolor, self.brush.size,
                       Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(x0, y0, x1, y1)

        self._apply_shape_to_layer(layer, _draw)

    def draw_rect(self, x0, y0, x1, y1,
                  filled=False, stroke=True):
        layer = self.active_layer
        if layer is None:
            return
        from PyQt6.QtGui import QPen
        from PyQt6.QtCore import Qt, QRect

        def _draw(painter):
            if stroke:
                painter.setPen(QPen(self.brush.qcolor,
                                    self.brush.size))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.brush.qcolor if filled
                             else Qt.BrushStyle.NoBrush)
            painter.drawRect(QRect(min(x0,x1), min(y0,y1),
                                   abs(x1-x0), abs(y1-y0)))

        self._apply_shape_to_layer(layer, _draw)

    def draw_ellipse(self, x0, y0, x1, y1,
                     filled=False, stroke=True):
        layer = self.active_layer
        if layer is None:
            return
        from PyQt6.QtGui import QPen
        from PyQt6.QtCore import Qt, QRect

        def _draw(painter):
            if stroke:
                painter.setPen(QPen(self.brush.qcolor,
                                    self.brush.size))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.brush.qcolor if filled
                             else Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRect(min(x0,x1), min(y0,y1),
                                      abs(x1-x0), abs(y1-y0)))

        self._apply_shape_to_layer(layer, _draw)

    def draw_triangle(self, x0, y0, x1, y1,
                      filled=False, stroke=True):
        """
        Triángulo definido por base (x0,y0)-(x1,y1).
        El vértice superior se centra horizontalmente.
        """
        layer = self.active_layer
        if layer is None:
            return
        from PyQt6.QtGui import QPen, QPolygon
        from PyQt6.QtCore import Qt, QPoint

        def _draw(painter):
            cx = (x0 + x1) // 2
            poly = QPolygon([
                QPoint(cx, y0),       # vértice superior
                QPoint(x0, y1),       # esquina inferior izquierda
                QPoint(x1, y1),       # esquina inferior derecha
            ])
            if stroke:
                painter.setPen(QPen(self.brush.qcolor,
                                    self.brush.size,
                                    Qt.PenStyle.SolidLine,
                                    Qt.PenCapStyle.RoundCap,
                                    Qt.PenJoinStyle.RoundJoin))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.brush.qcolor if filled
                             else Qt.BrushStyle.NoBrush)
            painter.drawPolygon(poly)

        self._apply_shape_to_layer(layer, _draw)

    def draw_text(self, x, y, text, font_size=24):
        layer = self.active_layer
        if layer is None:
            return
        from PyQt6.QtGui import QFont
        painter = QPainter(layer.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver)
        font = QFont()
        font.setPointSize(font_size)
        painter.setFont(font)
        painter.setPen(QPen(self.brush.qcolor))
        painter.drawText(x, y, text)
        painter.end()
        self.invalidate_onion_cache()

    # ── Historial ─────────────────────────────────────────────────────

    def push_history(self):
        self.history.push(self.current_frame)

    def undo(self) -> bool:
        return self.history.undo(self.current_frame)

    def redo(self) -> bool:
        return self.history.redo(self.current_frame)

    # ── Helpers fill ──────────────────────────────────────────────────

    def _build_edge_map(self, ref, ox, oy):
        alpha      = ref[:, :, 3].astype(np.int16)
        lum        = (ref[:,:,0].astype(np.float32)*0.07 +
                      ref[:,:,1].astype(np.float32)*0.72 +
                      ref[:,:,2].astype(np.float32)*0.21)
        origin_rgb = ref[oy, ox, :3].astype(np.int16)
        dark_edge  = (lum < 180) & (alpha > 30)
        color_diff = np.max(np.abs(
            ref[:,:,:3].astype(np.int16) - origin_rgb), axis=2)
        return dark_edge | (color_diff > self.fill_tolerance)

    @staticmethod
    def _dilate(mask, radius):
        result = mask.copy()
        for _ in range(radius):
            result[:-1,:] |= result[1:,:]
            result[1:,:]  |= result[:-1,:]
            result[:,:-1] |= result[:,1:]
            result[:,1:]  |= result[:,:-1]
        return result
    

    def _build_onion_overlay(self):
        """
        Calcula el overlay de onion skinning.
        La opacidad se aplica con painter.setOpacity() — color siempre puro.
        """
        if not self.onion_enabled:
            self._onion_overlay = None
            return

        cur   = self.animation.current_frame_index
        total = len(self.animation.frames)

        overlay = QImage(self.width, self.height,
                         QImage.Format.Format_ARGB32_Premultiplied)
        overlay.fill(Qt.GlobalColor.transparent)
        painter = QPainter(overlay)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver)

        def get_opacity(offset, max_offset):
            if max_offset <= 1:
                return self.onion_op_first / 100.0
            t  = (offset - 1) / (max_offset - 1)
            op = self.onion_op_first + t * (
                self.onion_op_last - self.onion_op_first)
            return max(0.01, min(1.0, op / 100.0))

        # Anteriores → color past
        for offset in range(self.onion_prev, 0, -1):
            idx = cur - offset
            if 0 <= idx < total:
                op     = get_opacity(offset, self.onion_prev)
                tinted = self._get_tinted_frame(
                    idx, self.onion_color_past, op)
                painter.setOpacity(op)   # opacidad aquí, no en el pixel
                painter.drawImage(0, 0, tinted)

        # Siguientes → color future
        for offset in range(1, self.onion_next + 1):
            idx = cur + offset
            if 0 <= idx < total:
                op     = get_opacity(offset, self.onion_next)
                tinted = self._get_tinted_frame(
                    idx, self.onion_color_future, op)
                painter.setOpacity(op)   # opacidad aquí, no en el pixel
                painter.drawImage(0, 0, tinted)

        painter.end()
        self._onion_overlay = overlay

    def begin_transform(self) -> bool:
        layer = self.active_layer
        if layer is None:
            return False

        self.push_history()
        arr = layer.get_numpy()

        if self.selection.active:
            sel = self.selection

            if sel._is_lasso and sel._lasso_mask is not None:
                # ── Selección con máscara exacta ──────────────────────
                full_mask = sel._lasso_mask   # (H, W) bool

                # Bounding box de la máscara
                rows = np.any(full_mask, axis=1)
                cols = np.any(full_mask, axis=0)
                if not rows.any():
                    self.history.undo(self.current_frame)
                    return False

                y0 = int(np.argmax(rows))
                y1 = int(len(rows) - np.argmax(rows[::-1]))
                x0 = int(np.argmax(cols))
                x1 = int(len(cols) - np.argmax(cols[::-1]))

                # Recortar región y máscara al bounding box
                region    = arr[y0:y1, x0:x1].copy()
                mask_crop = full_mask[y0:y1, x0:x1]

                # Píxeles fuera de la máscara → transparentes en el float
                region[~mask_crop] = 0

                # Borrar de la capa solo píxeles dentro de la máscara
                tmp = arr[y0:y1, x0:x1].copy()
                tmp[mask_crop] = 0
                arr[y0:y1, x0:x1] = tmp

            else:
                # ── Selección rectangular ─────────────────────────────
                r  = sel.rect
                x0 = max(0, r.left())
                y0 = max(0, r.top())
                x1 = min(self.width,  r.right())
                y1 = min(self.height, r.bottom())
                if x1 <= x0 or y1 <= y0:
                    self.history.undo(self.current_frame)
                    return False
                region    = arr[y0:y1, x0:x1].copy()
                mask_crop = None
                arr[y0:y1, x0:x1] = 0

            self.selection.clear()

        else:
            # ── Sin selección: bounding box del contenido visible ─────
            alpha = arr[:, :, 3]
            rows  = np.any(alpha > 0, axis=1)
            cols  = np.any(alpha > 0, axis=0)
            if not rows.any():
                self.history.undo(self.current_frame)
                return False
            y0 = int(np.argmax(rows))
            y1 = int(len(rows) - np.argmax(rows[::-1]))
            x0 = int(np.argmax(cols))
            x1 = int(len(cols) - np.argmax(cols[::-1]))
            if x1 <= x0 or y1 <= y0:
                self.history.undo(self.current_frame)
                return False
            region    = arr[y0:y1, x0:x1].copy()
            mask_crop = None
            arr[y0:y1, x0:x1] = 0

        layer.set_numpy(arr)

        from core.transform import TransformBox
        self.transform_box = TransformBox(region, x0, y0,
                                          mask=mask_crop)
        self.invalidate_onion_cache()
        return True

    def commit_transform(self):
        """Aplica el TransformBox a la capa activa."""
        if self.transform_box is None:
            return
        layer = self.active_layer
        if layer is None:
            return
        arr = layer.get_numpy()
        arr = self.transform_box.stamp_to(arr, self.width, self.height)
        layer.set_numpy(arr)
        self.transform_box = None
        self.invalidate_onion_cache()

    def cancel_transform(self):
        """Cancela — restaura vía undo."""
        if self.transform_box is not None:
            self.transform_box = None
            self.undo()
            self.invalidate_onion_cache()


    # ── Operaciones de selección ──────────────────────────────────────

    def select_by_opacity(self):
        """
        Selección de opacidad — igual que ibis Paint.
        Genera una máscara exacta desde el canal alpha de la capa activa.
        Mientras esté activa, TODO (pincel, borrador, fill) queda
        limitado a esa máscara.
        """
        layer = self.active_layer
        if layer is None:
            return

        arr   = layer.get_numpy()
        alpha = arr[:, :, 3]

        # Máscara exacta píxel a píxel
        mask = alpha > 0

        if not mask.any():
            return

        # Bounding box para el rect visual
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        y0   = int(np.argmax(rows))
        y1   = int(len(rows) - np.argmax(rows[::-1]))
        x0   = int(np.argmax(cols))
        x1   = int(len(cols) - np.argmax(cols[::-1]))

        from PyQt6.QtCore import QRect
        self.selection._rect       = QRect(x0, y0, x1-x0, y1-y0)
        self.selection._lasso_mask = mask
        self.selection._is_lasso   = True
        self.selection._lasso_pts  = []

        # Activar máscara de pintura
        self.paint_mask        = mask
        self.paint_mask_active = True
        self.selection._is_opacity_mask = True

    def clear_selection_area(self):
        """
        Borra el contenido dentro de la selección activa
        en la capa activa únicamente.
        """
        if not self.selection.active:
            return
        layer = self.active_layer
        if layer is None:
            return
        self.push_history()
        arr = layer.get_numpy()

        if self.selection._is_lasso and \
                self.selection._lasso_mask is not None:
            arr[self.selection._lasso_mask] = 0
        elif self.selection.rect is not None:
            r  = self.selection.rect
            x0 = max(0, r.left())
            y0 = max(0, r.top())
            x1 = min(self.width,  r.right())
            y1 = min(self.height, r.bottom())
            arr[y0:y1, x0:x1] = 0

        layer.set_numpy(arr)
        self.invalidate_onion_cache()

    def copy_selection(self) -> bool:
        """
        Copia el contenido de la selección al portapapeles interno.
        Devuelve True si había algo que copiar.
        """
        layer = self.active_layer
        if layer is None:
            return False
        arr = layer.get_numpy()

        if self.selection._is_lasso and \
                self.selection._lasso_mask is not None:
            mask = self.selection._lasso_mask
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            y0   = int(np.argmax(rows))
            y1   = int(len(rows) - np.argmax(rows[::-1]))
            x0   = int(np.argmax(cols))
            x1   = int(len(cols) - np.argmax(cols[::-1]))
            region = arr[y0:y1, x0:x1].copy()
            # Borrar píxeles fuera de la máscara del lazo
            lasso_crop = mask[y0:y1, x0:x1]
            region[~lasso_crop] = 0
        elif self.selection.rect is not None:
            r  = self.selection.rect
            x0 = max(0, r.left())
            y0 = max(0, r.top())
            x1 = min(self.width,  r.right())
            y1 = min(self.height, r.bottom())
            if x1 <= x0 or y1 <= y0:
                return False
            region = arr[y0:y1, x0:x1].copy()
        else:
            return False

        self._clipboard = region
        return True

    def cut_selection(self) -> bool:
        """Copia y borra el contenido de la selección."""
        if not self.copy_selection():
            return False
        self.clear_selection_area()
        return True

    def paste_clipboard(self):
        """
        Pega el portapapeles como nueva capa centrada en el canvas.
        """
        if not hasattr(self, '_clipboard') or \
                self._clipboard is None:
            return
        self.push_history()

        # Crear nueva capa
        layer = self.add_layer("Pasted")
        arr   = layer.get_numpy()

        clip  = self._clipboard
        ch, cw = clip.shape[:2]

        # Centrar en el canvas
        cx = (self.width  - cw) // 2
        cy = (self.height - ch) // 2

        # Clamp al canvas
        src_x0 = max(0, -cx)
        src_y0 = max(0, -cy)
        dst_x0 = max(0,  cx)
        dst_y0 = max(0,  cy)
        copy_w = min(cw - src_x0, self.width  - dst_x0)
        copy_h = min(ch - src_y0, self.height - dst_y0)

        if copy_w > 0 and copy_h > 0:
            arr[dst_y0:dst_y0+copy_h,
                dst_x0:dst_x0+copy_w] = \
                clip[src_y0:src_y0+copy_h,
                     src_x0:src_x0+copy_w]

        layer.set_numpy(arr)
        self.invalidate_onion_cache()


    def clear_paint_mask(self):
        self.paint_mask        = None
        self.paint_mask_active = False


    def crop_layer(self) -> bool:
        """
        Recorta la capa activa:
        - Si hay selección activa → borra todo fuera de ella
        - Si no hay selección → usa alpha > 0 como área a conservar
        Solo afecta la capa activa. No cambia el canvas.
        Soporta undo.
        """
        layer = self.active_layer
        if layer is None:
            return False

        self.push_history()
        arr = layer.get_numpy()

        if self.selection.active:
            # ── Usar selección activa ─────────────────────────────────
            if (self.selection._is_lasso
                    and self.selection._lasso_mask is not None):
                # Máscara exacta (lazo, elipse, opacidad)
                keep_mask = self.selection._lasso_mask
            elif self.selection.rect is not None:
                # Selección rectangular
                keep_mask = np.zeros(
                    (self.height, self.width), dtype=bool)
                r  = self.selection.rect
                x0 = max(0, r.left())
                y0 = max(0, r.top())
                x1 = min(self.width,  r.right())
                y1 = min(self.height, r.bottom())
                keep_mask[y0:y1, x0:x1] = True
            else:
                self.history.undo(self.current_frame)
                return False
        else:
            # ── Sin selección: conservar píxeles visibles ─────────────
            alpha     = arr[:, :, 3]
            keep_mask = alpha > 0
            if not keep_mask.any():
                self.history.undo(self.current_frame)
                return False

        # Borrar todo lo que está FUERA de la máscara
        arr[~keep_mask] = 0
        layer.set_numpy(arr)
        self.invalidate_onion_cache()
        return True
    

    def draw_bezier_path(self, path, stroke_width: int = 3):
        """
        Renderiza un BezierPath en la capa activa usando QPainterPath.
        """
        from core.bezier_path import BezierPath
        from PyQt6.QtGui import QPainterPath, QPen
        from PyQt6.QtCore import Qt

        layer = self.active_layer
        if layer is None:
            return
        if not path.points:
            return

        def _draw(painter):
            pp = QPainterPath()
            pts = path.points
            n   = len(pts)

            pp.moveTo(pts[0].x, pts[0].y)

            segments = path.all_segments()
            for i, j in segments:
                a  = pts[i]
                b  = pts[j]
                c1 = a.handle_out
                c2 = b.handle_in
                pp.cubicTo(c1[0], c1[1],
                           c2[0], c2[1],
                           b.x,   b.y)

            if path.closed:
                pp.closeSubpath()

            pen = QPen(self.brush.qcolor, stroke_width,
                       Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(pp)

        self._apply_shape_to_layer(layer, _draw)
    

    def smudge(self, x0: int, y0: int, x1: int, y1: int,
               first: bool = False):
        """
        Herramienta de difuminar — mezcla los píxeles
        en la dirección del trazo con los píxeles vecinos.
        """
        layer = self.active_layer
        if layer is None:
            return
        if first:
            self.history.push(self.current_frame)

        arr = layer.get_numpy()
        r   = max(1, self.brush.size // 2)
        strength = min(0.95, self.brush_opacity * 0.8)

        # Interpolar puntos entre (x0,y0) y (x1,y1)
        dist  = max(1, int(((x1-x0)**2 + (y1-y0)**2) ** 0.5))
        steps = max(1, dist // 2)

        for i in range(steps + 1):
            t  = i / steps
            cx = int(x0 + (x1 - x0) * t)
            cy = int(y0 + (y1 - y0) * t)

            x_min = max(0, cx - r)
            x_max = min(layer.width,  cx + r + 1)
            y_min = max(0, cy - r)
            y_max = min(layer.height, cy + r + 1)

            if x_max <= x_min or y_max <= y_min:
                continue

            # Región actual
            region = arr[y_min:y_max, x_min:x_max].astype(np.float32)

            # Gaussiana de peso
            ys, xs = np.ogrid[y_min:y_max, x_min:x_max]
            dist_sq = (xs - cx)**2 + (ys - cy)**2
            r_sq    = r * r
            gauss   = np.exp(-2.0 * dist_sq / max(1, r_sq))
            gauss[dist_sq > r_sq] = 0.0
            gauss   = gauss[:, :, np.newaxis]

            # Blur local — promedio ponderado de la región
            total_w  = gauss.sum()
            if total_w < 1e-6:
                continue
            blurred  = (region * gauss).sum(axis=(0,1)) / total_w
            blurred  = blurred[np.newaxis, np.newaxis, :]

            # Mezclar original con blurred según strength y gaussiana
            arr[y_min:y_max, x_min:x_max] = (
                region * (1 - gauss * strength) +
                blurred * gauss * strength
            ).astype(np.uint8)

        # Aplicar máscara de selección si está activa
        if self.paint_mask_active and self.paint_mask is not None:
            orig = layer.get_numpy()
            arr[~self.paint_mask] = orig[~self.paint_mask]

        layer.set_numpy(arr)
        self.invalidate_onion_cache()