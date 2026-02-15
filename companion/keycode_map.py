"""
Keycode Mapping: Qt Key constants to Arduino USB HID keycodes

Translates between PySide6/Qt key values and the Arduino USB HID keycode
format expected by the device firmware (ESP32 USBHIDKeyboard.h).

Qt::Key_A = 0x41 (uppercase ASCII 'A'), but Arduino expects lowercase 'a' (0x61).
Qt::Key_Return = 0x01000004, but Arduino KEY_RETURN = 0xB0.
These are completely different numbering systems -- this module bridges them.
"""

from PySide6.QtCore import Qt


# Qt modifier flags to device MOD_* bitmask (matches shared/protocol.h)
QT_MOD_TO_DEVICE = {
    Qt.ControlModifier: 0x01,  # MOD_CTRL
    Qt.ShiftModifier:   0x02,  # MOD_SHIFT
    Qt.AltModifier:     0x04,  # MOD_ALT
    Qt.MetaModifier:    0x08,  # MOD_GUI (Super/Windows/Command)
}

# Qt::Key -> Arduino keycode for special keys
# Source: ESP32 Arduino USBHIDKeyboard.h
QT_KEY_TO_ARDUINO = {
    Qt.Key_Return:      0xB0,
    Qt.Key_Enter:       0xB0,
    Qt.Key_Escape:      0xB1,
    Qt.Key_Backspace:   0xB2,
    Qt.Key_Tab:         0xB3,
    Qt.Key_Space:       0x20,
    Qt.Key_Insert:      0xD1,
    Qt.Key_Delete:      0xD4,
    Qt.Key_Home:        0xD2,
    Qt.Key_End:         0xD5,
    Qt.Key_PageUp:      0xD3,
    Qt.Key_PageDown:    0xD6,
    Qt.Key_Up:          0xDA,
    Qt.Key_Down:        0xD9,
    Qt.Key_Left:        0xD8,
    Qt.Key_Right:       0xD7,
    Qt.Key_CapsLock:    0xC1,
    Qt.Key_NumLock:     0xDB,
    Qt.Key_Print:       0xCE,
    Qt.Key_ScrollLock:  0xCF,
    Qt.Key_Pause:       0xD0,
    # F-keys
    Qt.Key_F1:  0xC2, Qt.Key_F2:  0xC3, Qt.Key_F3:  0xC4,
    Qt.Key_F4:  0xC5, Qt.Key_F5:  0xC6, Qt.Key_F6:  0xC7,
    Qt.Key_F7:  0xC8, Qt.Key_F8:  0xC9, Qt.Key_F9:  0xCA,
    Qt.Key_F10: 0xCB, Qt.Key_F11: 0xCC, Qt.Key_F12: 0xCD,
    Qt.Key_F13: 0xF0, Qt.Key_F14: 0xF1, Qt.Key_F15: 0xF2,
    Qt.Key_F16: 0xF3, Qt.Key_F17: 0xF4, Qt.Key_F18: 0xF5,
    Qt.Key_F19: 0xF6, Qt.Key_F20: 0xF7, Qt.Key_F21: 0xF8,
    Qt.Key_F22: 0xF9, Qt.Key_F23: 0xFA, Qt.Key_F24: 0xFB,
}

# Reverse lookup: Arduino keycode -> human-readable name
ARDUINO_KEY_NAMES = {
    0xB0: "Return",
    0xB1: "Escape",
    0xB2: "Backspace",
    0xB3: "Tab",
    0x20: "Space",
    0xD1: "Insert",
    0xD4: "Delete",
    0xD2: "Home",
    0xD5: "End",
    0xD3: "PageUp",
    0xD6: "PageDown",
    0xDA: "Up",
    0xD9: "Down",
    0xD8: "Left",
    0xD7: "Right",
    0xC1: "CapsLock",
    0xDB: "NumLock",
    0xCE: "PrintScreen",
    0xCF: "ScrollLock",
    0xD0: "Pause",
    # F-keys
    0xC2: "F1",  0xC3: "F2",  0xC4: "F3",
    0xC5: "F4",  0xC6: "F5",  0xC7: "F6",
    0xC8: "F7",  0xC9: "F8",  0xCA: "F9",
    0xCB: "F10", 0xCC: "F11", 0xCD: "F12",
    0xF0: "F13", 0xF1: "F14", 0xF2: "F15",
    0xF3: "F16", 0xF4: "F17", 0xF5: "F18",
    0xF6: "F19", 0xF7: "F20", 0xF8: "F21",
    0xF9: "F22", 0xFA: "F23", 0xFB: "F24",
}


def qt_key_to_arduino(qt_key: int) -> int:
    """Convert Qt::Key to Arduino USB HID keycode.

    Checks special key table first, then for ASCII printable chars (0x20-0x7E)
    converts letters to lowercase and returns ASCII value for others.
    Returns 0 for unknown keys.
    """
    # Check special keys table first
    if qt_key in QT_KEY_TO_ARDUINO:
        return QT_KEY_TO_ARDUINO[qt_key]
    # For ASCII printable characters (Qt::Key_Space through Key_AsciiTilde),
    # Qt::Key values match ASCII uppercase. Arduino expects lowercase for letters.
    if 0x20 <= qt_key <= 0x7E:
        ch = chr(qt_key)
        if ch.isalpha():
            return ord(ch.lower())
        return qt_key
    return 0  # Unknown key


def qt_modifiers_to_device(qt_mods) -> int:
    """Convert Qt::KeyboardModifiers to device modifier bitmask.

    OR's together device modifier bits for each active Qt modifier.
    """
    result = 0
    for qt_mod, device_mod in QT_MOD_TO_DEVICE.items():
        if qt_mods & qt_mod:
            result |= device_mod
    return result


def arduino_keycode_to_display_name(keycode: int) -> str:
    """Convert Arduino keycode to human-readable display name.

    Returns named string for special keys (e.g. 0xB0 -> "Return"),
    or the uppercase character for printable ASCII (e.g. 0x61 -> "A").
    """
    if keycode in ARDUINO_KEY_NAMES:
        return ARDUINO_KEY_NAMES[keycode]
    if 0x20 <= keycode <= 0x7E:
        return chr(keycode).upper()
    if keycode == 0:
        return "(none)"
    return f"0x{keycode:02X}"
