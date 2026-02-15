---
phase: 01-wired-command-foundation
plan: 03
subsystem: firmware
tags: [lvgl, tabview, hotkey-ui, uart-transmit, esp32-s3, sof-framing, crc8]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Multi-env PlatformIO build, shared protocol.h, display firmware skeleton with I2C mutex"
provides:
  - "3-page LVGL tabview with 36 color-coded hotkey buttons (icons, labels, press feedback)"
  - "UART1 transmit module with SOF+CRC8 framing for hotkey commands"
  - "Display main loop integrating touch, LVGL, UART ACK polling"
  - "Non-blocking frame parser for receiving ACK messages from bridge"
affects: [01-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [UART1 HardwareSerial for display-bridge link, SOF frame send/receive with state machine parser]

key-files:
  created:
    - display/ui.h
    - display/ui.cpp
    - display/uart_link.h
    - display/uart_link.cpp
  modified:
    - display/main.cpp

key-decisions:
  - "Replaced page 3 media keys with keyboard-only dev shortcuts (Phase 1 is keyboard-only, consumer control in Phase 3)"
  - "UART1 on GPIO 10 (TX) / GPIO 11 (RX) for display-to-bridge link"
  - "Key codes defined locally in ui.cpp to avoid pulling in USBHIDKeyboard.h on display side"

patterns-established:
  - "Button callback sends UART message to bridge, never calls USB HID directly (architectural separation)"
  - "HardwareSerial(1) for cross-board UART communication at 115200 baud"
  - "Frame parser state machine for non-blocking ACK reception"

# Metrics
duration: 3min
completed: 2026-02-15
---

# Phase 1 Plan 3: Display Hotkey UI and UART Transmit Summary

**3-page swipeable LVGL tabview with 36 color-coded hotkey buttons, SOF-framed UART1 transmit to bridge, and non-blocking ACK parser**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-15T07:12:07Z
- **Completed:** 2026-02-15T07:15:25Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Built 3-page hotkey UI (General, Windows, Dev Tools) with 12 buttons each, all keyboard-only for Phase 1
- Each button has LVGL symbol icon, label, description sublabel, and category-based color coding
- Press feedback via color darken + transform shrink on LV_STATE_PRESSED (DISP-03)
- UART1 transmit module sends SOF-framed MSG_HOTKEY messages with CRC8 checksum
- Main loop integrates touch polling (20Hz), LVGL tick, and non-blocking ACK reception
- Display firmware compiles at 588KB flash / 120KB RAM

## Task Commits

Each task was committed atomically:

1. **Task 1: Create multi-page hotkey UI with tabview, icons, colors, and press feedback** - `c8545a2` (feat)
2. **Task 2: Create display UART transmit module and wire up main loop** - `da2cd65` (feat)

## Files Created/Modified
- `display/ui.h` - Public API: create_ui() function declaration
- `display/ui.cpp` - 36 hotkey definitions, tabview creation, button styling with press feedback, event callbacks
- `display/uart_link.h` - Public API: uart_link_init(), uart_send(), send_hotkey_to_bridge(), uart_poll_ack()
- `display/uart_link.cpp` - UART1 init, SOF-framed send, hotkey convenience function, ACK frame parser state machine
- `display/main.cpp` - Updated from skeleton: full init sequence + UART + UI, loop with ACK polling

## Decisions Made
- **Page 3 media keys replaced:** All 6 media key entries (Play/Pause, Next, Prev, Vol Up/Down, Mute) replaced with keyboard-only dev shortcuts (Go to Line, Sidebar, Split, Close All, Zoom In/Out). Phase 1 is keyboard-only; consumer control will be added in Phase 3 with a separate message type.
- **Local key code defines:** KEY_TAB, KEY_ESC, KEY_F5, KEY_LEFT_ARROW etc. defined locally in ui.cpp rather than including USBHIDKeyboard.h, since the display firmware does not use USB HID.
- **GPIO 10/11 for UART1:** These pins are confirmed free on the CrowPanel ESP32-S3 for the display-to-bridge UART link.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Display UI is complete and ready for end-to-end testing with the bridge
- UART transmit sends properly framed MSG_HOTKEY messages matching the shared protocol
- ACK reception is implemented for future bridge acknowledgment feedback
- Plan 04 (integration/wiring) can proceed with the display and bridge connected

---
*Phase: 01-wired-command-foundation*
*Completed: 2026-02-15*

## Self-Check: PASSED

All 5 files verified present. Both commit hashes (c8545a2, da2cd65) confirmed in git log.
