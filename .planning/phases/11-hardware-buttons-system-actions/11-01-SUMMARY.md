---
phase: 11-hardware-buttons-system-actions
plan: 01
subsystem: firmware
tags: [arduino, esp32, config, action-types, json, lvgl]

requires:
  - phase: 10-companion-action-execution
    provides: ActionType enum (0-7), button event identity system, config JSON schema
provides:
  - ActionType enum extended with 6 system action types (8-13)
  - HwButtonConfig, EncoderConfig, ModeCycleConfig, DisplaySettings structs
  - JSON serialization/deserialization for hardware config sections
  - System action dispatch in btn_event_cb (page nav, mode cycle, brightness, config mode)
  - mode_cycle_next() function for cycling through enabled display modes
  - ui_goto_page() for jumping to specific page by index
affects: [11-02, 11-03, 11-04]

tech-stack:
  added: []
  patterns: [system-action-local-dispatch, hardware-config-model]

key-files:
  created: []
  modified:
    - display/config.h
    - display/config.cpp
    - display/ui.cpp
    - display/ui.h
    - display/power.h
    - display/power.cpp

key-decisions:
  - "System action types use values 8-13, continuing from existing 0-7 range"
  - "ACTION_CONFIG_MODE duplicates ACTION_DISPLAY_SETTINGS toggle behavior (consistent UX)"
  - "ButtonEventData extended with keycode field for PAGE_GOTO target page"
  - "ui.cpp includes ui.h for get_global_config() access in btn_event_cb"

patterns-established:
  - "Display-local actions return early from btn_event_cb without sending to bridge"
  - "Hardware config sections optional in JSON with sensible defaults (backward compatible)"

requirements-completed: [HW-SYS-ACTIONS, HW-CONFIG-MODEL]

duration: 5min
completed: 2026-02-16
---

# Plan 11-01: Config Model + System Action Types Summary

**Extended ActionType enum with 6 system actions and 4 hardware config structs, with JSON round-trip and local dispatch in btn_event_cb**

## Performance

- **Duration:** 5 min
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- ActionType enum extended with PAGE_NEXT, PAGE_PREV, PAGE_GOTO, MODE_CYCLE, BRIGHTNESS, CONFIG_MODE
- HwButtonConfig, EncoderConfig, ModeCycleConfig, DisplaySettings structs with sensible defaults
- config_load/save handles all new JSON sections with backward compatibility
- btn_event_cb dispatches all system actions locally without sending to bridge
- mode_cycle_next() cycles through user-configured enabled modes list

## Task Commits

1. **Task 1: Extend ActionType enum and add hardware config structs** - `38b9006` (feat)
2. **Task 2: Add JSON serialization and system action dispatch** - `8c98b5f` (feat)

## Files Created/Modified
- `display/config.h` - 6 new ActionType values, 4 new config structs, AppConfig members
- `display/config.cpp` - JSON deser/ser for hardware_buttons, encoder, mode_cycle, display_settings
- `display/ui.cpp` - System action dispatch in btn_event_cb, ui_goto_page() function
- `display/ui.h` - ui_goto_page() declaration
- `display/power.h` - mode_cycle_next() declaration, vector include
- `display/power.cpp` - mode_cycle_next() implementation

## Decisions Made
- System action types 8-13 continue existing enum (no gaps)
- ButtonEventData gained keycode field for PAGE_GOTO target
- ui.cpp now includes ui.h for get_global_config() visibility

## Deviations from Plan

### Auto-fixed Issues

**1. ButtonEventData needed keycode field for PAGE_GOTO**
- **Found during:** Task 2 (system action dispatch)
- **Issue:** Plan referenced bed->keycode but struct had no keycode member
- **Fix:** Added keycode field to ButtonEventData, populated during widget render
- **Verification:** Build succeeds

**2. ui.cpp needed ui.h include for get_global_config()**
- **Found during:** Task 2 (mode cycle dispatch)
- **Issue:** get_global_config() not in scope in btn_event_cb
- **Fix:** Added #include "ui.h" to ui.cpp
- **Verification:** Build succeeds

---

**Total deviations:** 2 auto-fixed (build fixes)
**Impact on plan:** Both necessary for compilation. No scope creep.

## Issues Encountered
None

## Next Phase Readiness
- Config model and action types ready for hw_input driver (11-02)
- Companion config model can mirror these types (11-03)

---
*Phase: 11-hardware-buttons-system-actions*
*Completed: 2026-02-16*
