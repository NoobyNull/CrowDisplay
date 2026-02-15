"""
Icon Picker Widget: QComboBox dropdown for LVGL symbol selection

Populates from the lvgl_symbols registry module. Each item stores
the UTF-8 bytes (decoded to string) as itemData for direct JSON serialization.
The device JSON stores raw UTF-8 characters, not symbol name strings.
"""

from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Signal

from companion.lvgl_symbols import LVGL_SYMBOLS, SYMBOL_BY_NAME, SYMBOL_BY_UTF8


class IconPicker(QComboBox):
    """Dropdown for selecting LVGL symbols.

    Stores and returns UTF-8 strings (decoded bytes) matching the device
    JSON format -- NOT symbol name strings like "LV_SYMBOL_HOME".
    """

    # Signal emitted when icon is selected
    # Payload: UTF-8 string for JSON serialization
    icon_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)

        # Populate dropdown from LVGL symbol registry
        for name, codepoint, utf8_bytes in LVGL_SYMBOLS:
            # The UTF-8 bytes decoded to a Python string -- this is what
            # gets stored in JSON (the raw Unicode character)
            utf8_str = utf8_bytes.decode("utf-8")
            # Try to show the Unicode character; for private-use area (0xF000+)
            # the system font likely can't render it, so show name instead
            preview_char = chr(codepoint)
            display_text = f"{name} (U+{codepoint:04X}) {preview_char}"
            self.addItem(display_text, utf8_str)

        # Connect signal
        self.currentIndexChanged.connect(self._on_index_changed)

    def _on_index_changed(self, index: int):
        """Emit icon_selected signal when selection changes"""
        if index >= 0:
            utf8_str = self.itemData(index)
            self.icon_selected.emit(utf8_str)

    def set_symbol(self, icon_str: str):
        """Set the selected symbol.

        Accepts either:
        - A UTF-8 string (the decoded bytes from JSON, e.g. the character at U+F015)
        - A symbol name string ("HOME" or "LV_SYMBOL_HOME")

        Looks up in SYMBOL_BY_UTF8 first (for JSON-format values),
        then SYMBOL_BY_NAME (for legacy name-format values).
        """
        # Try matching as UTF-8 string (the normal case from device JSON)
        icon_bytes = icon_str.encode("utf-8") if isinstance(icon_str, str) else icon_str
        if icon_bytes in SYMBOL_BY_UTF8:
            # Find the combo item with this UTF-8 string
            target_str = icon_bytes.decode("utf-8")
            for i in range(self.count()):
                if self.itemData(i) == target_str:
                    self.setCurrentIndex(i)
                    return

        # Try matching as symbol name (strip LV_SYMBOL_ prefix if present)
        name = icon_str
        if name.startswith("LV_SYMBOL_"):
            name = name[len("LV_SYMBOL_"):]
        if name in SYMBOL_BY_NAME:
            _cp, utf8_bytes = SYMBOL_BY_NAME[name]
            target_str = utf8_bytes.decode("utf-8")
            for i in range(self.count()):
                if self.itemData(i) == target_str:
                    self.setCurrentIndex(i)
                    return

    def get_symbol(self) -> str:
        """Get currently selected symbol as UTF-8 string for JSON serialization.

        Returns the raw UTF-8 character (e.g. the character at U+F015),
        NOT a symbol name like "LV_SYMBOL_HOME".
        """
        index = self.currentIndex()
        if index >= 0:
            return self.itemData(index)
        # Default fallback: HOME symbol as UTF-8 string
        return SYMBOL_BY_NAME["HOME"][1].decode("utf-8")
