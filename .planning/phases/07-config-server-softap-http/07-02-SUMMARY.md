---
phase: 07-config-server-softap-http
plan: 02
subsystem: ui
tags: [lvgl, config-screen, softap, wifi-ui, gear-icon]

requires:
  - phase: 07-config-server-softap-http
    plan: 01
    provides: Unified config_server_start/stop/poll API, config_server_timed_out() latching flag

provides:
  - Config mode screen with SSID, password, IP, config upload URL, OTA firmware URL
  - Gear icon (LV_SYMBOL_SETTINGS) in header bar replacing OTA download icon
  - "Apply & Exit" button to stop SoftAP and return to main hotkey view
  - Inactivity timeout auto-return from config screen to main view

affects: [08-desktop-gui-editor]

tech-stack:
  added: []
  patterns: [config mode screen, gear icon trigger, auto-return on timeout]

key-files:
  created: []
  modified:
    - display/ui.cpp
    - display/ui.h
    - display/main.cpp

key-decisions:
  - "LV_SYMBOL_SETTINGS gear icon in CLR_TEAL color -- visually distinct from WiFi and brightness icons"
  - "Apply & Exit button in CLR_GREEN -- positive action color, stops SoftAP and returns to main view"
  - "Left-aligned config info text -- cleaner readability for URLs and credentials"
  - "show_config_screen() takes no args -- fetches IP from WiFi.softAPIP() internally"

patterns-established:
  - "Config screen created once in create_ui(), persists across rebuilds"
  - "config_btn_event_cb toggles config server and screen in one callback"
  - "hide_config_screen() callable from main.cpp timeout handler and UI exit button"

duration: 3min
completed: 2026-02-15
---

# Plan 07-02: Config Mode UI Screen with Header Icon

**Gear icon in header triggers config mode screen showing WiFi credentials, upload URLs, and "Apply & Exit" button for SoftAP control**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-15
- **Completed:** 2026-02-15
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

### Task 1: Replace OTA screen/button with config mode screen/button in ui.cpp
- Replaced OTA download icon (LV_SYMBOL_DOWNLOAD) with gear icon (LV_SYMBOL_SETTINGS) in header bar
- Created config mode screen with title, info label showing SSID/password/IP/URLs, and "Apply & Exit" button
- show_config_screen() fetches WiFi.softAPIP() and formats connection info
- hide_config_screen() loads main_screen, callable from both UI button and timeout handler
- Removed all OTA-specific UI elements (ota_screen, ota_ip_label, show/hide_ota_screen)

### Task 2: Wire config screen timeout handling in main.cpp
- config_server_timed_out() check in main loop calls hide_config_screen()
- No remaining references to ota_* functions in any display source file

## Task Commits

Code changes were committed alongside Plan 07-01:
- `b4bfe6d` (feat) - Merge OTA into config_server, includes UI refactoring

## Files Created/Modified
- `display/ui.cpp` - Config screen creation, gear icon, show/hide functions, config_btn_event_cb
- `display/ui.h` - show_config_screen() and hide_config_screen() declarations (replacing OTA equivalents)
- `display/main.cpp` - hide_config_screen() called on inactivity timeout

## Decisions Made
- Gear icon uses CLR_TEAL (0x1ABC9C) to distinguish from WiFi (grey) and brightness (yellow) icons
- Config info label uses left alignment for URL readability
- "Apply & Exit" uses CLR_GREEN to indicate positive/safe action

## Deviations from Plan
None - plan executed exactly as specified.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 7 complete: config server + config mode UI fully functional
- Display renders config screen with all connection info on gear icon tap
- Inactivity timeout auto-exits config mode
- Both firmware targets compile cleanly
- Ready for Phase 8 (Desktop GUI Editor)

---
*Phase: 07-config-server-softap-http*
*Completed: 2026-02-15*
