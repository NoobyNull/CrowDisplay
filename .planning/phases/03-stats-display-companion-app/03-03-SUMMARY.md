---
phase: 03-stats-display-companion-app
plan: 03
subsystem: companion
tags: [python, hidapi, psutil, pynvml, systemd, udev, hid-output-report]

# Dependency graph
requires:
  - phase: 03-stats-display-companion-app
    plan: 01
    provides: "USBHIDVendor on bridge accepts 63-byte output reports, StatsPayload struct in protocol.h"
provides:
  - "Python companion app that collects CPU/RAM/GPU/temps/network/disk and streams to bridge"
  - "StatsPayload binary packing matching shared/protocol.h layout"
  - "Auto-detection of bridge by VID 0x303A and product string HotkeyBridge"
  - "Systemd user service for auto-start on login"
  - "Udev rule for non-root HID access"
affects: [03-04, display-stats-header]

# Tech tracking
tech-stack:
  added: [hidapi, psutil, pynvml, python3]
  patterns: [hid-output-report-streaming, delta-network-stats, gpu-fallback-chain]

key-files:
  created:
    - companion/hotkey_companion.py
    - companion/requirements.txt
    - companion/hotkey-companion.service
    - companion/99-hotkey-bridge.rules

key-decisions:
  - "Python with hidapi chosen for companion (per user discretion and research recommendation)"
  - "GPU detection: NVIDIA via pynvml, AMD via sysfs, graceful 0xFF fallback"
  - "Network stats use delta calculation with time-based KB/s rate"
  - "Leading 0x00 report ID byte for hidapi Linux HID writes"

patterns-established:
  - "GPUCollector class initialized once at startup, not per-loop"
  - "Auto-reconnect loop on HID device disconnect"
  - "psutil.cpu_percent() primed once before main loop"

# Metrics
duration: 2min
completed: 2026-02-15
---

# Phase 3 Plan 3: Python Companion App Summary

**Python companion streams CPU/RAM/GPU/temps/network/disk to bridge via hidapi HID output reports at 1 Hz with NVIDIA/AMD/fallback GPU support**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-15T08:57:00Z
- **Completed:** 2026-02-15T08:58:46Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created single-file Python companion that collects all 8 required system metrics
- Auto-detects bridge by Espressif VID and product string, with vendor usage page preference
- Packs 10-byte StatsPayload matching shared/protocol.h struct layout exactly
- GPU support chain: NVIDIA (pynvml) -> AMD (sysfs) -> graceful 0xFF fallback
- Network stats use proper delta calculation for KB/s rate (not cumulative bytes)
- Systemd user service and udev rules ready for deployment

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Python companion app with stats collection and HID output** - `a335447` (feat)
2. **Task 2: Create systemd service and udev rules** - `6cce1fc` (feat)

## Files Created/Modified
- `companion/hotkey_companion.py` - Main companion app: stats collection, HID streaming, auto-reconnect
- `companion/requirements.txt` - Python dependencies: hidapi, psutil, pynvml
- `companion/hotkey-companion.service` - Systemd user service with restart-on-failure
- `companion/99-hotkey-bridge.rules` - Udev rule granting non-root hidraw access via uaccess tag

## Decisions Made
- Python with hidapi chosen as companion language (matches research recommendation and user discretion)
- GPU detection initializes once at startup via GPUCollector class (NVIDIA -> AMD -> None)
- Network delta uses time-based calculation: (bytes_now - bytes_prev) / dt / 1024
- Leading 0x00 byte prepended to HID write for Linux hidapi report ID convention
- Struct format `<BBBBBBhh` maps exactly to StatsPayload packed layout

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

External services require manual configuration:

**Udev rule (non-root HID access):**
```bash
sudo cp companion/99-hotkey-bridge.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

**Systemd user service (auto-start):**
```bash
mkdir -p ~/.config/systemd/user
cp companion/hotkey-companion.service ~/.config/systemd/user/
# Edit ExecStart path in service file to match your installation
systemctl --user daemon-reload
systemctl --user enable --now hotkey-companion
```

**Python dependencies:**
```bash
pip install -r companion/requirements.txt
```

## Next Phase Readiness
- Companion app ready to stream stats to bridge once hardware is connected
- Bridge (03-01) already accepts vendor HID reports and relays via ESP-NOW
- Display stats header UI (03-02) and hotkey page rework (03-04) can proceed independently

---
*Phase: 03-stats-display-companion-app*
*Completed: 2026-02-15*

## Self-Check: PASSED

All 4 created files verified on disk. Both task commits (a335447, 6cce1fc) verified in git log.
