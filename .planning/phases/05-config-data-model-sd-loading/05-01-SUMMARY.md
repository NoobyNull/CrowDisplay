---
phase: 05-config-data-model-sd-loading
plan: 01
subsystem: config
tags: [arduinojson, sd-card, psram, esp32-s3, json]

requires:
  - phase: 04
    provides: "Working display firmware with SD card module and hardcoded hotkey UI"
provides:
  - "ArduinoJson v7 dependency in platformio.ini"
  - "Config version field (uint8_t) in AppConfig struct and JSON schema"
  - "PSRAM-allocated JSON parse buffers (64KB off stack)"
  - "Backup-before-overwrite: config.json.bak auto-created on save"
  - "Atomic save: write to config.tmp then rename to config.json"
  - "Page count validation (1-16 per profile)"
  - "sdcard_file_remove() utility function"
  - "Const-correct get_active_profile() overload"
affects: [06-data-driven-display-ui, 07-config-server]

tech-stack:
  added: [ArduinoJson v7.4.0]
  patterns: [PSRAM-allocated buffers for large JSON, atomic file writes via temp+rename, backup-before-overwrite]

key-files:
  created: []
  modified:
    - platformio.ini
    - display/config.h
    - display/config.cpp
    - display/config_server.cpp
    - display/sdcard.h
    - display/sdcard.cpp
    - display/ui.cpp

key-decisions:
  - "Used ps_malloc() for all JSON parse/backup buffers to keep 64KB allocations in PSRAM"
  - "FAT rename requires explicit remove of target first (sdcard_file_remove before sdcard_file_rename)"
  - "Config version mismatch logs warning but still loads (forward compatibility)"
  - "Replaced raw string literal delimiter R\"(\" with R\"rawliteral(\" to avoid premature termination by onclick handlers"

patterns-established:
  - "PSRAM allocation: use ps_malloc() for any buffer >4KB, free() when done"
  - "Atomic SD writes: write to .tmp, remove old, rename .tmp to final"
  - "ArduinoJson v7 API: JsonDocument (no Static/Dynamic), .isNull() not containsKey(), .to<JsonArray>() not createNestedArray()"

duration: 5min
completed: 2026-02-15
---

# Plan 05-01: Config Data Model + SD Loading Summary

**ArduinoJson v7 migration with PSRAM buffers, schema versioning, backup-before-overwrite, and atomic save pattern for SD card config persistence**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-15
- **Completed:** 2026-02-15
- **Tasks:** 3 (combined into single commit due to tight coupling)
- **Files modified:** 7

## Accomplishments
- Migrated entire config system from ArduinoJson v6 to v7 API (zero StaticJsonDocument/containsKey/createNestedArray remnants)
- Config save now backs up existing config.json to config.json.bak before any write
- Atomic write pattern: write to /config.tmp, remove old /config.json, rename tmp to final
- Post-save verification: re-reads and parses written file, restores from backup on failure
- Page count validated to 1-16 range with truncation warning
- Load summary logging: version, page count, total buttons printed to serial

## Task Commits

All three tasks were tightly coupled (same files) and committed together:

1. **Task 1: ArduinoJson v7 migration + PSRAM + version field** - `eac08ab` (feat)
2. **Task 2: Backup-before-overwrite + atomic save** - included in `eac08ab`
3. **Task 3: Page validation + logging + dead code removal** - included in `eac08ab`

## Files Created/Modified
- `platformio.ini` - Added bblanchon/ArduinoJson@^7.4.0 to display lib_deps
- `display/config.h` - Added CONFIG_VERSION, CONFIG_MAX_PAGES, CONFIG_MAX_BUTTONS defines; version field in AppConfig; const get_active_profile() overload
- `display/config.cpp` - Full v7 API migration, PSRAM buffers, version read/write, backup + atomic save, page validation, load summary logging, removed dead config_init()
- `display/config_server.cpp` - v7 API migration (JsonDocument), ps_malloc for upload buffer, fixed raw string literal delimiter, removed redundant read-back validation buffer
- `display/sdcard.h` - Added sdcard_file_remove() declaration
- `display/sdcard.cpp` - Implemented sdcard_file_remove() using SD.remove()
- `display/ui.cpp` - Fixed rebuild_ui() to delete+recreate tabview (LVGL 8.3 has no lv_tabview_remove_tab)

## Decisions Made
- Combined all 3 tasks into single commit because Task 2 and 3 modify the same functions in config.cpp that Task 1 rewrites
- Fixed LV_SYMBOL_BELL_MUTE (doesn't exist in LVGL 8.3) to LV_SYMBOL_MUTE
- Fixed raw string literal `R"(...)"` to `R"rawliteral(...)rawliteral"` because HTML onclick handlers contain `)"` which prematurely terminated the string
- Fixed HTTPUpload.contentLength (doesn't exist in ESP32 WebServer) by removing size logging from upload start

## Deviations from Plan

### Auto-fixed Issues

**1. Pre-existing build errors in config_server.cpp**
- **Found during:** Task 1 (compilation)
- **Issue:** Raw string literal terminated early by `onclick="uploadConfig()"` containing `)"`, and HTTPUpload has no contentLength member
- **Fix:** Changed delimiter to `rawliteral`, removed contentLength references
- **Files modified:** display/config_server.cpp
- **Verification:** Clean compilation

**2. Pre-existing build error: LV_SYMBOL_BELL_MUTE**
- **Found during:** Task 1 (compilation)
- **Issue:** LV_SYMBOL_BELL_MUTE not defined in LVGL 8.3.11
- **Fix:** Replaced with LV_SYMBOL_MUTE
- **Files modified:** display/config.cpp
- **Verification:** Clean compilation

**3. Pre-existing build error: lv_tabview_remove_tab**
- **Found during:** Task 1 (compilation)
- **Issue:** LVGL 8.3 has no lv_tabview_remove_tab API
- **Fix:** Delete entire tabview and recreate on rebuild
- **Files modified:** display/ui.cpp
- **Verification:** Clean compilation

**4. Missing includes in config.cpp**
- **Found during:** Task 1 (compilation)
- **Issue:** config.cpp uses LV_SYMBOL_* and MOD_* but didn't include lvgl.h or protocol.h
- **Fix:** Added #include <lvgl.h> and #include "protocol.h"
- **Files modified:** display/config.cpp
- **Verification:** Clean compilation

---

**Total deviations:** 4 auto-fixed (4 blocking build errors)
**Impact on plan:** All fixes necessary for compilation. No scope creep.

## Issues Encountered
None beyond the pre-existing build issues documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Config system compiles and satisfies all CFG-01 through CFG-08 requirements
- Phase 6 (Data-Driven Display UI) can now build on the config struct and JSON I/O
- Widget-pool pattern for dynamic UI reload still needs Phase 6 prototyping

---
*Phase: 05-config-data-model-sd-loading*
*Completed: 2026-02-15*
