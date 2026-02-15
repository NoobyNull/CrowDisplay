"""
Keyboard Recorder Widget: Capture keyboard shortcuts via keyPressEvent

Uses a custom QLineEdit subclass (ShortcutCapture) that overrides keyPressEvent
to capture key combos. Translates Qt key values to Arduino USB HID keycodes
using the keycode_map module.

Displays pressed keys as "Super+1" or "Ctrl+A" format.
Pressing Escape clears the shortcut.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent

from companion.keycode_map import (
    qt_key_to_arduino,
    qt_modifiers_to_device,
    arduino_keycode_to_display_name,
)

# Modifier-only Qt keys that should not count as a keycode
_MODIFIER_KEYS = {
    Qt.Key_Shift,
    Qt.Key_Control,
    Qt.Key_Alt,
    Qt.Key_Meta,
    Qt.Key_Super_L,
    Qt.Key_Super_R,
    Qt.Key_AltGr,
}


class ShortcutCapture(QLineEdit):
    """QLineEdit that captures key combos instead of typing text.

    Click to focus, then press a key combination. The widget displays
    the combo as human-readable text (e.g. "Ctrl+A") and emits the
    Arduino-format (modifiers, keycode) via shortcut_captured signal.
    """

    # Signal: (device_modifiers: int, arduino_keycode: int)
    shortcut_captured = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click, then press keys...")
        self.setAlignment(Qt.AlignCenter)
        self._device_modifiers = 0
        self._arduino_keycode = 0

    def keyPressEvent(self, event: QKeyEvent):
        """Override to capture key combos instead of typing."""
        qt_key = event.key()
        qt_mods = event.modifiers()

        # Escape clears the shortcut
        if qt_key == Qt.Key_Escape:
            self._device_modifiers = 0
            self._arduino_keycode = 0
            self.clear()
            self.setPlaceholderText("Click, then press keys...")
            self.shortcut_captured.emit(0, 0)
            return

        # Ignore bare modifier keys (wait for a real key)
        if qt_key in _MODIFIER_KEYS:
            return

        # Translate to device format
        arduino_keycode = qt_key_to_arduino(qt_key)
        device_mods = qt_modifiers_to_device(qt_mods)

        if arduino_keycode == 0:
            return  # Unknown key, ignore

        self._device_modifiers = device_mods
        self._arduino_keycode = arduino_keycode

        # Build display text
        display = _format_shortcut(device_mods, arduino_keycode)
        self.setText(display)
        self.shortcut_captured.emit(device_mods, arduino_keycode)

    def get_values(self):
        """Return (device_modifiers, arduino_keycode)."""
        return self._device_modifiers, self._arduino_keycode

    def set_values(self, modifiers: int, keycode: int):
        """Set from device-format values (for loading existing config)."""
        self._device_modifiers = modifiers
        self._arduino_keycode = keycode
        if keycode != 0:
            self.setText(_format_shortcut(modifiers, keycode))
        else:
            self.clear()


def _format_shortcut(modifiers: int, keycode: int) -> str:
    """Format (device_modifiers, arduino_keycode) as human-readable string."""
    parts = []
    if modifiers & 0x01:
        parts.append("Ctrl")
    if modifiers & 0x02:
        parts.append("Shift")
    if modifiers & 0x04:
        parts.append("Alt")
    if modifiers & 0x08:
        parts.append("Super")
    parts.append(arduino_keycode_to_display_name(keycode))
    return "+".join(parts)


class KeyboardRecorder(QWidget):
    """Widget for capturing keyboard shortcuts.

    Contains a ShortcutCapture line edit and a Clear button.
    Maintains the same public API as the previous version:
    - shortcut_confirmed Signal(int, int)
    - current_modifiers, current_keycode properties
    - set_shortcut(), get_shortcut() methods
    """

    # Signal emitted when a shortcut is captured
    # Payload: (modifiers: int, keycode: int) in device format
    shortcut_confirmed = Signal(int, int)

    # Signal emitted when recording is cancelled / cleared
    recording_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_modifiers = 0
        self.current_keycode = 0

        self._capture = ShortcutCapture()
        self._capture.shortcut_captured.connect(self._on_shortcut_captured)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedWidth(60)
        self._clear_btn.clicked.connect(self._on_clear)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._capture, stretch=1)
        layout.addWidget(self._clear_btn)
        self.setLayout(layout)

    def _on_shortcut_captured(self, modifiers: int, keycode: int):
        """Internal handler for ShortcutCapture signal."""
        self.current_modifiers = modifiers
        self.current_keycode = keycode
        if keycode != 0:
            self.shortcut_confirmed.emit(modifiers, keycode)

    def _on_clear(self):
        """Clear button clicked."""
        self.current_modifiers = 0
        self.current_keycode = 0
        self._capture.set_values(0, 0)
        self.recording_cancelled.emit()

    def get_shortcut(self) -> tuple:
        """Get currently recorded shortcut as (modifiers, keycode)."""
        return (self.current_modifiers, self.current_keycode)

    def set_shortcut(self, modifiers: int, keycode: int):
        """Set shortcut display from device-format values."""
        self.current_modifiers = modifiers
        self.current_keycode = keycode
        self._capture.set_values(modifiers, keycode)
