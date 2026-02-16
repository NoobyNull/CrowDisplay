---
phase: 10-companion-action-execution
plan: 01
subsystem: firmware, protocol, companion
tags: [esp-now, usb-hid, vendor-hid, button-press, action-types]

# Dependency graph
requires:
  - phase: 09-tweaks-and-breakfix
    provides: WYSIWYG widget system with absolute positioning and grid spans
provides:
  - MSG_BUTTON_PRESS protocol message (0x0B) with ButtonPressMsg struct
  - Identity-based button press pipeline (page_index + widget_index)
  - Bridge relay of button presses to companion via Vendor HID INPUT reports
  - send_vendor_report() function for bridge device-to-host communication
  - ACTION_LAUNCH_APP, ACTION_SHELL_CMD, ACTION_OPEN_URL config constants
  - New widget fields for launch_command, shell_command, url, launch_wm_class
affects: [10-02, 10-03, companion-app, editor-ui]

# Tech tracking
tech-stack:
  added: []
  patterns: [identity-based button press, vendor HID relay, static event data pool]

key-files:
  created: []
  modified:
    - shared/protocol.h
    - display/espnow_link.cpp
    - display/espnow_link.h
    - display/ui.cpp
    - bridge/main.cpp
    - bridge/usb_hid.cpp
    - bridge/usb_hid.h
    - companion/config_manager.py

key-decisions:
  - "Identity-based button press (page+widget index) instead of keystroke-based"
  - "Static ButtonEventData pool (CONFIG_MAX_WIDGETS entries) for LVGL event user_data"
  - "Keep legacy MSG_HOTKEY/MSG_MEDIA_KEY handlers for backward compat"
  - "VALID_ACTION_TYPES tuple for centralized action type validation"

patterns-established:
  - "send_vendor_report: bridge-to-companion communication via USB Vendor HID INPUT reports"
  - "ButtonEventData pool: static array indexed by btn_event_count for LVGL callbacks"

# Metrics
duration: 3min
completed: 2026-02-16
---

# Phase 10 Plan 01: Protocol + Pipeline Summary

**MSG_BUTTON_PRESS protocol with identity-based button press pipeline: display sends page+widget index, bridge ACKs and relays to companion via Vendor HID**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-16T06:47:57Z
- **Completed:** 2026-02-16T06:51:11Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Added MSG_BUTTON_PRESS (0x0B) message type with ButtonPressMsg struct (page_index, widget_index)
- Changed display button press from keystroke-based to identity-based: btn_event_cb now sends page+widget index
- Bridge receives MSG_BUTTON_PRESS, immediately ACKs display, relays to companion via Vendor.write()
- Added ACTION_LAUNCH_APP=2, ACTION_SHELL_CMD=3, ACTION_OPEN_URL=4 constants with validation
- Added new widget default fields for downstream action execution (launch_command, shell_command, url)

## Task Commits

Each task was committed atomically:

1. **Task 1: Protocol message + display firmware changes** - `f3c2f4e` (feat)
2. **Task 2: Bridge relay + vendor HID write + config_manager constants** - `85ed42d` (feat)

## Files Created/Modified
- `shared/protocol.h` - Added MSG_BUTTON_PRESS enum value and ButtonPressMsg struct
- `display/espnow_link.h` - Added send_button_press_to_bridge() declaration
- `display/espnow_link.cpp` - Implemented send_button_press_to_bridge() function
- `display/ui.cpp` - ButtonEventData pool, identity-based btn_event_cb, render_widget with indices
- `bridge/usb_hid.h` - Added send_vendor_report() declaration
- `bridge/usb_hid.cpp` - Implemented send_vendor_report() for device-to-host HID reports
- `bridge/main.cpp` - Added MSG_BUTTON_PRESS case: ACK display + relay to companion
- `companion/config_manager.py` - New action type constants, VALID_ACTION_TYPES, widget fields, migration

## Decisions Made
- Used static ButtonEventData array (CONFIG_MAX_WIDGETS=32 entries) instead of dynamic allocation -- avoids heap fragmentation on embedded target, reset on page rebuild
- Kept legacy MSG_HOTKEY and MSG_MEDIA_KEY handlers in bridge -- prevents breakage if old display firmware is used
- Added VALID_ACTION_TYPES tuple for centralized validation -- easier to extend when new action types are added

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Protocol and firmware pipeline ready for companion-side action execution (plan 10-02)
- Config manager constants and widget fields ready for companion action handler implementation
- Editor UI can be updated to expose new action types and fields (plan 10-03)

## Self-Check: PASSED

All 8 modified files verified present. Both task commits (f3c2f4e, 85ed42d) confirmed in git log.

---
*Phase: 10-companion-action-execution*
*Completed: 2026-02-16*
