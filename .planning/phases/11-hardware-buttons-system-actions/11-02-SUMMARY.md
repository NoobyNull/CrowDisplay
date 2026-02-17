---
phase: 11-hardware-buttons-system-actions
plan: 02
subsystem: firmware
tags: [pcf8575, i2c, quadrature-encoder, sd-card, http-api, tca9548a]

requires:
  - phase: 11-hardware-buttons-system-actions
    provides: ActionType enum (8-13), HwButtonConfig, EncoderConfig, config JSON serialization
provides:
  - PCF8575 hardware input driver with auto-detect via TCA9548A mux
  - Quadrature encoder decoder with gray code transition table
  - Button debounce (50ms) and configurable action dispatch
  - App-select encoder mode with LVGL widget focus management
  - SD card management HTTP endpoints (usage, listing, deletion)
  - sdcard_list_dir() and sdcard_get_usage() helpers
affects: [11-03, 11-04]

tech-stack:
  added: []
  patterns: [pcf8575-mux-read, quadrature-gray-code, i2c-mutex-discipline]

key-files:
  created:
    - display/hw_input.h
    - display/hw_input.cpp
  modified:
    - display/main.cpp
    - display/ui.h
    - display/ui.cpp
    - display/config_server.cpp
    - display/sdcard.h
    - display/sdcard.cpp
    - display/rotary_encoder.h
    - display/rotary_encoder.cpp

key-decisions:
  - "PCF8575 auto-detected at 0x20-0x27 on TCA9548A channel 0 -- graceful degradation if absent"
  - "Active LOW pin logic for buttons (pressed = bit 0)"
  - "Encoder switch in app-select mode fires focused widget; normal mode uses push_action config"
  - "Config.json protected from deletion via HTTP API (403 Forbidden)"
  - "ui_get_widget_obj() uses lv_obj_get_child for LVGL child traversal"

patterns-established:
  - "I2C mutex wrapping: take -> mux select -> device read -> mux deselect -> give"
  - "Hardware button page 0xFF signals hardware source to companion"

requirements-completed: [HW-PCF8575-DRIVER, HW-ENCODER-QUAD, HW-SD-API, HW-APP-SELECT]

duration: 8min
completed: 2026-02-16
---

# Plan 11-02: PCF8575 Driver + SD Card API Summary

**PCF8575 hardware input driver with quadrature encoder, I2C mux auto-detect, and SD card management HTTP API**

## Performance

- **Duration:** 8 min
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- PCF8575 auto-detected via TCA9548A mux channel 0 with full I2C mutex discipline
- 4 hardware buttons debounced at 50ms, encoder quadrature decoded with gray code table
- Encoder rotation dispatches based on config mode (page nav, volume, brightness, app-select, mode cycle)
- App-select mode highlights focused widget with gold border, push fires its action
- SD card HTTP API: GET usage, GET listing, POST delete with config.json protection
- Old rotary_encoder module completely replaced

## Task Commits

1. **Task 1: hw_input module + rotary_encoder replacement** - `bba9ac4` (feat)
2. **Task 2: SD card HTTP endpoints** - `d4d300c` (feat)

## Files Created/Modified
- `display/hw_input.h` - PCF8575 polling API declarations
- `display/hw_input.cpp` - Full hardware input driver implementation
- `display/main.cpp` - Replaced encoder_init/poll with hw_input_init/poll
- `display/ui.h` - Added ui_get_widget_obj() and lvgl include
- `display/ui.cpp` - ui_get_widget_obj() implementation
- `display/config_server.cpp` - SD card management HTTP endpoints
- `display/sdcard.h` - sdcard_list_dir() and sdcard_get_usage() declarations
- `display/sdcard.cpp` - Directory listing and usage stats implementations
- `display/rotary_encoder.h` - Replaced with stub
- `display/rotary_encoder.cpp` - Replaced with stub

## Decisions Made
- PCF8575 address auto-detected (0x20-0x27) for hardware flexibility
- lv_obj_get_child() used for widget access instead of separate tracking array
- ui.h now includes lvgl.h for lv_obj_t return type

## Deviations from Plan
None - plan executed as written

## Issues Encountered
- ui.h needed lvgl.h include for lv_obj_t return type in ui_get_widget_obj()

## Next Phase Readiness
- Hardware input ready for companion config editor (11-03)
- SD card API ready for Settings tab file manager (11-04)

---
*Phase: 11-hardware-buttons-system-actions*
*Completed: 2026-02-16*
