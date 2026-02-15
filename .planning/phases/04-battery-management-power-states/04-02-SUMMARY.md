---
phase: 04-battery-management-power-states
plan: 02
subsystem: companion
tags: [dbus, systemd, inhibitor-lock, time-sync, hid, python, asyncio]

# Dependency graph
requires:
  - phase: 03-stats-display-companion-app
    provides: "Companion app with HID stats streaming to bridge"
provides:
  - "D-Bus PrepareForShutdown listener with inhibitor lock"
  - "MSG_POWER_STATE (0x05) shutdown notification via HID"
  - "MSG_TIME_SYNC (0x06) epoch seconds with each stats cycle"
  - "Type-prefixed HID vendor protocol (0x03 stats, 0x05 power, 0x06 time)"
affects: [04-battery-management-power-states]

# Tech tracking
tech-stack:
  added: [dbus-next, asyncio, threading]
  patterns: [type-prefixed-vendor-hid, thread-safe-event-signaling, graceful-degradation]

key-files:
  created: []
  modified:
    - companion/hotkey_companion.py

key-decisions:
  - "D-Bus listener runs in daemon thread with asyncio loop, communicates to main thread via threading.Event (thread safety)"
  - "All HID writes now include 1-byte message type prefix after report ID for bridge dispatch"
  - "dbus-next imported inside function for graceful degradation if not installed"

patterns-established:
  - "Type-prefixed vendor HID protocol: [0x00 report ID] [msg type] [payload]"
  - "Thread-safe D-Bus to main thread signaling via threading.Event"

# Metrics
duration: 2min
completed: 2026-02-15
---

# Phase 04 Plan 02: Companion Shutdown + Time Sync Summary

**D-Bus shutdown detection with systemd inhibitor lock and epoch time sync via type-prefixed vendor HID protocol**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-15T16:07:42Z
- **Completed:** 2026-02-15T16:09:56Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- D-Bus PrepareForShutdown signal listener with systemd delay inhibitor lock ensures bridge is notified before PC powers off
- MSG_TIME_SYNC sends epoch seconds with each stats cycle so display can show accurate clock (no onboard RTC)
- Existing stats writes updated with 0x03 type prefix byte for unified bridge dispatch protocol
- Graceful degradation when dbus-next is not installed (companion still streams stats)

## Task Commits

Each task was committed atomically:

1. **Task 1: D-Bus shutdown listener + time sync** - `a655717` (feat)

## Files Created/Modified
- `companion/hotkey_companion.py` - Added D-Bus shutdown listener, time sync, power state messaging, type-prefixed HID writes

## Decisions Made
- D-Bus listener runs in a daemon thread with its own asyncio event loop; communicates shutdown to main thread via `threading.Event` (no cross-thread HID access)
- All HID writes now include a 1-byte message type prefix after the report ID (0x03=stats, 0x05=power, 0x06=time) for bridge-side dispatch
- `dbus-next` is imported inside the listener function to allow graceful degradation if the package is not installed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
Optional: `pip install dbus-next` for shutdown detection. Without it, companion still streams stats normally but cannot notify the display of PC shutdown.

## Next Phase Readiness
- Companion now sends typed HID messages ready for bridge firmware dispatch (Plan 03)
- Power state and time sync messages match protocol.h definitions
- Bridge firmware needs to parse type prefix byte and route MSG_POWER_STATE and MSG_TIME_SYNC to display via ESP-NOW

---
*Phase: 04-battery-management-power-states*
*Completed: 2026-02-15*
