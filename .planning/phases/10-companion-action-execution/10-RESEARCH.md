# Phase 10: Companion Action Execution - Research

**Researched:** 2026-02-15
**Domain:** USB HID vendor protocol, Linux desktop action execution, PySide6 editor UX
**Confidence:** HIGH

## Summary

This phase transforms the button press flow from "display sends keystroke to bridge, bridge fires USB HID keyboard" to "display sends button identity to bridge, bridge relays to companion, companion executes the configured action." The companion service already communicates bidirectionally with the bridge over vendor HID (report ID 6). The bridge currently only reads from vendor HID (host-to-device OUTPUT reports) but USBHIDVendor also supports `write()` for device-to-host INPUT reports, enabling the bridge to forward button presses to the companion.

Four action types are needed: Launch App (with focus-or-launch), Run Shell Command, Open URL, and Keyboard Shortcut (legacy). The editor needs a new action type system with appropriate input widgets per type, a test button, and fixes for the scroll-wheel-hijacking-dropdown bug.

**Primary recommendation:** Implement companion-side action execution using subprocess for all action types, with ydotool for keyboard shortcuts (Wayland-compatible), wmctrl for focus-or-launch on X11 (with compositor-specific fallbacks documented), and watchdog for config auto-reload.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Four action types: Launch App (.desktop), Run Shell Command, Open URL, Keyboard Shortcut (legacy)
- Launch App supports focus-or-launch behavior (configurable per-button)
- Shell commands: fire and forget, no sudo, output/errors logged to companion log only
- Open URL: opens in default browser
- Display sends page number + widget index (NOT modifier+keycode) to identify which button was pressed
- Companion looks up the action from the config by page + widget index
- Companion auto-reloads config when the file changes (file watcher)
- If companion isn't running, button presses fail silently -- no fallback
- Bridge keeps USB HID keyboard interface registered but does NOT fire keystrokes for hotkey actions
- Bridge relays button presses to companion via vendor HID input reports
- Media key commands also route through companion -- no direct USB consumer control
- ACK flow: Claude decides whether bridge ACKs immediately or waits for companion confirmation
- App picker auto-fills launch command; dropdown + text field for other action types
- Action type dropdown selects which input is shown
- Existing keyboard shortcut recorder stays -- shown only when action type is Keyboard Shortcut
- Default app launch behavior: focus-or-launch (smart), user can change per-button
- "Test" button in editor fires the action immediately on PC without going through display/bridge
- Window opens maximized/expanded (not full screen, but expanded to fill available space)
- Fix scroll wheel bug: prevent mouse scroll over dropdown widgets from changing their value

### Claude's Discretion
- Keyboard shortcut execution method (bridge USB HID vs companion xdotool/ydotool)
- Config storage approach (same config.json vs separate actions file)
- Vendor HID input report format for bridge -> companion communication
- ACK flow timing (instant bridge ACK vs wait for companion)
- Media key simulation method on companion side

### Deferred Ideas (OUT OF SCOPE)
- None
</user_constraints>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hidapi | current | USB HID vendor communication | Already used by companion for stats |
| PySide6 | current | Desktop editor GUI | Already the project's Qt binding |
| subprocess | stdlib | Launch apps, run commands | Python built-in, no deps needed |

### New Dependencies
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| watchdog | 4.x+ | File system monitoring for config reload | Config auto-reload on file change |
| ydotool | system | Keyboard shortcut simulation (Wayland-safe) | When action type is Keyboard Shortcut |
| wmctrl | system | Window focus by WM_CLASS (X11) | Focus-or-launch on X11 desktops |
| xdg-open | system | Open URLs in default browser | Open URL action type |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ydotool (companion) | Bridge USB HID keystroke | USB HID works universally but loses per-compositor features; ydotool works on Wayland+X11 but requires ydotoold daemon |
| watchdog | inotifyx / polling | watchdog is cross-platform, well-maintained, simple API |
| wmctrl | hyprctl/swaymsg | wmctrl is X11-only; Wayland needs compositor-specific tools |

**Installation:**
```bash
pip install watchdog
# System packages (Arch):
sudo pacman -S ydotool wmctrl xdg-utils
```

## Architecture Patterns

### Recommended Changes to Existing Files

```
bridge/
  main.cpp              # Add MSG_BUTTON_PRESS case in ESP-NOW poll, relay via Vendor.write()
  usb_hid.cpp           # Add send_vendor_report() function using Vendor.write()
  usb_hid.h             # Declare send_vendor_report()

shared/
  protocol.h            # Add MSG_BUTTON_PRESS type, ButtonPressMsg struct

display/
  espnow_link.cpp       # Add send_button_press_to_bridge() that sends page+widget index
  ui.cpp                # Change btn_event_cb to send page+widget instead of modifiers+keycode

companion/
  hotkey_companion.py   # Add read thread for vendor HID input reports, action executor
  config_manager.py     # Add new action types, action lookup by page+widget
  action_executor.py    # NEW: Action execution logic (launch, shell, URL, keyboard)
  ui/
    button_editor.py    # Overhaul: action type dropdown with 4 types, per-type input widgets
    editor_main.py      # Add test button, fix scroll wheel bug, window maximize
    no_scroll_combo.py  # NEW: QComboBox subclass that ignores wheel events when unfocused
```

### Pattern 1: New Message Type for Button Press

**What:** A new protocol message `MSG_BUTTON_PRESS` carries page index and widget index from display to bridge, then from bridge to companion via vendor HID.

**When to use:** Every time a hotkey button is pressed on the display.

**Recommended report format (Claude's discretion: vendor HID input report):**
```c
// In shared/protocol.h
// MSG_BUTTON_PRESS = 0x0B  (next available message type)

struct __attribute__((packed)) ButtonPressMsg {
    uint8_t page_index;    // 0-based page number
    uint8_t widget_index;  // 0-based widget index within that page
};
```

**Bridge relay flow:**
```
Display -> ESP-NOW -> Bridge -> Vendor.write() -> Host -> companion reads
```

Bridge sends via Vendor.write():
```c
// bridge/usb_hid.cpp
void send_vendor_report(uint8_t msg_type, const uint8_t *payload, uint8_t len) {
    uint8_t buf[63];
    memset(buf, 0, sizeof(buf));
    buf[0] = msg_type;
    if (len > 0 && payload) memcpy(&buf[1], payload, len);
    Vendor.write(buf, 1 + len);
}
```

Companion reads via device.read():
```python
# In companion, on a background thread:
data = device.read(63, timeout_ms=100)
if data and len(data) >= 2:
    msg_type = data[0]
    if msg_type == MSG_BUTTON_PRESS:
        page_idx = data[1]
        widget_idx = data[2]
        execute_action(page_idx, widget_idx)
```

**Confidence:** HIGH -- USBHIDVendor.write() sends INPUT reports to host, hidapi device.read() reads them. This is exactly the same mechanism but in reverse direction of what stats uses.

### Pattern 2: ACK Flow (Claude's discretion)

**Recommendation: Bridge ACKs immediately to the display, does not wait for companion.**

Rationale:
- The display needs fast visual feedback (button press animation)
- Companion action execution is inherently asynchronous (launching apps takes variable time)
- Waiting for companion adds latency and failure modes (companion crash = display hangs)
- The display already handles ACK timeouts; immediate ACK preserves this contract

Flow:
1. Display sends MSG_BUTTON_PRESS via ESP-NOW
2. Bridge receives, immediately sends MSG_HOTKEY_ACK back to display
3. Bridge simultaneously relays MSG_BUTTON_PRESS via Vendor.write() to companion
4. Companion executes action asynchronously

**Confidence:** HIGH -- This is the simplest and most resilient approach.

### Pattern 3: Keyboard Shortcut Execution (Claude's discretion)

**Recommendation: Execute keyboard shortcuts via ydotool on the companion side, NOT via bridge USB HID.**

Rationale:
- Consistency: ALL action types go through the same companion execution path
- Wayland support: ydotool works on both X11 and Wayland via /dev/uinput
- Simplicity: Bridge no longer needs to distinguish "relay to companion" vs "fire keystroke"
- The bridge's USB HID keyboard interface stays registered but idle (for potential future use)

Implementation:
```python
def execute_keyboard_shortcut(modifiers: int, keycode: int):
    """Simulate keyboard shortcut via ydotool."""
    keys = []
    if modifiers & MOD_CTRL:  keys.append("ctrl")
    if modifiers & MOD_SHIFT: keys.append("shift")
    if modifiers & MOD_ALT:   keys.append("alt")
    if modifiers & MOD_GUI:   keys.append("super")

    # Convert USB HID keycode to ydotool key name
    key_name = hid_keycode_to_name(keycode)
    keys.append(key_name)

    subprocess.Popen(["ydotool", "key", "+".join(keys)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```

Fallback: If ydotool is not available, log a warning and try xdotool (X11 only).

**Confidence:** MEDIUM -- ydotool key name syntax needs verification against the existing keycode_map.py. The `ydotool key` command accepts human-readable names like "ctrl+alt+t" which is straightforward.

### Pattern 4: Media Key Simulation (Claude's discretion)

**Recommendation: Use ydotool for media keys too, since consumer control codes map to standard key names.**

```python
MEDIA_KEY_NAMES = {
    0xCD: "playpause",
    0xB5: "nextsong",
    0xB6: "previoussong",
    0xB7: "stopcd",
    0xE9: "volumeup",
    0xEA: "volumedown",
    0xE2: "mute",
}

def execute_media_key(consumer_code: int):
    key_name = MEDIA_KEY_NAMES.get(consumer_code)
    if key_name:
        subprocess.Popen(["ydotool", "key", key_name],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
```

**Confidence:** MEDIUM -- ydotool key names for media keys need verification. The Linux input event codes (KEY_PLAYPAUSE etc.) are what ydotool uses internally via /dev/uinput, but the human-readable name syntax may differ. May need to use raw keycodes (e.g., `164:1 164:0` for KEY_PLAYPAUSE).

### Pattern 5: Config Storage (Claude's discretion)

**Recommendation: Store action configuration in the SAME config.json, adding new fields to the widget dict.**

Rationale:
- The widget already has `action_type`, `modifiers`, `keycode`, `consumer_code`
- Just extend the existing schema with new action type constants and fields
- Single file means deploy-to-device stays simple
- The display doesn't need to understand the new action types -- it just sends page+widget index

New config fields per hotkey button widget:
```json
{
    "widget_type": 0,
    "action_type": 3,
    "label": "Firefox",
    "launch_command": "firefox",
    "launch_focus_or_launch": true,
    "launch_wm_class": "firefox",
    "shell_command": "",
    "url": "",
    "modifiers": 0,
    "keycode": 0,
    "consumer_code": 0
}
```

New action type constants:
```python
ACTION_HOTKEY = 0        # Existing: keyboard shortcut
ACTION_MEDIA_KEY = 1     # Existing: consumer control
ACTION_LAUNCH_APP = 2    # New: launch/focus application
ACTION_SHELL_CMD = 3     # New: run shell command
ACTION_OPEN_URL = 4      # New: open URL in browser
```

**Confidence:** HIGH -- Clean extension of existing schema, no migration needed (new fields default to empty).

### Pattern 6: Focus-or-Launch Implementation

**What:** When launching an app, first check if it's already running. If yes, focus its window. If no, launch it.

**Implementation strategy:**
```python
import subprocess
import shutil

def focus_or_launch(exec_cmd: str, wm_class: str, focus_enabled: bool):
    if focus_enabled and wm_class:
        # Try to focus existing window
        if _try_focus_window(wm_class):
            return  # Window found and focused

    # Launch the application
    # Strip .desktop Exec field codes (%u, %U, %f, %F, etc.)
    clean_cmd = re.sub(r'%[uUfFdDnNickvm]', '', exec_cmd).strip()
    subprocess.Popen(clean_cmd, shell=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _try_focus_window(wm_class: str) -> bool:
    """Try to focus a window by WM_CLASS. Returns True if successful."""
    # Try wmctrl first (X11, widely available)
    if shutil.which("wmctrl"):
        result = subprocess.run(
            ["wmctrl", "-x", "-a", wm_class],
            capture_output=True, timeout=2
        )
        return result.returncode == 0

    # Could add hyprctl, swaymsg fallbacks here in future
    return False
```

**Key detail:** The .desktop `Exec` field contains format codes like `%u` (URL), `%f` (file) that must be stripped before execution.

**WM_CLASS discovery:** The app_scanner already reads .desktop files. The `StartupWMClass` field in .desktop files provides the WM_CLASS. Fall back to the app name if not present.

**Confidence:** HIGH for X11 (wmctrl is well-tested). MEDIUM for Wayland (compositor-specific, but can degrade gracefully to just launching).

### Anti-Patterns to Avoid
- **Do not keep bridge USB HID keystroke for some actions and companion for others:** All actions go through companion for consistency. Bridge only relays button identity.
- **Do not block the companion main stats loop waiting for action completion:** Action execution must be async (subprocess.Popen, not subprocess.run).
- **Do not execute shell commands with sudo:** Security risk, explicitly forbidden by user decision.
- **Do not use shell=True for launch commands without sanitization:** Strip .desktop Exec format codes first.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File watching | Custom inotify wrapper | watchdog library | Cross-platform, handles edge cases (atomic writes, rename events) |
| .desktop file parsing | Custom parser | configparser (already used in app_scanner.py) | Already implemented, handles quoting/escaping |
| URL opening | Custom browser detection | xdg-open / webbrowser.open | System standard, respects user's default browser |
| Keyboard simulation | Raw /dev/uinput | ydotool | Handles key mapping, timing, modifier combos |
| WM_CLASS window focus | D-Bus/X11 protocol code | wmctrl command | Battle-tested, handles edge cases |

## Common Pitfalls

### Pitfall 1: HID Report ID Byte Offset
**What goes wrong:** The hidapi library on Linux prepends/expects a report ID byte. The bridge's USBHIDVendor.write() does NOT include the report ID in its buffer.
**Why it happens:** On the host side, hidapi's `device.read()` returns data starting AFTER the report ID byte. But the bridge's `Vendor.write(buf, len)` sends `buf` as-is without a report ID prefix -- TinyUSB handles the report ID internally.
**How to avoid:** When companion reads with `device.read(63)`, the first byte IS the message type (not report ID). When companion writes with `device.write(b"\x06" + payload)`, it prepends 0x06 report ID. The asymmetry is because hidapi strips the report ID on read but requires it on write.
**Warning signs:** Off-by-one in received data, message type byte appearing as wrong value.

### Pitfall 2: .desktop Exec Field Format Codes
**What goes wrong:** Running `exec_cmd` directly fails because it contains `%u`, `%F`, etc. placeholders.
**Why it happens:** .desktop Exec fields use freedesktop.org format codes that the desktop entry launcher substitutes.
**How to avoid:** Strip all `%[uUfFdDnNickvm]` patterns before executing.
**Warning signs:** Shell errors about unexpected arguments, apps failing to launch.

### Pitfall 3: Blocking the Stats Loop
**What goes wrong:** If action execution blocks the main companion loop, stats stop streaming.
**Why it happens:** Using subprocess.run() with a long-running command, or waiting for focus-or-launch.
**How to avoid:** Always use subprocess.Popen (fire-and-forget) for action execution. Run action execution on a separate thread or use non-blocking patterns.
**Warning signs:** Stats freeze on the display after pressing a button.

### Pitfall 4: Vendor HID Read Thread Safety
**What goes wrong:** Reading from the vendor HID device on a background thread while the main thread writes stats can cause race conditions.
**Why it happens:** The hidapi device handle is not thread-safe by default.
**How to avoid:** Use a threading.Lock around all device.read() and device.write() calls, or use a single I/O thread that handles both reads and writes.
**Warning signs:** Corrupted HID reports, intermittent IOError exceptions.

### Pitfall 5: QComboBox Scroll Wheel Hijacking
**What goes wrong:** Scrolling in the editor panel changes dropdown values instead of scrolling the panel.
**Why it happens:** QComboBox consumes wheel events regardless of focus state by default.
**How to avoid:** Subclass QComboBox to ignore wheel events when not focused:
```python
class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
```
Set `setFocusPolicy(Qt.StrongFocus)` on all instances.
**Warning signs:** Accidentally changing action type or other dropdowns while scrolling.

### Pitfall 6: Config Reload Race Condition
**What goes wrong:** File watcher triggers reload while config is being written (partial write).
**Why it happens:** JSON save writes are not atomic; watchdog fires on each write syscall.
**How to avoid:** Debounce file change events (e.g., 500ms delay). Also, the config_manager.save_json_file already writes directly -- consider atomic write (write to .tmp, rename).
**Warning signs:** JSON parse errors on reload, partial config loaded.

## Code Examples

### Vendor HID Bidirectional Communication

Bridge side (C++, sending button press to companion):
```cpp
// In bridge/main.cpp, in the ESP-NOW poll section:
case MSG_BUTTON_PRESS: {
    if (payload_len >= sizeof(ButtonPressMsg)) {
        // Immediately ACK back to display
        HotkeyAckMsg ack = { 0 };
        espnow_send(MSG_HOTKEY_ACK, (uint8_t *)&ack, sizeof(ack));

        // Relay to companion via vendor HID INPUT report
        send_vendor_report(MSG_BUTTON_PRESS, payload, sizeof(ButtonPressMsg));
        Serial.printf("BTN: page=%d widget=%d -> companion\n",
                      payload[0], payload[1]);
    }
    break;
}
```

Companion side (Python, reading button presses):
```python
MSG_BUTTON_PRESS = 0x0B

def _vendor_read_thread(device, lock, config_manager):
    """Background thread that reads vendor HID input reports from bridge."""
    while running:
        try:
            with lock:
                data = device.read(63, timeout_ms=100)
            if data and len(data) >= 3:
                msg_type = data[0]
                if msg_type == MSG_BUTTON_PRESS:
                    page_idx = data[1]
                    widget_idx = data[2]
                    threading.Thread(
                        target=execute_action,
                        args=(config_manager, page_idx, widget_idx),
                        daemon=True
                    ).start()
        except (IOError, OSError):
            break  # Device disconnected
```

### Action Executor Module

```python
# companion/action_executor.py

import subprocess
import shutil
import re
import logging
import webbrowser

logger = logging.getLogger(__name__)

ACTION_HOTKEY = 0
ACTION_MEDIA_KEY = 1
ACTION_LAUNCH_APP = 2
ACTION_SHELL_CMD = 3
ACTION_OPEN_URL = 4

def execute_action(config_manager, page_idx: int, widget_idx: int):
    """Look up and execute the action for a button press."""
    widget = config_manager.get_widget(page_idx, widget_idx)
    if widget is None:
        logger.warning("No widget at page=%d widget=%d", page_idx, widget_idx)
        return

    action_type = widget.get("action_type", ACTION_HOTKEY)

    if action_type == ACTION_LAUNCH_APP:
        _exec_launch_app(widget)
    elif action_type == ACTION_SHELL_CMD:
        _exec_shell_cmd(widget)
    elif action_type == ACTION_OPEN_URL:
        _exec_open_url(widget)
    elif action_type == ACTION_MEDIA_KEY:
        _exec_media_key(widget)
    elif action_type == ACTION_HOTKEY:
        _exec_keyboard_shortcut(widget)

def _exec_launch_app(widget):
    exec_cmd = widget.get("launch_command", "")
    wm_class = widget.get("launch_wm_class", "")
    focus_enabled = widget.get("launch_focus_or_launch", True)

    if not exec_cmd:
        logger.warning("Launch app: no command configured")
        return

    if focus_enabled and wm_class and _try_focus_window(wm_class):
        logger.info("Focused existing window: %s", wm_class)
        return

    clean_cmd = re.sub(r'%[uUfFdDnNickvm]', '', exec_cmd).strip()
    logger.info("Launching: %s", clean_cmd)
    subprocess.Popen(clean_cmd, shell=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _exec_shell_cmd(widget):
    cmd = widget.get("shell_command", "")
    if not cmd:
        return
    if "sudo" in cmd.split():
        logger.warning("Shell command contains sudo -- blocked: %s", cmd)
        return
    logger.info("Running shell: %s", cmd)
    subprocess.Popen(cmd, shell=True,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def _exec_open_url(widget):
    url = widget.get("url", "")
    if not url:
        return
    logger.info("Opening URL: %s", url)
    webbrowser.open(url)

def _try_focus_window(wm_class: str) -> bool:
    if shutil.which("wmctrl"):
        result = subprocess.run(["wmctrl", "-x", "-a", wm_class],
                                capture_output=True, timeout=2)
        return result.returncode == 0
    return False
```

### Config File Watcher

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time

class ConfigReloadHandler(FileSystemEventHandler):
    def __init__(self, config_path, config_manager, debounce_sec=0.5):
        self.config_path = config_path
        self.config_manager = config_manager
        self.debounce_sec = debounce_sec
        self._timer = None

    def on_modified(self, event):
        if event.src_path == str(self.config_path):
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(
                self.debounce_sec, self._reload
            )
            self._timer.start()

    def _reload(self):
        if self.config_manager.load_json_file(str(self.config_path)):
            logging.info("Config reloaded from %s", self.config_path)
```

### NoScrollComboBox Widget

```python
from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Qt

class NoScrollComboBox(QComboBox):
    """QComboBox that ignores wheel events when not focused."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| xdotool for keyboard sim | ydotool for Wayland compat | 2023+ | xdotool broken on Wayland; ydotool uses /dev/uinput |
| wmctrl for window mgmt | Compositor-specific IPC | 2022+ | wmctrl X11-only; Wayland needs hyprctl/swaymsg per compositor |
| Direct USB HID keystroke | Companion-side execution | This phase | Enables non-keyboard actions (launch, URL, shell) |

**Deprecated/outdated:**
- xdotool: Still works on X11 but broken on Wayland. Use ydotool as primary, xdotool as fallback.
- wmctrl: X11-only. Works well where available but no Wayland equivalent exists as a single universal tool.

## Open Questions

1. **ydotool daemon requirement**
   - What we know: ydotool requires ydotoold running (needs /dev/uinput access)
   - What's unclear: Whether the user's system already has this configured
   - Recommendation: Check at startup, log clear instructions if missing. Consider adding a "ydotoold not running" warning in the editor.

2. **Wayland focus-or-launch**
   - What we know: wmctrl only works on X11. Wayland compositors each have their own IPC (hyprctl, swaymsg, etc.)
   - What's unclear: Which compositor the user runs (though project mentions Hyprland in old profile names)
   - Recommendation: Start with wmctrl, degrade gracefully. Log a message if focus fails on Wayland. Can add compositor-specific backends later.

3. **ydotool key name mapping**
   - What we know: ydotool accepts names like "ctrl+alt+t" and raw keycodes like "28:1 28:0"
   - What's unclear: Exact mapping from USB HID keycodes (used in existing keycode_map.py) to Linux input event keycodes used by ydotool
   - Recommendation: Build a mapping table from HID keycodes to Linux KEY_* names. The existing keycode_map.py already has HID-to-name mappings that can be adapted.

4. **StartupWMClass availability in .desktop files**
   - What we know: Many .desktop files include StartupWMClass but not all
   - What's unclear: Coverage percentage for common applications
   - Recommendation: Use StartupWMClass when available, fall back to executable name. The app_scanner should extract this field.

## Sources

### Primary (HIGH confidence)
- `/home/matthew/.platformio/packages/framework-arduinoespressif32/libraries/USB/src/USBHIDVendor.h` -- Confirmed Vendor.write() exists for device-to-host input reports
- `/data/Elcrow-Display-hotkeys/bridge/usb_hid.cpp` -- Current bridge vendor HID implementation (read-only)
- `/data/Elcrow-Display-hotkeys/companion/hotkey_companion.py` -- Current companion HID write pattern (device.write with 0x06 report ID)
- `/data/Elcrow-Display-hotkeys/shared/protocol.h` -- Current message types and structs
- `/data/Elcrow-Display-hotkeys/companion/config_manager.py` -- Current config schema and action types
- `/data/Elcrow-Display-hotkeys/companion/app_scanner.py` -- Existing .desktop file scanner
- `/data/Elcrow-Display-hotkeys/companion/ui/button_editor.py` -- Current editor widget layout

### Secondary (MEDIUM confidence)
- [ydotool GitHub](https://github.com/ReimuNotMoe/ydotool) -- ydotool syntax and capabilities
- [ydotool man page](https://man.archlinux.org/man/ydotool.1.en) -- Key name syntax reference
- [wmctrl man page](https://linux.die.net/man/1/wmctrl) -- Window focus by WM_CLASS
- [focus-or-launch GitHub](https://github.com/Eigenbahn/focus-or-launch) -- Reference implementation of pattern
- [watchdog PyPI](https://pypi.org/project/watchdog/) -- File watcher library
- [Qt Forum: QComboBox wheel event](https://forum.qt.io/topic/25072/how-to-ignore-the-mouse-wheel-event-when-combo-box-is-not-in-focus/2) -- Scroll wheel fix pattern

### Tertiary (LOW confidence)
- ydotool media key names need verification against actual `ydotool key --help` output
- Wayland compositor-specific IPC for window focus needs per-compositor testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries verified in existing codebase or well-known Python/Linux ecosystem
- Architecture: HIGH -- Vendor HID bidirectional communication confirmed via source code inspection
- Protocol design: HIGH -- Simple extension of existing message protocol
- Action execution: MEDIUM -- ydotool key mapping and media key names need runtime verification
- Focus-or-launch: MEDIUM -- X11 path solid, Wayland path compositor-dependent
- Editor UX: HIGH -- Standard PySide6 patterns, QComboBox fix well-documented
- Pitfalls: HIGH -- Based on direct source code analysis of existing codebase

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (stable domain, 30 days)
