---
phase: 01-wired-command-foundation
plan: 01
subsystem: firmware
tags: [platformio, esp32-s3, lvgl, lovyangfx, freertos-mutex, i2c, gt911, crc8, uart-protocol]

# Dependency graph
requires: []
provides:
  - "Multi-env PlatformIO build (env:display + env:bridge)"
  - "SOF-framed binary protocol with CRC8/CCITT (shared/protocol.h)"
  - "Display firmware skeleton with LovyanGFX + LVGL + I2C mutex-protected GT911 touch"
  - "Bridge firmware skeleton that compiles for ESP32-S3 DevKitC-1"
  - "I2C mutex helpers (i2c_take/i2c_give) for shared bus access"
affects: [01-02, 01-03, 01-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [build_src_filter multi-env, FreeRTOS mutex for I2C, header-only shared protocol]

key-files:
  created:
    - shared/protocol.h
    - display/main.cpp
    - display/display_hw.h
    - display/display_hw.cpp
    - display/touch.h
    - display/touch.cpp
    - bridge/main.cpp
  modified:
    - platformio.ini

key-decisions:
  - "Used build_src_filter instead of src_dir for multi-env builds (PlatformIO does not support per-env src_dir)"
  - "Moved lib_deps for LovyanGFX/LVGL to display env only (bridge has no display dependencies)"
  - "Init order: Wire -> touch_init(mutex) -> display_init(PCA9557+LCD) -> gt911_discover -> lvgl_init"

patterns-established:
  - "build_src_filter: Each firmware env uses +<dir/> to select source tree"
  - "I2C mutex: All Wire operations wrapped in i2c_take()/i2c_give() from touch.h"
  - "Header-only shared protocol: shared/protocol.h uses static/inline, compiles in both targets"

# Metrics
duration: 5min
completed: 2026-02-15
---

# Phase 1 Plan 1: Project Structure Summary

**Dual-firmware PlatformIO project with SOF+CRC8 binary protocol, LovyanGFX display driver, and FreeRTOS mutex-protected GT911 touch polling**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-15T07:04:51Z
- **Completed:** 2026-02-15T07:09:27Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Restructured monolithic project into dual-firmware architecture (display + bridge) with shared protocol header
- Implemented SOF-framed binary protocol with CRC8/CCITT lookup table, packed message structs, and modifier masks
- Ported LovyanGFX LGFX class, LVGL driver registration, and GT911 touch polling from src/main.cpp into modular display firmware
- Added FreeRTOS mutex protection around all I2C bus operations (DISP-12 requirement satisfied)
- Both firmware targets compile cleanly (display: 508KB flash / 120KB RAM, bridge: 264KB flash / 19KB RAM)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create multi-env platformio.ini and shared protocol header** - `b39f8c6` (feat)
2. **Task 2: Create display and bridge firmware skeletons with I2C mutex** - `30df4de` (feat)

## Files Created/Modified
- `platformio.ini` - Multi-env build config with build_src_filter for display/ and bridge/
- `shared/protocol.h` - SOF-framed binary protocol with CRC8/CCITT, HotkeyMsg/HotkeyAckMsg structs, modifier masks
- `display/main.cpp` - Display firmware entry point with correct init ordering
- `display/display_hw.h` - Public API: display_init(), lvgl_init(), lvgl_tick()
- `display/display_hw.cpp` - LovyanGFX LGFX class (CrowPanel 7.0" RGB565), PCA9557 touch reset, LVGL buffer/driver setup
- `display/touch.h` - Public API: touch_init(), gt911_discover(), touch_poll(), i2c_take/give
- `display/touch.cpp` - GT911 I2C touch driver with full FreeRTOS mutex wrapping
- `bridge/main.cpp` - Bridge firmware skeleton including shared protocol.h

## Decisions Made
- **build_src_filter over src_dir:** PlatformIO's `src_dir` is a project-level option in `[platformio]`, not per-env. Used `build_src_filter = +<display/>` and `+<bridge/>` with `src_dir = .` in `[platformio]` section instead.
- **Library deps per-env:** Moved LovyanGFX and LVGL lib_deps from base `[env]` to `[env:display]` only. Bridge has no display library dependencies, avoiding LDF conflicts.
- **gt911_discover() as separate step:** Exposed publicly in touch.h and called from main.cpp after display_init(), because PCA9557 must reset GT911 before discovery can succeed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] PlatformIO src_dir is not per-environment**
- **Found during:** Task 2 (compilation verification)
- **Issue:** Plan specified `src_dir = display` and `src_dir = bridge` in per-env sections. PlatformIO ignores unknown per-env options silently, causing bridge to compile src/main.cpp (which requires LovyanGFX).
- **Fix:** Used `[platformio] src_dir = .` globally and `build_src_filter = +<display/>` / `+<bridge/>` per-env to select source directories.
- **Files modified:** platformio.ini
- **Verification:** Both `pio run -e display` and `pio run -e bridge` compile successfully
- **Committed in:** 30df4de (Task 2 commit)

**2. [Rule 3 - Blocking] Bridge inheriting display lib_deps caused LDF conflicts**
- **Found during:** Task 2 (compilation verification)
- **Issue:** Base `[env]` had LovyanGFX and LVGL in lib_deps. Even with `lib_ignore`, the `-I src` flag in base build_flags caused LDF to scan src/main.cpp and find LovyanGFX dependency.
- **Fix:** Moved lib_deps, `-DLV_CONF_INCLUDE_SIMPLE`, and `-I src` from base `[env]` to `[env:display]` only.
- **Files modified:** platformio.ini
- **Verification:** Bridge compiles without any display library errors
- **Committed in:** 30df4de (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking issues)
**Impact on plan:** Both fixes were necessary to achieve the plan's core goal of dual-firmware compilation. The build_src_filter approach is the correct PlatformIO pattern for multi-target embedded projects.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Display and bridge firmware skeletons compile and are ready for UART link (Plan 02)
- I2C mutex is in place for safe concurrent bus access
- Shared protocol header defines message types for hotkey delivery
- Bridge is a minimal skeleton awaiting USB HID and UART receive code

---
*Phase: 01-wired-command-foundation*
*Completed: 2026-02-15*

## Self-Check: PASSED

All 8 files verified present. Both commit hashes (b39f8c6, 30df4de) confirmed in git log.
