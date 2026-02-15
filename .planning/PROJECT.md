# CrowPanel Command Center

## What This Is

A wireless desktop command center built around the Elcrow CrowPanel 7.0" touchscreen display and a companion ESP32-S3 USB bridge. The display shows a configurable grid of hotkey buttons and live PC system stats (CPU, RAM, GPU, network, disk). The bridge plugs into the PC via USB, acts as an HID keyboard, and communicates with the display over both UART (wired) and ESP-NOW (wireless). A desktop companion app streams system stats, manages hotkey configuration via a GUI editor, and handles power state signaling.

## Core Value

Tap a button on the display, the correct keyboard shortcut fires on the PC — reliably, with minimal latency, whether connected by wire or wirelessly.

## Current Milestone: v1.1 System Control

**Goal:** Make the display fully configurable — all hotkey layouts, button properties, and visual assets defined by config files on SD card, editable via a Linux GUI app and pushed over WiFi.

**Target features:**
- SD card as config + asset storage (JSON config, button icon images, backgrounds)
- Data-driven display UI (reads config at boot, renders pages/buttons dynamically)
- Fully flexible layouts (variable pages, variable buttons per page, variable sizes/positions)
- Full button customization (keystroke bindings, labels, colors, icon images, sizes, positions)
- SoftAP + HTTP server on display for receiving config/asset uploads
- Python GUI layout editor (extend companion app) for designing and pushing layouts

## Requirements

### Validated

- ✓ Dual-ESP32 architecture: CrowPanel display + ESP32-S3 USB bridge as separate firmware targets — v1.0 Phase 1
- ✓ ESP-NOW wireless communication between display and bridge (bidirectional) — v1.0 Phase 1
- ✓ Shared binary protocol with SOF framing, message types, CRC8 — v1.0 Phase 1
- ✓ Bridge recognized as USB HID keyboard by PC (no drivers) — v1.0 Phase 1
- ✓ Bridge relays hotkey commands as USB HID keystrokes — v1.0 Phase 1
- ✓ Bridge supports modifier+key combos and media keys — v1.0 Phase 1/3
- ✓ Multi-page hotkey grid with swipe navigation and press feedback — v1.0 Phase 1
- ✓ Live PC stats streaming (CPU/RAM/GPU/net/disk) via Python companion app — v1.0 Phase 3
- ✓ Persistent stats header bar with device status (battery, link, brightness) — v1.0 Phase 3/4
- ✓ Battery-powered display with LiPo, voltage monitoring, brightness control — v1.0 Phase 4
- ✓ Power state machine (ACTIVE → DIMMED → CLOCK_MODE) with companion shutdown signal — v1.0 Phase 4
- ✓ Clock mode with time display, auto-wake on bridge reconnect — v1.0 Phase 4
- ✓ I2C bus mutex prevents GT911 touch corruption — v1.0 Phase 1
- ✓ LVGL v8.3.11 UI on LovyanGFX with double-buffered PSRAM rendering — existing

### Active

- [ ] SD card storage for config files and image assets (icons, backgrounds)
- [ ] Data-driven UI: display reads layout config from SD card and renders dynamically
- [ ] Fully flexible page layouts (variable button count, sizes, positions per page)
- [ ] Full button customization (keystroke, label, color, icon image, size, position)
- [ ] SoftAP WiFi mode on display for config upload
- [ ] HTTP server on display for receiving config + asset files from GUI editor
- [ ] Python GUI layout editor for designing hotkey layouts with visual preview
- [ ] Config push from GUI editor to display over WiFi/HTTP

### Out of Scope

- BLE HID connection to PC — replaced by USB HID on the bridge
- Physical dock/cradle with pogo pins — just a cable for now
- Mobile app — desktop companion only
- Audio output or speaker integration
- Config transfer via bridge/ESP-NOW — replaced by direct WiFi SoftAP + HTTP
- NVS/LittleFS config storage — SD card is the storage medium
- Web-based configurator hosted on ESP32 — dedicated desktop GUI app instead

## Context

**Hardware:**
- Display: Elcrow CrowPanel 7.0" v3.0 — ESP32-S3 SoM, 800x480 RGB TFT, GT911 capacitive touch, PCA9557 I/O expander, 8MB PSRAM (OPI), 4MB flash (QIO). I2C on SDA=19, SCL=20. Backlight PWM on GPIO 2.
- Bridge: ESP32-S3 DevKitC-1 — native USB HID support, ESP-NOW capable, UART available.
- PCF8575 detected at I2C 0x27 on the CrowPanel (purpose being investigated).
- CrowPanel USB-C cannot be used simultaneously with touch display — hence UART for wired bridge connection.

**Existing codebase:**
- Working BLE hotkey firmware (src/main.cpp, monolithic ~470 lines)
- Backup of richer modular USB HID version with 3-page tabbed UI, media keys, color-coded buttons (backup/)
- Previous touch debugging revealed I2C bus conflicts — currently using manual GT911 polling instead of LovyanGFX built-in touch
- Startup currently has debug I2C scan and PCF8575 probing (adds ~10s boot delay, needs removal)

**Platform:**
- PlatformIO with espressif32@6.5.0
- LovyanGFX v1.1.8, LVGL v8.3.11, NimBLE-Arduino v1.4.0
- Upload via /dev/ttyUSB1 at 921600 baud

## Constraints

- **Hardware**: CrowPanel USB-C is unavailable for data when touch is active — wired link must use UART on separate GPIO pins
- **Display**: 800x480 resolution, LVGL v8.3.11 API (not v9) — all UI code must target v8
- **Memory**: 96KB LVGL internal memory pool + 8MB PSRAM for buffers — stats + multi-page UI must fit within this budget
- **Power**: Battery operation requires aggressive power management — ESP-NOW and UART should have configurable duty cycles
- **Compatibility**: Linux PC (Arch/CachyOS) primary target for companion app

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ESP-NOW over BLE for wireless link | ESP-NOW is faster, lower latency, peer-to-peer, no pairing overhead. BLE was the old PC connection method. | — Pending |
| UART over I2C for wired link | Full-duplex, faster, easier to debug. I2C bus already congested with GT911 + PCA9557 + PCF8575. | — Pending |
| USB HID on bridge (not display) | Separates display concerns from PC interface. Display focuses on UI + wireless. Bridge is a simple relay. | — Pending |
| Desktop GUI for config (not web UI) | Direct USB serial access to bridge. No need to run a web server on constrained ESP32. Richer UI capabilities. | — Pending |
| Clock mode over deep sleep | Keeps ESP-NOW listener active for fast wake. User can glance at time/battery. Trade-off: higher standby power. | — Pending |

---
*Last updated: 2026-02-15 after milestone v1.1 System Control started*
