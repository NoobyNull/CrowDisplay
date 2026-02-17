# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-15)

**Core value:** Tap a button on the display, the correct keyboard shortcut fires on the PC -- reliably, with minimal latency, whether connected by wire or wirelessly.
**Current focus:** Phase 11 - Hardware Buttons + System Actions

## Current Position

**Phase:** 11 (Hardware Buttons + System Actions)
**Current Plan:** 4
**Total Plans in Phase:** 4
**Status:** Complete (all 4 plans executed)
**Last Activity:** 2026-02-16

Progress: [####################] 100% (11-01 through 11-04 complete)

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 7 (across v1.0)
- Average duration: 2min
- Total execution time: 0.25 hours

**By Phase (v1.0 + v1.1):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 11min | 4min |
| 03 | 4 | 9min | 2min |
| 04 | 3 | 5min | 2min |
| 05 | 1 | 5min | 5min |
| 06 | 2 | 6min | 3min |
| 07 | 2 | 11min | 5.5min |
| 08 | 3 | 7min | 2.3min |
| 09 | 5 | ~60min | ~12min |
| 10 | 3 | 11min | 3.7min |
| 11 | 4 | 27min | 6.75min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.1 Roadmap]: SD card is config storage medium (not NVS/LittleFS) -- human-readable, removable, large capacity
- [v1.1 Roadmap]: SoftAP + HTTP for config upload (not ESP-NOW relay) -- direct WiFi avoids bridge bottleneck
- [v1.1 Roadmap]: PySide6 desktop editor (not web UI on ESP32) -- richer UX, no flash/RAM cost on device
- [v1.1 Roadmap]: ArduinoJson v7 with PSRAM allocator for config parsing -- avoids internal SRAM exhaustion
- [v1.1 Roadmap]: Widget-pool pattern for dynamic UI -- prevents LVGL memory leak on config reload
- [Phase 5]: ps_malloc() for all buffers >4KB, free() on all return paths
- [Phase 5]: FAT rename requires explicit remove of target first
- [Phase 5]: Config version mismatch logs warning but still loads (forward compatibility)
- [Phase 5]: Raw string literals need custom delimiters when HTML contains )"
- [Phase 7]: Single unified config_server module -- eliminates dual-SoftAP conflict
- [Phase 7]: WiFi channel 1 pinning -- ensures ESP-NOW reliability during HTTP transfer
- [Phase 7]: 5-minute inactivity timeout -- auto-stops SoftAP to conserve power
- [Phase 7]: HTTP 400 for upload errors -- proper error propagation instead of always 200
- [Phase 7]: LV_SYMBOL_SETTINGS gear icon in CLR_TEAL -- visually distinct config mode trigger
- [Phase 8]: keyPressEvent override on custom QLineEdit (not QKeySequenceEdit) -- simpler, avoids system shortcut side effects
- [Phase 8]: Icon picker stores UTF-8 decoded strings (not symbol names) -- matches device JSON format directly
- [Phase 8]: 9 consumer control codes in media key dropdown (Play/Pause, Next, Prev, Stop, Vol+, Vol-, Mute, Browser Home/Back)
- [Phase 8]: Gold border (#FFD700) for selected button, luminance threshold 140 for text contrast
- [Phase 9]: DisplayMode orthogonal to PowerState -- mode controls UI, power controls brightness
- [Phase 9]: LVGL custom filesystem driver (S: letter) for SD card image access in picture frame mode
- [Phase 9]: LVGL grid layout (4x3 FR units) replaces flex row-wrap -- enables explicit positioning and variable sizing
- [Phase 9]: grid_row/grid_col = -1 means auto-flow, >= 0 means explicit cell placement
- [Phase 9]: pressed_color = 0x000000 means auto-darken, non-zero = explicit RGB
- [Phase 9]: CONFIG_MAX_BUTTONS reduced from 16 to 12 (4x3 grid capacity)
- [Phase 9]: TLV stats protocol with first-byte heuristic for backward compat (count <= 0x14 = TLV, > 0x14 = legacy)
- [Phase 9]: Max 8 configurable stats in header, position-based ordering
- [Phase 9]: pynvml for extended GPU metrics (memory, power, frequency)
- [Phase 9]: col_span/row_span only for explicit positioning, auto-flow forced to 1x1
- [Phase 9]: Grid overlap detection via occupancy matrix in config validation
- [Phase 9]: NotificationMsg 248 bytes (32+100+116) fits ESP-NOW 250-byte limit
- [Phase 9]: Notifications disabled by default, opt-in via notifications_enabled config flag
- [Phase 9]: Empty notification_filter = forward ALL notifications
- [Phase 9]: Toast overlay replaces previous (no stacking) to prevent LVGL memory leaks
- [Phase 9]: D-Bus session bus eavesdrop via AddMatch for Notify method calls
- [Phase 10]: Identity-based button press (page+widget index) instead of keystroke-based
- [Phase 10]: Static ButtonEventData pool (CONFIG_MAX_WIDGETS entries) for LVGL event user_data
- [Phase 10]: VALID_ACTION_TYPES tuple for centralized action type validation
- [Phase 10]: Keep legacy MSG_HOTKEY/MSG_MEDIA_KEY handlers for backward compat
- [Phase 10]: ydotool preferred over xdotool with automatic fallback -- supports Wayland natively
- [Phase 10]: watchdog optional dependency with graceful degradation for config auto-reload
- [Phase 10]: Action execution on separate daemon threads -- never blocks vendor read or stats loop
- [Phase 10]: NoScrollComboBox replaces all QComboBox in editor to prevent scroll wheel hijacking
- [Phase 10]: Lazy-load app picker on first use of Launch App action type
- [Phase 10]: Test Action fires on background thread to avoid UI freeze
- [Phase 11]: PCF8575 auto-detected at 0x20-0x27 on TCA9548A channel 0 -- graceful degradation if absent
- [Phase 11]: Active LOW pin logic for buttons (pressed = bit 0)
- [Phase 11]: Encoder switch in app-select mode fires focused widget; normal mode uses push_action config
- [Phase 11]: Config.json protected from deletion via HTTP API (403 Forbidden)
- [Phase 11]: PropertiesPanel dual mode: canvas widget mode vs hardware input mode
- [Phase 11]: Settings accessed via toggle button in page toolbar with QStackedWidget view swap

### Pending Todos

*(No pending todos -- Phase 11 completed all hardware button/encoder/settings requirements)*

### Roadmap Evolution

- Phase 10 added: Companion Action Execution
- Phase 11 added: Hardware Buttons + System Actions

### Blockers/Concerns

- [Research]: WiFi channel pinning needs hardware test (ESP-NOW packet loss during HTTP transfer) -- implemented but untested on hardware
- [Research]: BMP icon format validation deferred to v2 (LVGL symbols only for v1.1)

## Session Continuity

Last session: 2026-02-16
Stopped at: Completed Phase 11 (all 4 plans: config model, PCF8575 driver, companion config/editor, settings tab)
Resume file: None
