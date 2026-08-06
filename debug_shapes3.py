import sys, os, traceback

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)
OUT = os.path.join(BASE, "debug_shapes3_out.txt")

try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    from core.canvas import Canvas
    from core.tools import ToolType, BrushSettings
    from core.animation import Animation
    from core.selection import Selection
    from core.history import HistoryManager

    lines = []

    # Replicar EXACTAMENTE lo que hace MainWindow._open_project
    anim = Animation(200, 200, 24)

    new_canvas = Canvas.__new__(Canvas)
    new_canvas.width              = anim.width
    new_canvas.height             = anim.height
    new_canvas.animation          = anim
    new_canvas.current_tool       = ToolType.RECT
    new_canvas.fill_tolerance     = 15
    new_canvas.fill_expand        = 1
    new_canvas.onion_enabled      = False
    new_canvas.onion_prev         = 1
    new_canvas.onion_next         = 0
    new_canvas.onion_opacity      = 0.35
    new_canvas.onion_color_past   = (220, 60,  60)
    new_canvas.onion_color_future = (60,  120, 220)
    new_canvas.onion_op_first     = 50.0
    new_canvas.onion_op_last      = 20.0
    new_canvas._onion_overlay     = None
    new_canvas._onion_worker      = None
    new_canvas._onion_cache       = {}
    new_canvas.brush = BrushSettings()
    new_canvas.selection = Selection()
    new_canvas.history = HistoryManager()

    lines.append("Canvas creado via __new__ (como en _open_project)")

    try:
        new_canvas.draw_rect(20, 20, 100, 100, filled=True, stroke=True)
        arr = new_canvas.active_layer.get_numpy()
        nonzero = (arr[:, :, 3] > 0).sum()
        lines.append(f"draw_rect OK, nonzero pixels: {nonzero}")
    except Exception:
        lines.append("draw_rect FALLO:")
        lines.append(traceback.format_exc())

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

except Exception:
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("ERROR GLOBAL:\n")
        f.write(traceback.format_exc())
