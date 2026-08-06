import sys, os, traceback

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)
OUT = os.path.join(BASE, "debug_shapes2_out.txt")

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QPoint, QPointF, QEvent
    from PyQt6.QtGui import QMouseEvent

    app = QApplication(sys.argv)

    from ui.main_window import MainWindow, CanvasWidget
    from core.tools import ToolType

    win = MainWindow(200, 200, 24)
    cw = win.canvas_widget
    cw.resize(200, 200)
    cw._zoom = 1.0
    cw._offset = QPoint(0, 0)

    lines = []

    # Simular selección de herramienta RECT exactamente como lo hace la UI real
    win._set_tool_and_ui(ToolType.RECT)
    lines.append(f"current_tool after set: {win.canvas.current_tool}")
    lines.append(f"cw canvas is win canvas: {cw.canvas is win.canvas}")

    def make_event(etype, pos, button=Qt.MouseButton.LeftButton, buttons=None):
        if buttons is None:
            buttons = button
        return QMouseEvent(etype, QPointF(pos), QPointF(pos),
                            button, buttons, Qt.KeyboardModifier.NoModifier)

    p1 = QPoint(20, 20)
    p2 = QPoint(100, 100)

    ev1 = make_event(QEvent.Type.MouseButtonPress, p1)
    cw.mousePressEvent(ev1)
    lines.append(f"_shape_start after press: {cw._shape_start}")
    lines.append(f"_is_drawing after press: {cw._is_drawing}")

    ev2 = make_event(QEvent.Type.MouseMove, p2, buttons=Qt.MouseButton.LeftButton)
    cw.mouseMoveEvent(ev2)
    lines.append(f"_shape_preview_end after move: {cw._shape_preview_end}")

    ev3 = make_event(QEvent.Type.MouseButtonRelease, p2)
    cw.mouseReleaseEvent(ev3)
    lines.append(f"_shape_start after release: {cw._shape_start}")

    arr = win.canvas.active_layer.get_numpy()
    nonzero = (arr[:, :, 3] > 0).sum()
    lines.append(f"nonzero alpha pixels on active layer after simulated draw: {nonzero}")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

except Exception:
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("ERROR:\n")
        f.write(traceback.format_exc())
