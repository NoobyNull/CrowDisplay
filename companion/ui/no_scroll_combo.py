"""
NoScrollComboBox: QComboBox that ignores wheel events when not focused.

Prevents accidental value changes when scrolling the editor panel.
"""

from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Qt


class NoScrollComboBox(QComboBox):
    """QComboBox that ignores wheel events when not focused.
    Prevents accidental value changes when scrolling the editor panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
