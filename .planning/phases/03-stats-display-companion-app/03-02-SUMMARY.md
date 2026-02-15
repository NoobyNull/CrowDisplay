---
phase: 03-stats-display-companion-app
plan: 02
subsystem: firmware
tags: [lvgl, esp-now, hyprland, consumer-control, stats-display, esp32-s3]

# Dependency graph
requires:
  - phase: 01-wired-hotkey-foundation
    provides: "Display UI framework, ESP-NOW link, LVGL tabview"
  - phase: 03-01
    provides: "MSG_STATS, MSG_MEDIA_KEY protocol types, StatsPayload struct, bridge composite USB HID"
provides:
  - "Hyprland-specific hotkey pages (Windows/System/Media)"
  - "Media key buttons sending MSG_MEDIA_KEY consumer control codes"
  - "Persistent 2-row stats header with 8 system metric labels"
  - "update_stats() for rendering StatsPayload data"
  - "espnow_poll_msg() for generic message reception on display"
  - "Auto-show/hide stats header based on companion activity"
affects: [03-03, 03-04, display-ui, companion-app]

# Tech tracking
tech-stack:
  added: []
  patterns: [stats-header-auto-visibility, media-key-dispatch, generic-espnow-poll]

key-files:
  modified:
    - display/ui.h
    - display/ui.cpp
    - display/espnow_link.h
    - display/espnow_link.cpp
    - display/main.cpp

key-decisions:
  - "Stats header hidden by default, auto-shows on first MSG_STATS, auto-hides after 5s timeout"
  - "Tabview dynamically resizes when stats header appears/disappears"
  - "Generic espnow_poll_msg() queues non-ACK messages separately from ACK path"

patterns-established:
  - "Media keys use is_media flag in Hotkey struct to dispatch via send_media_key_to_bridge()"
  - "Stats timeout handled in main loop (5s), not in UI layer"

# Metrics
duration: 4min
completed: 2026-02-15
---

# Phase 3 Plan 2: Display UI Rework Summary

**Hyprland hotkey pages with live stats header, media key dispatch, and MSG_STATS reception over ESP-NOW**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-15T08:57:00Z
- **Completed:** 2026-02-15T09:01:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Replaced all 3 hotkey pages with Hyprland-specific shortcuts (Windows, System, Media)
- Added persistent 2-row stats header with 8 labeled metrics (CPU/RAM/GPU %, temps, network, disk)
- Media buttons on Page 3 send consumer control codes via MSG_MEDIA_KEY
- Display receives and renders live system stats from companion app via ESP-NOW

## Task Commits

Each task was committed atomically:

1. **Task 1: Rework hotkey pages for Hyprland and add media key support** - `c33949f` (feat)
2. **Task 2: Wire MSG_STATS reception into display main loop** - `28f88e7` (feat)

## Files Created/Modified
- `display/ui.h` - Added update_stats() and hide_stats_header() declarations
- `display/ui.cpp` - Complete rework: Hyprland pages, stats header, media key dispatch
- `display/espnow_link.h` - Added send_media_key_to_bridge() and espnow_poll_msg() declarations
- `display/espnow_link.cpp` - Implemented media key send, generic message polling with separate queue
- `display/main.cpp` - MSG_STATS polling, update_stats() dispatch, 5s stats timeout

## Decisions Made
- Stats header starts hidden and auto-shows on first MSG_STATS -- maximizes button space when companion is not running
- Tabview height dynamically adjusts (435px with stats, 480-45=435px without) to accommodate header
- Generic espnow_poll_msg() uses a separate buffer from ACK polling to avoid interference
- Stats timeout (5s) handled in main.cpp loop rather than UI layer for cleaner separation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Display firmware compiles clean: RAM 44.2%, Flash 76.7%
- Stats header ready to render StatsPayload from companion app (03-03/03-04)
- Media keys ready for bridge to dispatch consumer control codes
- All 36 buttons functional across 3 Hyprland-specific pages

## Self-Check: PASSED

All 5 modified files verified on disk. Both task commits (c33949f, 28f88e7) verified in git log.

---
*Phase: 03-stats-display-companion-app*
*Completed: 2026-02-15*
