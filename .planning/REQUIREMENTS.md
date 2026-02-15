# Requirements: CrowPanel Command Center

**Defined:** 2026-02-14
**Core Value:** Tap a button on the display, the correct keyboard shortcut fires on the PC — reliably, with minimal latency, whether connected by wire or wirelessly.

## v1.0 Requirements (Validated)

Shipped in milestone v1.0 (Phases 1-4). Confirmed working.

### Communication
- ✓ **COMM-01**: Display and bridge communicate bidirectionally over ESP-NOW — v1.0 Phase 1
- ✓ **COMM-03**: Both links use a shared binary protocol with SOF framing, message types, and CRC8 — v1.0 Phase 1

### Bridge Firmware
- ✓ **BRDG-01**: Bridge ESP32-S3 recognized as USB HID keyboard — v1.0 Phase 1
- ✓ **BRDG-02**: Bridge receives hotkey commands from display and sends USB HID keystrokes — v1.0 Phase 1
- ✓ **BRDG-03**: Bridge supports modifier+key combos — v1.0 Phase 1
- ✓ **BRDG-04**: Bridge supports media keys via USB consumer control — v1.0 Phase 3
- ✓ **BRDG-05**: Bridge routes stats data from companion app to display — v1.0 Phase 3
- ✓ **BRDG-07**: Bridge sends power state signals to display — v1.0 Phase 4

### Display UI
- ✓ **DISP-01**: Multi-page hotkey grid with swipe navigation — v1.0 Phase 1
- ✓ **DISP-03**: Visual press feedback on button tap — v1.0 Phase 1
- ✓ **DISP-06**: Persistent stats header bar — v1.0 Phase 3
- ✓ **DISP-07**: Stats header displays CPU/RAM/GPU/net/disk — v1.0 Phase 3
- ✓ **DISP-08**: Stats header displays battery %, ESP-NOW link, brightness — v1.0 Phase 4
- ✓ **DISP-09**: Clock mode on PC shutdown — v1.0 Phase 4
- ✓ **DISP-10**: Wake from clock mode on bridge reconnect — v1.0 Phase 4
- ✓ **DISP-11**: Brightness control from stats header — v1.0 Phase 4
- ✓ **DISP-12**: I2C bus mutex prevents GT911 corruption — v1.0 Phase 1

### Power Management
- ✓ **PWR-01**: LiPo battery with USB charging — v1.0 Phase 4
- ✓ **PWR-02**: Battery voltage monitored and displayed — v1.0 Phase 4
- ✓ **PWR-03**: Power state machine (ACTIVE → DIMMED → CLOCK_MODE) — v1.0 Phase 4
- ✓ **PWR-04**: Clock mode on companion shutdown signal — v1.0 Phase 4
- ✓ **PWR-05**: ESP-NOW listener active in clock mode — v1.0 Phase 4

### Companion App
- ✓ **COMP-01**: Python app collects live system stats — v1.0 Phase 3
- ✓ **COMP-02**: Stats streamed to bridge at 1-2 Hz — v1.0 Phase 3
- ✓ **COMP-03**: Companion sends shutdown signal via D-Bus — v1.0 Phase 4

## v1.1 Requirements

Requirements for milestone v1.1 "System Control". Configurable hotkey layouts via SD card, WiFi upload, and desktop GUI editor.

### SD Card Config (CFG)

- [ ] **CFG-01**: Hotkey layout stored as JSON config file on SD card, loaded at boot
- [ ] **CFG-02**: Per-button config includes label, key binding (modifier+keycode), color (hex), icon (name), type (keyboard/media), and consumer code
- [ ] **CFG-03**: Config supports variable number of pages (1-16) with named page labels
- [ ] **CFG-04**: Media keys stored as consumer control codes, distinct from keyboard shortcuts
- [ ] **CFG-05**: Device falls back to built-in default layout when SD card is missing or config is corrupt
- [ ] **CFG-06**: Config schema includes version field for future format migration
- [ ] **CFG-07**: Previous config auto-backed up before overwrite (config.json.bak)
- [ ] **CFG-08**: SD card writes use atomic pattern (temp file → rename) to prevent corruption on power loss

### WiFi Config Upload (WIFI)

- [ ] **WIFI-01**: User taps config icon in header to enter SoftAP config mode
- [ ] **WIFI-02**: HTTP server accepts JSON config upload via POST endpoint
- [ ] **WIFI-03**: Uploaded JSON validated before writing to SD card (malformed JSON rejected with error)
- [ ] **WIFI-04**: Display shows WiFi SSID, password, and IP address when config mode is active
- [ ] **WIFI-05**: SoftAP auto-stops after 5-minute inactivity timeout or after user taps "Apply & Exit"
- [ ] **WIFI-06**: OTA firmware upload merged into same HTTP server alongside config upload
- [ ] **WIFI-07**: ESP-NOW remains functional during SoftAP config mode (explicit WiFi channel pinning)

### Data-Driven Display UI (DRVUI)

- [ ] **DRVUI-01**: Display UI renders pages and buttons from parsed config struct, not hardcoded arrays
- [ ] **DRVUI-02**: Variable page count and variable buttons per page rendered from config
- [ ] **DRVUI-03**: Per-button label, color, icon (LVGL symbol), and keystroke description displayed as configured
- [ ] **DRVUI-04**: Config reload rebuilds display UI without device reboot (hot-reload)
- [ ] **DRVUI-05**: Widget-pool pattern prevents LVGL memory leaks on repeated config reloads

### Desktop GUI Editor (EDIT)

- [ ] **EDIT-01**: Python/PySide6 desktop app shows visual button grid matching device layout
- [ ] **EDIT-02**: User clicks a button in the grid to edit its properties in a side panel (label, shortcut, color, icon)
- [ ] **EDIT-03**: User can add, remove, rename, and reorder pages
- [ ] **EDIT-04**: User can save config to local JSON file and load existing JSON files
- [ ] **EDIT-05**: Icon picker displays available LVGL symbols visually for selection
- [ ] **EDIT-06**: Keyboard shortcut recorder captures key combos by pressing them (instead of manual entry)
- [ ] **EDIT-07**: User can deploy config directly to device via WiFi HTTP POST (no browser needed)

## Future Requirements

Deferred to v2+. Tracked but not in current roadmap.

### Advanced Layout
- **ADV-01**: Variable button sizes (1x1, 2x1, 1x2, 2x2 grid units)
- **ADV-02**: Custom bitmap images per button from SD card (not just LVGL symbols)
- **ADV-03**: Live preview push (edit in GUI → instant update on device without full upload)
- **ADV-04**: Per-app automatic profile switching (companion detects active window, switches layout)

### Advanced Editor
- **ADV-05**: Drag-and-drop button arrangement in editor canvas
- **ADV-06**: Config push via companion app HID channel (no WiFi needed)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web-based config editor on ESP32 | Severely limited UX, eats flash/RAM, WiFi conflicts with ESP-NOW |
| YAML/TOML config format | No maintained ESP32 parser; ArduinoJson handles JSON natively |
| Binary config format (MessagePack) | Not human-editable; JSON is inspectable for debugging |
| DuckyScript macro language | Scope creep; device sends keystrokes, not automation sequences |
| Electron desktop editor | 200+ MB bloat; PySide6 is 5 MB and native |
| Cloud config sync | No cloud infra; JSON files work with git/manual copy |
| Always-on WiFi AP | Drains battery, reduces ESP-NOW throughput, unnecessary attack surface |
| BLE HID connection to PC | Replaced by USB HID on bridge — v1.0 decision |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFG-01 | TBD | Pending |
| CFG-02 | TBD | Pending |
| CFG-03 | TBD | Pending |
| CFG-04 | TBD | Pending |
| CFG-05 | TBD | Pending |
| CFG-06 | TBD | Pending |
| CFG-07 | TBD | Pending |
| CFG-08 | TBD | Pending |
| WIFI-01 | TBD | Pending |
| WIFI-02 | TBD | Pending |
| WIFI-03 | TBD | Pending |
| WIFI-04 | TBD | Pending |
| WIFI-05 | TBD | Pending |
| WIFI-06 | TBD | Pending |
| WIFI-07 | TBD | Pending |
| DRVUI-01 | TBD | Pending |
| DRVUI-02 | TBD | Pending |
| DRVUI-03 | TBD | Pending |
| DRVUI-04 | TBD | Pending |
| DRVUI-05 | TBD | Pending |
| EDIT-01 | TBD | Pending |
| EDIT-02 | TBD | Pending |
| EDIT-03 | TBD | Pending |
| EDIT-04 | TBD | Pending |
| EDIT-05 | TBD | Pending |
| EDIT-06 | TBD | Pending |
| EDIT-07 | TBD | Pending |

**Coverage:**
- v1.1 requirements: 27 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 27

---
*Requirements defined: 2026-02-15*
*Last updated: 2026-02-15 after v1.1 milestone definition*
