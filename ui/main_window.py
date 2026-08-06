from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QColorDialog, QSizePolicy, QMessageBox,
    QMenuBar, QMenu
)

from PyQt6.QtGui import (
    QColor, QPainter, QWheelEvent, QImage,
    QKeySequence, QShortcut, QAction, QPen
)

from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, QPointF

import ctypes
import sys

from core.canvas import Canvas
from core.tools import ToolType
from ui.layer_panel import LayerPanel
from ui.timeline import TimelineWidget
from ui.import_panel import ImportPanel
from ui.toolbar_widget import SideToolbar
from core.user_config import UserConfig
from PyQt6.QtCore import QTimer
from ui.color_picker import ColorPickerDialog
from PyQt6.QtGui import QColor
from ui.transform_bar import TransformBar
from ui.tool_bar_props import ToolPropsBar
from PyQt6.QtGui import QPen
from core.ruler import SymmetryRuler
from core.bezier_path import BezierPath
from ui.video_import_dialog import VideoImportDialog

class CanvasWidget(QWidget):
    def __init__(self, canvas: Canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

        self._last_pos:   QPoint | None = None
        self._is_drawing  = False
        self._zoom        = 1.0
        self._offset      = QPoint(0, 0)
        self._pan_last:   QPoint | None = None

        # Selección
        self._sel_origin: QPoint | None = None
        self._sel_state   = "idle"
        self._move_last:  QPoint | None = None

        # Formas
        self._shape_start:       QPoint | None = None
        self._shape_preview_end: QPoint | None = None

        # Caché
        self._checkerboard:    QImage | None = None
        self._checker_size:    tuple         = (0, 0)
        self._composite_cache: QImage | None = None
        self._cache_dirty:     bool          = True

        # Throttle
        self._paint_pending = False
        self._paint_timer   = QTimer()
        self._paint_timer.setSingleShot(True)
        self._paint_timer.setInterval(8)
        self._paint_timer.timeout.connect(self._flush_paint)

        self._cursor_pos: QPoint | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._stab_last: QPoint | None = None

        # Animación "hormigas" de la selección (estilo Photoshop)
        self._ants_offset = 0.0
        self._ants_timer = QTimer()
        self._ants_timer.setInterval(80)
        self._ants_timer.timeout.connect(self._tick_ants)
        self._ants_timer.start()


        # Indicador de zoom
        self._zoom_label = QLabel("100%", self)
        self._zoom_label.setStyleSheet("""
            QLabel {
                background: rgba(32,32,32,235);
                color: #ffffff;
                font-size: 11px;
                padding: 2px 6px;
                border-radius: 4px;
            }
        """)
        self._zoom_label.adjustSize()
        self._zoom_label.move(8, 8)
        self._zoom_label.show()

        self._ref_dragging = False

        # Transform
        self._transform_drag_handle: int | None = None
        self._transform_moving = False
        self._transform_last: QPointF | None = None


        self._grid_visible = False
        self._grid_size    = 50


        self._active_ruler = None
        self._ruler_editing = False
        self._ruler_handle  = 0
        self._ruler_last_pts: list = []

        self._ruler_first_move = False



        
        self._bezier_path: BezierPath | None = None
        self._bezier_dragging_anchor: int | None = None
        self._bezier_dragging_hout:   int | None = None
        self._bezier_dragging_hin:    int | None = None
        self._bezier_placing: bool = False   # arrastrando al colocar
        self._bezier_stroke_width: int = 3

    # ── Caché ─────────────────────────────────────────────────────────

    def mark_dirty(self):
        self._cache_dirty = True
        if self.canvas.onion_enabled:
            self.canvas.request_onion_update(
                callback=self._on_onion_ready)
        else:
            self._request_paint()

    def mark_dirty_stroke(self):
        self._composite_cache = None
        self._cache_dirty     = True
        self.update()

    def _on_onion_ready(self):
        self._cache_dirty = True
        self._request_paint()

    def _request_paint(self):
        if not self._paint_pending:
            self._paint_pending = True
            self._paint_timer.start()

    def _flush_paint(self):
        self._paint_pending = False
        self.update()

    def _tick_ants(self):
        self._ants_offset = (self._ants_offset + 1) % 8
        if self.canvas.selection.active:
            self.update()


    def _get_checkerboard(self, w: int, h: int) -> QImage:
        if self._checkerboard is not None and self._checker_size == (w, h):
            return self._checkerboard
        import numpy as np
        tile = 16
        cols = (w + tile - 1) // tile
        rows = (h + tile - 1) // tile
        arr  = np.zeros((rows*tile, cols*tile, 4), dtype=np.uint8)
        for r in range(rows):
            for c in range(cols):
                v = 180 if (r + c) % 2 == 0 else 220
                arr[r*tile:(r+1)*tile, c*tile:(c+1)*tile] = (v, v, v, 255)
        checker = QImage(arr.tobytes(), cols*tile, rows*tile,
                         QImage.Format.Format_ARGB32)
        self._checkerboard = checker.copy(QRect(0, 0, w, h))
        self._checker_size = (w, h)
        return self._checkerboard

    def _get_composite(self) -> QImage:
        if not self._cache_dirty and self._composite_cache is not None:
            return self._composite_cache
        self._composite_cache = self.canvas.composite()
        self._cache_dirty     = False
        return self._composite_cache

    # ── Paint ─────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(45, 45, 45))

        cw = int(self.canvas.width  * self._zoom)
        ch = int(self.canvas.height * self._zoom)
        ox, oy = self._offset.x(), self._offset.y()

        painter.drawImage(QRect(ox, oy, cw, ch),
                          self._get_checkerboard(
                              self.canvas.width, self.canvas.height))
        painter.drawImage(QRect(ox, oy, cw, ch), self._get_composite())

        

        # Selección overlay
        self.canvas.selection.draw_overlay(
            painter, self._zoom, self._offset, self._ants_offset)

        # Preview forma geométrica
        tool = self.canvas.current_tool
        if (self._shape_start is not None
                and self._shape_preview_end is not None
                and tool in (ToolType.LINE, ToolType.RECT,
                             ToolType.ELLIPSE)):
            p1  = self._shape_start
            p2  = self._shape_preview_end
            sx1 = int(p1.x() * self._zoom + ox)
            sy1 = int(p1.y() * self._zoom + oy)
            sx2 = int(p2.x() * self._zoom + ox)
            sy2 = int(p2.y() * self._zoom + oy)
            painter.setPen(QPen(QColor(242, 128, 26), 1,
                                Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if tool == ToolType.LINE:
                painter.drawLine(sx1, sy1, sx2, sy2)
            elif tool == ToolType.RECT:
                painter.drawRect(QRect(min(sx1,sx2), min(sy1,sy2),
                                       abs(sx2-sx1), abs(sy2-sy1)))
            elif tool == ToolType.ELLIPSE:
                painter.drawEllipse(QRect(min(sx1,sx2), min(sy1,sy2),
                                          abs(sx2-sx1), abs(sy2-sy1)))

        if (self._shape_start is not None
                and self._shape_preview_end is not None
                and tool in (ToolType.LINE, ToolType.RECT,
                             ToolType.ELLIPSE, ToolType.TRIANGLE)):
            p1  = self._shape_start
            p2  = self._shape_preview_end
            sx1 = int(p1.x() * self._zoom + ox)
            sy1 = int(p1.y() * self._zoom + oy)
            sx2 = int(p2.x() * self._zoom + ox)
            sy2 = int(p2.y() * self._zoom + oy)
            painter.setPen(QPen(QColor(242, 128, 26), 1,
                                Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if tool == ToolType.LINE:
                painter.drawLine(sx1, sy1, sx2, sy2)
            elif tool == ToolType.RECT:
                painter.drawRect(QRect(min(sx1,sx2), min(sy1,sy2),
                                       abs(sx2-sx1), abs(sy2-sy1)))
            elif tool == ToolType.ELLIPSE:
                painter.drawEllipse(QRect(min(sx1,sx2), min(sy1,sy2),
                                          abs(sx2-sx1), abs(sy2-sy1)))
            elif tool == ToolType.TRIANGLE:
                from PyQt6.QtGui import QPolygon
                cx_t = (sx1 + sx2) // 2
                poly = QPolygon([
                    QPoint(cx_t, sy1),
                    QPoint(sx1,  sy2),
                    QPoint(sx2,  sy2),
                ])
                painter.drawPolygon(poly)

        # Brush outline
        tool = self.canvas.current_tool
        if (self._cursor_pos is not None
                and tool in (ToolType.PEN, ToolType.ERASER,
                             ToolType.SMUDGE)):
            r  = max(1, int(self.canvas.brush.size * self._zoom / 2))
            cx = self._cursor_pos.x()
            cy = self._cursor_pos.y()
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1,
                                Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            painter.setPen(QPen(QColor(0, 0, 0, 150), 1))
            painter.drawEllipse(cx-r-1, cy-r-1, r*2+2, r*2+2)

        # Preview cuentagotas
        if (self._cursor_pos is not None
                and tool == ToolType.EYEDROP):
            cp_canvas = self.widget_to_canvas(self._cursor_pos)
            x, y = cp_canvas.x(), cp_canvas.y()
            if (0 <= x < self.canvas.width
                    and 0 <= y < self.canvas.height):
                img   = self._get_composite()
                color = img.pixelColor(x, y)
                cx    = self._cursor_pos.x()
                cy    = self._cursor_pos.y()
                painter.setPen(QPen(Qt.GlobalColor.white, 2))
                painter.setBrush(color)
                painter.drawEllipse(cx-14, cy-14, 28, 28)
                painter.setPen(QPen(QColor(0,0,0,150), 1))
                painter.drawEllipse(cx-15, cy-15, 30, 30)

        # Transform handles
        if self.canvas.transform_box is not None:
            self.canvas.transform_box.draw(
                painter, self._zoom, self._offset)
            


        

        # Cuadrícula

        #cuadricula color y grosor
        if getattr(self, '_grid_visible', False):
            #RGB    TRansparencia     Grosor
            grid_pen = QPen(QColor(242, 128, 26, 90), 1,
                            Qt.PenStyle.SolidLine)
            painter.setPen(grid_pen)
            gs = max(1, int(self._grid_size * self._zoom))
            x  = ox % gs
            while x < self.width():
                painter.drawLine(x, 0, x, self.height())
                x += gs
            y = oy % gs
            while y < self.height():
                painter.drawLine(0, y, self.width(), y)
                y += gs
                

        # Overlay de regla activa
        if self._active_ruler is not None:
            self._active_ruler.draw_overlay(
                painter, self._zoom, self._offset)

        if (self.canvas.current_tool == ToolType.BEZIER
                and self._bezier_path is not None):
            self._draw_bezier_overlay(painter)

        painter.end()

    # ── Coordenadas ───────────────────────────────────────────────────

    def widget_to_canvas(self, p: QPoint) -> QPoint:
        return QPoint(
            int((p.x() - self._offset.x()) / self._zoom),
            int((p.y() - self._offset.y()) / self._zoom))

    # ── Mouse ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        tool = self.canvas.current_tool
        if (self._active_ruler is not None
                and event.button() == Qt.MouseButton.LeftButton):
            cp_r = self.widget_to_canvas(event.pos())
            handle = self._ruler_hit_handle(self._active_ruler, cp_r, self._zoom)
            if self._ruler_center_hit(self._active_ruler, cp_r, self._zoom):
                self._ruler_editing = True
                self._ruler_handle  = 0
                return
            elif handle > 0:
                self._ruler_editing = True
                self._ruler_handle  = handle
                return
        
        if tool == ToolType.BEZIER:
            self._bezier_press(event)
            return
            

        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last = event.pos()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        cp = self.widget_to_canvas(event.pos())

        # Referencia: Alt+Click para arrastrarla
        if (event.modifiers() & Qt.KeyboardModifier.AltModifier
                and self.canvas.reference.active):
            if self.canvas.reference.contains(cp):
                self.canvas.reference.start_drag(cp)
                self._ref_dragging = True
                return

        sel  = self.canvas.selection
        tool = self.canvas.current_tool

        # ── SELECT ────────────────────────────────────────────────────
        if tool == ToolType.SELECT:
            sel.clear()
            self._sel_state  = "drawing"
            self._sel_origin = cp
            self.mark_dirty_stroke()
            return

        # ── SELECT_CIRCLE ─────────────────────────────────────────────
        if tool == ToolType.SELECT_CIRCLE:
            sel.clear()
            self._sel_state  = "drawing"
            self._sel_origin = cp
            self.mark_dirty_stroke()
            return

        # ── HAND ──────────────────────────────────────────────────────
        if tool == ToolType.HAND:
            self._pan_last = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        # ── LASSO ─────────────────────────────────────────────────────
        if tool == ToolType.LASSO:
            if sel.has_float:
                if sel.point_in_float(cp):
                    self._sel_state = "floating"
                    self._move_last = cp
                else:
                    self.canvas.stamp_selection()
                    sel.clear()
                    self._sel_state  = "drawing"
                    self._sel_origin = cp
                    sel.lasso_add_point(cp)
            else:
                if (self._sel_state == "ready"
                        and sel.point_in_rect(cp)):
                    self.canvas.lift_selection()
                    self._sel_state = "floating"
                    self._move_last = cp
                else:
                    sel.clear()
                    self._sel_state  = "drawing"
                    self._sel_origin = cp
                    sel.lasso_add_point(cp)
            self.mark_dirty_stroke()
            return

        # ── FILL ──────────────────────────────────────────────────────
        if tool == ToolType.FILL:
            x, y = cp.x(), cp.y()
            if 0 <= x < self.canvas.width and 0 <= y < self.canvas.height:
                self.canvas.fill(x, y)
                self.mark_dirty()
            return

        # ── EYEDROP ───────────────────────────────────────────────────
        if tool == ToolType.EYEDROP:
            x, y = cp.x(), cp.y()
            if (0 <= x < self.canvas.width
                    and 0 <= y < self.canvas.height):
                img   = self.canvas.composite()
                color = img.pixelColor(x, y)
                b     = self.canvas.brush
                b.color_r = color.red()
                b.color_g = color.green()
                b.color_b = color.blue()
                b.color_a = color.alpha()
                win = self.window()
                if hasattr(win, '_apply_primary_color'):
                    win._apply_primary_color(color)
            return

        # ── TRANSFORM ─────────────────────────────────────────────────
        if tool == ToolType.TRANSFORM:
            tb = self.canvas.transform_box

            if tb is None:
                self.canvas.begin_transform()
                self.mark_dirty_stroke()
                return

            cpf    = QPointF(cp.x(), cp.y())
            handle = tb.hit_handle(cpf, self._zoom)

            if handle is not None:
                tb.start_drag(handle, cpf)
                self._transform_drag_handle = handle
            elif tb.hit_interior(cpf):
                tb.start_drag(-1, cpf)
                self._transform_moving = True
            else:
                self.canvas.commit_transform()
                self.mark_dirty()
            return

        # ── FORMAS ────────────────────────────────────────────────────
        if tool in (ToolType.LINE, ToolType.RECT,
                    ToolType.ELLIPSE, ToolType.TRIANGLE):
            self.canvas.push_history()
            snapped = self._apply_ruler(cp.x(), cp.y())
            start = (QPoint(int(snapped[0][0]), int(snapped[0][1]))
                     if snapped else cp)
            self._shape_start       = start
            self._shape_preview_end = start
            self._is_drawing        = True
            return

        # ── TEXT ──────────────────────────────────────────────────────
        if tool == ToolType.TEXT:
            self._place_text(cp)
            return

        # ── PEN / ERASER / SMUDGE ─────────────────────────────────────
        self._is_drawing  = True
        ruler_pts_init = self._apply_ruler(cp.x(), cp.y())
        # Inicializar todos los slots con el punto snapeado correspondiente
        snapped_init = ruler_pts_init if ruler_pts_init else [(cp.x(), cp.y())]
        self._ruler_last_pts = []
        for i in range(16):
            if i < len(snapped_init):
                self._ruler_last_pts.append(snapped_init[i])
            else:
                self._ruler_last_pts.append(snapped_init[0])
        if ruler_pts_init:
            self._last_pos = QPoint(int(ruler_pts_init[0][0]), int(ruler_pts_init[0][1]))
        else:
            self._last_pos = cp
        self._stab_last  = None
        self.canvas.stabilizer.reset()

        if tool == ToolType.SMUDGE:
            for (rx, ry) in self._apply_ruler(cp.x(), cp.y()):
                self.canvas.smudge(
                    self._last_pos.x(), self._last_pos.y(),
                    rx, ry)
            self.mark_dirty_stroke()
            return

        self.canvas.begin_stroke()
        self._ruler_first_move = (self._active_ruler is not None)

        self.mark_dirty_stroke()

    def mouseMoveEvent(self, event):
        tool = self.canvas.current_tool
        if self._ruler_editing and self._active_ruler is not None:
            cp = self.widget_to_canvas(event.pos())
            self._active_ruler.handle_drag(
                cp.x(), cp.y(), self._ruler_handle)
            self._request_paint()
            return

        self._cursor_pos = event.pos()
        self.update()


        if tool == ToolType.BEZIER:
            self._bezier_move(event)
            return

        if self._active_ruler is not None and not self._is_drawing:
            cp_r = self.widget_to_canvas(event.pos())
            handle = self._ruler_hit_handle(self._active_ruler, cp_r, self._zoom)
            if self._ruler_center_hit(self._active_ruler, cp_r, self._zoom):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            elif handle > 0:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

        if self._pan_last is not None:
            self._offset  += event.pos() - self._pan_last
            self._pan_last = event.pos()
            self._request_paint()
            return

        if getattr(self, '_ref_dragging', False):
            cp = self.widget_to_canvas(event.pos())
            self.canvas.reference.drag_to(cp)
            self._request_paint()
            return

        cp   = self.widget_to_canvas(event.pos())
        sel  = self.canvas.selection
        tool = self.canvas.current_tool

        if tool == ToolType.LASSO:
            if self._sel_state == "floating" and self._move_last is not None:
                delta = cp - self._move_last
                self.canvas.selection.move_float(delta)
                self._move_last = cp
                self.mark_dirty_stroke()
                return
            if self._sel_state == "drawing":
                self.canvas.selection.lasso_add_point(cp)
                self.mark_dirty_stroke()
            return

        if self._sel_state == "floating" and self._move_last is not None:
            delta = cp - self._move_last
            sel.move_float(delta)
            self._move_last = cp
            self.mark_dirty_stroke()
            return

        if tool == ToolType.SELECT:
            if self._sel_state == "drawing" and self._sel_origin is not None:
                sel.set_rect(self._sel_origin.x(), self._sel_origin.y(),
                             cp.x(), cp.y())
                self.mark_dirty_stroke()
            return

        if tool == ToolType.SELECT_CIRCLE:
            if self._sel_state == "drawing" and \
                    self._sel_origin is not None:
                self.canvas.selection.set_ellipse(
                    self._sel_origin.x(), self._sel_origin.y(),
                    cp.x(), cp.y(),
                    self.canvas.width, self.canvas.height)
                self.mark_dirty_stroke()
            return

        if (self._is_drawing
                and tool in (ToolType.LINE, ToolType.RECT,
                             ToolType.ELLIPSE, ToolType.TRIANGLE)):
            snapped = self._apply_ruler(cp.x(), cp.y())
            self._shape_preview_end = (
                QPoint(int(snapped[0][0]), int(snapped[0][1]))
                if snapped else cp)
            self._request_paint()
            return

        if tool == ToolType.TRANSFORM:
            tb = self.canvas.transform_box
            if tb is not None and (
                    self._transform_drag_handle is not None
                    or self._transform_moving):
                cpf = QPointF(cp.x(), cp.y())
                win = self.window()
                constrain = bool(
                    (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                    or getattr(win, '_transform_lock_ratio', False)
                )
                tb.drag_to(cpf, constrain)
                if hasattr(win, 'props_bar'):
                    win.props_bar.update_transform(tb)
                self.mark_dirty_stroke()
            return
        
        if self._is_drawing and self._last_pos is not None:
            if tool == ToolType.SMUDGE:
                stab = self.canvas.stabilizer
                # Estabilizar el punto crudo del cursor ANTES de snapear
                # a la regla — si se snapea primero y se promedia después,
                # el trazo corta por dentro de curvas (círculo/elipse) y
                # mezcla puntos de distintos ejes en la regla de simetría.
                if stab.active:
                    smoothed_raw = stab.add_point(cp)
                    if smoothed_raw is None:
                        return
                    draw_input = smoothed_raw
                else:
                    draw_input = cp

                ruler_pts = self._apply_ruler(draw_input.x(), draw_input.y())

                for i, (rx, ry) in enumerate(ruler_pts):
                    lx, ly = (self._ruler_last_pts[i]
                              if i < len(self._ruler_last_pts)
                              else (cp.x(), cp.y()))
                    self.canvas.smudge(lx, ly, rx, ry)

                self._ruler_last_pts = [(rx, ry) for (rx, ry) in ruler_pts]
                self._last_pos = cp

                self.mark_dirty_stroke()
                return

            stab = self.canvas.stabilizer

            # Estabilizar el punto CRUDO del cursor antes de aplicar la
            # regla. Antes se snapeaba primero y se promediaban los
            # puntos YA snapeados — eso corta por dentro de las curvas
            # (círculo/elipse) y, con la regla de simetría, mezclaba en
            # un solo buffer puntos de distintos ejes reflejados.
            # Estabilizando el punto crudo una sola vez y snapeándolo
            # después, la forma de la regla siempre se respeta y los
            # reflejos quedan perfectamente simétricos.
            if stab.active:
                smoothed_raw = stab.add_point(cp)
                if smoothed_raw is None:
                    return
                draw_input = smoothed_raw
            else:
                draw_input = cp

            ruler_pts = self._apply_ruler(draw_input.x(), draw_input.y())

            from core.ruler import CircleRuler, EllipseRuler
            use_arc = (self._active_ruler is not None
                       and self._active_ruler.active
                       and isinstance(self._active_ruler, (CircleRuler, EllipseRuler)))
            for i, (rx, ry) in enumerate(ruler_pts):
                if i < len(self._ruler_last_pts):
                    lx, ly = self._ruler_last_pts[i]
                else:
                    lx, ly = self._ruler_last_pts[0] if self._ruler_last_pts else (self._last_pos.x(), self._last_pos.y())

                # Interpolar a lo largo del arco si es círculo o elipse
                if use_arc:
                    arc_pts = self._active_ruler.snap_interpolated(lx, ly, rx, ry)
                    prev_x, prev_y = lx, ly
                    for ax, ay in arc_pts:
                        self.canvas.stroke(int(prev_x), int(prev_y), int(ax), int(ay))
                        prev_x, prev_y = ax, ay
                else:
                    self.canvas.stroke(lx, ly, rx, ry)

            self._ruler_last_pts = [(rx, ry) for (rx, ry) in ruler_pts]
            from core.ruler import SymmetryRuler
            if isinstance(self._active_ruler, SymmetryRuler):
                self._last_pos = cp
            else:
                if ruler_pts:
                    self._last_pos = QPoint(int(ruler_pts[0][0]), int(ruler_pts[0][1]))
                else:
                    self._last_pos = cp

            self.mark_dirty_stroke()

    def mouseReleaseEvent(self, event):
        tool = self.canvas.current_tool
        if self._ruler_editing:
            self._ruler_editing = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if tool == ToolType.BEZIER:
            self._bezier_release(event)
            return

        if getattr(self, '_ref_dragging', False):
            self.canvas.reference.end_drag()
            self._ref_dragging = False
            self._request_paint()
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last = None
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.canvas.current_tool == ToolType.HAND:
            self._pan_last = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return

        cp   = self.widget_to_canvas(event.pos())
        tool = self.canvas.current_tool
        sel  = self.canvas.selection

        if tool == ToolType.SELECT:
            if self._sel_state == "drawing":
                self._sel_state = "ready" if sel.active else "idle"
            self.mark_dirty_stroke()
            return

        if tool == ToolType.SELECT_CIRCLE:
            if self._sel_state == "drawing":
                self._sel_state = "ready" if self.canvas.selection.active else "idle"
            self.mark_dirty_stroke()
            return

        if tool == ToolType.LASSO:
            if self._sel_state == "drawing":
                self.canvas.selection.lasso_close(
                    self.canvas.width, self.canvas.height)
                self._sel_state = "ready" if self.canvas.selection.active else "idle"
            self.mark_dirty_stroke()
            return

        if (tool in (ToolType.LINE, ToolType.RECT,
                     ToolType.ELLIPSE, ToolType.TRIANGLE)
                and self._shape_start is not None):
            filled = getattr(self.canvas, '_shape_filled', False)
            stroke = True

            snapped_end = self._apply_ruler(cp.x(), cp.y())
            if snapped_end:
                cp = QPoint(int(snapped_end[0][0]), int(snapped_end[0][1]))

            if tool == ToolType.LINE:

                constrain = bool(
                    event.modifiers() &
                    Qt.KeyboardModifier.ShiftModifier)
                if constrain:
                    dx = cp.x() - self._shape_start.x()
                    dy = cp.y() - self._shape_start.y()
                    import math
                    angle = math.degrees(math.atan2(dy, dx))
                    snap  = round(angle / 45) * 45
                    dist  = math.sqrt(dx*dx + dy*dy)
                    rad   = math.radians(snap)
                    cp    = QPoint(
                        self._shape_start.x() + int(dist * math.cos(rad)),
                        self._shape_start.y() + int(dist * math.sin(rad)))
                self.canvas.draw_line(
                    self._shape_start.x(), self._shape_start.y(),
                    cp.x(), cp.y())

            elif tool == ToolType.RECT:
                end = cp
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    dx   = cp.x() - self._shape_start.x()
                    dy   = cp.y() - self._shape_start.y()
                    side = min(abs(dx), abs(dy))
                    end  = QPoint(
                        self._shape_start.x() + (side if dx>0 else -side),
                        self._shape_start.y() + (side if dy>0 else -side))
                self.canvas.draw_rect(
                    self._shape_start.x(), self._shape_start.y(),
                    end.x(), end.y(), filled, stroke)

            elif tool == ToolType.ELLIPSE:
                end = cp
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    dx   = cp.x() - self._shape_start.x()
                    dy   = cp.y() - self._shape_start.y()
                    side = min(abs(dx), abs(dy))
                    end  = QPoint(
                        self._shape_start.x() + (side if dx>0 else -side),
                        self._shape_start.y() + (side if dy>0 else -side))
                self.canvas.draw_ellipse(
                    self._shape_start.x(), self._shape_start.y(),
                    end.x(), end.y(), filled, stroke)

            elif tool == ToolType.TRIANGLE:
                self.canvas.draw_triangle(
                    self._shape_start.x(), self._shape_start.y(),
                    cp.x(), cp.y(), filled, stroke)

            self._shape_start       = None
            self._shape_preview_end = None
            self._is_drawing        = False
            self.mark_dirty()
            return

        if tool == ToolType.TRANSFORM:
            tb = self.canvas.transform_box
            if tb is not None:
                tb.end_drag()
            self._transform_drag_handle = None
            self._transform_moving      = False
            return

        if self._is_drawing:
            stab = self.canvas.stabilizer
            if stab.active and stab._last_committed is not None:
                from core.ruler import CircleRuler, EllipseRuler
                use_arc = (self._active_ruler is not None
                           and self._active_ruler.active
                           and isinstance(self._active_ruler,
                                          (CircleRuler, EllipseRuler)))
                # Los puntos que "flushea" el estabilizador son posiciones
                # CRUDAS del cursor — hay que snapearlas a la regla antes
                # de dibujarlas, igual que durante el arrastre.
                for raw_pt in stab.flush(cp):
                    ruler_pts = self._apply_ruler(raw_pt.x(), raw_pt.y())
                    for i, (rx, ry) in enumerate(ruler_pts):
                        lx, ly = (self._ruler_last_pts[i]
                                  if i < len(self._ruler_last_pts)
                                  else (self._ruler_last_pts[0]
                                        if self._ruler_last_pts
                                        else (rx, ry)))
                        if use_arc:
                            arc_pts = self._active_ruler.snap_interpolated(
                                lx, ly, rx, ry)
                            prev_x, prev_y = lx, ly
                            for ax, ay in arc_pts:
                                self.canvas.stroke(
                                    int(prev_x), int(prev_y),
                                    int(ax), int(ay))
                                prev_x, prev_y = ax, ay
                        else:
                            self.canvas.stroke(lx, ly, rx, ry)
                    self._ruler_last_pts = [
                        (rx, ry) for (rx, ry) in ruler_pts]

            self.canvas.commit_stroke()
            self._is_drawing  = False
            self._last_pos    = None
            self._stab_last   = None
            self.canvas.stabilizer.reset()
            self.mark_dirty()

    

    def wheelEvent(self, event: QWheelEvent):
        factor    = 1.1 if event.angleDelta().y() > 0 else 0.9
        mouse_pos = event.position().toPoint()
        old_zoom  = self._zoom
        self._zoom = max(0.05, min(20.0, self._zoom * factor))
        sc = self._zoom / old_zoom
        self._offset = QPoint(
            int(mouse_pos.x() - sc*(mouse_pos.x() - self._offset.x())),
            int(mouse_pos.y() - sc*(mouse_pos.y() - self._offset.y())))
        self._request_paint()
        self._update_zoom_label()

    def fit_canvas(self):
        if self.width() == 0 or self.height() == 0:
            return
        zw = self.width()  / self.canvas.width
        zh = self.height() / self.canvas.height
        self._zoom = min(zw, zh) * 0.95
        self._offset = QPoint(
            int((self.width()  - self.canvas.width  * self._zoom) / 2),
            int((self.height() - self.canvas.height * self._zoom) / 2))
        self._request_paint()
        self._update_zoom_label()

    def _place_text(self, cp: QPoint):
        from ui.text_dialog import TextDialog
        dlg = TextDialog(self.window())
        if dlg.exec() == TextDialog.DialogCode.Accepted:
            self.canvas.push_history()
            self.canvas.draw_text(cp.x(), cp.y(),
                                  dlg.result_text, dlg.result_font_size)
            self.mark_dirty()

    def leaveEvent(self, event):
        self._cursor_pos = None
        self._request_paint()

    def _update_zoom_label(self):
        pct = int(self._zoom * 100)
        self._zoom_label.setText(f"{pct}%")
        self._zoom_label.adjustSize()


    def _ruler_hit_handle(self, ruler, cp: QPoint, zoom: float = 1.0) -> int:
        """Detecta qué handle de la regla tocó el cursor. 0=centro."""
        from core.ruler import CircleRuler, EllipseRuler, LineRuler
        import math
        x, y = cp.x(), cp.y()
        thr  = 12 / max(0.05, zoom)  # ~12px de pantalla, no de canvas

        if isinstance(ruler, CircleRuler):
            # Handle de radio
            hx = ruler.cx + ruler.radius
            hy = ruler.cy
            if abs(x - hx) < thr and abs(y - hy) < thr:
                return 1

        elif isinstance(ruler, EllipseRuler):
            rad  = math.radians(ruler.angle)
            cos_ = math.cos(rad)
            sin_ = math.sin(rad)
            # Handle rx
            hx1 = ruler.cx + cos_ * ruler.rx
            hy1 = ruler.cy + sin_ * ruler.rx
            if abs(x - hx1) < thr and abs(y - hy1) < thr:
                return 1
            # Handle ry
            hx2 = ruler.cx - sin_ * ruler.ry
            hy2 = ruler.cy + cos_ * ruler.ry
            if abs(x - hx2) < thr and abs(y - hy2) < thr:
                return 2
            # Handle de rotación — un poco más allá de la punta de rx
            hx3 = ruler.cx + cos_ * (ruler.rx + 24)
            hy3 = ruler.cy + sin_ * (ruler.rx + 24)
            if abs(x - hx3) < thr and abs(y - hy3) < thr:
                return 3

        elif isinstance(ruler, LineRuler):
            # Handle de rotación — a una distancia fija del centro,
            # sobre la propia línea
            rad = math.radians(ruler.angle)
            hx  = ruler.cx + math.cos(rad) * 80
            hy  = ruler.cy + math.sin(rad) * 80
            if abs(x - hx) < thr and abs(y - hy) < thr:
                return 1

        return 0  # centro por defecto

    

    def _ruler_center_hit(self, ruler, cp: QPoint, zoom: float = 1.0) -> bool:
        """Devuelve True si el cursor está sobre el centro de la regla."""
        thr = 14 / max(0.05, zoom)  # ~14px de pantalla, no de canvas
        return (abs(cp.x() - ruler.cx) < thr
                and abs(cp.y() - ruler.cy) < thr)
    

    def _apply_ruler(self, x: int, y: int) -> list[tuple[int, int]]:
        """Aplica la regla activa y devuelve lista de puntos."""
        if (self._active_ruler is None
                or not self._active_ruler.active):
            return [(x, y)]

        snapped = self._active_ruler.snap(x, y)
        return [(int(px), int(py)) for px, py in snapped]
    




    def _draw_bezier_overlay(self, painter):
        from PyQt6.QtGui import QPainterPath, QPen, QBrush, QColor
        from PyQt6.QtCore import QPointF, Qt, QRectF

        path = self._bezier_path
        if path is None:
            return

        ox   = self._offset.x()
        oy   = self._offset.y()
        z    = self._zoom

        def sp(x, y):
            """Canvas coords → screen coords."""
            return QPointF(x * z + ox, y * z + oy)

        # ── Curva preview ─────────────────────────────────────────────
        segments = path.all_segments()
        if segments:
            pp = QPainterPath()
            pts = path.points
            first = pts[segments[0][0]]
            p0 = sp(first.x, first.y)
            pp.moveTo(p0)

            for i, j in segments:
                a  = pts[i]
                b  = pts[j]
                c1 = sp(*a.handle_out)
                c2 = sp(*b.handle_in)
                pb = sp(b.x, b.y)
                pp.cubicTo(c1, c2, pb)

            pen = QPen(QColor(self.canvas.brush.color_r,
                               self.canvas.brush.color_g,
                               self.canvas.brush.color_b,
                               self.canvas.brush.color_a),
                       self._bezier_stroke_width * z,
                       Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(pp)

        # ── Handles y anclas ──────────────────────────────────────────
        for i, pt in enumerate(path.points):
            ps = sp(pt.x, pt.y)

            # Líneas de handle
            painter.setPen(QPen(QColor(242, 128, 26, 160), 1))
            hout = sp(*pt.handle_out)
            hin  = sp(*pt.handle_in)

            # Solo dibujar handle out si tiene segmento siguiente
            has_next = any(s == i for s, _ in segments)
            has_prev = any(e == i for _, e in segments)

            if has_next and (pt.cx1 != 0 or pt.cy1 != 0):
                painter.drawLine(ps, hout)
                # Círculo handle out
                painter.setPen(QPen(QColor(242, 128, 26), 1))
                painter.setBrush(QBrush(QColor(242, 128, 26, 200)))
                painter.drawEllipse(hout, 5, 5)

            if has_prev and (pt.cx2 != 0 or pt.cy2 != 0):
                painter.drawLine(ps, hin)
                painter.setPen(QPen(QColor(242, 128, 26), 1))
                painter.setBrush(QBrush(QColor(242, 128, 26, 200)))
                painter.drawEllipse(hin, 5, 5)

            # Cuadrado ancla
            is_first = (i == 0)
            color = QColor(255, 220, 50) if is_first else QColor(255, 255, 255)
            painter.setPen(QPen(QColor(242, 128, 26), 2))
            painter.setBrush(QBrush(color))
            r = QRectF(ps.x() - 5, ps.y() - 5, 10, 10)
            painter.drawRect(r)

    # ── Bézier mouse events ───────────────────────────────────────────

    def _bezier_press(self, event):
        from core.bezier_path import BezierPath
        from PyQt6.QtCore import Qt

        cp   = self.widget_to_canvas(event.pos())
        x, y = float(cp.x()), float(cp.y())

        if self._bezier_path is None:
            self._bezier_path = BezierPath()
            self._bezier_path._stroke_width = self._bezier_stroke_width

        path = self._bezier_path

        # ── Intentar cerrar el path ───────────────────────────────────
        if (len(path.points) >= 2
                and path.hit_first_anchor(x, y)):
            path.close()
            self.mark_dirty_stroke()
            return

        # ── Hit test: mover ancla existente ──────────────────────────
        ai = path.hit_anchor(x, y)
        if ai is not None:
            self._bezier_dragging_anchor = ai
            return

        # Hit handle out
        hi = path.hit_handle_out(x, y)
        if hi is not None:
            self._bezier_dragging_hout = hi
            return

        # Hit handle in
        hi = path.hit_handle_in(x, y)
        if hi is not None:
            self._bezier_dragging_hin = hi
            return

        # ── Shift: ángulo fijo 45° ────────────────────────────────────
        if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                and path.points):
            import math
            prev = path.points[-1]
            dx = x - prev.x
            dy = y - prev.y
            angle = math.degrees(math.atan2(dy, dx))
            snap  = round(angle / 45) * 45
            dist  = math.sqrt(dx*dx + dy*dy)
            rad   = math.radians(snap)
            x = prev.x + dist * math.cos(rad)
            y = prev.y + dist * math.sin(rad)
        elif self._active_ruler is not None and self._active_ruler.active:
            # Sin Shift: si hay una regla puesta, la nueva ancla
            # se ajusta a ella igual que el resto de herramientas.
            snapped = self._apply_ruler(x, y)
            if snapped:
                x, y = float(snapped[0][0]), float(snapped[0][1])


        # ── Agregar nuevo punto ───────────────────────────────────────
        pt = path.add_point(x, y)
        self._bezier_placing = True
        self._bezier_dragging_anchor = len(path.points) - 1
        self.mark_dirty_stroke()

    def _bezier_move(self, event):
        from PyQt6.QtCore import Qt

        if self._bezier_path is None:
            return

        cp   = self.widget_to_canvas(event.pos())
        x, y = float(cp.x()), float(cp.y())
        path = self._bezier_path

        if self._bezier_placing and self._bezier_dragging_anchor is not None:
            # Al colocar con arrastre → definir handles
            pt = path.points[self._bezier_dragging_anchor]
            pt.set_handles_from_drag(x, y)
            self.mark_dirty_stroke()
            return

        if self._bezier_dragging_anchor is not None:
            # Mover ancla
            pt = path.points[self._bezier_dragging_anchor]
            dx = x - pt.x
            dy = y - pt.y
            path.move_anchor(self._bezier_dragging_anchor, dx, dy)
            self.mark_dirty_stroke()
            return

        if self._bezier_dragging_hout is not None:
            path.move_handle_out(self._bezier_dragging_hout, x, y)
            self.mark_dirty_stroke()
            return

        if self._bezier_dragging_hin is not None:
            path.move_handle_in(self._bezier_dragging_hin, x, y)
            self.mark_dirty_stroke()
            return

        # Solo redibuja para el cursor
        self.mark_dirty_stroke()

    def _bezier_release(self, event):
        self._bezier_placing          = False
        self._bezier_dragging_anchor  = None
        self._bezier_dragging_hout    = None
        self._bezier_dragging_hin     = None

    def bezier_confirm(self):
        """Aplica el path al canvas y lo limpia."""
        if (self._bezier_path is None
                or len(self._bezier_path.points) < 2):
            self._bezier_path = None
            self.mark_dirty_stroke()
            return
        self.canvas.push_history()
        self.canvas.draw_bezier_path(
            self._bezier_path,
            self._bezier_stroke_width)
        self._bezier_path = None
        self.mark_dirty()

    def bezier_cancel(self):
        """Descarta el path sin dibujar."""
        self._bezier_path = None
        self.mark_dirty_stroke()


class MainWindow(QMainWindow):
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 24):
        super().__init__()
        self._pen_size    = 8
        self._eraser_size = 24
        self._smudge_size = 16
        self.setWindowTitle("DrawEngine")
        self.resize(1440, 920)
        self.setStyleSheet(self._app_style())
        self._apply_dark_titlebar()
        self.canvas = Canvas(width, height, fps)
        self._anim_settings = {
            "playback_mode":      0,
            "onion_mode":         0,
            "onion_layers":       1,
            "onion_op_first":     50,
            "onion_op_last":      20,
            "onion_color_past":   "#dc3c3c",
            "onion_color_future": "#3c78dc",
        }

        self._config = UserConfig()
        self._apply_config()
        self._transform_use_center  = False
        self._transform_use_percent = False
        self._transform_lock_ratio  = False
        self._build_menu()
        self._build_ui()
        self._build_shortcuts()

        self._grid_visible  = False
        self._grid_size     = 50      # px en coordenadas canvas
        self._ref_window: 'ReferenceWindow | None' = None


        self._ruler_window: 'RulerPanel | None' = None
        self._active_ruler = None   # instancia de Ruler activa

    def _apply_dark_titlebar(self):
        from ui.dark_titlebar import apply_dark_titlebar
        apply_dark_titlebar(self)
      

    def _app_style(self):
        # Paleta MeshCraft: acento naranja RGB(242,128,26), fondos casi negro
        # (32,32,32) para menús, gris oscuro (40,40,40) para paneles/botones
        # inactivos y texto blanco puro.
        return """
            QMainWindow, QWidget { background: #202020; color: #ffffff; }
            QMenuBar {
                background: #181818; color: #cccccc;
                border-bottom: 1px solid #333; font-size: 12px;
            }
            QMenuBar::item:selected { background: #f2801a; color: #ffffff; }
            QMenu { background: #202020; color: #ffffff; border: 1px solid #444; }
            QMenu::item:selected { background: #f2801a; }
            QScrollBar:horizontal {
                background: #282828; height: 8px; border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #555; border-radius: 4px; min-width: 20px;
            }
            QScrollBar:vertical {
                background: #282828; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #555; border-radius: 4px; min-height: 20px;
            }
            QListWidget { background: #282828; border: none; color: #ffffff; }
            QListWidget::item:selected { background: #f2801a; }
            QListWidget::item:hover    { background: #333333; }
        """

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        self._add_action(file_menu, "New Project",   "Ctrl+N", self._new_project)
        file_menu.addSeparator()
        self._add_action(file_menu, "Save Project",  "Ctrl+S", self._save_project)
        self._add_action(file_menu, "Open Project…", "Ctrl+O", self._open_project)
        file_menu.addSeparator()
        self._add_action(file_menu, "Export…",       "Ctrl+E", self._open_export)
        file_menu.addSeparator()
        self._add_action(file_menu, "Import Image…", "Ctrl+I", self._trigger_import_image)
        self._add_action(file_menu, "Import Audio…", "Ctrl+M", self._trigger_import_audio)
        self._add_action(file_menu, "Import Video…", "Ctrl+Shift+V", self._trigger_import_video)

        edit_menu = mb.addMenu("Edit")
        self._add_action(edit_menu, "Undo", "Ctrl+Z", self._undo)
        self._add_action(edit_menu, "Redo", "Ctrl+Y", self._redo)
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Crop Layer",
                         "Ctrl+Shift+X", self._crop_layer)
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Flip Horizontal",
                         "Ctrl+Shift+H", self._flip_h)
        self._add_action(edit_menu, "Flip Vertical",
                         "Ctrl+Shift+V", self._flip_v)
        self._add_action(edit_menu, "Commit Transform",
                         "Return",       self._commit_transform)

        view_menu = mb.addMenu("View")
        self._add_action(view_menu, "Fit Canvas", "Ctrl+0", self._fit_canvas)
        self._add_action(view_menu, "Zoom In",    "Ctrl++", self._zoom_in)
        self._add_action(view_menu, "Zoom Out",   "Ctrl+-", self._zoom_out)

        anim_menu = mb.addMenu("Animation")
        self._add_action(anim_menu, "Add Frame",       "Ctrl+J",      self._add_frame)
        self._add_action(anim_menu, "Duplicate Frame", "Ctrl+D",      self._dup_current_frame)
        self._add_action(anim_menu, "Delete Frame",    "Ctrl+Delete", self._del_current_frame)


        

        # ── Adición ───────────────────────────────────────────────────
        add_menu = mb.addMenu("Adición")
        self._add_action(add_menu, "Ventana de Referencia",
                         "Ctrl+Shift+R", self._open_reference_window)
        self._add_action(add_menu, "Cuadrícula",
                         "Ctrl+G",       self._toggle_grid)
        self._add_action(add_menu, "Reglas",
                         "Ctrl+Shift+U", self._open_ruler_panel)

    def _add_action(self, menu: QMenu, label, shortcut, slot):
        act = QAction(label, self)
        act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        menu.addAction(act)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Barra de propiedades contextual (siempre visible) ─────────
        self.props_bar = ToolPropsBar()
        root.addWidget(self.props_bar)

        # ── Props bar — lápiz ─────────────────────────────────────────
        self.props_bar.pen_size_changed.connect(
            lambda v: setattr(self.canvas.brush, 'size', v))
        self.props_bar.pen_opacity_changed.connect(
            lambda v: setattr(self.canvas, 'brush_opacity', v))
        self.props_bar.pen_hardness_changed.connect(
            lambda v: setattr(self.canvas.brush, 'hardness', v))
        self.props_bar.pen_type_changed.connect(self._set_pen_type)
        self.props_bar.pen_stab_changed.connect(
            lambda v: self.canvas.stabilizer.set_level(v))

        # ── Props bar — borrador ──────────────────────────────────────
        self.props_bar.eraser_size_changed.connect(self._on_eraser_size)
        self.props_bar.eraser_opacity_changed.connect(
            lambda v: setattr(self.canvas, 'brush_opacity', v))
        self.props_bar.eraser_soft_changed.connect(
            lambda v: setattr(self.canvas, 'eraser_soft', v))
        self.props_bar.eraser_stab_changed.connect(
            lambda v: self.canvas.stabilizer.set_level(v))

        # ── Props bar — smudge ────────────────────────────────────────
        self.props_bar.smudge_size_changed.connect(self._on_smudge_size)
        self.props_bar.smudge_opacity_changed.connect(
            lambda v: setattr(self.canvas, 'brush_opacity', v))
        self.props_bar.smudge_stab_changed.connect(
            lambda v: self.canvas.stabilizer.set_level(v))

        # ── Props bar — fill ──────────────────────────────────────────
        self.props_bar.fill_tolerance_changed.connect(
            lambda v: setattr(self.canvas, 'fill_tolerance', v))

        # ── Props bar — texto ─────────────────────────────────────────
        self.props_bar.text_font_changed.connect(
            lambda f: setattr(self.canvas, '_text_font', f))
        self.props_bar.text_size_changed.connect(
            lambda v: setattr(self.canvas, '_text_size', v))
        self.props_bar.text_bold_changed.connect(
            lambda v: setattr(self.canvas, '_text_bold', v))
        self.props_bar.text_italic_changed.connect(
            lambda v: setattr(self.canvas, '_text_italic', v))

        # ── Props bar — formas ────────────────────────────────────────
        self.props_bar.shape_fill_changed.connect(
            lambda v: setattr(self.canvas, '_shape_filled', v))
        self.props_bar.shape_stroke_changed.connect(
            lambda v: setattr(self.canvas.brush, 'size', v))

        # ── Props bar — transform ─────────────────────────────────────
        self.props_bar.tx_x_changed.connect(self._tx_set_x)
        self.props_bar.tx_y_changed.connect(self._tx_set_y)
        self.props_bar.tx_w_changed.connect(self._tx_set_w)
        self.props_bar.tx_h_changed.connect(self._tx_set_h)
        self.props_bar.tx_angle_changed.connect(self._tx_set_angle)
        self.props_bar.tx_lock_toggled.connect(
            lambda v: setattr(self, '_transform_lock_ratio', v))
        self.props_bar.tx_pivot_toggled.connect(
            lambda v: setattr(self, '_transform_use_center', v))
        self.props_bar.tx_unit_toggled.connect(
            lambda v: setattr(self, '_transform_use_percent', v))
        self.props_bar.tx_rotate_left.connect(self._tx_rotate_left)
        self.props_bar.tx_rotate_right.connect(self._tx_rotate_right)
        self.props_bar.tx_flip_h.connect(self._flip_h)
        self.props_bar.tx_flip_v.connect(self._flip_v)
        self.props_bar.tx_cancelled.connect(self._tx_cancel)
        self.props_bar.tx_committed.connect(self._tx_commit)

        # ── Área de trabajo ───────────────────────────────────────────
        work = QWidget()
        work_layout = QHBoxLayout(work)
        work_layout.setContentsMargins(0, 0, 0, 0)
        work_layout.setSpacing(0)

        self.side_toolbar = SideToolbar()
        work_layout.addWidget(self.side_toolbar)

        # ── Popup de formas ───────────────────────────────────────────
        sp = self.side_toolbar._shapes_popup
        sp.line_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.LINE))
        sp.rect_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.RECT))
        sp.ellipse_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.ELLIPSE))
        sp.triangle_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.TRIANGLE))
        
        sp.bezier_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.BEZIER))

        # ── Popup de brush ────────────────────────────────────────────
        bp = self.side_toolbar._brush_popup
        bp.pen_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.PEN))
        bp.eraser_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.ERASER))
        bp.fill_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.FILL))
        bp.eyedrop_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.EYEDROP))
        bp.text_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.TEXT))
        bp.hand_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.HAND))
        bp.smudge_selected.connect(
            lambda: self._set_tool_and_ui(ToolType.SMUDGE))

        self.canvas_widget = CanvasWidget(self.canvas)
        work_layout.addWidget(self.canvas_widget)

        right = QWidget()
        right.setFixedWidth(204)
        right.setStyleSheet(
            "background: #202020; border-left: 1px solid #333;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.layer_panel  = LayerPanel()
        self.import_panel = ImportPanel()

        right_layout.addWidget(self.layer_panel,  stretch=1)
        right_layout.addWidget(self.import_panel, stretch=0)

        work_layout.addWidget(right)

        self.timeline = TimelineWidget(self.canvas.animation)
        root.addWidget(work)
        root.addWidget(self.timeline)

        # ── Señales del toolbar lateral ───────────────────────────────
        self.side_toolbar.tool_changed.connect(self._set_tool)
        self.side_toolbar.color_clicked.connect(self._pick_color)
        self.side_toolbar.color2_clicked.connect(self._pick_color2)
        self.side_toolbar.colors_swapped.connect(self._on_swap_colors)
        self.side_toolbar.recent_panel.color_selected.connect(
            self._apply_recent_color)

        # ── Señales del panel de capas ────────────────────────────────
        self.layer_panel.layer_added.connect(self._add_layer)
        self.layer_panel.layer_deleted.connect(self._delete_layer)
        self.layer_panel.layer_selected.connect(self._select_layer)
        self.layer_panel.layer_renamed.connect(self._rename_layer)
        self.layer_panel.layer_reordered.connect(self._reorder_layer)
        self.layer_panel.layer_visibility_changed.connect(
            self._toggle_layer_visibility)
        self.layer_panel.layer_opacity_changed.connect(
            self._set_layer_opacity)
        self.layer_panel.layer_blend_changed.connect(
            self._set_layer_blend)

        # ── Señales del timeline ──────────────────────────────────────
        self.timeline.frame_selected.connect(self._on_frame_changed)
        self.timeline.frame_added.connect(self._add_frame)
        self.timeline.frame_duplicated.connect(self._dup_frame)
        self.timeline.frame_deleted.connect(self._del_frame)
        self.timeline.btn_anim_cfg.clicked.connect(
            self._open_anim_settings)

        # ── Señales del import panel ──────────────────────────────────
        self.import_panel.image_import_requested.connect(
            self._import_image)
        self.import_panel.audio_import_requested.connect(
            self._import_audio)
        self.import_panel.video_import_requested.connect(self._import_video)
       

        # ── Popup de selección ────────────────────────────────────────
        popup = self.side_toolbar._sel_popup
        popup.deselect_requested.connect(self._sel_deselect)
        popup.select_by_opacity_requested.connect(self._sel_by_opacity)
        popup.clear_layer_requested.connect(self._sel_clear_layer)
        popup.select_rect_requested.connect(
            lambda: self._set_tool_and_ui(ToolType.SELECT))
        popup.select_circle_requested.connect(
            lambda: self._set_tool_and_ui(ToolType.SELECT_CIRCLE))
        popup.copy_requested.connect(self._sel_copy)
        popup.cut_requested.connect(self._sel_cut)
        popup.paste_requested.connect(self._sel_paste)

        self._refresh_layers()
        self.canvas_widget.show()
        QTimer.singleShot(100, self.canvas_widget.fit_canvas)
        self._restore_tools()



        self.props_bar.bezier_stroke_changed.connect(
            lambda v: setattr(self.canvas_widget, '_bezier_stroke_width', v))
        self.props_bar.bezier_confirm.connect(
            self.canvas_widget.bezier_confirm)
        self.props_bar.bezier_cancel.connect(
            self.canvas_widget.bezier_cancel)

    def _build_shortcuts(self):
        shortcuts = [
            ("P",      lambda: self._set_tool_and_ui(ToolType.PEN)),
            ("E",      lambda: self._set_tool_and_ui(ToolType.ERASER)),
            ("F",      lambda: self._set_tool_and_ui(ToolType.FILL)),
            ("S",      lambda: self._set_tool_and_ui(ToolType.SELECT)),
            ("A",      lambda: self._set_tool_and_ui(ToolType.LASSO)),
            ("I",      lambda: self._set_tool_and_ui(ToolType.EYEDROP)),
            ("L",      lambda: self._set_tool_and_ui(ToolType.LINE)),
            ("R",      lambda: self._set_tool_and_ui(ToolType.RECT)),
            ("O",      lambda: self._set_tool_and_ui(ToolType.ELLIPSE)),
            ("T",      lambda: self._set_tool_and_ui(ToolType.TEXT)),
            ("[",      lambda: self._adjust_size(-2)),
            ("]",      lambda: self._adjust_size(+2)),
            ("Space",  self.canvas_widget.fit_canvas),
            ("Escape", self._escape_selection),
            ("X",      self._swap_colors),
            ("G",      lambda: self._set_tool_and_ui(ToolType.TRIANGLE)),
            ("H",      lambda: self._set_tool_and_ui(ToolType.HAND)),
            ("B",      lambda: self._set_tool_and_ui(ToolType.SMUDGE)),
            ("C", lambda: self._set_tool_and_ui(ToolType.BEZIER)),
        
        # Enter confirma Bézier (además del transform):
        # Modifica el handler de Return así:
        ]
        for key, slot in shortcuts:
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(slot)

        sc_ct = QShortcut(QKeySequence("Ctrl+T"), self)
        sc_ct.activated.connect(self._activate_transform)

        sc_enter = QShortcut(QKeySequence("Return"), self)
        sc_enter.activated.connect(self._on_enter)

        sc_del = QShortcut(QKeySequence("Delete"), self)
        sc_del.activated.connect(self._tx_delete)

        sc_bs = QShortcut(QKeySequence("Backspace"), self)
        sc_bs.activated.connect(self._tx_delete)

        sc_copy = QShortcut(QKeySequence("Ctrl+C"), self)
        sc_copy.activated.connect(self._sel_copy)

        sc_cut = QShortcut(QKeySequence("Ctrl+X"), self)
        sc_cut.activated.connect(self._sel_cut)

        sc_paste = QShortcut(QKeySequence("Ctrl+V"), self)
        sc_paste.activated.connect(self._sel_paste)

    def _activate_transform(self):
        ok = self.canvas.begin_transform()
        if ok:
            self._set_tool_and_ui(ToolType.TRANSFORM)
            self._tx_sync()
            self.canvas_widget.mark_dirty()
        else:
            QMessageBox.information(
                self, "Transform",
                "No hay contenido para transformar en esta capa.")

    def _set_tool_and_ui(self, tool: ToolType):
        self.canvas.current_tool = tool
        self.side_toolbar.select_tool_external(tool)
        self.props_bar.switch_tool(tool)
        # Aplicar tamaño correcto según herramienta
        if tool == ToolType.ERASER:
            self.canvas.brush.size = self._eraser_size
        elif tool == ToolType.SMUDGE:
            self.canvas.brush.size = self._smudge_size
        else:
            self.canvas.brush.size = self._pen_size

    def _adjust_size(self, delta: int):
        tool = self.canvas.current_tool
        if tool == ToolType.ERASER:
            spin = self.props_bar.eraser_size
            new_val = max(1, min(200, spin.value() + delta))
            spin.setValue(new_val)
            self._eraser_size = new_val
            self.canvas.brush.size = new_val
        elif tool == ToolType.SMUDGE:
            spin = self.props_bar.smudge_size
            new_val = max(1, min(200, spin.value() + delta))
            spin.setValue(new_val)
            self._smudge_size = new_val
            self.canvas.brush.size = new_val
        else:
            spin = self.props_bar.pen_size
            new_val = max(1, min(200, spin.value() + delta))
            spin.setValue(new_val)
            self._pen_size = new_val
            self.canvas.brush.size = new_val

    def _set_tool(self, tool: ToolType):
        self.canvas.current_tool = tool
        self.props_bar.switch_tool(tool)
        if tool == ToolType.ERASER:
            self.canvas.brush.size = self._eraser_size
        elif tool == ToolType.SMUDGE:
            self.canvas.brush.size = self._smudge_size
        else:
            self.canvas.brush.size = self._pen_size
        if tool == ToolType.HAND:
            self.canvas_widget.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.canvas_widget.setCursor(Qt.CursorShape.ArrowCursor)

    def _pick_color(self):
        b   = self.canvas.brush
        dlg = ColorPickerDialog(
            QColor(b.color_r, b.color_g, b.color_b, b.color_a), self)
        dlg.color_selected.connect(self._apply_primary_color)
        dlg.exec()

    def _pick_color2(self):
        b   = self.canvas.brush
        dlg = ColorPickerDialog(
            QColor(b.color2_r, b.color2_g, b.color2_b, b.color2_a), self)
        dlg.color_selected.connect(self._apply_secondary_color)
        dlg.exec()

    def _apply_primary_color(self, color: QColor):
        b = self.canvas.brush
        b.color_r, b.color_g = color.red(),  color.green()
        b.color_b, b.color_a = color.blue(), color.alpha()
        self.side_toolbar.update_swatch(
            b.color_r, b.color_g, b.color_b, b.color_a)
        self.side_toolbar.add_recent_color(
            b.color_r, b.color_g, b.color_b, b.color_a)
        self._config.add_recent_color(
            b.color_r, b.color_g, b.color_b, b.color_a)

    def _apply_secondary_color(self, color: QColor):
        b = self.canvas.brush
        b.color2_r, b.color2_g = color.red(),  color.green()
        b.color2_b, b.color2_a = color.blue(), color.alpha()
        self.side_toolbar.update_swatch2(
            b.color2_r, b.color2_g, b.color2_b, b.color2_a)

    def _swap_colors(self):
        self.canvas.brush.swap_colors()
        b = self.canvas.brush
        self.side_toolbar.update_swatch(
            b.color_r, b.color_g, b.color_b, b.color_a)
        self.side_toolbar.update_swatch2(
            b.color2_r, b.color2_g, b.color2_b, b.color2_a)

    def _on_swap_colors(self):
        self._swap_colors()

    def _apply_recent_color(self, r: int, g: int, b: int, a: int):
        brush = self.canvas.brush
        brush.color_r = r
        brush.color_g = g
        brush.color_b = b
        brush.color_a = a
        self.side_toolbar.update_swatch(r, g, b, a)

    # ── Capas ─────────────────────────────────────────────────────────

    def _add_layer(self):
        self.canvas.push_history()
        self.canvas.add_layer()
        self._refresh_layers()
        self.canvas_widget.mark_dirty()

    def _delete_layer(self, index: int):
        self.canvas.push_history()
        real = len(self.canvas.layers) - 1 - index
        self.canvas.delete_layer(real)
        self._refresh_layers()
        self.canvas_widget.mark_dirty()

    def _select_layer(self, panel_index: int):
        self.canvas.active_layer_index = (
            len(self.canvas.layers) - 1 - panel_index)

    def _rename_layer(self, panel_index: int, name: str):
        real = len(self.canvas.layers) - 1 - panel_index
        if 0 <= real < len(self.canvas.layers):
            self.canvas.layers[real].name = name

    def _reorder_layer(self, from_panel: int, to_panel: int):
        layers    = self.canvas.layers
        n         = len(layers)
        from_real = n - 1 - from_panel
        to_real   = n - 1 - to_panel
        if from_real == to_real:
            return
        self.canvas.push_history()
        layer = layers.pop(from_real)
        layers.insert(to_real, layer)
        ai = self.canvas.active_layer_index
        if ai == from_real:
            self.canvas.active_layer_index = to_real
        self._refresh_layers()
        self.canvas_widget.mark_dirty()

    def _toggle_layer_visibility(self, panel_index: int, visible: bool):
        real = len(self.canvas.layers) - 1 - panel_index
        if 0 <= real < len(self.canvas.layers):
            self.canvas.layers[real].visible = visible
            self.canvas_widget.mark_dirty()

    def _refresh_layers(self):
        self.layer_panel.refresh(
            self.canvas.layers, self.canvas.active_layer_index)

    # ── Timeline ──────────────────────────────────────────────────────

    def _on_frame_changed(self, _):
        if self.timeline._playing:
            self.canvas_widget.mark_dirty()
        else:
            self._refresh_layers()
            self.canvas_widget.mark_dirty()

    def _add_frame(self):
        self.canvas.animation.add_frame()
        self.canvas.animation.current_frame_index = (
            len(self.canvas.animation.frames) - 1)
        self.timeline.refresh()
        self._refresh_layers()
        self.canvas_widget.mark_dirty()

    def _dup_frame(self, index: int):
        self.canvas.animation.duplicate_frame(index)
        self.canvas.animation.current_frame_index = index + 1
        self.timeline.refresh()
        self._refresh_layers()
        self.canvas_widget.mark_dirty()

    def _dup_current_frame(self):
        self._dup_frame(self.canvas.animation.current_frame_index)

    def _del_frame(self, index: int):
        self.canvas.animation.delete_frame(index)
        self.timeline.refresh()
        self._refresh_layers()
        self.canvas_widget.mark_dirty()

    def _del_current_frame(self):
        self._del_frame(self.canvas.animation.current_frame_index)

    # ── Import ────────────────────────────────────────────────────────

    def _import_image(self, path: str):
        import os
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "Error", f"Cannot load:\n{path}")
            return
        name  = os.path.splitext(os.path.basename(path))[0]
        layer = self.canvas.add_layer(f"IMG: {name}")
        if (image.width() != self.canvas.width
                or image.height() != self.canvas.height):
            image = image.scaled(
                self.canvas.width, self.canvas.height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        image   = image.convertToFormat(
            QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(layer.image)
        x = (self.canvas.width  - image.width())  // 2
        y = (self.canvas.height - image.height()) // 2
        painter.drawImage(x, y, image)
        painter.end()
        self._refresh_layers()
        self.canvas_widget.mark_dirty()


    def _import_video(self, path: str):
        
        dlg = VideoImportDialog(path, self.canvas, self)
        dlg.exec()
        self.timeline.refresh()
        self._refresh_layers()
        self.canvas_widget.mark_dirty()


    def _import_audio(self, path: str):
        self.canvas.animation.audio_path = path

    def _trigger_import_image(self):
        self.import_panel._pick_image()

    def _trigger_import_audio(self):
        self.import_panel._pick_audio()


    def _trigger_import_video(self):
        self.import_panel._pick_video()

    # ── Vista ─────────────────────────────────────────────────────────

    def _fit_canvas(self):
        self.canvas_widget.fit_canvas()

    def _zoom_in(self):
        self.canvas_widget._zoom = min(20.0, self.canvas_widget._zoom * 1.2)
        self.canvas_widget.mark_dirty()

    def _zoom_out(self):
        self.canvas_widget._zoom = max(0.05, self.canvas_widget._zoom / 1.2)
        self.canvas_widget.mark_dirty()

    # ── Proyecto ──────────────────────────────────────────────────────

    def _new_project(self):
        from ui.startup_dialog import StartupDialog
        dlg = StartupDialog(self)
        if dlg.exec() == StartupDialog.DialogCode.Accepted:
            self.canvas = Canvas(
                dlg.result_width, dlg.result_height, dlg.result_fps)
            self.canvas_widget.canvas = self.canvas
            self.timeline.animation   = self.canvas.animation
            self.timeline.refresh()
            self._refresh_layers()
            self.canvas_widget.fit_canvas()

    def _save_project(self):
        from PyQt6.QtWidgets import QFileDialog
        from core.project_io import save_project
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "project.dwe",
            "DrawEngine Project (*.dwe)")
        if not path:
            return
        try:
            save_project(self.canvas.animation, path)
            self.setWindowTitle(f"DrawEngine — {path}")
            self._config.add_recent_project(path)
            self._config.save()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _open_project(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "",
            "DrawEngine Project (*.dwe)")
        if not path:
            return
        self._open_project_path(path)

    def _open_project_path(self, path: str):
        """Carga un proyecto .dwe desde una ruta ya conocida (usado tanto
        por el diálogo 'Open Project' como por la pantalla de inicio al
        elegir un proyecto reciente)."""
        from core.project_io import load_project
        try:
            anim = load_project(path)
            from core.tools import BlendMode
            for frame in anim.frames:
                for layer in frame.layers:
                    if not hasattr(layer, "blend_mode"):
                        layer.blend_mode = BlendMode.NORMAL

            # Usar el constructor completo de Canvas (no Canvas.__new__),
            # para que existan TODOS los atributos que el resto del
            # código espera (paint_mask_active, brush_opacity,
            # stabilizer, reference, transform_box, etc.). Antes esto
            # se creaba con Canvas.__new__() y le faltaban atributos,
            # lo que rompía silenciosamente el dibujo de formas y otras
            # herramientas después de abrir un proyecto.
            new_canvas = Canvas(anim.width, anim.height, anim.fps)
            new_canvas.animation      = anim
            new_canvas.current_tool   = self.canvas.current_tool
            new_canvas.fill_tolerance = self.canvas.fill_tolerance
            new_canvas.fill_expand    = self.canvas.fill_expand

            self.canvas = new_canvas
            self.canvas_widget.canvas = new_canvas
            self.timeline.animation   = anim
            self.timeline.refresh()
            self._refresh_layers()
            self.canvas_widget.fit_canvas()
            self.setWindowTitle(f"DrawEngine — {path}")
            self._config.add_recent_project(path)
            self._config.save()
        except Exception as e:
            QMessageBox.critical(self, "Open Error", str(e))

    def _open_export(self):
        from ui.export_dialog import ExportDialog
        dlg = ExportDialog(self.canvas.animation, self.canvas, self)
        dlg.exec()

    # ── Selección ─────────────────────────────────────────────────────

    def _escape_selection(self):
        # Bézier: Escape cancela
        if self.canvas.current_tool == ToolType.BEZIER:
            self.canvas_widget.bezier_cancel()
            return
        sel = self.canvas.selection
        if sel.has_float:
            self.canvas.stamp_selection()
        sel.clear()
        self.canvas.clear_paint_mask()
        self.canvas_widget._sel_state = "idle"
        self.canvas_widget.mark_dirty()


    def _on_enter(self):
        if self.canvas.current_tool == ToolType.BEZIER:
            self.canvas_widget.bezier_confirm()
        else:
            self._tx_commit()

    # ── Historial ─────────────────────────────────────────────────────

    def _undo(self):
        if self.canvas.undo():
            self._refresh_layers()
            self.timeline.refresh()
            self.canvas_widget.mark_dirty()

    def _redo(self):
        if self.canvas.redo():
            self._refresh_layers()
            self.timeline.refresh()
            self.canvas_widget.mark_dirty()

    # ── Animación ─────────────────────────────────────────────────────

    def _open_anim_settings(self):
        from ui.anim_settings import AnimSettingsDialog
        dlg = AnimSettingsDialog(self._anim_settings, self)
        dlg.settings_changed.connect(self._apply_anim_settings)
        dlg.exec()

    def _apply_anim_settings(self, s: dict):
        self._anim_settings = s
        c = self.canvas

        mode = s["onion_mode"]
        c.onion_enabled  = mode != 0
        c.onion_prev     = s["onion_layers"] if mode in (1, 2) else 0
        c.onion_next     = s["onion_layers"] if mode in (1, 3) else 0
        c.onion_op_first = float(s["onion_op_first"])
        c.onion_op_last  = float(s["onion_op_last"])

        pc = QColor(s["onion_color_past"])
        fc = QColor(s["onion_color_future"])
        c.onion_color_past   = (pc.red(), pc.green(), pc.blue())
        c.onion_color_future = (fc.red(), fc.green(), fc.blue())

        self.timeline.set_playback_mode(s["playback_mode"])
        c.request_onion_update(callback=self.canvas_widget.mark_dirty)
        self.canvas_widget.mark_dirty()

    def _apply_config(self):
        cfg = self._config
        w = cfg.get("window_w", 1440)
        h = cfg.get("window_h", 920)
        self.resize(w, h)
        x = cfg.get("window_x", -1)
        y = cfg.get("window_y", -1)
        if x >= 0 and y >= 0:
            self.move(x, y)
        self._anim_settings = cfg.get_anim_settings()
        QTimer.singleShot(150, lambda: self._apply_anim_settings(
            self._anim_settings))

    def _restore_tools(self):
        """Restaura herramientas después de que la UI está construida."""
        cfg = self._config

        # ── Color primario ────────────────────────────────────────────
        r = cfg.get("brush_color_r", 0)
        g = cfg.get("brush_color_g", 0)
        b = cfg.get("brush_color_b", 0)
        a = cfg.get("brush_color_a", 255)
        self.canvas.brush.color_r = r
        self.canvas.brush.color_g = g
        self.canvas.brush.color_b = b
        self.canvas.brush.color_a = a
        self.side_toolbar.update_swatch(r, g, b, a)

        # ── Tamaños ───────────────────────────────────────────────────
        pen_size    = cfg.get("brush_size",  8)
        eraser_size = cfg.get("eraser_size", 24)
        self._pen_size    = pen_size
        self._eraser_size = eraser_size
        self._smudge_size = cfg.get("smudge_size", 16)
        self.canvas.brush.size = pen_size

        # ── Opacidad ──────────────────────────────────────────────────
        op = cfg.get("brush_opacity", 100)
        self.canvas.brush_opacity = op / 100.0

        # ── Tolerancia ────────────────────────────────────────────────
        tol = cfg.get("fill_tolerance", 15)
        self.canvas.fill_tolerance = tol

        # ── Estabilizador ─────────────────────────────────────────────
        stab = cfg.get("stabilizer", 0)
        self.canvas.stabilizer.set_level(stab)

        # ── Borrador suave ────────────────────────────────────────────
        soft = cfg.get("eraser_soft", False)
        self.canvas.eraser_soft = soft

        # ── Sincronizar props_bar ─────────────────────────────────────
        self.props_bar.set_pen_values(
            size=pen_size,
            opacity=op,
            hardness=int(getattr(self.canvas.brush, 'hardness', 1.0) * 100),
            stab=stab,
        )
        self.props_bar.set_eraser_values(
            size=eraser_size,
            opacity=op,
            soft=soft,
            stab=stab,
        )
        self.props_bar.fill_tol.blockSignals(True)
        self.props_bar.fill_tol.setValue(tol)
        self.props_bar.fill_tol.blockSignals(False)

        # ── Colores recientes ─────────────────────────────────────────
        recent = cfg.get("recent_colors", [])
        self.side_toolbar.set_recent_colors(recent)

        # ── Herramienta activa ────────────────────────────────────────
        tool_name = cfg.get("tool", "PEN")
        tool_map  = {
            "PEN":     ToolType.PEN,
            "ERASER":  ToolType.ERASER,
            "FILL":    ToolType.FILL,
            "SELECT":  ToolType.SELECT,
            "LINE":    ToolType.LINE,
            "RECT":    ToolType.RECT,
            "ELLIPSE": ToolType.ELLIPSE,
            "TEXT":    ToolType.TEXT,
        }
        tool = tool_map.get(tool_name, ToolType.PEN)
        self._set_tool_and_ui(tool)

    def _save_config(self):
        """Guarda el estado actual antes de cerrar."""
        cfg = self._config
        b   = self.canvas.brush

        geo = self.geometry()
        cfg.set("window_w", geo.width())
        cfg.set("window_h", geo.height())
        cfg.set("window_x", geo.x())
        cfg.set("window_y", geo.y())

        cfg.set("tool",           self.canvas.current_tool.name)
        cfg.set("brush_size",     self.props_bar.pen_size.value())
        cfg.set("eraser_size",    self.props_bar.eraser_size.value())
        cfg.set("smudge_size",    self._smudge_size)
        cfg.set("brush_opacity",  self.props_bar.pen_opacity.value())
        cfg.set("brush_color_r",  b.color_r)
        cfg.set("brush_color_g",  b.color_g)
        cfg.set("brush_color_b",  b.color_b)
        cfg.set("brush_color_a",  b.color_a)
        cfg.set("fill_tolerance", self.props_bar.fill_tol.value())
        cfg.set("stabilizer",     self.props_bar.pen_stab.value())
        cfg.set("eraser_soft",
                self.props_bar.eraser_soft_combo.currentIndex() == 1)
        cfg.set("recent_colors",  self.side_toolbar._recent_colors)

        cfg.set_anim_settings(self._anim_settings)
        cfg.save()

    def closeEvent(self, event):
        self._save_config()
        event.accept()

    # ── Referencia ────────────────────────────────────────────────────

    def _load_reference(self, path: str):
        ok = self.canvas.reference.load(
            path, self.canvas.width, self.canvas.height)
        if not ok:
            QMessageBox.warning(self, "Error",
                                f"Cannot load reference:\n{path}")
            return
        self.canvas_widget._request_paint()

    def _clear_reference(self):
        self.canvas.reference.clear()
        self.canvas_widget._request_paint()

    def _set_reference_opacity(self, opacity: float):
        self.canvas.reference.opacity = opacity
        self.canvas_widget._request_paint()

    def _set_reference_visible(self, visible: bool):
        self.canvas.reference.visible = visible
        self.canvas_widget._request_paint()

    # ── Capas (propiedades) ───────────────────────────────────────────

    def _set_layer_opacity(self, panel_index: int, opacity: int):
        real = len(self.canvas.layers) - 1 - panel_index
        if 0 <= real < len(self.canvas.layers):
            self.canvas.layers[real].opacity = opacity
            self.canvas_widget.mark_dirty()

    def _set_layer_blend(self, panel_index: int, mode):
        real = len(self.canvas.layers) - 1 - panel_index
        if 0 <= real < len(self.canvas.layers):
            self.canvas.layers[real].blend_mode = mode
            self.canvas_widget.mark_dirty()

    # ── Flip / Transform ──────────────────────────────────────────────

    def _flip_h(self):
        if self.canvas.transform_box:
            self.canvas.transform_box.do_flip_h()
            self.canvas_widget.mark_dirty_stroke()

    def _flip_v(self):
        if self.canvas.transform_box:
            self.canvas.transform_box.do_flip_v()
            self.canvas_widget.mark_dirty_stroke()

    def _commit_transform(self):
        if self.canvas.transform_box:
            self.canvas.commit_transform()
            self.canvas_widget.mark_dirty()

    def _show_transform_bar(self, show):
        if show:
            self.props_bar.switch_tool(ToolType.TRANSFORM)

    def _tx_sync(self):
        if self.canvas.transform_box is not None:
            self.props_bar.update_transform(self.canvas.transform_box)

    def _tx_set_x(self, v: float):
        tb = self.canvas.transform_box
        if tb is None:
            return
        if self._transform_use_center:
            tb.set_position_center(v, tb.y + tb.h / 2)
        else:
            tb.set_position_topleft(v, tb.y)
        self.canvas_widget.mark_dirty_stroke()

    def _tx_set_y(self, v: float):
        tb = self.canvas.transform_box
        if tb is None:
            return
        if self._transform_use_center:
            tb.set_position_center(tb.x + tb.w / 2, v)
        else:
            tb.set_position_topleft(tb.x, v)
        self.canvas_widget.mark_dirty_stroke()

    def _tx_set_w(self, v: float):
        tb = self.canvas.transform_box
        if tb is None:
            return
        if self._transform_use_percent:
            tb.set_width_pct(v, self._transform_lock_ratio)
        else:
            tb.set_width_px(v, self._transform_lock_ratio)
        self._tx_sync()
        self.canvas_widget.mark_dirty_stroke()

    def _tx_set_h(self, v: float):
        tb = self.canvas.transform_box
        if tb is None:
            return
        if self._transform_use_percent:
            tb.set_height_pct(v, self._transform_lock_ratio)
        else:
            tb.set_height_px(v, self._transform_lock_ratio)
        self._tx_sync()
        self.canvas_widget.mark_dirty_stroke()

    def _tx_set_angle(self, v: float):
        tb = self.canvas.transform_box
        if tb is None:
            return
        tb.set_angle(v)
        self.canvas_widget.mark_dirty_stroke()

    def _tx_rotate_left(self):
        tb = self.canvas.transform_box
        if tb:
            tb.rotate_left_90()
            self._tx_sync()
            self.canvas_widget.mark_dirty_stroke()

    def _tx_rotate_right(self):
        tb = self.canvas.transform_box
        if tb:
            tb.rotate_right_90()
            self._tx_sync()
            self.canvas_widget.mark_dirty_stroke()

    def _tx_cancel(self):
        self.canvas.cancel_transform()
        self._set_tool_and_ui(ToolType.SELECT)
        self.canvas_widget.mark_dirty()

    def _tx_commit(self):
        self.canvas.commit_transform()
        self._set_tool_and_ui(ToolType.SELECT)
        self.canvas_widget.mark_dirty()

    def _tx_delete(self):
        if self.canvas.transform_box is not None:
            self.canvas.transform_box = None
            self.canvas.invalidate_onion_cache()
            self._set_tool_and_ui(ToolType.PEN)
            self.canvas_widget.mark_dirty()

    def _set_pen_type(self, tip_type: str):
        type_map = {
            "Round":  "round",
            "Square": "square",
            "Soft":   "soft",
        }
        self.canvas.brush.tip_type = type_map.get(tip_type, "round")

    # ── Operaciones de selección ──────────────────────────────────────

    def _sel_deselect(self):
        self.canvas.selection.clear()
        self.canvas.clear_paint_mask()
        self.canvas_widget._sel_state = "idle"
        self.canvas_widget.mark_dirty_stroke()

    def _sel_by_opacity(self):
        self.canvas.select_by_opacity()
        self.canvas_widget._sel_state = "ready"
        self.canvas_widget.mark_dirty_stroke()

    def _sel_clear_layer(self):
        self.canvas.clear_selection_area()
        self.canvas_widget.mark_dirty()

    def _sel_copy(self):
        self.canvas.copy_selection()

    def _sel_cut(self):
        self.canvas.cut_selection()
        self.canvas_widget.mark_dirty()

    def _sel_paste(self):
        self.canvas.paste_clipboard()
        self._refresh_layers()
        self.canvas_widget.mark_dirty()

    def _crop_layer(self):
        ok = self.canvas.crop_layer()
        if ok:
            self.canvas_widget.mark_dirty()
        else:
            QMessageBox.information(
                self, "Crop",
                "No hay contenido para recortar en esta capa.")
            

    # ── Adición ───────────────────────────────────────────────────────

    def _open_reference_window(self):
        from ui.reference_window import ReferenceWindow
        if self._ref_window is None:
            self._ref_window = ReferenceWindow(self)
            self._ref_window.image_loaded.connect(
                self._load_reference_and_preview)
            self._ref_window.image_cleared.connect(
                self._clear_reference)
        self._ref_window.update_preview(self.canvas.reference.image)
        self._ref_window.show()
        self._ref_window.raise_()

    def _load_reference_and_preview(self, path: str):
        self._load_reference(path)
        if self._ref_window is not None:
            self._ref_window.update_preview(self.canvas.reference.image)

    def _toggle_grid(self):
        self._grid_visible = not self._grid_visible
        self.canvas_widget._grid_visible = self._grid_visible
        self.canvas_widget._grid_size    = self._grid_size
        self.canvas_widget.update()


    # ── Reglas ────────────────────────────────────────────────────────

    def _open_ruler_panel(self):
        from ui.ruler_panel import RulerPanel
        if self._ruler_window is None:
            self._ruler_window = RulerPanel(self)
            self._ruler_window.ruler_type_changed.connect(self._on_ruler_type)
            self._ruler_window.ruler_active_changed.connect(self._on_ruler_active)
            self._ruler_window.ruler_config_changed.connect(self._on_ruler_config_changed)
        self._ruler_window.show()
        self._ruler_window.raise_()

    def _on_ruler_type(self, rtype):
        from core.ruler import (RulerType, LineRuler, CircleRuler,
                                 EllipseRuler, SymmetryRuler)
        cfg = self._ruler_window.get_ruler_config()
        cx  = self.canvas.width  / 2
        cy  = self.canvas.height / 2

        if rtype == RulerType.LINE:
            self._active_ruler = LineRuler(cx, cy, cfg["line_angle"])
        elif rtype == RulerType.CIRCLE:
            self._active_ruler = CircleRuler(cx, cy, cfg["circle_radius"])
        elif rtype == RulerType.ELLIPSE:
            self._active_ruler = EllipseRuler(
                cx, cy,
                cfg["ellipse_rx"], cfg["ellipse_ry"],
                cfg["ellipse_angle"])
        elif rtype == RulerType.SYMMETRY:
            mode_map = {
                "vertical":   "vertical",
                "horizontal": "horizontal",
                "ambos":      "both",
                "radial":     "radial",
            }
            self._active_ruler = SymmetryRuler(
                cx, cy,
                mode_map.get(cfg["sym_mode"], "vertical"),
                cfg["sym_radial_n"])

        self._active_ruler.active = True
        self.canvas_widget._active_ruler = self._active_ruler
        self.canvas_widget.update()

    def _on_ruler_active(self, active: bool):
        if self._active_ruler is not None:
            self._active_ruler.active = active
        self.canvas_widget._active_ruler = (
            self._active_ruler if active else None)
        self.canvas_widget.update()


    def _on_ruler_config_changed(self):
        if self._active_ruler is None:
            return
        from core.ruler import LineRuler, CircleRuler, EllipseRuler, SymmetryRuler
        cfg = self._ruler_window.get_ruler_config()
        if isinstance(self._active_ruler, LineRuler):
            self._active_ruler.angle = cfg["line_angle"]
        elif isinstance(self._active_ruler, CircleRuler):
            self._active_ruler.radius = cfg["circle_radius"]
        elif isinstance(self._active_ruler, EllipseRuler):
            self._active_ruler.rx    = cfg["ellipse_rx"]
            self._active_ruler.ry    = cfg["ellipse_ry"]
            self._active_ruler.angle = cfg["ellipse_angle"]
        elif isinstance(self._active_ruler, SymmetryRuler):
            mode_map = {"vertical": "vertical", "horizontal": "horizontal",
                        "ambos": "both", "radial": "radial"}
            self._active_ruler.mode     = mode_map.get(cfg["sym_mode"], "vertical")
            self._active_ruler.radial_n = cfg["sym_radial_n"]
        self.canvas_widget.update()

    def _on_eraser_size(self, v: int):
        self._eraser_size = v
        if self.canvas.current_tool == ToolType.ERASER:
            self.canvas.brush.size = v

    def _on_smudge_size(self, v: int):
        self._smudge_size = v
        if self.canvas.current_tool == ToolType.SMUDGE:
            self.canvas.brush.size = v
