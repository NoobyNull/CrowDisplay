---
phase: 04-battery-management-power-states
plan: 01
subsystem: firmware
tags: [max17048, battery, power-states, brightness, i2c, esp32-s3]

# Dependency graph
requires:
  - phase: 01-hardware-bringup
    provides: "I2C mutex (i2c_take/i2c_give), display_hw LCD init, LovyanGFX panel"
provides:
  - "MSG_POWER_STATE (0x05) and MSG_TIME_SYNC (0x06) protocol messages"
  - "BatteryState struct with battery_init()/battery_read() API"
  - "PowerState enum with ACTIVE/DIMMED/CLOCK state machine"
  - "set_backlight()/get_backlight() brightness wrappers"
  - "power_cycle_brightness() user brightness presets"
affects: [04-02, 04-03, 04-04]

# Tech tracking
tech-stack:
  added: [SparkFun MAX1704x Fuel Gauge Arduino Library]
  patterns: [power-state-machine, idle-timeout-dimming, mutex-protected-i2c-sensor]

key-files:
  created:
    - display/battery.h
    - display/battery.cpp
    - display/power.h
    - display/power.cpp
  modified:
    - shared/protocol.h
    - display/display_hw.h
    - display/display_hw.cpp
    - platformio.ini

key-decisions:
  - "Battery uses i2c_take/i2c_give helpers (not raw xSemaphoreTake) for consistency with touch module"
  - "User brightness presets (255/180/100) tracked separately from state-machine brightness for proper wake restore"
  - "TimeSyncMsg field named epoch_seconds (uint32_t) matching plan spec"

patterns-established:
  - "Power state machine: ACTIVE->DIMMED on idle, any->CLOCK on shutdown, CLOCK->ACTIVE on wake"
  - "Sensor modules use i2c_take/i2c_give with 50ms timeout for bus sharing"

# Metrics
duration: 2min
completed: 2026-02-15
---

# Phase 4 Plan 1: Protocol Extension + Battery + Power State Machine Summary

**MAX17048 battery fuel gauge with I2C mutex, three-state power machine (ACTIVE/DIMMED/CLOCK), and brightness wrappers using LovyanGFX**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-15T16:07:44Z
- **Completed:** 2026-02-15T16:10:19Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Extended protocol with MSG_POWER_STATE (0x05) and MSG_TIME_SYNC (0x06) including packed payload structs
- Battery module reads MAX17048 fuel gauge over I2C with graceful degradation when no gauge present
- Power state machine handles idle dimming (60s timeout), PC shutdown (clock mode), and wake transitions
- Brightness API (set_backlight/get_backlight) wrapping lcd.setBrightness() with user-selectable presets

## Task Commits

Each task was committed atomically:

1. **Task 1: Protocol extension + battery module** - `025a5fd` (feat)
2. **Task 2: Power state machine + brightness wrappers** - `7fe4f07` (feat)

## Files Created/Modified
- `shared/protocol.h` - Added MSG_POWER_STATE, MSG_TIME_SYNC, PowerStateMsg, TimeSyncMsg, POWER_SHUTDOWN/WAKE defines
- `display/battery.h` - BatteryState struct, battery_init()/battery_read() declarations
- `display/battery.cpp` - MAX17048 fuel gauge polling with i2c_take/i2c_give mutex protection
- `display/power.h` - PowerState enum (ACTIVE/DIMMED/CLOCK), power lifecycle functions
- `display/power.cpp` - State machine with idle timeout, shutdown/wake transitions, brightness cycling
- `display/display_hw.h` - Added set_backlight()/get_backlight() declarations
- `display/display_hw.cpp` - Brightness wrapper implementations using lcd.setBrightness()
- `platformio.ini` - Added SparkFun MAX1704x library to env:display lib_deps

## Decisions Made
- Battery module uses i2c_take/i2c_give helpers (matching touch.h pattern) rather than raw FreeRTOS semaphore calls
- User brightness presets tracked in separate variable so wake-from-dimmed restores user's chosen brightness, not default
- TimeSyncMsg uses epoch_seconds field name per plan spec

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Protocol types ready for 04-02 (UI clock/battery display) and 04-03 (bridge message handling)
- Battery module ready for periodic polling integration in main loop
- Power state machine ready for touch/message event hookup
- Brightness API available for UI brightness control buttons

## Self-Check: PASSED

All 8 files verified present. Both task commits (025a5fd, 7fe4f07) verified in git history.

---
*Phase: 04-battery-management-power-states*
*Completed: 2026-02-15*
