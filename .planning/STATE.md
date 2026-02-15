# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** Tap a button on the display, the correct keyboard shortcut fires on the PC -- reliably, with minimal latency, whether connected by wire or wirelessly.
**Current focus:** Phase 1 - Wired Command Foundation

## Current Position

Phase: 1 of 5 (Wired Command Foundation)
Plan: 3 of 4 in current phase
Status: Executing
Last activity: 2026-02-15 -- Completed 01-03-PLAN.md

Progress: [███░░░░░░░] 15%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 4min
- Total execution time: 0.18 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 11min | 4min |

**Recent Trend:**
- Last 5 plans: 01-01 (5min), 01-02 (3min), 01-03 (3min)
- Trend: Accelerating

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Build wired UART transport first, add ESP-NOW in Phase 2 (removes wireless uncertainty from early debugging)
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

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: USB CDC on bridge without HID needs resolution -- companion app needs serial access to bridge while bridge does HID-only. Resolve during Phase 1 architecture.
- [Research]: CrowPanel battery charging circuit unknown -- characterize during Phase 4 planning.
- [Research]: LVGL memory pool may need increase to 128KB+ or PSRAM-backed allocator -- test during Phase 2/3 UI expansion.

## Session Continuity

Last session: 2026-02-15
Stopped at: Completed 01-03-PLAN.md (display hotkey UI + UART transmit module)
Resume file: None
