"""
Guardado y carga de proyectos DrawEngine (.dwe).

Formato interno (ZIP):
  project.json          → metadatos
  frames/f{N}_l{M}.png  → imagen de cada capa (N=frame, M=layer)
"""

import json
import os
import zipfile
import tempfile
from typing import Optional

from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtCore import QBuffer, QIODevice, QByteArray

from core.animation import Animation, Frame
from core.layer import Layer


MAGIC_VERSION = "dwe-1"


def save_project(animation: Animation, path: str) -> None:
    """Guarda la animación completa en un archivo .dwe."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        # ── 1. Metadatos ──────────────────────────────────────────────
        meta = {
            "version":   MAGIC_VERSION,
            "width":     animation.width,
            "height":    animation.height,
            "fps":       animation.fps,
            "audio":     animation.audio_path,
            "current_frame": animation.current_frame_index,
            "frames": []
        }

        for fi, frame in enumerate(animation.frames):
            frame_meta = {
                "index":              frame.index,
                "active_layer_index": frame.active_layer_index,
                "layers": []
            }
            for li, layer in enumerate(frame.layers):
                layer_meta = {
                    "name":    layer.name,
                    "visible": layer.visible,
                    "opacity": layer.opacity,
                    "file":    f"frames/f{fi:04d}_l{li:04d}.png"
                }
                frame_meta["layers"].append(layer_meta)

                # ── 2. Imagen de la capa como PNG ─────────────────────
                png_data = _qimage_to_png_bytes(layer.image)
                zf.writestr(layer_meta["file"], png_data)

            meta["frames"].append(frame_meta)

        zf.writestr("project.json", json.dumps(meta, indent=2))


def load_project(path: str) -> Animation:
    """Carga un archivo .dwe y devuelve una Animation lista para usar."""
    with zipfile.ZipFile(path, "r") as zf:
        meta = json.loads(zf.read("project.json").decode("utf-8"))

        if meta.get("version") != MAGIC_VERSION:
            raise ValueError(
                f"Unsupported project version: {meta.get('version')}"
            )

        anim = Animation.__new__(Animation)
        anim.width               = meta["width"]
        anim.height              = meta["height"]
        anim.fps                 = meta["fps"]
        anim.audio_path          = meta.get("audio")
        anim.current_frame_index = meta.get("current_frame", 0)
        anim.frames              = []

        for frame_meta in meta["frames"]:
            frame = Frame.__new__(Frame)
            frame.index               = frame_meta["index"]
            frame._width              = anim.width
            frame._height             = anim.height
            frame.active_layer_index  = frame_meta["active_layer_index"]
            frame.layers              = []

            for layer_meta in frame_meta["layers"]:
                png_data = zf.read(layer_meta["file"])
                image    = _png_bytes_to_qimage(png_data, anim.width, anim.height)

                layer         = Layer.__new__(Layer)
                layer.name    = layer_meta["name"]
                layer.visible = layer_meta["visible"]
                layer.opacity = layer_meta["opacity"]
                layer.image   = image
                layer.width   = anim.width
                layer.height  = anim.height
                frame.layers.append(layer)

            anim.frames.append(frame)

    return anim


# ── Helpers ────────────────────────────────────────────────────────────

def _qimage_to_png_bytes(image: QImage) -> bytes:
    buf  = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    return bytes(buf.data())


def _png_bytes_to_qimage(data: bytes, width: int, height: int) -> QImage:
    img = QImage()
    img.loadFromData(QByteArray(data), "PNG")
    return img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)