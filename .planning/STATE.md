# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-15)

**Core value:** Tap a button on the display, the correct keyboard shortcut fires on the PC -- reliably, with minimal latency, whether connected by wire or wirelessly.
**Current focus:** Phase 6 - Data-Driven Display UI (v1.1 System Control)

## Current Position

Phase: 6 of 8 (Data-Driven Display UI)
Plan: 1 of 2 in current phase (06-01 complete)
Status: Executing wave 2
Last activity: 2026-02-15 -- Plan 06-01 complete (config lifetime fix, Hotkey struct eliminated)

Progress: [############........] 62% (v1.0 complete, v1.1 1/4 phases)

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

### Pending Todos

None.

### Blockers/Concerns

- [Research]: LVGL widget-pool pattern needs prototype validation in Phase 6 (memory leak risk on repeated reloads)
- [Research]: WiFi channel pinning needs hardware test in Phase 7 (ESP-NOW packet loss during HTTP transfer)
- [Research]: BMP icon format validation deferred to v2 (LVGL symbols only for v1.1)

## Session Continuity

Last session: 2026-02-15
Stopped at: Phase 5 complete, Phase 6 ready to plan
Resume file: None
