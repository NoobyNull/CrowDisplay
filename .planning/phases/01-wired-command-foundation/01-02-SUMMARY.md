---
phase: 01-wired-command-foundation
plan: 02
subsystem: firmware
tags: [esp32-s3, usb-hid, uart, state-machine, crc8, keyboard, hid-bridge]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Multi-env PlatformIO build, shared/protocol.h with SOF framing and CRC8"
provides:
  - "USB HID keyboard initialization and modifier+key keystroke firing (bridge/usb_hid.cpp)"
  - "SOF-framed UART state machine parser with CRC8 validation (bridge/uart_link.cpp)"
  - "Bridge dispatch loop: UART poll -> parse MSG_HOTKEY -> fire HID -> send ACK (bridge/main.cpp)"
affects: [01-03, 01-04]

# Tech tracking
tech-stack:
  added: [USBHIDKeyboard, HardwareSerial]
  patterns: [state-machine frame parser, modifier bitmask keystroke firing, non-blocking UART poll]

key-files:
  created:
    - bridge/usb_hid.h
    - bridge/usb_hid.cpp
    - bridge/uart_link.h
    - bridge/uart_link.cpp
  modified:
    - bridge/main.cpp

key-decisions:
  - "Keyboard only -- no consumer control (media keys deferred to Phase 3 per BRDG-04)"
  - "delay(20) keystroke hold time instead of backup's delay(50) -- minimum for host registration"
  - "Max 64 bytes per uart_poll() call to prevent main loop blocking"
  - "delay(1) main loop -- bridge has no LVGL overhead, should be maximally responsive"

patterns-established:
  - "FrameParser state machine: WAIT_SOF -> READ_LEN -> READ_TYPE -> READ_PAYLOAD -> READ_CRC"
  - "Modifier bitmask: press individual modifiers, press key, delay, releaseAll"
  - "ACK-after-action: bridge sends MSG_HOTKEY_ACK immediately after firing keystroke"

# Metrics
duration: 3min
completed: 2026-02-15
---

# Phase 1 Plan 2: Bridge Firmware Summary

**USB HID keyboard bridge with SOF-framed UART state machine parser, modifier+key combo firing, and hotkey command dispatch with ACK responses**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-15T07:12:04Z
- **Completed:** 2026-02-15T07:14:44Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Implemented USB HID keyboard module that appears as "HotkeyBridge" device on PC, supporting all modifier combos (Ctrl, Shift, Alt, GUI)
- Built UART receive state machine (FrameParser) that validates CRC8 and rejects corrupted/oversized frames
- Wired bridge main loop to dispatch MSG_HOTKEY commands by firing keystrokes and sending MSG_HOTKEY_ACK responses
- Bridge firmware compiles cleanly: 315KB flash / 31KB RAM with USB HID enabled

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement bridge USB HID keyboard and UART receive modules** - `cfd06ed` (feat)
2. **Task 2: Wire bridge main loop to dispatch hotkey commands** - `3ef8436` (feat)

## Files Created/Modified
- `bridge/usb_hid.h` - Public API: usb_hid_init(), fire_keystroke(modifiers, keycode)
- `bridge/usb_hid.cpp` - USBHIDKeyboard with modifier bitmask pressing and releaseAll
- `bridge/uart_link.h` - Public API: uart_link_init(), uart_poll(), uart_send()
- `bridge/uart_link.cpp` - FrameParser state machine with CRC8 validation, UART1 on GPIO 17/18
- `bridge/main.cpp` - Dispatch loop: poll UART -> handle MSG_HOTKEY -> fire keystroke -> send ACK

## Decisions Made
- **Keyboard only, no consumer control:** Media keys deferred to Phase 3 per BRDG-04. Simplifies initial implementation and avoids USB HID composite device complexity.
- **20ms keystroke hold time:** Reduced from backup's 50ms -- 20ms is sufficient minimum for host OS registration while improving throughput.
- **64-byte poll limit per cycle:** Prevents uart_poll() from blocking the main loop if display sends burst data.
- **delay(1) in main loop:** Bridge has no LVGL/display overhead, so 1ms yield is sufficient for FreeRTOS task scheduling while maintaining fast command response.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing Arduino.h include in usb_hid.cpp**
- **Found during:** Task 1 (compilation verification)
- **Issue:** usb_hid.cpp used `delay()` and `Serial` but only included `<USB.h>` and `<USBHIDKeyboard.h>`. These Arduino globals require `<Arduino.h>`.
- **Fix:** Added `#include <Arduino.h>` to usb_hid.cpp
- **Files modified:** bridge/usb_hid.cpp
- **Verification:** `pio run -e bridge` compiles successfully
- **Committed in:** cfd06ed (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial missing include. No scope change.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Bridge firmware is complete and ready for integration with display firmware (Plan 03)
- USB HID keyboard will enumerate as "HotkeyBridge" when flashed to ESP32-S3 DevKitC-1
- UART link uses GPIO 17 (TX) / 18 (RX) -- must be cross-wired to display UART TX/RX pins
- Display firmware needs corresponding uart_send() for MSG_HOTKEY (Plan 03 scope)

---
*Phase: 01-wired-command-foundation*
*Completed: 2026-02-15*

## Self-Check: PASSED

All 5 files verified present. Both commit hashes (cfd06ed, 3ef8436) confirmed in git log.
