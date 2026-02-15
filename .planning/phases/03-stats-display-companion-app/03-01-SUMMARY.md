---
phase: 03-stats-display-companion-app
plan: 01
subsystem: firmware
tags: [usb-hid, esp-now, consumer-control, vendor-hid, esp32-s3]

# Dependency graph
requires:
  - phase: 01-wired-hotkey-foundation
    provides: "Bridge USB HID keyboard, ESP-NOW link, protocol.h framing"
provides:
  - "MSG_STATS and MSG_MEDIA_KEY protocol message types"
  - "StatsPayload struct (10 bytes) for system metrics"
  - "MediaKeyMsg struct (2 bytes) for consumer control codes"
  - "Composite USB HID: Keyboard + ConsumerControl + Vendor"
  - "poll_vendor_hid() for receiving stats from companion app"
  - "fire_media_key() for USB consumer control"
  - "Stats relay: USB Vendor HID -> ESP-NOW MSG_STATS"
affects: [03-02, 03-03, 03-04, display-ui, companion-app]

# Tech tracking
tech-stack:
  added: [USBHIDConsumerControl, USBHIDVendor]
  patterns: [composite-usb-hid, vendor-hid-stats-relay]

key-files:
  modified:
    - shared/protocol.h
    - bridge/usb_hid.h
    - bridge/usb_hid.cpp
    - bridge/main.cpp

key-decisions:
  - "USBHIDVendor 63-byte reports with no size prepend (matches companion app expectations)"
  - "Stats relay is fire-and-forget -- no ACK from display for MSG_STATS"

patterns-established:
  - "Composite USB HID: register all devices with .begin() before USB.begin()"
  - "Vendor HID polling in main loop before ESP-NOW polling"

# Metrics
duration: 2min
completed: 2026-02-15
---

# Phase 3 Plan 1: Protocol + Bridge Stats/Media Key Summary

**Composite USB HID (Keyboard + ConsumerControl + Vendor) with stats relay over ESP-NOW and media key dispatch**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-15T08:52:58Z
- **Completed:** 2026-02-15T08:54:33Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Extended protocol.h with MSG_STATS (0x03), MSG_MEDIA_KEY (0x04), StatsPayload, and MediaKeyMsg
- Upgraded bridge from keyboard-only to composite USB HID with three interfaces
- Bridge receives stats via USB Vendor HID and relays to display over ESP-NOW
- Bridge dispatches consumer control codes (media keys) from display commands

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend protocol.h with stats and media key message types** - `618c754` (feat)
2. **Task 2: Upgrade bridge to composite USB HID with ConsumerControl + Vendor + stats relay** - `fdcc43b` (feat)

## Files Created/Modified
- `shared/protocol.h` - Added MSG_STATS, MSG_MEDIA_KEY, StatsPayload (10 bytes), MediaKeyMsg (2 bytes)
- `bridge/usb_hid.h` - Added fire_media_key() and poll_vendor_hid() declarations
- `bridge/usb_hid.cpp` - Composite USB HID with Keyboard, ConsumerControl, Vendor; media key and vendor polling
- `bridge/main.cpp` - Stats relay from vendor HID to ESP-NOW, MSG_MEDIA_KEY case in receive handler

## Decisions Made
- USBHIDVendor configured with 63-byte reports and no size prepend -- matches the expected companion app report format
- Stats relay is fire-and-forget (no ACK for MSG_STATS) to minimize latency and complexity
- Vendor HID polled before ESP-NOW in loop() to prioritize fresh stats data

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Protocol types ready for display UI (03-02) to render StatsPayload
- Protocol types ready for companion app (03-03/03-04) to send stats via USB Vendor HID
- Bridge firmware compiles clean: RAM 17.6%, Flash 55.6%

## Self-Check: PASSED

All 4 modified files verified on disk. Both task commits (618c754, fdcc43b) verified in git log.

---
*Phase: 03-stats-display-companion-app*
*Completed: 2026-02-15*
