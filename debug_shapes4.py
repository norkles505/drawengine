import sys, os, traceback

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)
OUT = os.path.join(BASE, "debug_shapes4_out.txt")

try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    from ui.main_window import MainWindow
    from core.project_io import save_project, load_project
    from core.tools import ToolType

    lines = []

    win = MainWindow(200, 200, 24)

    # Guardar un proyecto de prueba y volver a abrirlo, tal cual
    # hace el usuario desde el menu File > Save / Open.
    test_path = os.path.join(BASE, "_test_project.dwe")
    save_project(win.canvas.animation, test_path)
    lines.append("Proyecto guardado OK")

    win._open_project = win._open_project  # noop, just referencing
    # Simular _open_project sin dialogo de archivo:
    anim = load_project(test_path)
    from core.tools import BlendMode
    for frame in anim.frames:
        for layer in frame.layers:
            if not hasattr(layer, "blend_mode"):
                layer.blend_mode = BlendMode.NORMAL

    from core.canvas import Canvas
    new_canvas = Canvas(anim.width, anim.height, anim.fps)
    new_canvas.animation      = anim
    new_canvas.current_tool   = win.canvas.current_tool
    new_canvas.fill_tolerance = win.canvas.fill_tolerance
    new_canvas.fill_expand    = win.canvas.fill_expand
    win.canvas = new_canvas
    win.canvas_widget.canvas = new_canvas
    lines.append("Proyecto reabierto OK con constructor completo")

    # Ahora dibujar una forma, como haria el usuario
    win.canvas.current_tool = ToolType.RECT
    win.canvas.draw_rect(20, 20, 100, 100, filled=True, stroke=True)
    arr = win.canvas.active_layer.get_numpy()
    nonzero = (arr[:, :, 3] > 0).sum()
    lines.append(f"draw_rect tras reabrir proyecto: {nonzero} pixeles pintados")

    os.remove(test_path)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

except Exception:
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("ERROR:\n")
        f.write(traceback.format_exc())
