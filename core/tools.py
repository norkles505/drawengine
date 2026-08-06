from enum import Enum, auto


class ToolType(Enum):
    PEN       = auto()
    ERASER    = auto()
    FILL      = auto()
    SELECT    = auto()
    TEXT      = auto()
    LINE      = auto()
    RECT      = auto()
    ELLIPSE   = auto()
    LASSO     = auto()
    EYEDROP   = auto()
    TRANSFORM = auto()
    SELECT_CIRCLE = auto()
    TRIANGLE  = auto()
    HAND      = auto()
    SMUDGE    = auto()
    BEZIER    = auto()   # ← NUEVO


class SelectMode(Enum):
    RECTANGULAR = "rectangular"
    CIRCULAR    = "circular"


class BlendMode(Enum):
    NORMAL   = "Normal"
    MULTIPLY = "Multiply"
    SCREEN   = "Screen"
    OVERLAY  = "Overlay"
    ADD      = "Add"


class BrushSettings:
    def __init__(self):
        self.size: int = 8
        self.color_r: int = 0
        self.color_g: int = 0
        self.color_b: int = 0
        self.color_a: int = 255
        self.hardness: float = 1.0
        self.tip_type: str = "round"
        self.color2_r: int = 255
        self.color2_g: int = 255
        self.color2_b: int = 255
        self.color2_a: int = 255

    @property
    def qcolor(self):
        from PyQt6.QtGui import QColor
        return QColor(self.color_r, self.color_g,
                      self.color_b, self.color_a)

    @property
    def qcolor2(self):
        from PyQt6.QtGui import QColor
        return QColor(self.color2_r, self.color2_g,
                      self.color2_b, self.color2_a)

    def swap_colors(self):
        self.color_r,  self.color2_r  = self.color2_r,  self.color_r
        self.color_g,  self.color2_g  = self.color2_g,  self.color_g
        self.color_b,  self.color2_b  = self.color2_b,  self.color_b
        self.color_a,  self.color2_a  = self.color2_a,  self.color_a
