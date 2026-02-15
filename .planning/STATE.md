# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-14)

**Core value:** Tap a button on the display, the correct keyboard shortcut fires on the PC -- reliably, with minimal latency, whether connected by wire or wirelessly.
**Current focus:** Phase 4 - Battery Management + Power States

## Current Position

Phase: 4 of 5 (Battery Management + Power States)
Plan: 2 of 4 in current phase
Status: In Progress
Last activity: 2026-02-15 -- Completed 04-02 (companion shutdown + time sync)

Progress: [████████░░] 80%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 2min
- Total execution time: 0.25 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 11min | 4min |
| 03 | 4 | 9min | 2min |

| 04 | 2 | 2min | 1min |

**Recent Trend:**
- Last 5 plans: 03-02 (4min), 03-03 (2min), 03-04 (1min), 04-01 (~2min), 04-02 (2min)
- Trend: Stable

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
- [03-02]: Stats header hidden by default, auto-shows on first MSG_STATS, auto-hides after 5s timeout
- [03-02]: Generic espnow_poll_msg() queues non-ACK messages separately from ACK path
- [03-02]: Media keys use is_media flag in Hotkey struct to dispatch via send_media_key_to_bridge()
- [03-03]: Python with hidapi for companion app (per user discretion and research)
- [03-03]: GPU detection chain: NVIDIA (pynvml) -> AMD (sysfs) -> 0xFF fallback
- [03-03]: Leading 0x00 report ID byte for hidapi Linux HID writes
- [Phase 03-04]: Verification checkpoint pattern confirmed effective for hardware integration testing
- [04-01]: Battery module uses i2c_take/i2c_give helpers (consistent with touch module pattern)
- [04-01]: User brightness presets tracked separately from state-machine brightness for proper wake restore
- [04-02]: All HID writes now include 1-byte message type prefix after report ID for bridge dispatch (0x03=stats, 0x05=power, 0x06=time)
- [04-02]: D-Bus listener in daemon thread with asyncio loop, signals main thread via threading.Event (thread-safe)
- [04-02]: dbus-next imported inside function for graceful degradation if not installed

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: USB CDC on bridge -- bridge is HID-only on native USB. Companion app will need to communicate via ESP-NOW relay or separate serial adapter.
- [Research]: CrowPanel battery charging circuit unknown -- characterize during Phase 4 planning.
- [Research]: LVGL memory pool may need increase to 128KB+ or PSRAM-backed allocator -- test during Phase 2/3 UI expansion.

## Session Continuity

Last session: 2026-02-15
Stopped at: Completed 04-02-PLAN.md (companion shutdown + time sync)
Resume file: None
