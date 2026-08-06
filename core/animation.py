from typing import List
from core.layer import Layer


class Frame:
    def __init__(self, width: int, height: int, index: int):
        self.index = index
        self.layers: List[Layer] = []
        self._width = width
        self._height = height
        self.add_layer("Layer 1")
        self.active_layer_index: int = 0

    def add_layer(self, name: str = None) -> Layer:
        idx = len(self.layers) + 1
        layer = Layer(self._width, self._height, name or f"Layer {idx}")
        self.layers.append(layer)
        self.active_layer_index = len(self.layers) - 1
        return layer

    def delete_layer(self, index: int):
        if len(self.layers) <= 1:
            return
        self.layers.pop(index)
        self.active_layer_index = max(0, min(self.active_layer_index, len(self.layers) - 1))

    @property
    def active_layer(self) -> Layer:
        return self.layers[self.active_layer_index]


class Animation:
    def __init__(self, width: int, height: int, fps: int = 24):
        self.width = width
        self.height = height
        self.fps = fps
        self.frames: List[Frame] = []
        self.current_frame_index: int = 0
        self.audio_path: str | None = None   # ← NUEVO

        self.add_frame()

    def add_frame(self) -> Frame:
        frame = Frame(self.width, self.height, len(self.frames))
        self.frames.append(frame)
        return frame

    def duplicate_frame(self, index: int) -> Frame:
        from PyQt6.QtGui import QPainter
        source = self.frames[index]
        new_frame = Frame(self.width, self.height, len(self.frames))
        new_frame.layers.clear()
        for src_layer in source.layers:
            new_layer = Layer(self.width, self.height, src_layer.name)
            new_layer.visible = src_layer.visible
            new_layer.opacity = src_layer.opacity
            painter = QPainter(new_layer.image)
            painter.drawImage(0, 0, src_layer.image)
            painter.end()
            new_frame.layers.append(new_layer)
        new_frame.active_layer_index = source.active_layer_index
        self.frames.insert(index + 1, new_frame)
        for i, f in enumerate(self.frames):
            f.index = i
        return new_frame

    def delete_frame(self, index: int):
        if len(self.frames) <= 1:
            return
        self.frames.pop(index)
        for i, f in enumerate(self.frames):
            f.index = i
        self.current_frame_index = max(0, min(self.current_frame_index, len(self.frames) - 1))

    @property
    def current_frame(self) -> Frame:
        return self.frames[self.current_frame_index]

    def total_duration_ms(self) -> int:
        return int(len(self.frames) / self.fps * 1000)