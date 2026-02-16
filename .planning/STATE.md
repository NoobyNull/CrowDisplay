# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-15)

**Core value:** Tap a button on the display, the correct keyboard shortcut fires on the PC -- reliably, with minimal latency, whether connected by wire or wirelessly.
**Current focus:** Phase 9 - Tweaks and Break-Fix (v0.9.1)

## Current Position

Phase: 9 of 9 (Tweaks and Break-Fix v0.9.1)
Plan: 5 of 5 in current phase (COMPLETE)
Status: Phase Complete
Last activity: 2026-02-16 -- Completed 09-02 Variable Button Sizing (Grid Spans)

Progress: [####################] 100% (v1.0 complete, v1.1 beta, v0.9.1 5/5 plans have summaries)

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
| 09 | 5 | ~60min | ~12min |

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
- [Phase 9]: DisplayMode orthogonal to PowerState -- mode controls UI, power controls brightness
- [Phase 9]: LVGL custom filesystem driver (S: letter) for SD card image access in picture frame mode
- [Phase 9]: LVGL grid layout (4x3 FR units) replaces flex row-wrap -- enables explicit positioning and variable sizing
- [Phase 9]: grid_row/grid_col = -1 means auto-flow, >= 0 means explicit cell placement
- [Phase 9]: pressed_color = 0x000000 means auto-darken, non-zero = explicit RGB
- [Phase 9]: CONFIG_MAX_BUTTONS reduced from 16 to 12 (4x3 grid capacity)
- [Phase 9]: TLV stats protocol with first-byte heuristic for backward compat (count <= 0x14 = TLV, > 0x14 = legacy)
- [Phase 9]: Max 8 configurable stats in header, position-based ordering
- [Phase 9]: pynvml for extended GPU metrics (memory, power, frequency)
- [Phase 9]: col_span/row_span only for explicit positioning, auto-flow forced to 1x1
- [Phase 9]: Grid overlap detection via occupancy matrix in config validation
- [Phase 9]: NotificationMsg 248 bytes (32+100+116) fits ESP-NOW 250-byte limit
- [Phase 9]: Notifications disabled by default, opt-in via notifications_enabled config flag
- [Phase 9]: Empty notification_filter = forward ALL notifications
- [Phase 9]: Toast overlay replaces previous (no stacking) to prevent LVGL memory leaks
- [Phase 9]: D-Bus session bus eavesdrop via AddMatch for Notify method calls

### Pending Todos

1. **Execute image support plan from Claude plans** (ui) -- add custom image icons to hotkey buttons via BMP on SD card, Pillow optimizer, HTTP upload endpoint
2. **Companion executes button actions instead of blind keyboard shortcuts** (companion) -- bridge forwards MSG_HOTKEY to vendor HID, companion intercepts and launches apps/commands directly

### Roadmap Evolution

- Phase 10 added: Companion Action Execution

### Blockers/Concerns

- [Research]: WiFi channel pinning needs hardware test (ESP-NOW packet loss during HTTP transfer) -- implemented but untested on hardware
- [Research]: BMP icon format validation deferred to v2 (LVGL symbols only for v1.1)

## Session Continuity

Last session: 2026-02-16
Stopped at: Completed 09-02-PLAN.md (Variable Button Sizing with Grid Spans)
Resume file: None
