---
phase: 11-hardware-buttons-system-actions
plan: 03
subsystem: companion
tags: [python, pyside6, config-manager, editor-ui, hardware-buttons, encoder]

requires:
  - phase: 11-hardware-buttons-system-actions
    provides: ActionType enum (8-13), HwButtonConfig, EncoderConfig, config JSON serialization
provides:
  - 14 action type constants in companion config_manager (matching firmware)
  - DISPLAY_LOCAL_ACTIONS set for filtering system actions in action_executor
  - ACTION_TYPE_NAMES and ENCODER_MODE_NAMES dicts for UI dropdowns
  - Hardware config default helpers (buttons, encoder, mode_cycle, display_settings)
  - HardwareSection widget below canvas with B1-B4 buttons and ENC encoder
  - PropertiesPanel hardware input mode with action type dropdown and encoder mode
affects: [11-04]

tech-stack:
  added: []
  patterns: [hardware-input-properties-panel, dual-selection-mode]

key-files:
  created: []
  modified:
    - companion/config_manager.py
    - companion/action_executor.py
    - companion/ui/editor_main.py

key-decisions:
  - "PropertiesPanel dual mode: canvas widget mode vs hardware input mode, toggled by selection"
  - "Hardware section uses dark gray strip (#2a2a2a) below canvas to visually distinguish from display area"
  - "Encoder styled as circular button (border-radius: 30px) to suggest rotary form factor"
  - "ACTION_TYPE_NAMES used for both canvas widget and hardware input action dropdowns"
  - "Page goto uses keycode field to store target page index (0-based in config, 1-based in UI)"

patterns-established:
  - "Separate hw_action_type_combo for hardware inputs to avoid interfering with canvas widget combo"
  - "Hardware label updates propagated via hw_config_updated signal"

requirements-completed: [HW-COMPANION-CONFIG, HW-EDITOR-HARDWARE]

duration: 6min
completed: 2026-02-16
---

# Plan 11-03: Companion Config Model + Hardware Editor Summary

**System action types, hardware config model, and hardware input editor section in companion app**

## Performance

- **Duration:** 6 min
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- 6 new action type constants (ACTION_PAGE_NEXT through ACTION_CONFIG_MODE) added to config_manager.py
- DISPLAY_LOCAL_ACTIONS set prevents companion from executing display-local system actions
- ACTION_TYPE_NAMES (14 entries) and ENCODER_MODE_NAMES (5 entries) for UI dropdowns
- Hardware config default helpers for buttons, encoder, mode cycle, and display settings
- ConfigManager.new_config() and load_json_file() populate hardware sections with defaults
- HardwareSection widget with 4 dark gray buttons (B1-B4) and circular encoder (ENC) below canvas
- PropertiesPanel dual mode: switches between canvas widget properties and hardware input properties
- Encoder properties show push action + rotation mode with informational CW/CCW text
- All 14 action types available in both canvas widget and hardware input dropdowns

## Task Commits

1. **Task 1: System action types + hardware config model** - `002672c` (feat)
2. **Task 2: Hardware editor section below canvas** - `c6ecd3d` (feat)

## Files Modified
- `companion/config_manager.py` - 6 new action constants, DISPLAY_LOCAL_ACTIONS, ACTION_TYPE_NAMES, ENCODER_MODE_NAMES, hardware default helpers, ConfigManager updates
- `companion/action_executor.py` - DISPLAY_LOCAL_ACTIONS import and early return for display-local actions
- `companion/ui/editor_main.py` - HardwareSection class, PropertiesPanel hardware mode, encoder rotation group, page goto spinner

## Decisions Made
- Separate hw_action_type_combo for hardware inputs to keep canvas widget combo independent
- Gold highlight (#FFD700) on selected hardware input matches existing selection style
- Page goto stored as 0-based keycode in config, displayed as 1-based page number in UI

## Deviations from Plan
None - plan executed as written

## Issues Encountered
- Qt `isVisible()` returns false in offscreen mode when parent isn't shown; confirmed working with `win.show()`

## Next Phase Readiness
- Hardware config model ready for Settings tab (11-04)
- All 14 action types available in editor for both widgets and hardware inputs

---
*Phase: 11-hardware-buttons-system-actions*
*Completed: 2026-02-16*
