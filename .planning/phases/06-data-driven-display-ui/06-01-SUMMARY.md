---
phase: 06-data-driven-display-ui
plan: 01
subsystem: ui
tags: [lvgl, esp32, config, memory-safety]

requires:
  - phase: 05-config-data-model-sd-loading
    provides: AppConfig struct, config_load(), config_create_defaults()
provides:
  - Static global AppConfig with program lifetime
  - Single config-driven UI render path (no hardcoded fallback)
  - Safe ButtonConfig* as LVGL event user_data
affects: [06-02, 07-config-server]

tech-stack:
  added: []
  patterns: [ButtonConfig* as event user_data into long-lived global config]

key-files:
  created: []
  modified:
    - display/main.cpp
    - display/ui.cpp
    - display/ui.h

key-decisions:
  - "Removed Hotkey struct entirely rather than wrapping ButtonConfig -- eliminates translation layer"
  - "create_ui() requires non-null config pointer (no default parameter) -- forces explicit config at callsite"

patterns-established:
  - "ButtonConfig* user_data: all LVGL button events receive const ButtonConfig* pointing into static g_app_config"
  - "Single render path: config_create_defaults() is sole source of default layouts, no hardcoded arrays in ui.cpp"

duration: 5min
completed: 2026-02-15
---

# Plan 06-01: Fix Config Lifetime and Eliminate Hotkey Struct

**Static global AppConfig with ButtonConfig* event pointers, removing 3 use-after-free bugs and all hardcoded page arrays**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-15
- **Completed:** 2026-02-15
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- Fixed 3 dangling-pointer bugs (stack-local Hotkey as event user_data, local AppConfig in setup(), local AppConfig in config_server rebuild)
- Eliminated Hotkey struct, HotkeyPage struct, button_config_to_hotkey() helper, and all hardcoded page arrays (page1_hotkeys, page2_hotkeys, page3_hotkeys)
- Single config-driven render path -- create_ui() and rebuild_ui() both pass &page.buttons[j] as event user_data
- Removed KEY_* defines (keycodes now come from config)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix config lifetime and eliminate Hotkey struct** - `4238cdc` (feat)

## Files Created/Modified
- `display/main.cpp` - Static g_app_config with program lifetime, passed to create_ui
- `display/ui.cpp` - Removed Hotkey/HotkeyPage structs, hardcoded arrays, dual render path; btn_event_cb and create_hotkey_button use ButtonConfig*
- `display/ui.h` - Removed default nullptr parameter from create_ui()

## Decisions Made
- Removed Hotkey struct entirely rather than making it a thin wrapper -- eliminates unnecessary translation layer
- create_ui() requires non-null config pointer (removed default parameter) to make the single-path contract explicit
- Kept CLR_* color defines as they're still used by stats header, device status, clock screen, OTA screen

## Deviations from Plan
None - plan executed as specified.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- rebuild_ui() still uses partial tabview replacement (delete + recreate). Plan 06-02 will implement full lv_obj_clean() rebuild with memory monitoring.
- config_server.cpp still calls rebuild_ui(&new_config) with a local config -- 06-02 will fix this with deferred rebuild flag pattern.

---
*Phase: 06-data-driven-display-ui*
*Completed: 2026-02-15*
