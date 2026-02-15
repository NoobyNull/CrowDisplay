# CrowPanel Command Center

## What This Is

A wireless desktop command center built around the Elcrow CrowPanel 7.0" touchscreen display and a companion ESP32-S3 USB bridge. The display shows a configurable grid of hotkey buttons and live PC system stats (CPU, RAM, GPU, network, disk). The bridge plugs into the PC via USB, acts as an HID keyboard, and communicates with the display over both UART (wired) and ESP-NOW (wireless). A desktop companion app streams system stats, manages hotkey configuration via a GUI editor, and handles power state signaling.

## Core Value

Tap a button on the display, the correct keyboard shortcut fires on the PC — reliably, with minimal latency, whether connected by wire or wirelessly.

## Requirements

### Validated

- Display renders an LVGL-based touchscreen UI on the CrowPanel 7.0" (800x480 RGB565, LovyanGFX + LVGL v8.3.11) — existing
- GT911 capacitive touch input works via direct I2C polling — existing
- Touch events trigger hotkey button callbacks in LVGL — existing
- BLE HID keyboard sends modifier+key combos to the PC — existing (env:running)
- USB HID keyboard sends modifier+key combos to the PC — existing (env:test, backup code)
- 4x3 grid of styled hotkey buttons with press feedback — existing
- PCA9557 I/O expander handles GT911 touch reset sequence — existing
- Double-buffered LVGL rendering in PSRAM — existing
- PlatformIO build system with ESP32-S3 target — existing

### Active

- [ ] Dual-ESP32 architecture: CrowPanel display + ESP32-S3 USB bridge as separate firmware targets
- [ ] ESP-NOW wireless communication between display and bridge (bidirectional)
- [ ] UART wired communication between display and bridge (bidirectional)
- [ ] Dual-link transport: UART and ESP-NOW active simultaneously with seamless fallback
- [ ] Bridge recognized as USB HID keyboard by PC
- [ ] Bridge relays hotkey commands from display to PC as USB HID keystrokes
- [ ] Companion desktop app streams live PC stats (CPU, RAM, GPU, network, disk) to bridge via USB serial
- [ ] Bridge forwards PC stats to display over active transport link
- [ ] Persistent stats header bar on display showing live PC metrics and device status (battery %, brightness, ESP-NOW link)
- [ ] Configurable hotkey grid with swipeable pages below the stats header
- [ ] Desktop GUI app for designing hotkey layout (buttons, shortcuts, pages) — pushes config to display via bridge
- [ ] Battery-powered display with LiPo + USB charging
- [ ] Battery level monitoring and display in stats header
- [ ] Display brightness control accessible from stats header
- [ ] ESP-NOW connection status indicator in stats header
- [ ] Clock mode when PC is off: dim screen showing time and battery level
- [ ] Companion app sends explicit shutdown signal before PC powers off
- [ ] Display wakes from clock mode when bridge comes online

### Out of Scope

- BLE HID connection to PC — replaced by USB HID on the bridge
- Physical dock/cradle with pogo pins — just a cable for now
- Web-based configuration interface — using desktop GUI app instead
- Mobile app — desktop companion only
- Audio output or speaker integration
- OTA firmware updates (can add later)

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
*Last updated: 2026-02-14 after initialization*
