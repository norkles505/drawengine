"""
Configuración persistente del usuario.
Se guarda en un archivo JSON en la carpeta del usuario.
"""

import json
import os
from typing import Any


def _config_path() -> str:
    """Ruta del archivo de config según el sistema operativo."""
    base = os.path.expanduser("~")
    folder = os.path.join(base, ".drawengine")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "config.json")


DEFAULTS: dict = {
    # Ventana
    "window_w":        1440,
    "window_h":        920,
    "window_x":        -1,     # -1 = centrar
    "window_y":        -1,

    # Herramienta
    "tool":            "PEN",
    "brush_size":      8,
    "eraser_size":     24,
    "brush_opacity":   100,    # %
    "brush_color_r":   0,
    "brush_color_g":   0,
    "brush_color_b":   0,
    "brush_color_a":   255,
    "fill_tolerance":  15,
    "stabilizer":      0,
    "eraser_soft":     False,

    # Colores recientes (lista de hasta 12 colores RGBA)
    "recent_colors":   [],

    # Último proyecto
    "last_project":    "",

    # Proyectos recientes (rutas completas, más reciente primero, máx 10)
    "recent_projects": [],

    # Animación
    "anim_settings": {
        "playback_mode":      0,
        "onion_mode":         0,
        "onion_layers":       1,
        "onion_op_first":     50,
        "onion_op_last":      20,
        "onion_color_past":   "#dc3c3c",
        "onion_color_future": "#3c78dc",
    },
}


class UserConfig:
    def __init__(self):
        self._path = _config_path()
        self._data: dict = {}
        self.load()

    def load(self):
        """Carga config desde disco. Si no existe usa defaults."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Merge: defaults primero, luego los valores guardados
            self._data = dict(DEFAULTS)
            self._deep_merge(self._data, saved)
        except Exception:
            self._data = dict(DEFAULTS)

    def save(self):
        """Guarda config actual en disco."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Config save error: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def get_anim_settings(self) -> dict:
        return dict(self._data.get(
            "anim_settings", DEFAULTS["anim_settings"]))

    def set_anim_settings(self, s: dict):
        self._data["anim_settings"] = dict(s)

    def add_recent_color(self, r: int, g: int, b: int, a: int):
        """Agrega un color a la lista de recientes (máx 12)."""
        color = [r, g, b, a]
        colors: list = self._data.get("recent_colors", [])
        # Evitar duplicados
        if color in colors:
            colors.remove(color)
        colors.insert(0, color)
        self._data["recent_colors"] = colors[:12]

    def get_recent_projects(self) -> list:
        """Devuelve la lista de rutas de proyectos recientes."""
        return list(self._data.get("recent_projects", []))

    def add_recent_project(self, path: str):
        """Agrega/mueve una ruta de proyecto al tope de recientes (máx 10)."""
        projects: list = self._data.get("recent_projects", [])
        projects = [p for p in projects if p != path]
        projects.insert(0, path)
        self._data["recent_projects"] = projects[:10]

    def remove_recent_project(self, path: str):
        """Quita una ruta de la lista de recientes (p.ej. si ya no existe)."""
        projects: list = self._data.get("recent_projects", [])
        self._data["recent_projects"] = [p for p in projects if p != path]

    def _deep_merge(self, base: dict, override: dict):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v
