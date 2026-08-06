import sys, os, traceback

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)
OUT = os.path.join(BASE, "debug_shapes_out.txt")

try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    from core.canvas import Canvas
    from core.tools import ToolType

    c = Canvas(200, 200, 24)
    c.add_layer()

    lines = []
    lines.append(f"active_layer is None: {c.active_layer is None}")
    lines.append(f"num layers: {len(c.layers)}")

    c.current_tool = ToolType.RECT
    c.draw_rect(20, 20, 100, 100, filled=True, stroke=True)

    arr = c.active_layer.get_numpy()
    nonzero = (arr[:, :, 3] > 0).sum()
    lines.append(f"draw_rect nonzero alpha pixels: {nonzero}")

    c2 = Canvas(200, 200, 24)
    c2.add_layer()
    c2.draw_ellipse(20, 20, 100, 100, filled=True, stroke=True)
    arr2 = c2.active_layer.get_numpy()
    nonzero2 = (arr2[:, :, 3] > 0).sum()
    lines.append(f"draw_ellipse nonzero alpha pixels: {nonzero2}")

    lines.append(f"brush size: {c.brush.size}")
    lines.append(f"brush color: {c.brush.color_r},{c.brush.color_g},{c.brush.color_b},{c.brush.color_a}")
    lines.append(f"brush_opacity: {c.brush_opacity}")
    lines.append(f"selection.active: {c.selection.active}")
    lines.append(f"paint_mask_active: {c.paint_mask_active}")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

except Exception:
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("ERROR:\n")
        f.write(traceback.format_exc())
