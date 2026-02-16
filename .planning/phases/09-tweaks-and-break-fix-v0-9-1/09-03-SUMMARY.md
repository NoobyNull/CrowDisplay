---
phase: 09-tweaks-and-break-fix-v0-9-1
plan: 03
subsystem: ui, protocol, companion
tags: [tlv, stats, lvgl, psutil, pynvml, pyside6, configurable-header]

# Dependency graph
requires:
  - phase: 03-stats-display-companion-app
    provides: original stats streaming and header rendering
  - phase: 08-desktop-gui-editor
    provides: PySide6 editor framework
  - phase: 05-config-data-model-sd-loading
    provides: AppConfig JSON schema and SD card persistence
provides:
  - TLV stats protocol (StatType enum, encode/decode)
  - Configurable stats_header in AppConfig JSON schema
  - Dynamic LVGL stats header from config (up to 8 stats, colored labels)
  - Stats header configuration panel in desktop editor
  - 20 system metric types (CPU, RAM, GPU, temps, network, disk, swap, battery, etc.)
affects: [companion-app, display-ui, config-schema]

# Tech tracking
tech-stack:
  added: [pynvml]
  patterns: [TLV binary protocol, first-byte heuristic format detection, config-driven widget generation]

key-files:
  created: []
  modified:
    - shared/protocol.h
    - display/config.h
    - display/config.cpp
    - display/ui.cpp
    - display/ui.h
    - display/main.cpp
    - companion/hotkey_companion.py
    - companion/ui/editor_main.py
    - companion/config_manager.py
    - companion/requirements.txt

key-decisions:
  - "TLV with first-byte heuristic for backward compatibility (count byte <= 0x14 = TLV, > 0x14 = legacy StatsPayload)"
  - "Max 8 configurable stats with position-based ordering for display layout"
  - "pynvml for extended GPU metrics (memory, power, frequency) beyond basic percent"

patterns-established:
  - "TLV protocol pattern: count byte + [type, length, value...] for extensible binary messages"
  - "Config-driven LVGL widget generation: iterate config array to create labeled flex-row elements"

# Metrics
duration: ~45min
completed: 2026-02-15
---

# Phase 9 Plan 3: Configurable Stats Header with TLV Protocol Summary

**Replaced fixed 8-stat header with user-configurable stats (20 types) using TLV binary protocol and editor panel**

## Performance

- **Duration:** ~45 min
- **Tasks:** 4
- **Files modified:** 10

## Accomplishments
- Defined TLV stats protocol with 20 StatType values covering CPU, RAM, GPU, temps, network, disk I/O, swap, uptime, battery, fan RPM, and more
- Implemented config-driven dynamic stats header rendering in LVGL with colored labels and auto row-splitting
- Added TLV encoding in companion with conditional collection (only enabled stat types collected)
- Built StatsHeaderPanel in PySide6 editor with type/color/position table, color pickers, reorder buttons, and live preview

## Task Commits

Each task was committed atomically:

1. **Task 1: Define TLV stats protocol** - `698af09` (feat)
2. **Task 2: Stats header config schema + TLV encoding** - `1a66aa2` (feat)
3. **Task 3: Dynamic stats header rendering + TLV decoding** - `c0a6274` (feat)
4. **Task 4: Stats header configuration panel in editor** - `881739a` (feat)

## Files Created/Modified
- `shared/protocol.h` - StatType enum (20 types), tlv_decode_stats() inline helper, legacy StatsPayload marked
- `display/config.h` - StatConfig struct, CONFIG_MAX_STATS, stats_header vector in AppConfig
- `display/config.cpp` - JSON parse/serialize of stats_header with 8 sensible defaults
- `display/ui.cpp` - Dynamic stats header creation from config, TLV decoding callback, format helpers
- `display/ui.h` - Changed update_stats signature to raw bytes (TLV-aware)
- `display/main.cpp` - Updated MSG_STATS dispatch to pass raw payload
- `companion/hotkey_companion.py` - TLV encoding, 20 metric collectors, config-driven stat selection
- `companion/ui/editor_main.py` - StatsHeaderPanel widget with table editor and live preview
- `companion/config_manager.py` - stats_header validation (type 1-20, max 8 entries, unique positions)
- `companion/requirements.txt` - Added pynvml dependency

## Decisions Made
- Used first-byte heuristic for TLV vs legacy format detection: data[0] <= 0x14 means TLV (count of stats), > 0x14 means legacy StatsPayload (cpu_percent typically 21-100). This provides seamless backward compatibility.
- Limited to 8 configurable stats (CONFIG_MAX_STATS) to fit the display header width reasonably on the 320px screen.
- Added pynvml for extended GPU stats beyond basic utilization percent (memory usage, power draw, clock frequency).
- Conditional collection: companion only calls collectors for enabled stat types, avoiding unnecessary system calls.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed corrupt .sconsign314.dblite build artifact**
- **Found during:** Task 3 (PlatformIO build)
- **Issue:** PIO build failed with FileNotFoundError for .sconsign314.tmp due to empty/corrupt .sconsign314.dblite
- **Fix:** Removed the file and rebuilt
- **Files modified:** .pio/build/display/.sconsign314.dblite (deleted)
- **Verification:** Build succeeded after removal

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal - stale build artifact, no code changes needed.

## Issues Encountered
None beyond the build artifact issue noted in deviations.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Stats protocol is extensible: new StatType values can be added (up to 0xFF) without protocol changes
- Editor panel ready for use; companion streams TLV automatically when stats_header present in config
- Legacy companion without TLV will still work (display auto-detects format)

---
*Phase: 09-tweaks-and-break-fix-v0-9-1*
*Completed: 2026-02-15*

## Self-Check: PASSED
- All 10 key files verified present
- All 4 task commit hashes verified in git log
