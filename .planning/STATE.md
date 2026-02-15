# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** Tap a button on the display, the correct keyboard shortcut fires on the PC -- reliably, with minimal latency, whether connected by wire or wirelessly.
**Current focus:** Phase 3 - Stats Display + Companion App

## Current Position

Phase: 3 of 5 (Stats Display + Companion App)
Plan: 3 of 4 in current phase
Status: Executing
Last activity: 2026-02-15 -- Completed 03-03 (Python companion app)

Progress: [██████░░░░] 55%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 3min
- Total execution time: 0.24 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 11min | 4min |
| 03 | 2 | 4min | 2min |

**Recent Trend:**
- Last 5 plans: 01-01 (5min), 01-02 (3min), 01-03 (3min), 03-01 (2min), 03-03 (2min)
- Trend: Accelerating

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Build wired UART transport first, add ESP-NOW in Phase 2 (removes wireless uncertainty from early debugging) -- SUPERSEDED: went straight to ESP-NOW since bridge USB-C is dedicated to HID
- [01-04]: ESP-NOW broadcast replaces UART link (bridge USB-C occupied by HID, no wired path available)
- [01-04]: Forced USB D+/D- low before USB.begin() to fix JTAG-to-OTG PHY re-enumeration
- [01-04]: board_build.arduino.extra.cdc_on_boot has no effect in espressif32@6.5.0 (removed)
- [Roadmap]: Bridge is HID-only to PC (avoids documented USB HID+CDC composite stall bug)
- [Roadmap]: I2C mutex from day one in Phase 1 (prevents GT911 touch corruption)
- [01-01]: Used build_src_filter instead of src_dir for multi-env PlatformIO builds
- [01-01]: Display lib_deps (LovyanGFX, LVGL) moved to env:display only, not shared base
- [01-01]: Init order: Wire -> touch_init(mutex) -> display_init(PCA9557+LCD) -> gt911_discover -> lvgl_init
- [01-02]: Keyboard only, no consumer control (media keys deferred to Phase 3 per BRDG-04)
- [01-02]: delay(20) keystroke hold, delay(1) main loop -- bridge is maximally responsive
- [01-02]: 64-byte poll limit per uart_poll() cycle to prevent main loop blocking
- [01-03]: Page 3 media keys replaced with keyboard-only dev shortcuts (consumer control deferred to Phase 3)
- [01-03]: UART1 on GPIO 10/11 for display-to-bridge link at 115200 baud
- [01-03]: Key codes defined locally in ui.cpp (display does not include USBHIDKeyboard.h)
- [03-01]: USBHIDVendor 63-byte reports with no size prepend (matches companion app expectations)
- [03-01]: Stats relay is fire-and-forget -- no ACK from display for MSG_STATS
- [03-03]: Python with hidapi for companion app (per user discretion and research)
- [03-03]: GPU detection chain: NVIDIA (pynvml) -> AMD (sysfs) -> 0xFF fallback
- [03-03]: Leading 0x00 report ID byte for hidapi Linux HID writes

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: USB CDC on bridge -- bridge is HID-only on native USB. Companion app will need to communicate via ESP-NOW relay or separate serial adapter.
- [Research]: CrowPanel battery charging circuit unknown -- characterize during Phase 4 planning.
- [Research]: LVGL memory pool may need increase to 128KB+ or PSRAM-backed allocator -- test during Phase 2/3 UI expansion.

## Session Continuity

Last session: 2026-02-15
Stopped at: Completed 03-03-PLAN.md (Python companion app). Ready for 03-04.
Resume file: None
