"""
Hardware Section: Hardware button/encoder configuration strip for the editor.
"""

import logging

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QWidget,
)
from PySide6.QtCore import Signal

from companion.config_manager import get_default_hardware_buttons

logger = logging.getLogger(__name__)


class HardwareSection(QWidget):
    """Hardware button/encoder strip below the canvas, simulating the device bezel."""

    hw_input_selected = Signal(str, int)  # "button" or "encoder", index (0-3 for buttons, 0 for encoder)
    hw_input_deselected = Signal()
    hw_config_changed = Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._selected_type = None  # "button" or "encoder"
        self._selected_index = -1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)

        header = QLabel("Hardware Inputs")
        header.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        outer.addWidget(header)

        strip = QWidget()
        strip.setStyleSheet("background: #2a2a2a; border: 1px solid #444; border-radius: 4px;")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(8, 6, 8, 6)
        strip_layout.setSpacing(8)

        # Centered layout: [stretch] B1 B2 ENC B3 B4 [stretch]
        strip_layout.addStretch()

        self.hw_buttons = []
        for i in range(2):
            btn = QPushButton(f"B{i+1}")
            btn.setFixedSize(100, 50)
            btn.setStyleSheet(self._button_style(False))
            btn.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            strip_layout.addWidget(btn)
            self.hw_buttons.append(btn)

        # Encoder widget between button pairs
        self.enc_button = QPushButton("ENC")
        self.enc_button.setFixedSize(60, 60)
        self.enc_button.setStyleSheet(self._encoder_style(False))
        self.enc_button.clicked.connect(self._on_encoder_clicked)
        strip_layout.addWidget(self.enc_button)

        for i in range(2, 4):
            btn = QPushButton(f"B{i+1}")
            btn.setFixedSize(100, 50)
            btn.setStyleSheet(self._button_style(False))
            btn.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            strip_layout.addWidget(btn)
            self.hw_buttons.append(btn)

        strip_layout.addStretch()
        outer.addWidget(strip)

    def _button_style(self, selected):
        base = ("QPushButton { background: #3a3a3a; border: 2px solid %s; "
                "border-radius: 4px; color: %s; font-weight: bold; font-size: 12px; }"
                "QPushButton:hover { background: #4a4a4a; }")
        if selected:
            return base % ("#FFD700", "#FFD700")
        return base % ("#555", "#aaa")

    def _encoder_style(self, selected):
        base = ("QPushButton { background: #3a3a3a; border: 2px solid %s; "
                "border-radius: 30px; color: %s; font-weight: bold; font-size: 11px; }"
                "QPushButton:hover { background: #4a4a4a; }")
        if selected:
            return base % ("#FFD700", "#FFD700")
        return base % ("#555", "#aaa")

    def _on_button_clicked(self, index):
        self._select("button", index)

    def _on_encoder_clicked(self):
        self._select("encoder", 0)

    def _select(self, hw_type, index):
        # Deselect previous
        self._clear_highlight()
        self._selected_type = hw_type
        self._selected_index = index
        # Highlight selected
        if hw_type == "button":
            self.hw_buttons[index].setStyleSheet(self._button_style(True))
        else:
            self.enc_button.setStyleSheet(self._encoder_style(True))
        self.hw_input_selected.emit(hw_type, index)

    def deselect(self):
        """Deselect any hardware input (called when canvas widget is selected)."""
        if self._selected_type is not None:
            self._clear_highlight()
            self._selected_type = None
            self._selected_index = -1

    def _clear_highlight(self):
        for btn in self.hw_buttons:
            btn.setStyleSheet(self._button_style(False))
        self.enc_button.setStyleSheet(self._encoder_style(False))

    def update_labels(self):
        """Update button labels from config."""
        buttons = self.config_manager.config.get("hardware_buttons", get_default_hardware_buttons())
        for i, btn in enumerate(self.hw_buttons):
            if i < len(buttons):
                label = buttons[i].get("label", f"B{i+1}")
                btn.setText(label[:10] if label else f"B{i+1}")
            else:
                btn.setText(f"B{i+1}")


# ============================================================
# Editor Main Window
