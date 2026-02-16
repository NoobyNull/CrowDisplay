# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-15)

**Core value:** Tap a button on the display, the correct keyboard shortcut fires on the PC -- reliably, with minimal latency, whether connected by wire or wirelessly.
**Current focus:** Phase 9 - Tweaks and Break-Fix (v0.9.1)

## Current Position

Phase: 9 of 9 (Tweaks and Break-Fix v0.9.1)
Plan: 1 of 5 in current phase
Status: Executing
Last activity: 2026-02-15 -- Completed 09-01 Grid Layout + Positioning + Pressed Color

Progress: [##################..] 91% (v1.0 complete, v1.1 beta, v0.9.1 1/5)

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 7 (across v1.0)
- Average duration: 2min
- Total execution time: 0.25 hours

**By Phase (v1.0 + v1.1):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 11min | 4min |
| 03 | 4 | 9min | 2min |
| 04 | 3 | 5min | 2min |
| 05 | 1 | 5min | 5min |
| 06 | 2 | 6min | 3min |
| 07 | 2 | 11min | 5.5min |
| 08 | 3 | 7min | 2.3min |
| 09 | 1 | 6min | 6min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.1 Roadmap]: SD card is config storage medium (not NVS/LittleFS) -- human-readable, removable, large capacity
- [v1.1 Roadmap]: SoftAP + HTTP for config upload (not ESP-NOW relay) -- direct WiFi avoids bridge bottleneck
- [v1.1 Roadmap]: PySide6 desktop editor (not web UI on ESP32) -- richer UX, no flash/RAM cost on device
- [v1.1 Roadmap]: ArduinoJson v7 with PSRAM allocator for config parsing -- avoids internal SRAM exhaustion
- [v1.1 Roadmap]: Widget-pool pattern for dynamic UI -- prevents LVGL memory leak on config reload
- [Phase 5]: ps_malloc() for all buffers >4KB, free() on all return paths
- [Phase 5]: FAT rename requires explicit remove of target first
- [Phase 5]: Config version mismatch logs warning but still loads (forward compatibility)
- [Phase 5]: Raw string literals need custom delimiters when HTML contains )"
- [Phase 7]: Single unified config_server module -- eliminates dual-SoftAP conflict
- [Phase 7]: WiFi channel 1 pinning -- ensures ESP-NOW reliability during HTTP transfer
- [Phase 7]: 5-minute inactivity timeout -- auto-stops SoftAP to conserve power
- [Phase 7]: HTTP 400 for upload errors -- proper error propagation instead of always 200
- [Phase 7]: LV_SYMBOL_SETTINGS gear icon in CLR_TEAL -- visually distinct config mode trigger
- [Phase 8]: keyPressEvent override on custom QLineEdit (not QKeySequenceEdit) -- simpler, avoids system shortcut side effects
- [Phase 8]: Icon picker stores UTF-8 decoded strings (not symbol names) -- matches device JSON format directly
- [Phase 8]: 9 consumer control codes in media key dropdown (Play/Pause, Next, Prev, Stop, Vol+, Vol-, Mute, Browser Home/Back)
- [Phase 8]: Gold border (#FFD700) for selected button, luminance threshold 140 for text contrast
- [Phase 9]: LVGL grid layout (4x3 FR units) replaces flex row-wrap -- enables explicit positioning and variable sizing
- [Phase 9]: grid_row/grid_col = -1 means auto-flow, >= 0 means explicit cell placement
- [Phase 9]: pressed_color = 0x000000 means auto-darken, non-zero = explicit RGB
- [Phase 9]: CONFIG_MAX_BUTTONS reduced from 16 to 12 (4x3 grid capacity)

### Pending Todos

1. **Make buttons positionable with variable count per page** (ui) -- variable button count, grid positioning, button reorder within pages
2. **Add button depressed color to config schema** (ui) -- separate pressed/depressed color per button, with auto-darken default
3. **Add button sizing options and variable dimensions** (ui) -- 1x1, 2x1, 1x2, 2x2 grid spans per button (ADV-01)
4. **Forward host OS notifications to display as toast overlays** (general) -- D-Bus notification listener with app filter, MSG_NOTIFICATION protocol, toast popup on display
5. **Configurable stats header with selectable and placeable monitors** (ui) -- user picks which stats to show, arranges order/position, expanded monitor types (20+ via psutil/pynvml)
6. **Add display modes: standby, macro pad, picture frame, clock** (ui) -- 4 user-selectable modes with analog/digital clock, SD card slideshow, standby screen-off

### Blockers/Concerns

- [Research]: WiFi channel pinning needs hardware test (ESP-NOW packet loss during HTTP transfer) -- implemented but untested on hardware
- [Research]: BMP icon format validation deferred to v2 (LVGL symbols only for v1.1)

## Session Continuity

Last session: 2026-02-15
Stopped at: Completed 09-01-PLAN.md (Grid Layout + Positioning + Pressed Color)
Resume file: None
