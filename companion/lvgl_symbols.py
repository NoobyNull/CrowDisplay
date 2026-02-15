"""
LVGL Symbol Registry: maps symbol names to Unicode codepoints and UTF-8 bytes

Source: LVGL lv_symbol_def.h (FontAwesome 4 codepoints)
The device firmware stores icon values as raw UTF-8 byte strings in JSON.
This module provides the lookup tables needed to translate between:
- Human-friendly names ("HOME")
- Unicode codepoints (0xF015)
- Raw UTF-8 bytes (b"\\xEF\\x80\\x95") as stored in config JSON
"""

# Each entry: (name, unicode_codepoint, utf8_bytes)
# Extracted from .pio/libdeps/elcrow_7inch/lvgl/src/font/lv_symbol_def.h
LVGL_SYMBOLS = [
    ("AUDIO",         0xF001, b"\xEF\x80\x81"),
    ("VIDEO",         0xF008, b"\xEF\x80\x88"),
    ("LIST",          0xF00B, b"\xEF\x80\x8B"),
    ("OK",            0xF00C, b"\xEF\x80\x8C"),
    ("CLOSE",         0xF00D, b"\xEF\x80\x8D"),
    ("POWER",         0xF011, b"\xEF\x80\x91"),
    ("SETTINGS",      0xF013, b"\xEF\x80\x93"),
    ("HOME",          0xF015, b"\xEF\x80\x95"),
    ("DOWNLOAD",      0xF019, b"\xEF\x80\x99"),
    ("DRIVE",         0xF01C, b"\xEF\x80\x9C"),
    ("REFRESH",       0xF021, b"\xEF\x80\xA1"),
    ("MUTE",          0xF026, b"\xEF\x80\xA6"),
    ("VOLUME_MID",    0xF027, b"\xEF\x80\xA7"),
    ("VOLUME_MAX",    0xF028, b"\xEF\x80\xA8"),
    ("IMAGE",         0xF03E, b"\xEF\x80\xBE"),
    ("TINT",          0xF043, b"\xEF\x81\x83"),
    ("PREV",          0xF048, b"\xEF\x81\x88"),
    ("PLAY",          0xF04B, b"\xEF\x81\x8B"),
    ("PAUSE",         0xF04C, b"\xEF\x81\x8C"),
    ("STOP",          0xF04D, b"\xEF\x81\x8D"),
    ("NEXT",          0xF051, b"\xEF\x81\x91"),
    ("EJECT",         0xF052, b"\xEF\x81\x92"),
    ("LEFT",          0xF053, b"\xEF\x81\x93"),
    ("RIGHT",         0xF054, b"\xEF\x81\x94"),
    ("PLUS",          0xF067, b"\xEF\x81\xA7"),
    ("MINUS",         0xF068, b"\xEF\x81\xA8"),
    ("EYE_OPEN",      0xF06E, b"\xEF\x81\xAE"),
    ("EYE_CLOSE",     0xF070, b"\xEF\x81\xB0"),
    ("WARNING",       0xF071, b"\xEF\x81\xB1"),
    ("SHUFFLE",       0xF074, b"\xEF\x81\xB4"),
    ("UP",            0xF077, b"\xEF\x81\xB7"),
    ("DOWN",          0xF078, b"\xEF\x81\xB8"),
    ("LOOP",          0xF079, b"\xEF\x81\xB9"),
    ("DIRECTORY",     0xF07B, b"\xEF\x81\xBB"),
    ("UPLOAD",        0xF093, b"\xEF\x82\x93"),
    ("CALL",          0xF095, b"\xEF\x82\x95"),
    ("CUT",           0xF0C4, b"\xEF\x83\x84"),
    ("COPY",          0xF0C5, b"\xEF\x83\x85"),
    ("SAVE",          0xF0C7, b"\xEF\x83\x87"),
    ("BARS",          0xF0C9, b"\xEF\x83\x89"),
    ("ENVELOPE",      0xF0E0, b"\xEF\x83\xA0"),
    ("CHARGE",        0xF0E7, b"\xEF\x83\xA7"),
    ("PASTE",         0xF0EA, b"\xEF\x83\xAA"),
    ("BELL",          0xF0F3, b"\xEF\x83\xB3"),
    ("KEYBOARD",      0xF11C, b"\xEF\x84\x9C"),
    ("GPS",           0xF124, b"\xEF\x84\xA4"),
    ("FILE",          0xF158, b"\xEF\x85\x9B"),
    ("WIFI",          0xF1EB, b"\xEF\x87\xAB"),
    ("BATTERY_FULL",  0xF240, b"\xEF\x89\x80"),
    ("BATTERY_3",     0xF241, b"\xEF\x89\x81"),
    ("BATTERY_2",     0xF242, b"\xEF\x89\x82"),
    ("BATTERY_1",     0xF243, b"\xEF\x89\x83"),
    ("BATTERY_EMPTY", 0xF244, b"\xEF\x89\x84"),
    ("USB",           0xF287, b"\xEF\x8A\x87"),
    ("BLUETOOTH",     0xF293, b"\xEF\x8A\x93"),
    ("TRASH",         0xF2ED, b"\xEF\x8B\xAD"),
    ("EDIT",          0xF304, b"\xEF\x8C\x84"),
    ("BACKSPACE",     0xF55A, b"\xEF\x95\x9A"),
    ("SD_CARD",       0xF7C2, b"\xEF\x9F\x82"),
    ("NEW_LINE",      0xF8A2, b"\xEF\xA2\xA2"),
]

# Build lookup dicts
SYMBOL_BY_NAME = {name: (cp, utf8) for name, cp, utf8 in LVGL_SYMBOLS}
SYMBOL_BY_UTF8 = {utf8: (name, cp) for name, cp, utf8 in LVGL_SYMBOLS}


def symbol_name_to_utf8(name: str) -> bytes:
    """Convert symbol name to UTF-8 bytes.

    Example: symbol_name_to_utf8("HOME") -> b"\\xEF\\x80\\x95"
    Returns empty bytes if name not found.
    """
    entry = SYMBOL_BY_NAME.get(name)
    if entry is not None:
        return entry[1]
    return b""


def utf8_to_symbol_name(utf8: bytes) -> str:
    """Convert UTF-8 bytes to symbol name.

    Example: utf8_to_symbol_name(b"\\xEF\\x80\\x95") -> "HOME"
    Returns "UNKNOWN" if bytes not recognized.
    """
    entry = SYMBOL_BY_UTF8.get(utf8)
    if entry is not None:
        return entry[0]
    return "UNKNOWN"
