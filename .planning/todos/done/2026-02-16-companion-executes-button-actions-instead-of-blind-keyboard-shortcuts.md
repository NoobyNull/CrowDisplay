---
created: 2026-02-16T06:05:25.677Z
title: Companion executes button actions instead of blind keyboard shortcuts
area: companion
files:
  - bridge/main.cpp
  - bridge/usb_hid.cpp
  - companion/hotkey_companion.py
  - shared/protocol.h
  - companion/ui/editor_main.py
---

## Problem

Currently, tapping a button on the display sends a MSG_HOTKEY (modifiers + keycode) via ESP-NOW to the bridge, which fires it as a USB HID keyboard keystroke on the PC. The user must then separately configure their desktop environment (KDE/GNOME custom shortcuts) to bind that key combo to launching an app or running a command. This is fragile, unintuitive, and defeats the purpose of having a companion service running on the PC.

The companion service (`hotkey_companion.py`) already runs on the PC, already communicates with the bridge over USB HID vendor interface (report ID 6), and already knows the full button configuration. It should be the one interpreting button presses and executing the configured action directly.

## Solution

### Architecture Change

1. **Bridge forwards MSG_HOTKEY to companion via vendor HID**: When the bridge receives MSG_HOTKEY from the display via ESP-NOW, it should also (or instead of) firing a keyboard keystroke, send the hotkey command out the vendor HID interface to the companion app.

2. **Companion listens for incoming vendor HID reports**: The companion service reads from the vendor HID device and dispatches button actions based on the config.

3. **Action types in config**: Extend the button config to support:
   - `launch_app`: Execute a command / launch a .desktop file (e.g. `firefox`, `gimp`)
   - `open_url`: Open a URL in the default browser
   - `run_command`: Run an arbitrary shell command
   - `keyboard_shortcut`: Legacy behavior — fire a keyboard shortcut (for backward compat)

4. **Editor UI**: The properties panel in the editor should let the user configure what action a button performs — app picker already resolves .desktop files, just need to store the Exec command.

### Key Files

- `bridge/main.cpp`: Forward MSG_HOTKEY payload to vendor HID output (in addition to or instead of firing keystroke)
- `bridge/usb_hid.cpp`: Add function to write vendor HID output reports
- `companion/hotkey_companion.py`: Add HID read loop to receive commands and dispatch actions
- `shared/protocol.h`: May need new message types or action type enum
- `companion/ui/editor_main.py`: Update properties panel to configure launch commands per button
