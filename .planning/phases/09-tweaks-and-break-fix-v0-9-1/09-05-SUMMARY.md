---
phase: 09-tweaks-and-break-fix-v0-9-1
plan: 05
subsystem: notifications
tags: [dbus, esp-now, lvgl, toast, hid, notification-forwarding]

# Dependency graph
requires:
  - phase: 09-03
    provides: TLV protocol pattern, MSG_NOTIFICATION constant reserved
provides:
  - MSG_NOTIFICATION protocol message and NotificationMsg struct (248 bytes)
  - D-Bus session bus notification listener with app name filtering
  - Bridge relay for notification messages over ESP-NOW
  - LVGL toast notification overlay with auto-dismiss and tap-dismiss
  - Editor notification config panel with enable toggle and app filter list
  - Config schema validation for notifications_enabled and notification_filter
affects: [companion, bridge, display, editor, config]

# Tech tracking
tech-stack:
  added: [dbus-next session bus monitoring]
  patterns: [toast overlay with LVGL animation, D-Bus eavesdrop for Notify method calls]

key-files:
  created: []
  modified:
    - shared/protocol.h
    - companion/hotkey_companion.py
    - bridge/main.cpp
    - display/ui.cpp
    - display/ui.h
    - display/main.cpp
    - companion/ui/editor_main.py
    - companion/config_manager.py

key-decisions:
  - "NotificationMsg 248 bytes (32+100+116) fits ESP-NOW 250-byte limit"
  - "Notifications disabled by default -- opt-in via config"
  - "Empty notification_filter list forwards ALL notifications"
  - "Toast replaces previous (no stacking) to prevent memory leaks"
  - "D-Bus eavesdrop via AddMatch on session bus for Notify method calls"

patterns-established:
  - "Toast overlay pattern: create on lv_scr_act(), auto-dismiss via lv_anim with ready_cb delete"
  - "Notification pipeline: D-Bus -> companion -> HID -> bridge -> ESP-NOW -> display"

# Metrics
duration: 4min
completed: 2026-02-16
---

# Phase 9 Plan 5: Desktop Notification Forwarding Summary

**D-Bus desktop notification forwarding to display with app filtering, 248-byte MSG_NOTIFICATION over ESP-NOW, and LVGL toast overlay with 5-second auto-dismiss**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-16T00:09:48Z
- **Completed:** 2026-02-16T00:13:56Z
- **Tasks:** 5
- **Files modified:** 8

## Accomplishments
- Full notification pipeline from D-Bus session bus through companion, bridge, ESP-NOW to display toast
- App name filtering with configurable list (empty = forward all)
- Styled toast overlay with app name, summary, body; auto-dismiss with fade animation
- Editor panel for enabling notifications and managing app filter list
- Graceful degradation when D-Bus unavailable or dbus-next not installed

## Task Commits

Each task was committed atomically:

1. **Task 1: Define MSG_NOTIFICATION protocol message** - `dba1aff` (feat)
2. **Task 2: D-Bus notification listener with app filtering** - `e73b5a9` (feat)
3. **Task 3: Bridge relay for MSG_NOTIFICATION** - `03ddcb5` (feat)
4. **Task 4: Toast notification overlay on display** - `2b1874d` (feat)
5. **Task 5: Notification filter config in editor** - `b029ad4` (feat)

## Files Created/Modified
- `shared/protocol.h` - Added MSG_NOTIFICATION enum value and NotificationMsg struct (248 bytes) with static_assert
- `companion/hotkey_companion.py` - NotificationListener class, send_notification_to_display(), config loading, thread startup
- `bridge/main.cpp` - MSG_NOTIFICATION relay case, fixed MSG_STATS relay for TLV variable-length
- `display/ui.cpp` - show_notification_toast() with LVGL styled overlay, animation, tap-dismiss
- `display/ui.h` - Public API declaration for show_notification_toast()
- `display/main.cpp` - MSG_NOTIFICATION handler in message dispatch with null-termination safety
- `companion/ui/editor_main.py` - NotificationsPanel with enable checkbox, app filter list, add/remove
- `companion/config_manager.py` - Validation for notifications_enabled (bool) and notification_filter (string array)

## Decisions Made
- NotificationMsg sized to 248 bytes (32+100+116) to fit within 250-byte ESP-NOW payload limit
- Notifications disabled by default (notifications_enabled = false) for backward compatibility
- Empty notification_filter list means forward ALL notifications (permissive default when enabled)
- Toast replaces previous instead of stacking -- prevents LVGL memory accumulation
- D-Bus session bus eavesdrop via AddMatch rule for org.freedesktop.Notifications Notify method

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MSG_STATS bridge relay truncating TLV payloads**
- **Found during:** Task 3 (bridge relay)
- **Issue:** Bridge was sending only sizeof(StatsPayload) = 10 bytes for MSG_STATS, truncating TLV packets from 09-03 which are variable-length
- **Fix:** Changed to forward actual payload_len instead of fixed struct size
- **Files modified:** bridge/main.cpp
- **Verification:** Code review confirms variable-length relay matches TLV encoding
- **Committed in:** 03ddcb5 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Bug fix was necessary for correct TLV stats relay. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. D-Bus policy configuration may be needed on some systems for eavesdrop permissions (documented in code comments).

## Next Phase Readiness
- All 5 plans in phase 9 now have summaries (09-01 through 09-05)
- Notification forwarding pipeline complete, ready for hardware testing
- D-Bus eavesdrop may require session bus policy adjustment on restrictive systems

---
*Phase: 09-tweaks-and-break-fix-v0-9-1*
*Completed: 2026-02-16*
