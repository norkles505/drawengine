"""
Estilo compartido para los botones de ícono "de acción" (timeline,
panel de capas, etc.): gris por defecto, naranja de acento al
presionar/activar, y naranja translúcido en hover.

    from ui.button_styles import ICON_BUTTON_STYLE
    btn.setStyleSheet(ICON_BUTTON_STYLE)
"""

ICON_BUTTON_STYLE = """
    QPushButton {
        background: #282828;
        border: none;
        border-radius: 4px;
    }
    QPushButton:hover {
        background: rgba(242, 128, 26, 204);
    }
    QPushButton:pressed {
        background: #f2801a;
    }
    QPushButton:checked {
        background: #f2801a;
    }
    QPushButton:disabled {
        background: #202020;
    }
"""
