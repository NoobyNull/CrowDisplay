---
phase: 10-companion-action-execution
plan: 02
subsystem: companion
tags: [action-executor, vendor-hid, watchdog, ydotool, wmctrl, threading]

# Dependency graph
requires:
  - phase: 10-companion-action-execution
    plan: 01
    provides: MSG_BUTTON_PRESS protocol, bridge relay, config_manager action type constants
provides:
  - Action executor dispatching 5 action types (hotkey, media key, launch app, shell cmd, open URL)
  - Vendor HID read thread receiving button presses from bridge
  - Config file auto-reload via watchdog with 500ms debounce
  - Thread-safe HID device access via threading.Lock
  - WM_CLASS extraction from .desktop files for focus-or-launch
affects: [10-03, editor-ui, companion-app]

# Tech tracking
tech-stack:
  added: [watchdog (optional)]
  patterns: [action dispatch by type, focus-or-launch via wmctrl, sudo blocking, ydotool/xdotool fallback]

key-files:
  created:
    - companion/action_executor.py
  modified:
    - companion/hotkey_companion.py
    - companion/app_scanner.py

key-decisions:
  - "ydotool preferred over xdotool with automatic fallback -- supports Wayland natively"
  - "watchdog optional dependency with graceful degradation -- logs warning if not installed"
  - "hid_lock as optional parameter to existing functions -- backward compatible, no breakage"
  - "Action execution on separate daemon threads -- never blocks vendor read or stats loop"

patterns-established:
  - "Action dispatch: execute_action looks up widget, dispatches by action_type to handler function"
  - "HID lock pattern: all device.write/read calls wrapped in threading.Lock for thread safety"
  - "Config watcher: watchdog observer with debounced reload handler"

# Metrics
duration: 3min
completed: 2026-02-16
---

# Phase 10 Plan 02: Action Execution + Vendor Read Thread Summary

**Action executor with 5 action types (hotkey, media, app launch, shell, URL), vendor HID read thread for button presses, and watchdog config auto-reload**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-16T06:53:25Z
- **Completed:** 2026-02-16T06:56:22Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created action_executor.py with dispatch for all 5 action types: keyboard shortcuts (ydotool/xdotool), media keys, app launch with focus-or-launch, shell commands (sudo blocked), and URL opening
- Added vendor HID read thread to companion that receives MSG_BUTTON_PRESS from bridge and dispatches to execute_action on separate daemon threads
- Implemented config file auto-reload via watchdog with 500ms debounce, graceful degradation if watchdog not installed
- Made all HID device access thread-safe with threading.Lock protecting every device.write() and device.read() call
- Added StartupWMClass extraction to app_scanner for focus-or-launch feature

## Task Commits

Each task was committed atomically:

1. **Task 1: Action executor module + app_scanner WM_CLASS** - `915cdf6` (feat)
2. **Task 2: Vendor HID read thread + config file watcher** - `fdc4140` (feat)

## Files Created/Modified
- `companion/action_executor.py` - Action dispatch for 5 types with HID keycode mapping, consumer code mapping, ydotool/xdotool/wmctrl integration
- `companion/hotkey_companion.py` - Vendor read thread, config watcher, hid_lock for thread-safe access
- `companion/app_scanner.py` - Added wm_class field to AppEntry dataclass, StartupWMClass extraction

## Decisions Made
- Used ydotool as primary keyboard/media simulation tool with xdotool fallback -- ydotool works on both X11 and Wayland
- watchdog is an optional dependency -- companion logs a warning and continues without auto-reload if not installed
- Added hid_lock as optional parameter to existing send_ functions rather than refactoring signatures -- maintains backward compatibility
- Button actions execute on separate daemon threads to prevent blocking the vendor read loop or stats streaming

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Optional dependencies:
- `pip install watchdog` for config auto-reload
- `ydotool` or `xdotool` for keyboard shortcuts
- `wmctrl` for focus-or-launch window management

## Next Phase Readiness
- Action execution pipeline complete: display button press -> bridge relay -> companion action dispatch
- Editor UI can now expose action type selection and configuration fields (plan 10-03)
- All 5 action types functional with appropriate error handling and logging

## Self-Check: PASSED

All 3 modified/created files verified present. Both task commits (915cdf6, fdc4140) confirmed in git log.

---
*Phase: 10-companion-action-execution*
*Completed: 2026-02-16*
