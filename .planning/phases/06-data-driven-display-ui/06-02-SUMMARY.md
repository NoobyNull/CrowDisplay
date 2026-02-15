---
phase: 06-data-driven-display-ui
plan: 02
subsystem: ui
tags: [lvgl, esp32, hot-reload, memory-monitoring]

requires:
  - phase: 06-data-driven-display-ui
    provides: Static global AppConfig, single config-driven render path, ButtonConfig* event pointers
provides:
  - Full-screen lv_obj_clean rebuild without reboot
  - Deferred rebuild flag pattern (safe from any context)
  - LVGL memory monitoring (lv_mem_monitor before/after each rebuild)
  - create_ui_widgets() shared helper for initial and rebuild paths
affects: [07-config-server]

tech-stack:
  added: []
  patterns: [deferred rebuild flag, lv_obj_clean full teardown, lv_mem_monitor delta logging]

key-files:
  created: []
  modified:
    - display/ui.cpp
    - display/ui.h
    - display/main.cpp
    - display/config_server.cpp

key-decisions:
  - "Full lv_obj_clean instead of partial tabview delete -- ensures no orphaned widgets on rebuild"
  - "Deferred rebuild via volatile flag instead of direct call -- avoids animation conflicts"
  - "create_stats_header() takes parent parameter instead of lv_scr_act() -- enables rebuild"

patterns-established:
  - "Deferred rebuild: config_server sets flag, loop() executes rebuild_ui safely"
  - "lv_mem_monitor logging: every rebuild prints before/after memory delta to serial"
  - "create_ui_widgets(screen, cfg): shared helper for both initial creation and rebuild"

duration: 5min
completed: 2026-02-15
---

# Plan 06-02: Full-Screen Rebuild with Memory Monitoring

**lv_obj_clean() full teardown, deferred rebuild flag, and LVGL memory delta logging for leak-free hot-reload**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-15
- **Completed:** 2026-02-15
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- rebuild_ui() uses lv_obj_clean(main_screen) to destroy all children, null widget pointers, then recreate from config
- lv_mem_monitor() logs memory usage before and after every rebuild (proves DRVUI-05 no-leak requirement)
- Deferred rebuild flag: config_server sets get_global_config() then request_ui_rebuild(), loop() calls rebuild_ui safely
- Extracted create_ui_widgets() helper shared by create_ui() and rebuild_ui() -- eliminates code duplication

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Full-screen rebuild + deferred flag** - `588f50c` (feat)

## Files Created/Modified
- `display/ui.cpp` - Extracted create_ui_widgets() helper, rewrote rebuild_ui() with lv_obj_clean + mem monitoring, updated create_stats_header to take parent param
- `display/ui.h` - Added request_ui_rebuild() and get_global_config() declarations
- `display/main.cpp` - Added g_rebuild_pending flag, get_global_config(), request_ui_rebuild(), rebuild check in loop()
- `display/config_server.cpp` - Replaced direct rebuild_ui call with deferred flag pattern, validates config before updating global

## Decisions Made
- Combined Tasks 1 and 2 into a single commit since they are tightly coupled (helper extraction + rebuild rewrite + deferred flag all part of same mechanism)
- create_stats_header() takes explicit parent parameter rather than using lv_scr_act() for rebuild safety

## Deviations from Plan
None - plan executed as specified.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 complete: display renders entirely from config, supports hot-reload without reboot, memory stability proven
- Phase 7 (Config Server SoftAP + HTTP) can build on the deferred rebuild pattern

---
*Phase: 06-data-driven-display-ui*
*Completed: 2026-02-15*
