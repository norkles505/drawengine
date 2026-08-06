from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QSpinBox, QPushButton
)
from PyQt6.QtCore import Qt


class TextDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Text")
        self.setFixedSize(340, 180)
        self.setModal(True)
        from ui.dark_titlebar import apply_dark_titlebar
        apply_dark_titlebar(self)
        self.setStyleSheet("""
            QDialog  { background: #202020; }
            QLabel   { color: #ccc; font-size: 12px; }
            QLineEdit, QSpinBox {
                background: #282828; color: #eee;
                border: 1px solid #3a3a3a; border-radius: 4px;
                padding: 4px; font-size: 12px;
            }
            QLineEdit:focus, QSpinBox:focus { border: 1px solid #f2801a; }
        """)
        self.result_text      = ""
        self.result_font_size = 24
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Text:"))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Type your text here…")
        layout.addWidget(self.edit)

        row = QHBoxLayout()
        row.addWidget(QLabel("Font size:"))
        self.spin = QSpinBox()
        self.spin.setRange(6, 300)
        self.spin.setValue(24)
        row.addWidget(self.spin)
        row.addStretch()
        layout.addLayout(row)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Place Text")
        btn_ok.setFixedHeight(34)
        btn_ok.setStyleSheet("""
            QPushButton {
                background: #f2801a; color: white;
                border: none; border-radius: 5px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: #ff9d40; }
        """)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(34)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #333; color: #aaa;
                border: none; border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover { background: #444; }
        """)
        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _accept(self):
        self.result_text      = self.edit.text()
        self.result_font_size = self.spin.value()
        if self.result_text.strip():
            self.accept()
