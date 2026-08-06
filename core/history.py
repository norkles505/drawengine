"""
Historial de deshacer/rehacer por frame.
Guarda snapshots de todas las capas antes de cada operación destructiva.
"""

from typing import List, Dict
import numpy as np
from PyQt6.QtGui import QImage, QPainter


class FrameSnapshot:
    """Copia completa del estado de capas de un frame en un momento dado."""

    def __init__(self, frame):
        self.active_layer_index = frame.active_layer_index
        self.layers = []
        for layer in frame.layers:
            self.layers.append({
                "name":    layer.name,
                "visible": layer.visible,
                "opacity": layer.opacity,
                "data":    _qimage_to_numpy(layer.image),
            })


class FrameHistory:
    """
    Pila de deshacer/rehacer para un frame específico.
    Máximo `max_steps` snapshots en memoria.
    """

    def __init__(self, max_steps: int = 40):
        self._undo_stack: List[FrameSnapshot] = []
        self._redo_stack: List[FrameSnapshot] = []
        self.max_steps = max_steps

    def push(self, frame):
        """Guarda el estado actual antes de una operación."""
        self._undo_stack.append(FrameSnapshot(frame))
        if len(self._undo_stack) > self.max_steps:
            self._undo_stack.pop(0)
        self._redo_stack.clear()   # nueva acción borra el redo

    def undo(self, frame) -> bool:
        """
        Restaura el estado anterior.
        Devuelve True si se pudo deshacer.
        """
        if not self._undo_stack:
            return False
        self._redo_stack.append(FrameSnapshot(frame))
        snapshot = self._undo_stack.pop()
        _apply_snapshot(frame, snapshot)
        return True

    def redo(self, frame) -> bool:
        """
        Rehace la última operación deshecha.
        Devuelve True si se pudo rehacer.
        """
        if not self._redo_stack:
            return False
        self._undo_stack.append(FrameSnapshot(frame))
        snapshot = self._redo_stack.pop()
        _apply_snapshot(frame, snapshot)
        return True

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0


class HistoryManager:
    """
    Un FrameHistory por frame de la animación.
    El Canvas lo usa como punto de entrada único.
    """

    def __init__(self, max_steps: int = 40):
        self._histories: Dict[int, FrameHistory] = {}
        self.max_steps = max_steps

    def _get(self, frame_index: int) -> FrameHistory:
        if frame_index not in self._histories:
            self._histories[frame_index] = FrameHistory(self.max_steps)
        return self._histories[frame_index]

    def push(self, frame):
        self._get(frame.index).push(frame)

    def undo(self, frame) -> bool:
        return self._get(frame.index).undo(frame)

    def redo(self, frame) -> bool:
        return self._get(frame.index).redo(frame)

    def can_undo(self, frame_index: int) -> bool:
        return self._get(frame_index).can_undo

    def can_redo(self, frame_index: int) -> bool:
        return self._get(frame_index).can_redo

    def clear_frame(self, frame_index: int):
        """Limpia el historial de un frame (ej: al eliminarlo)."""
        self._histories.pop(frame_index, None)

    def clear_all(self):
        self._histories.clear()


# ── Helpers internos ───────────────────────────────────────────────────

def _qimage_to_numpy(image: QImage) -> np.ndarray:
    img = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    ptr = img.bits()
    ptr.setsize(img.sizeInBytes())
    return np.frombuffer(ptr, dtype=np.uint8).reshape(
        img.height(), img.width(), 4).copy()


def _apply_snapshot(frame, snapshot: FrameSnapshot):
    """Restaura las capas de un frame desde un snapshot."""
    from core.layer import Layer

    # Ajustar cantidad de capas
    while len(frame.layers) < len(snapshot.layers):
        frame.layers.append(
            Layer(frame._width, frame._height, "restored"))
    while len(frame.layers) > len(snapshot.layers):
        frame.layers.pop()

    for layer, saved in zip(frame.layers, snapshot.layers):
        layer.name    = saved["name"]
        layer.visible = saved["visible"]
        layer.opacity = saved["opacity"]
        _numpy_to_qimage(saved["data"], layer.image)

    frame.active_layer_index = min(
        snapshot.active_layer_index, len(frame.layers) - 1)


def _numpy_to_qimage(arr: np.ndarray, target: QImage):
    """Escribe un array numpy de vuelta en un QImage existente."""
    src = QImage(
        arr.tobytes(),
        arr.shape[1], arr.shape[0],
        QImage.Format.Format_ARGB32_Premultiplied
    )
    painter = QPainter(target)
    painter.setCompositionMode(
        QPainter.CompositionMode.CompositionMode_Source)
    painter.drawImage(0, 0, src)
    painter.end()