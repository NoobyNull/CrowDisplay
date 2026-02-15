# Requirements: CrowPanel Command Center

**Defined:** 2026-02-14
**Core Value:** Tap a button on the display, the correct keyboard shortcut fires on the PC — reliably, with minimal latency, whether connected by wire or wirelessly.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Communication

- [ ] **COMM-01**: Display and bridge communicate bidirectionally over UART (GPIO 10/11 on display, dedicated pins on bridge)
- [ ] **COMM-02**: Display and bridge communicate bidirectionally over ESP-NOW (point-to-point, no router)
- [ ] **COMM-03**: Both links use a shared binary protocol with SOF framing, message types, and CRC8 validation
- [ ] **COMM-04**: Transport abstraction layer provides single send/receive API regardless of active link
- [ ] **COMM-05**: Dual-link failover: if UART disconnected, traffic routes over ESP-NOW automatically (and vice versa)
- [ ] **COMM-06**: Application-layer ACK protocol with sequence numbers and retries (2-3 attempts, 20ms timeout)
- [ ] **COMM-07**: PING/PONG heartbeat monitors link health on both channels
- [ ] **COMM-08**: ESP-NOW configured with no concurrent WiFi, channel pinned, power save disabled

### Bridge Firmware

- [ ] **BRDG-01**: Bridge ESP32-S3 recognized as USB HID keyboard when plugged into PC (no drivers needed)
- [ ] **BRDG-02**: Bridge receives hotkey commands from display and sends corresponding USB HID keystrokes to PC
- [ ] **BRDG-03**: Bridge supports modifier+key combos (Ctrl, Shift, Alt, GUI + any key)
- [ ] **BRDG-04**: Bridge supports media keys via USB consumer control report (play/pause, volume, next/prev, mute)
- [ ] **BRDG-05**: Bridge routes stats data from companion app (USB serial) to display over active transport link
- [ ] **BRDG-06**: Bridge routes config data from companion app to display over active transport link
- [ ] **BRDG-07**: Bridge sends power state signals (PC on/off) to display

### Display UI

- [ ] **DISP-01**: Multi-page hotkey grid with at least 3 pages of 12 buttons (4x3 layout)
- [ ] **DISP-02**: Swipe or tab navigation between hotkey pages
- [ ] **DISP-03**: Visual press feedback on button tap (color darken + shrink animation)
- [ ] **DISP-04**: Per-button color coding by function category
- [ ] **DISP-05**: Button icons (LVGL symbols) and text labels on each button
- [ ] **DISP-06**: Persistent stats header bar at top of screen showing live PC metrics
- [ ] **DISP-07**: Stats header displays CPU usage, RAM usage, GPU usage, network up/down speeds, disk usage
- [ ] **DISP-08**: Stats header displays device status: battery %, ESP-NOW link indicator, brightness control
- [ ] **DISP-09**: Clock mode activates when PC sends shutdown signal: dim screen showing time and battery level
- [ ] **DISP-10**: Display wakes from clock mode when bridge comes online (heartbeat detected)
- [ ] **DISP-11**: Brightness control adjustable from stats header (PWM backlight on GPIO 2)
- [ ] **DISP-12**: I2C bus access wrapped in FreeRTOS mutex to prevent GT911 touch corruption

### Power Management

- [ ] **PWR-01**: Display operates on LiPo battery with USB charging
- [ ] **PWR-02**: Battery voltage monitored and displayed as percentage in stats header
- [ ] **PWR-03**: Power state machine: ACTIVE → DIMMED (idle timeout) → CLOCK_MODE (PC off)
- [ ] **PWR-04**: Display transitions to clock mode on explicit shutdown signal from companion app
- [ ] **PWR-05**: ESP-NOW listener remains active in clock mode for fast wake

### Companion App

- [ ] **COMP-01**: Python desktop app collects live system stats (CPU, RAM, GPU, network, disk) via psutil
- [ ] **COMP-02**: Stats streamed to bridge via USB serial at 1-2 Hz using binary protocol
- [ ] **COMP-03**: Companion app sends explicit shutdown signal before PC powers off (D-Bus integration)
- [ ] **COMP-04**: GUI hotkey editor (GTK4 + PyGObject) for designing button layout, shortcuts, and pages
- [ ] **COMP-05**: Config pushed from GUI editor to display via bridge over active transport
- [ ] **COMP-06**: Companion app reads current config from display for editing

### Configuration

- [ ] **CONF-01**: Hotkey layout persists across power cycles (stored in NVS or LittleFS on display)
- [ ] **CONF-02**: Config format supports variable number of pages with variable number of buttons per page
- [ ] **CONF-03**: Each button config includes: label, icon, modifier mask, key code, color
- [ ] **CONF-04**: Chunked config transfer protocol handles configs larger than 250-byte ESP-NOW payload

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Features

- **ADV-01**: Per-app automatic profile switching (companion app detects active window, switches layout)
- **ADV-02**: Custom bitmap icons per button (user-uploaded, stored in SPIFFS/SD)
- **ADV-03**: OTA firmware updates for both display and bridge units
- **ADV-04**: Macro sequences (multi-step automation from single button press)
- **ADV-05**: Configurable button sizes (1x1, 2x1, 1x2, 2x2 grid units)
- **ADV-06**: Plugin/extension system for companion app

## Out of Scope

| Feature | Reason |
|---------|--------|
| BLE HID connection to PC | Replaced by USB HID on bridge — lower latency, more reliable |
| Web-based configurator on ESP32 | Conflicts with ESP-NOW (WiFi radio contention), wastes ESP32 RAM, inferior UI vs desktop app |
| WiFi connectivity on display | Radio contention destroys ESP-NOW reliability (80%+ packet loss) |
| Physical dock/cradle with pogo pins | Just a cable for now — can revisit for v2 hardware |
| Deep sleep mode | Kills ESP-NOW listener, prevents fast wake, eliminates clock mode |
| Mobile companion app | Desktop-only for v1, Linux primary |
| Windows/macOS companion app | Linux (Arch/CachyOS) primary target for v1 |
| Arduino 3.x / pioarduino upgrade | Community fork with single maintainer, risks breaking LovyanGFX and LVGL |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| COMM-01 | Phase 1 | Pending |
| COMM-02 | Phase 2 | Pending |
| COMM-03 | Phase 1 | Pending |
| COMM-04 | Phase 2 | Pending |
| COMM-05 | Phase 2 | Pending |
| COMM-06 | Phase 2 | Pending |
| COMM-07 | Phase 2 | Pending |
| COMM-08 | Phase 2 | Pending |
| BRDG-01 | Phase 1 | Pending |
| BRDG-02 | Phase 1 | Pending |
| BRDG-03 | Phase 1 | Pending |
| BRDG-04 | Phase 3 | Pending |
| BRDG-05 | Phase 3 | Pending |
| BRDG-06 | Phase 5 | Pending |
| BRDG-07 | Phase 4 | Pending |
| DISP-01 | Phase 1 | Pending |
| DISP-02 | Phase 1 | Pending |
| DISP-03 | Phase 1 | Pending |
| DISP-04 | Phase 1 | Pending |
| DISP-05 | Phase 1 | Pending |
| DISP-06 | Phase 3 | Pending |
| DISP-07 | Phase 3 | Pending |
| DISP-08 | Phase 4 | Pending |
| DISP-09 | Phase 4 | Pending |
| DISP-10 | Phase 4 | Pending |
| DISP-11 | Phase 4 | Pending |
| DISP-12 | Phase 1 | Pending |
| PWR-01 | Phase 4 | Pending |
| PWR-02 | Phase 4 | Pending |
| PWR-03 | Phase 4 | Pending |
| PWR-04 | Phase 4 | Pending |
| PWR-05 | Phase 4 | Pending |
| COMP-01 | Phase 3 | Pending |
| COMP-02 | Phase 3 | Pending |
| COMP-03 | Phase 4 | Pending |
| COMP-04 | Phase 5 | Pending |
| COMP-05 | Phase 5 | Pending |
| COMP-06 | Phase 5 | Pending |
| CONF-01 | Phase 5 | Pending |
| CONF-02 | Phase 5 | Pending |
| CONF-03 | Phase 5 | Pending |
| CONF-04 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 38 total
- Mapped to phases: 38
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-14*
*Last updated: 2026-02-14 after initial definition*
