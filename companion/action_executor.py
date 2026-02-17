"""
Action Executor: Dispatches button press actions from the companion.

Handles 5 action types:
- ACTION_HOTKEY: Simulate keyboard shortcut via ydotool/xdotool
- ACTION_MEDIA_KEY: Simulate media key via ydotool
- ACTION_LAUNCH_APP: Launch or focus an application
- ACTION_SHELL_CMD: Run a shell command (sudo blocked)
- ACTION_OPEN_URL: Open URL in default browser
"""

import logging
import re
import shutil
import subprocess
import webbrowser
from subprocess import DEVNULL

from companion.config_manager import (
    ACTION_HOTKEY,
    ACTION_MEDIA_KEY,
    ACTION_LAUNCH_APP,
    ACTION_SHELL_CMD,
    ACTION_OPEN_URL,
    ACTION_DISPLAY_SETTINGS,
    ACTION_DISPLAY_CLOCK,
    ACTION_DISPLAY_PICTURE,
    DISPLAY_LOCAL_ACTIONS,
    MOD_CTRL,
    MOD_SHIFT,
    MOD_ALT,
    MOD_GUI,
)

# ---------------------------------------------------------------------------
# Keycode to key name mapping
# ---------------------------------------------------------------------------
#
# The config stores Arduino keyboard codes:
# - ASCII printable chars: 0x20-0x7E (space, letters, digits, symbols)
# - Arduino special keys: 0x80+ (Enter=0xB0, arrows=0xD7-0xDA, etc.)
#
# We also keep HID scan code mappings for backward compatibility.

_KEY_NAMES = {}

# --- Arduino ASCII keycodes (primary: what config.json actually stores) ---
# Printable ASCII: map to their character name for ydotool/xdotool
for _i in range(ord('a'), ord('z') + 1):
    _KEY_NAMES[_i] = chr(_i)
for _i in range(ord('A'), ord('Z') + 1):
    _KEY_NAMES[_i] = chr(_i).lower()  # ydotool uses lowercase
for _i in range(ord('0'), ord('9') + 1):
    _KEY_NAMES[_i] = chr(_i)
_KEY_NAMES[ord(' ')] = 'space'

# Arduino special key constants (from Arduino USBHIDKeyboard)
_KEY_NAMES.update({
    0xB0: 'enter',       # KEY_RETURN
    0xB1: 'esc',         # KEY_ESC
    0xB2: 'backspace',   # KEY_BACKSPACE
    0xB3: 'tab',         # KEY_TAB
    0xD7: 'right',       # KEY_RIGHT_ARROW
    0xD8: 'left',        # KEY_LEFT_ARROW
    0xD9: 'down',        # KEY_DOWN_ARROW
    0xDA: 'up',          # KEY_UP_ARROW
    0xD1: 'home',        # KEY_HOME
    0xD2: 'insert',      # KEY_INSERT
    0xD4: 'end',         # KEY_END
    0xD5: 'pageup',      # KEY_PAGE_UP
    0xD6: 'pagedown',    # KEY_PAGE_DOWN
    0xD3: 'delete',      # KEY_DELETE
    0xCE: 'print',       # KEY_PRINT_SCREEN (sysrq for ydotool)
    0xCF: 'scrolllock',  # KEY_SCROLL_LOCK
    0xD0: 'pause',       # KEY_PAUSE
    0xC1: 'capslock',    # KEY_CAPS_LOCK
})

# Arduino function keys: 0xC2 (F1) through 0xCD (F12)
for _i in range(0xC2, 0xCE):
    _KEY_NAMES[_i] = f'f{_i - 0xC2 + 1}'

# --- HID scan codes (fallback for any code not matched above) ---
# Letters: 0x04 ('a') through 0x1D ('z')
for _i in range(0x04, 0x1E):
    _KEY_NAMES.setdefault(_i, chr(ord('a') + (_i - 0x04)))

# Digits: 0x1E ('1') through 0x26 ('9'), 0x27 ('0')
for _i in range(0x1E, 0x27):
    _KEY_NAMES.setdefault(_i, str(_i - 0x1E + 1))
_KEY_NAMES.setdefault(0x27, '0')

# HID special keys (fallback)
for _code, _name in {
    0x28: 'enter', 0x29: 'esc', 0x2A: 'backspace', 0x2B: 'tab',
    0x2C: 'space', 0x39: 'capslock', 0x4F: 'right', 0x50: 'left',
    0x51: 'down', 0x52: 'up', 0x4A: 'home', 0x4D: 'end',
    0x4B: 'pageup', 0x4E: 'pagedown', 0x4C: 'delete', 0x49: 'insert',
}.items():
    _KEY_NAMES.setdefault(_code, _name)

# HID function keys: 0x3A ('f1') through 0x45 ('f12')
for _i in range(0x3A, 0x46):
    _KEY_NAMES.setdefault(_i, f'f{_i - 0x3A + 1}')

# ---------------------------------------------------------------------------
# Consumer code to key name mapping
# ---------------------------------------------------------------------------

_CONSUMER_KEY_NAMES = {
    0xCD: "playpause",
    0xB5: "nextsong",
    0xB6: "previoussong",
    0xB7: "stopcd",
    0xE9: "volumeup",
    0xEA: "volumedown",
    0xE2: "mute",
}

# ---------------------------------------------------------------------------
# Modifier mapping
# ---------------------------------------------------------------------------

_MOD_NAMES = {
    MOD_CTRL: "ctrl",
    MOD_SHIFT: "shift",
    MOD_ALT: "alt",
    MOD_GUI: "super",
}


# ---------------------------------------------------------------------------
# Action dispatch
# ---------------------------------------------------------------------------

def execute_action(config_manager, page_idx: int, widget_idx: int):
    """Look up widget by page+widget index and execute its configured action."""
    widget = config_manager.get_widget(page_idx, widget_idx)
    if widget is None:
        logging.warning("No widget at page=%d widget=%d", page_idx, widget_idx)
        return

    action_type = widget.get("action_type", ACTION_HOTKEY)

    # Skip display-local actions (handled on device, not on PC)
    if action_type in DISPLAY_LOCAL_ACTIONS:
        logging.debug("Skipping display-local action type %d", action_type)
        return

    if action_type == ACTION_LAUNCH_APP:
        _exec_launch_app(widget)
    elif action_type == ACTION_SHELL_CMD:
        _exec_shell_cmd(widget)
    elif action_type == ACTION_OPEN_URL:
        _exec_open_url(widget)
    elif action_type == ACTION_HOTKEY:
        _exec_keyboard_shortcut(widget)
    elif action_type == ACTION_MEDIA_KEY:
        _exec_media_key(widget)
    elif action_type in (ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE):
        logging.debug("Display-local action_type %d handled on device, ignoring on PC", action_type)
    else:
        logging.warning("Unknown action_type %d for page=%d widget=%d",
                        action_type, page_idx, widget_idx)


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def _exec_launch_app(widget):
    """Launch or focus an application."""
    launch_command = widget.get("launch_command", "")
    if not launch_command:
        logging.warning("Launch app: empty launch_command")
        return

    wm_class = widget.get("launch_wm_class", "")
    focus_or_launch = widget.get("launch_focus_or_launch", True)

    # Try to focus existing window first
    if focus_or_launch and wm_class:
        if _try_focus_window(wm_class):
            logging.info("Focused existing window: %s", wm_class)
            return

    # Strip .desktop Exec format codes (%u, %U, %f, %F, etc.)
    clean_cmd = re.sub(r'%[uUfFdDnNickvm]', '', launch_command).strip()

    try:
        subprocess.Popen(clean_cmd, shell=True, stdout=DEVNULL, stderr=DEVNULL)
        logging.info("Launched app: %s", clean_cmd)
    except Exception as exc:
        logging.error("Failed to launch app: %s", exc)


def _exec_shell_cmd(widget):
    """Run a shell command (blocks sudo)."""
    cmd = widget.get("shell_command", "")
    if not cmd:
        return

    # Block sudo commands
    if "sudo" in cmd.split():
        logging.warning("Shell command blocked (contains sudo): %s", cmd)
        return

    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info("Shell command: %s", cmd)
    except Exception as exc:
        logging.error("Failed to run shell command: %s", exc)


def _exec_open_url(widget):
    """Open a URL in the default browser."""
    url = widget.get("url", "")
    if not url:
        return

    try:
        webbrowser.open(url)
        logging.info("Opened URL: %s", url)
    except Exception as exc:
        logging.error("Failed to open URL: %s", exc)


def _exec_keyboard_shortcut(widget):
    """Simulate a keyboard shortcut via ydotool (with xdotool fallback)."""
    modifiers = widget.get("modifiers", 0)
    keycode = widget.get("keycode", 0)

    if keycode == 0:
        logging.warning("Keyboard shortcut: no keycode set")
        return

    # Build key name from keycode (supports Arduino ASCII + HID scan codes)
    key_name = _KEY_NAMES.get(keycode)
    if key_name is None:
        logging.warning("Unknown keycode: 0x%02X", keycode)
        return

    # Build modifier+key combo string
    parts = []
    for mod_bit, mod_name in _MOD_NAMES.items():
        if modifiers & mod_bit:
            parts.append(mod_name)
    parts.append(key_name)
    key_combo = "+".join(parts)

    # Try ydotool first
    if shutil.which("ydotool"):
        try:
            subprocess.Popen(["ydotool", "key", key_combo],
                             stdout=DEVNULL, stderr=DEVNULL)
            logging.info("Keyboard shortcut (ydotool): %s", key_combo)
            return
        except Exception as exc:
            logging.debug("ydotool failed: %s", exc)

    # Fallback to xdotool
    if shutil.which("xdotool"):
        try:
            subprocess.Popen(["xdotool", "key", key_combo],
                             stdout=DEVNULL, stderr=DEVNULL)
            logging.info("Keyboard shortcut (xdotool): %s", key_combo)
            return
        except Exception as exc:
            logging.debug("xdotool failed: %s", exc)

    logging.error("Neither ydotool nor xdotool available for keyboard shortcuts")


def _exec_media_key(widget):
    """Simulate a media key via ydotool."""
    consumer_code = widget.get("consumer_code", 0)
    if consumer_code == 0:
        logging.warning("Media key: no consumer_code set")
        return

    key_name = _CONSUMER_KEY_NAMES.get(consumer_code)
    if key_name is None:
        logging.warning("Unknown consumer code: 0x%04X", consumer_code)
        return

    if shutil.which("ydotool"):
        try:
            subprocess.Popen(["ydotool", "key", key_name],
                             stdout=DEVNULL, stderr=DEVNULL)
            logging.info("Media key (ydotool): %s", key_name)
            return
        except Exception as exc:
            logging.debug("ydotool media key failed: %s", exc)

    logging.warning("ydotool not available for media keys")


def _try_focus_window(wm_class: str) -> bool:
    """Try to focus an existing window by WM_CLASS using wmctrl.

    Returns True if a window was focused, False otherwise.
    """
    if not shutil.which("wmctrl"):
        return False

    try:
        result = subprocess.run(
            ["wmctrl", "-x", "-a", wm_class],
            capture_output=True, timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False
