---
phase: 07-config-server-softap-http
plan: 01
subsystem: firmware
tags: [softap, http, ota, wifi, channel-pinning]

requires:
  - phase: 06-data-driven-display-ui
    provides: Config server foundation, deferred rebuild pattern

provides:
  - Unified SoftAP manager (config upload + OTA firmware upload on single WebServer)
  - WiFi channel 1 pinning on both display and bridge for ESP-NOW coexistence
  - 5-minute inactivity timeout auto-stops SoftAP
  - Error propagation fix (HTTP 400 for failures, 200 for success with JSON)
  - ArduinoOTA alongside WebServer on port 80
  - ota.cpp/ota.h deleted, functionality migrated

affects: [07-config-ui-mode]

tech-stack:
  added: []
  patterns: [unified softap manager, channel pinning, inactivity timeout, deferred shutdown]

key-files:
  created: []
  modified:
    - display/config_server.cpp
    - display/config_server.h
    - display/espnow_link.cpp
    - bridge/espnow_link.cpp
    - display/main.cpp
    - display/ui.cpp
  deleted:
    - display/ota.cpp
    - display/ota.h

key-decisions:
  - "Single unified config_server module -- eliminates dual-SoftAP conflict"
  - "WiFi channel 1 pinning -- ensures ESP-NOW reliability during HTTP transfer"
  - "5-minute inactivity timeout -- auto-stops SoftAP to conserve power and prevent WiFi conflicts"
  - "HTTP 400 for upload errors -- proper error propagation instead of always returning 200"
  - "lv_obj_clean full rebuild -- Phase 6 deferred pattern supports config-driven UI"

patterns-established:
  - "config_server_poll() called from loop() handles HTTP + OTA + timeout"
  - "config_server_timed_out() latching flag allows UI to detect auto-stop"
  - "WiFi channel explicit pinning to 1 on both peers for deterministic coexistence"

duration: 8min
completed: 2026-02-15
---

# Plan 07-01: Merge OTA into Config Server with Channel Pinning

**Unified SoftAP manager with config upload + OTA firmware upload on single WebServer, explicit WiFi channel 1 pinning, 5-minute inactivity timeout, and upload error propagation fix**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-15
- **Completed:** 2026-02-15
- **Tasks:** 2
- **Files modified:** 9 (7 modified, 2 deleted)

## Accomplishments

### Task 1: Merge OTA into config_server with channel pinning and error fixes
- Unified SoftAP manager: config_server_start() starts SoftAP on channel 1 with both endpoints
- OTA handlers (handle_ota_upload, handle_ota_done) merged into config_server.cpp from ota.cpp
- ArduinoOTA integrated alongside WebServer, re-pinned after WiFi mode transitions
- Channel pinning: esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE) in:
  - config_server_start() after softAP bring-up
  - config_server_stop() after STA mode transition
  - display/espnow_link.cpp at init and peer registration
  - bridge/espnow_link.cpp at init and dynamic peer registration
- 5-minute inactivity timeout: INACTIVITY_TIMEOUT_MS (5 * 60 * 1000) with latching g_timed_out flag
- Error propagation fixed: g_upload_success/g_upload_error state tracked, HTTP 400 returned on failure with error JSON
- config_server_timed_out() returns true once per timeout, clearing flag on read

### Task 2: Delete ota.cpp/ota.h and update main.cpp
- Deleted display/ota.cpp and display/ota.h
- Removed #include "ota.h" from display/main.cpp and display/ui.cpp
- Removed ota_active() / ota_poll() polling block from main.cpp loop
- Consolidated config_server_poll() as sole WiFi handler
- Added config_server_timed_out() check in loop with Serial message
- Updated UI: config_btn_event_cb() replaces ota_btn_event_cb
- Updated UI: show_config_screen()/hide_config_screen() unified interface

## Task Commits

Single atomic commit:
- `b4bfe6d` (feat) - Merge OTA into config_server, channel pinning, timeout, error fix

## Files Created/Modified
- `display/config_server.cpp` - Unified SoftAP with OTA handlers, ArduinoOTA, channel pinning, inactivity timeout, error propagation
- `display/config_server.h` - Added config_server_timed_out() declaration
- `display/espnow_link.cpp` - Channel 1 pinning in init and peer registration
- `bridge/espnow_link.cpp` - Channel 1 pinning in init and dynamic peer registration
- `display/main.cpp` - Removed OTA polling, consolidated config_server_poll, added timeout check
- `display/ui.cpp` - Callback renamed, screen names updated, forward declarations added
- `display/ota.cpp` - DELETED
- `display/ota.h` - DELETED

## Decisions Made
- No changes needed to platformio.ini (ArduinoOTA + Update already present)
- UI now shows unified config server status instead of "OTA mode"
- Timeout detection via return flag from config_server_timed_out() (latching pattern)

## Deviations from Plan
None - plan executed exactly as specified. All must-haves verified:
1. ✅ config_server starts SoftAP on channel 1
2. ✅ ESP-NOW peers explicitly pin to channel 1
3. ✅ SoftAP auto-stops after 5 minutes inactivity
4. ✅ Upload errors return HTTP 400 with JSON error
5. ✅ OTA firmware upload triggers ESP.restart() on success
6. ✅ ArduinoOTA for PlatformIO upload still works
7. ✅ ESP-NOW channel re-pinned after config_server_stop()

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 7-01 complete: unified config_server module, channel pinning, inactivity timeout
- Phase 7-02 (Config Server UI Mode) can now build on unified backend
- Both firmware targets (display, bridge) compile cleanly
- Ready for hardware testing

---
*Phase: 07-config-server-softap-http*
*Completed: 2026-02-15*
