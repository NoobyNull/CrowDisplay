# Phase 8: Desktop GUI Editor - Research

**Researched:** 2026-02-15
**Domain:** PySide6 desktop application / JSON config editor / WiFi HTTP deployment
**Confidence:** HIGH

## Summary

Phase 8 requires building a standalone PySide6 desktop application that lets users visually design hotkey layouts for the CrowPanel device and deploy them over WiFi. The application is a JSON config editor with a 4x3 button grid preview, property editing panel, page management, icon picker, keyboard shortcut recorder, and one-click WiFi deployment.

PySide6 (currently v6.10.x) provides all the needed widgets out of the box: QGridLayout for the button grid, QKeySequenceEdit for shortcut recording, QColorDialog for color selection, and QNetworkAccessManager (or Python `requests`) for HTTP upload. The main engineering challenge is the translation layer between Qt key concepts (Qt::Key enum, Qt::KeyboardModifiers) and the device's Arduino USB HID keycodes + modifier bitmask format. A second challenge is mapping LVGL symbol UTF-8 byte strings to displayable FontAwesome-derived glyphs in the desktop app's icon picker.

The device already has a fully working HTTP config upload endpoint at `POST /api/config/upload` on SoftAP `CrowPanel-Config` (192.168.4.1), which validates JSON, writes atomically to SD, and rebuilds the UI without reboot. The JSON schema is well-defined and stable (version 1). The editor app just needs to produce valid JSON matching this schema and POST it.

**Primary recommendation:** Build as a single-file PySide6 app (expandable to a package later), with a clear data model layer that mirrors the device's JSON schema, a Qt-to-Arduino keycode translation table, and an LVGL symbol registry mapping symbol names to their UTF-8 byte strings and Unicode codepoints for desktop rendering.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.10.x | Desktop GUI framework | Official Qt for Python binding, actively maintained, LGPL |
| Python | 3.10+ | Runtime | PySide6 6.10 requires 3.10+; matches companion app |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| requests | 2.31+ | HTTP POST multipart upload | Simpler than QNetworkAccessManager for one-shot file upload |
| FontAwesome 4 (font file) | 4.7.0 | Render LVGL symbols in desktop icon picker | LVGL built-in symbols use FontAwesome 4 codepoints |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `requests` for HTTP | `QNetworkAccessManager` + `QHttpMultiPart` | Qt-native but more boilerplate for a simple POST; `requests` is simpler and already a standard Python library |
| FontAwesome 4 OTF | Rendering symbols as text labels (e.g. "HOME") | Font renders actual icons matching device; fallback is just text names |
| Single-file app | Multi-file package with setuptools | Start simple, refactor if it grows beyond ~800 lines |

**Installation:**
```bash
pip install PySide6 requests
```

## Architecture Patterns

### Recommended Project Structure
```
editor/
    hotkey_editor.py          # Main application (single entry point)
    keycode_map.py            # Qt Key -> Arduino keycode translation table
    lvgl_symbols.py           # LVGL symbol name -> UTF-8 bytes + Unicode codepoint registry
    requirements.txt          # PySide6, requests
```

If the app grows large, it can be split further, but starting with 3 files (app + 2 data/mapping modules) keeps things manageable.

### Pattern 1: Data Model Mirroring Device JSON Schema
**What:** Python dataclasses (or plain dicts) that exactly mirror the device JSON structure: AppConfig -> profiles[] -> pages[] -> buttons[]. Serialize/deserialize with `json` module.
**When to use:** Always -- the model IS the JSON schema.
**Example:**
```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class ButtonConfig:
    label: str = ""
    description: str = ""
    color: int = 0xFFFFFF        # 0xRRGGBB stored as decimal int
    icon: str = ""               # UTF-8 bytes string (LVGL symbol)
    action_type: int = 0         # 0=HOTKEY, 1=MEDIA_KEY
    modifiers: int = 0           # MOD_CTRL=0x01 | MOD_SHIFT=0x02 | MOD_ALT=0x04 | MOD_GUI=0x08
    keycode: int = 0             # Arduino USB HID keycode (ASCII for letters, 0xB0+ for special)
    consumer_code: int = 0       # USB HID consumer control code

@dataclass
class PageConfig:
    name: str = ""
    buttons: List[ButtonConfig] = field(default_factory=list)

@dataclass
class ProfileConfig:
    name: str = ""
    pages: List[PageConfig] = field(default_factory=list)

@dataclass
class AppConfig:
    version: int = 1
    active_profile_name: str = ""
    brightness_level: int = 100
    profiles: List[ProfileConfig] = field(default_factory=list)
```

### Pattern 2: Main Window Layout (QSplitter or QHBoxLayout)
**What:** Left panel = button grid + page tabs. Right panel = property editor for selected button.
**When to use:** Standard master-detail pattern for editors.
**Example:**
```python
# Main window layout concept
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        splitter = QSplitter(Qt.Horizontal)

        # Left: page tabs + 4x3 button grid
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.page_tabs = QTabBar()        # Page selector
        self.button_grid = QGridLayout()  # 4 cols x 3 rows of QPushButtons
        left_layout.addWidget(self.page_tabs)
        grid_widget = QWidget()
        grid_widget.setLayout(self.button_grid)
        left_layout.addWidget(grid_widget)

        # Right: property editor
        self.prop_panel = PropertyPanel()  # QWidget with form fields

        splitter.addWidget(left_panel)
        splitter.addWidget(self.prop_panel)
        self.setCentralWidget(splitter)
```

### Pattern 3: Keyboard Shortcut Recorder (Custom Widget wrapping QKeySequenceEdit)
**What:** QKeySequenceEdit captures key combos, then a translation layer converts Qt::Key + Qt::KeyboardModifiers to the device's Arduino keycode + modifier bitmask.
**When to use:** EDIT-06 requirement.
**Key insight:** QKeySequenceEdit records key combos natively. The hard part is mapping Qt key values to Arduino/ESP32 USB HID keycodes. This requires a lookup table (see Don't Hand-Roll section).

### Pattern 4: Icon Picker (Grid of clickable icon buttons)
**What:** A popup dialog or panel showing all available LVGL symbols as clickable icons. Requires loading FontAwesome 4 font to render the actual glyphs. Each icon is a QPushButton with the FA4 codepoint rendered in the FA font.
**When to use:** EDIT-05 requirement.
**Key insight:** LVGL symbols map to FontAwesome 4 Unicode codepoints (0xF001-0xF8A2 range). Loading FA4 OTF as a QFont and rendering each codepoint as a QLabel/QPushButton gives a visual icon picker that matches what the device displays.

### Anti-Patterns to Avoid
- **Storing color as hex string in the model:** The device JSON uses decimal uint32 for color (e.g., 3512027 not "#3498DB"). The editor must read/write decimal integers. Convert to QColor for display only.
- **Using QKeySequenceEdit output directly as keycode:** Qt key values are NOT the same as Arduino USB HID keycodes. Must translate through a mapping table.
- **Hardcoding button count:** The device supports up to CONFIG_MAX_BUTTONS (16) per page. The grid should be 4x3 (12 slots) to match the physical layout, but the model can hold up to 16.
- **Blocking UI during HTTP upload:** Always use a background thread or async for the WiFi deploy, with a progress indicator.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Color picking | Custom color wheel | `QColorDialog.getColor()` | Handles all color spaces, native look |
| Key combo recording | Custom keyDown/keyUp tracker | `QKeySequenceEdit` | Handles modifier detection, timeout, display |
| JSON serialization | Custom string builder | `json.dumps()` with dataclass `asdict()` | Handles escaping, unicode, pretty-print |
| File dialogs | Custom path input | `QFileDialog.getOpenFileName()` / `getSaveFileName()` | Native OS dialogs |
| HTTP multipart POST | Manual boundary construction | `requests.post(url, files={"config": ...})` | Handles encoding, headers, chunking |

**Key insight:** The only truly custom component needed is the Qt-to-Arduino keycode translation table. Everything else has a standard solution.

## Common Pitfalls

### Pitfall 1: Qt Key Values vs Arduino USB HID Keycodes
**What goes wrong:** Qt::Key_A = 0x41 (ASCII 'A'), but Arduino expects lowercase 'a' (0x61) for the keycode field. Qt::Key_Return = 0x01000004, but Arduino KEY_RETURN = 0xB0. These are completely different numbering systems.
**Why it happens:** Qt uses its own enum namespace (Qt::Key_*) while Arduino uses a custom mapping derived from USB HID spec but with Arduino-specific offsets (0x80+ range for special keys).
**How to avoid:** Build an explicit translation table mapping Qt::Key enum values to Arduino keycode bytes. For ASCII letters (a-z), just use the lowercase ASCII value. For special keys (arrows, F-keys, etc.), map each one individually.
**Warning signs:** Shortcuts that work for letter keys but break for Enter, arrows, or F-keys.

### Pitfall 2: Color Format Mismatch
**What goes wrong:** QColor works with QRgb (0xAARRGGBB with alpha), while the device JSON stores color as a plain decimal uint32 of 0xRRGGBB (no alpha). Writing QColor.rgb() includes alpha channel bits (0xFF000000 | color).
**Why it happens:** Different color representation conventions between Qt and the embedded device.
**How to avoid:** Always mask to 24-bit: `color_int = qcolor.rgb() & 0x00FFFFFF`. When reading from JSON, construct QColor with `QColor.fromRgb((val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF)`.
**Warning signs:** Colors displaying correctly in editor but showing wrong on device (shifted by alpha bits).

### Pitfall 3: LVGL Symbol Icon Encoding
**What goes wrong:** LVGL symbols are stored as raw UTF-8 byte strings in JSON (e.g., `"\xEF\x80\x95"` for LV_SYMBOL_HOME). These are NOT human-readable symbol names. The editor must map between human-friendly names ("HOME"), Unicode codepoints (0xF015), and raw UTF-8 byte strings.
**Why it happens:** The device firmware uses C string literals with hex escape sequences. JSON stores the actual UTF-8 bytes.
**How to avoid:** Build an LVGL symbol registry with three representations per symbol: name ("HOME"), codepoint (0xF015), and UTF-8 bytes (b"\xEF\x80\x95"). The icon picker shows names/rendered glyphs; the JSON serializer writes UTF-8 bytes.
**Warning signs:** Icons showing as "?" or blank squares on the device after deployment.

### Pitfall 4: WiFi Connection to Device SoftAP
**What goes wrong:** User clicks "Deploy" but their PC is not connected to the CrowPanel-Config WiFi network. The HTTP POST times out or fails silently.
**Why it happens:** The device runs a SoftAP (192.168.4.1) that the PC must join first. The editor app cannot programmatically join WiFi networks.
**How to avoid:** Before deploying, check reachability with a quick HTTP GET to `http://192.168.4.1/` (or a timeout ping). Show clear instructions: "Connect to WiFi network 'CrowPanel-Config' (password: crowconfig) first." Show connection status in the deploy UI.
**Warning signs:** Deploy button appears to hang with no feedback.

### Pitfall 5: QKeySequenceEdit Captures System Shortcuts
**What goes wrong:** When recording a shortcut like Ctrl+C, the QKeySequenceEdit captures it but the OS/Qt also processes it (e.g., copies clipboard content). Certain shortcuts like Alt+F4 may close the window.
**Why it happens:** QKeySequenceEdit does not consume all key events before the system processes them.
**How to avoid:** This is largely acceptable for a config editor (the recording still works). Document that some system-reserved shortcuts may cause side effects during recording. Alternatively, provide a manual entry mode as fallback.
**Warning signs:** Window closing or unexpected clipboard operations during shortcut recording.

## Code Examples

### Qt Key to Arduino Keycode Translation
```python
# Source: ESP32 Arduino USBHIDKeyboard.h key definitions
# (https://github.com/espressif/arduino-esp32/blob/master/libraries/USB/src/USBHIDKeyboard.h)

from PySide6.QtCore import Qt

# Qt modifier flags to device MOD_* bitmask
QT_MOD_TO_DEVICE = {
    Qt.ControlModifier: 0x01,  # MOD_CTRL
    Qt.ShiftModifier:   0x02,  # MOD_SHIFT
    Qt.AltModifier:     0x04,  # MOD_ALT
    Qt.MetaModifier:    0x08,  # MOD_GUI (Super/Windows/Command)
}

# Qt::Key -> Arduino keycode for special keys
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

def qt_key_to_arduino(qt_key: int) -> int:
    """Convert Qt::Key to Arduino USB HID keycode."""
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
    """Convert Qt::KeyboardModifiers to device modifier bitmask."""
    result = 0
    for qt_mod, device_mod in QT_MOD_TO_DEVICE.items():
        if qt_mods & qt_mod:
            result |= device_mod
    return result
```

### LVGL Symbol Registry
```python
# Source: LVGL lv_symbol_def.h
# (from .pio/libdeps/elcrow_7inch/lvgl/src/font/lv_symbol_def.h)

# Each entry: (name, unicode_codepoint, utf8_bytes)
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
```

### WiFi Deploy (HTTP POST)
```python
import requests
import json

DEVICE_IP = "192.168.4.1"
UPLOAD_URL = f"http://{DEVICE_IP}/api/config/upload"

def deploy_config(config_dict: dict, timeout: float = 10.0) -> tuple[bool, str]:
    """Deploy config JSON to device via WiFi HTTP POST.

    Returns (success: bool, message: str).
    The device expects multipart form data with field name 'config'.
    """
    json_bytes = json.dumps(config_dict).encode("utf-8")
    try:
        resp = requests.post(
            UPLOAD_URL,
            files={"config": ("config.json", json_bytes, "application/json")},
            timeout=timeout,
        )
        result = resp.json()
        if result.get("success"):
            return True, "Configuration deployed successfully"
        else:
            return False, result.get("error", "Unknown device error")
    except requests.ConnectionError:
        return False, "Cannot reach device. Is PC connected to 'CrowPanel-Config' WiFi?"
    except requests.Timeout:
        return False, "Device did not respond (timeout)"
    except Exception as e:
        return False, f"Deploy failed: {e}"
```

### Button Grid Widget
```python
from PySide6.QtWidgets import QPushButton, QGridLayout, QWidget, QSizePolicy
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Signal

GRID_COLS = 4
GRID_ROWS = 3

class ButtonGridWidget(QWidget):
    """4x3 grid of buttons matching the device's physical layout."""
    button_clicked = Signal(int)  # emits button index (0-11)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = []
        layout = QGridLayout(self)
        layout.setSpacing(8)

        for i in range(GRID_ROWS * GRID_COLS):
            row, col = divmod(i, GRID_COLS)
            btn = QPushButton()
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setMinimumSize(100, 80)
            btn.clicked.connect(lambda checked, idx=i: self.button_clicked.emit(idx))
            layout.addWidget(btn, row, col)
            self._buttons.append(btn)

    def update_button(self, index: int, label: str, color: int, icon_char: str = ""):
        """Update a button's appearance. color is 0xRRGGBB int."""
        btn = self._buttons[index]
        display_text = f"{icon_char}\n{label}" if icon_char else label
        btn.setText(display_text)
        qc = QColor((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
        # Set button stylesheet with contrasting text
        luminance = 0.299 * qc.red() + 0.587 * qc.green() + 0.114 * qc.blue()
        text_color = "#000" if luminance > 140 else "#FFF"
        btn.setStyleSheet(
            f"background-color: {qc.name()}; color: {text_color}; "
            f"font-size: 14px; font-weight: bold; border-radius: 8px;"
        )
```

### Shortcut Recorder Widget
```python
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QKeySequenceEdit
from PySide6.QtCore import Signal

class ShortcutRecorder(QWidget):
    """Widget that records a keyboard shortcut and emits (modifiers, keycode)
    in the device's format."""
    shortcut_changed = Signal(int, int)  # (modifier_bitmask, arduino_keycode)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._edit = QKeySequenceEdit()
        self._edit.setMaximumSequenceLength(1)  # Single key combo only
        self._edit.editingFinished.connect(self._on_editing_finished)
        layout.addWidget(self._edit)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._edit.clear)
        layout.addWidget(clear_btn)

    def _on_editing_finished(self):
        seq = self._edit.keySequence()
        if seq.count() == 0:
            return
        # Extract first key combination
        combo = seq[0]  # QKeyCombination
        qt_key = combo.key()
        qt_mods = combo.keyboardModifiers()

        arduino_keycode = qt_key_to_arduino(int(qt_key))
        device_mods = qt_modifiers_to_device(qt_mods)
        self.shortcut_changed.emit(device_mods, arduino_keycode)

    def set_shortcut(self, modifiers: int, keycode: int):
        """Set from device format for display (reverse mapping needed)."""
        # Build human-readable string for display
        parts = []
        if modifiers & 0x01: parts.append("Ctrl")
        if modifiers & 0x02: parts.append("Shift")
        if modifiers & 0x04: parts.append("Alt")
        if modifiers & 0x08: parts.append("Meta")
        # Reverse keycode to Qt key for display -- need reverse lookup
        key_name = arduino_keycode_to_display_name(keycode)
        parts.append(key_name)
        self._edit.setKeySequence(QKeySequence.fromString("+".join(parts)))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyQt5 | PySide6 (Qt 6) | 2021 | PySide6 is official Qt binding; LGPL license; Qt6 features |
| QKeySequenceEdit single-combo | QKeySequenceEdit with `setMaximumSequenceLength(1)` | Qt 6.5 | Previously hard to limit to single combo |
| `QKeyCombination` via indexing | `QKeySequence[0]` returns QKeyCombination | Qt 6.0 | Clean API for extracting key+modifiers from sequence |

**Deprecated/outdated:**
- PyQt5: Still works but PySide6 is the officially supported Qt for Python binding
- `QKeySequence.toString()` for parsing: Use `QKeyCombination.key()` and `.keyboardModifiers()` instead of string parsing

## Open Questions

1. **FontAwesome 4 Font Distribution**
   - What we know: LVGL built-in symbols use FontAwesome 4 codepoints. The FA4 OTF font file is needed to render these icons in the desktop app.
   - What's unclear: Should we bundle the FA4 font file in the editor directory, or fall back to text names if not available? FA4 is under SIL OFL license (permissive).
   - Recommendation: Bundle `fontawesome-webfont.ttf` (FA 4.7.0) in the editor directory. It is ~160KB and freely redistributable. Fall back to text names ("HOME", "PLAY") if font load fails.

2. **Reverse Keycode Mapping for Display**
   - What we know: We need forward mapping (Qt -> Arduino) for recording shortcuts. We also need reverse mapping (Arduino keycode -> human-readable name) for displaying existing config.
   - What's unclear: The reverse mapping from Arduino keycode to a QKeySequence string for display in the QKeySequenceEdit widget.
   - Recommendation: Build a reverse lookup table (Arduino keycode -> display name string) alongside the forward table. For ASCII keys, just `chr(keycode)`. For special keys, a dict of `{0xB0: "Return", 0xD8: "Left", ...}`.

3. **Consumer Control Code Entry**
   - What we know: Media keys use `action_type: 1` and `consumer_code` (e.g., 0x00CD for Play/Pause). QKeySequenceEdit cannot capture media keys on all platforms.
   - What's unclear: How to let users configure media keys in the editor.
   - Recommendation: Provide a dropdown/combobox with common consumer control codes (Play/Pause=0xCD, Next=0xB5, Prev=0xB6, VolUp=0xE9, VolDown=0xEA, Mute=0xE2, Stop=0xB7) rather than trying to capture them. Toggle between "Hotkey" and "Media Key" mode in the property panel.

4. **Device Discovery vs. Hardcoded IP**
   - What we know: Device SoftAP IP is always 192.168.4.1 (default ESP32 SoftAP IP).
   - What's unclear: Whether to support mDNS discovery (`crowpanel.local`) or just hardcode the IP.
   - Recommendation: Hardcode 192.168.4.1 as default with an editable IP field. The SoftAP IP is deterministic. mDNS adds complexity for no real benefit in SoftAP mode.

## Sources

### Primary (HIGH confidence)
- ESP32 Arduino USBHIDKeyboard.h - Full special keycode definitions (https://github.com/espressif/arduino-esp32/blob/master/libraries/USB/src/USBHIDKeyboard.h)
- LVGL lv_symbol_def.h - Complete symbol-to-UTF8 mapping (local: `.pio/libdeps/elcrow_7inch/lvgl/src/font/lv_symbol_def.h`)
- Device config.h / config.cpp - JSON schema, data structures, validation rules (local: `display/config.h`, `display/config.cpp`)
- Device config_server.cpp - HTTP upload endpoint implementation, SoftAP config (local: `display/config_server.cpp`)
- shared/protocol.h - Modifier mask definitions (local: `shared/protocol.h`)
- PySide6 QKeySequenceEdit docs (https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QKeySequenceEdit.html)
- PySide6 QColorDialog docs (https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QColorDialog.html)
- Qt QKeyCombination docs (https://doc.qt.io/qt-6/qkeycombination.html)
- PySide6 PyPI (https://pypi.org/project/PySide6/) - version 6.10.x confirmed current

### Secondary (MEDIUM confidence)
- PySide6 QGridLayout tutorial (https://www.pythonguis.com/tutorials/pyside6-layouts/)
- Qt QKeySequence docs - Key string format (https://doc.qt.io/qt-6/qkeysequence.html)
- LVGL font documentation - Symbol font architecture (https://docs.lvgl.io/8.0/overview/font.html)

### Tertiary (LOW confidence)
- FontAwesome 4 codepoint usage in LVGL - inferred from lv_symbol_def.h comments referencing FontAwesome, not directly confirmed by LVGL docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - PySide6 is the obvious choice per prior decision; version confirmed via PyPI
- Architecture: HIGH - Standard Qt patterns (QGridLayout, QSplitter, QKeySequenceEdit) well-documented
- Keycode mapping: HIGH - Arduino keycode values extracted directly from ESP32 Arduino source code
- LVGL symbol mapping: HIGH - Extracted directly from project's own lv_symbol_def.h header
- Pitfalls: HIGH - Based on concrete analysis of format mismatches between Qt and device firmware
- Icon picker font: MEDIUM - FA4 usage inferred from LVGL docs + codepoint ranges, not 100% confirmed the exact OTF version

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (stable domain, PySide6 and device firmware unlikely to change)
