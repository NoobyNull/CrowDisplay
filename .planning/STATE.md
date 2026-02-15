# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-15)

**Core value:** Tap a button on the display, the correct keyboard shortcut fires on the PC -- reliably, with minimal latency, whether connected by wire or wirelessly.
**Current focus:** Phase 7 - Config Server (SoftAP + HTTP) (v1.1 System Control)

## Current Position

Phase: 7 of 8 (Config Server SoftAP + HTTP)
Plan: 2 of 2 in current phase (all plans complete)
Status: Phase execution complete, pending verification
Last activity: 2026-02-15 -- Plan 07-02 complete (config mode UI screen with header icon)

Progress: [###############.....] 75% (v1.0 complete, v1.1 3/4 phases)

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

### Pending Todos

None.

### Blockers/Concerns

- [Research]: WiFi channel pinning needs hardware test (ESP-NOW packet loss during HTTP transfer) -- implemented but untested on hardware
- [Research]: BMP icon format validation deferred to v2 (LVGL symbols only for v1.1)

## Session Continuity

Last session: 2026-02-15
Stopped at: Phase 7 execution complete, pending verification
Resume file: None
