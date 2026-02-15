---
phase: 08-desktop-gui-editor
plan: 01
subsystem: ui
tags: [pyside6, keycode, lvgl, hid, icon-picker, keyboard-recorder]

requires:
  - phase: 07-config-server
    provides: HTTP config upload endpoint for WiFi deploy
provides:
  - Qt-to-Arduino USB HID keycode translation module (keycode_map.py)
  - LVGL symbol registry with 58 symbols (lvgl_symbols.py)
  - Corrected icon picker storing UTF-8 bytes for JSON
  - Corrected keyboard recorder producing Arduino keycodes
affects: [08-02, 08-03]

tech-stack:
  added: []
  patterns: [keycode-translation-table, utf8-symbol-registry]

key-files:
  created:
    - companion/keycode_map.py
    - companion/lvgl_symbols.py
  modified:
    - companion/ui/icon_picker.py
    - companion/ui/keyboard_recorder.py

key-decisions:
  - "keyPressEvent override on custom QLineEdit instead of QKeySequenceEdit -- simpler, avoids system shortcut side effects"
  - "Icon picker stores decoded UTF-8 strings as itemData (not symbol names) -- matches device JSON format directly"
  - "Keyboard recorder uses ShortcutCapture QLineEdit subclass with Clear button -- clean API preserved"

patterns-established:
  - "Keycode translation: always go through keycode_map module, never map Qt keys directly"
  - "LVGL icons: always use UTF-8 bytes from lvgl_symbols module, never hardcode symbol names"

duration: 3min
completed: 2026-02-15
---

# Plan 08-01: Data Translation Layer Summary

**Qt-to-Arduino keycode mapping module (26 special keys + F1-F24 + ASCII) and LVGL symbol registry (58 symbols with UTF-8 bytes) powering corrected icon picker and keyboard recorder widgets**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-15
- **Completed:** 2026-02-15
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created keycode_map.py with complete Qt::Key to Arduino USB HID translation (letters lowercased, special keys mapped to 0xB0+ range, F1-F24 mapped)
- Created lvgl_symbols.py with all 58 LVGL symbols from lv_symbol_def.h with name/codepoint/UTF-8 lookup dicts
- Rewrote icon_picker.py to use lvgl_symbols registry -- get_symbol() returns UTF-8 string for JSON, set_symbol() handles both UTF-8 and legacy name formats
- Rewrote keyboard_recorder.py with ShortcutCapture QLineEdit subclass using keyPressEvent override, proper modifier filtering, and Clear button

## Task Commits

Each task was committed atomically:

1. **Task 1: Create keycode and symbol mapping modules** - `70560e0` (feat)
2. **Task 2: Rewrite icon picker and keyboard recorder** - `f618bda` (feat)

## Files Created/Modified
- `companion/keycode_map.py` - Qt-to-Arduino keycode translation with forward and reverse lookup
- `companion/lvgl_symbols.py` - LVGL symbol registry (58 entries) with name/codepoint/UTF-8 dicts
- `companion/ui/icon_picker.py` - Rewritten to use lvgl_symbols, stores UTF-8 for JSON
- `companion/ui/keyboard_recorder.py` - Rewritten with ShortcutCapture widget and keycode_map integration

## Decisions Made
- Used keyPressEvent override on custom QLineEdit instead of QKeySequenceEdit -- simpler approach that avoids system shortcut capture side effects
- Icon picker stores decoded UTF-8 strings (not symbol name strings) as combo item data -- matches device JSON format directly without conversion
- Preserved existing KeyboardRecorder public API (shortcut_confirmed signal, current_modifiers/current_keycode, set_shortcut/get_shortcut) for backward compatibility with button_editor.py

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- keycode_map and lvgl_symbols modules ready for import by button_editor.py and editor_main.py
- Icon picker and keyboard recorder maintain same signal API -- button_editor.py integration unchanged
- Plan 08-02 can wire up media key dropdown, page rename, and grid polish

---
*Phase: 08-desktop-gui-editor*
*Completed: 2026-02-15*
