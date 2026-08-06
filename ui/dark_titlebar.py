"""
Utilidad compartida para forzar la barra de título nativa en modo oscuro
(Windows, vía DWM), y que combine con el resto de la interfaz (#202020).
Úsala en cualquier QWidget de nivel de ventana (QMainWindow, QDialog...):

    from ui.dark_titlebar import apply_dark_titlebar
    apply_dark_titlebar(self)
"""
import sys
import ctypes


def apply_dark_titlebar(window):
    """Fuerza el modo oscuro (DWM immersive dark mode) en la barra de
    título nativa de una ventana en Windows 10 1903+ / Windows 11.
    En otras plataformas no hace nada."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(window.winId())
        # Atributo 20 en builds recientes; 19 como fallback en Windows 10
        # más antiguo.
        for attr in (20, 19):
            value = ctypes.c_int(1)
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
            if res == 0:
                break
    except Exception:
        pass
