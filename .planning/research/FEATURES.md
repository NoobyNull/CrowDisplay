# Feature Research

**Domain:** Wireless desktop command center / configurable macropad with system monitoring display
**Researched:** 2026-02-14
**Confidence:** MEDIUM-HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Reliable hotkey delivery | Core function. Tap button, keystroke fires on PC. If this fails even occasionally users lose trust. | MEDIUM | ESP-NOW latency is under 20ms per Espressif testing. Dual-link (ESP-NOW + UART) with fallback covers reliability. Must deliver within 50ms perceived. |
| Visual press feedback | Every touchscreen button product does this. Stream Deck, FreeTouchDeck, InfiniteDeck all show press animation/color change. | LOW | Already exists in backup code (darken + shrink on press). Keep it. |
| Multi-page button layout | Stream Deck supports up to 10 pages per profile. FreeTouchDeck has multiple menus. Existing backup has 3 tabbed pages. Users expect this. | MEDIUM | LVGL tabview or swipe container. Backup code uses bottom tabs. Swipe navigation is more natural on 7" touchscreen. |
| Modifier+key combos | Standard keyboard shortcuts (Ctrl+C, Win+D, Alt+Tab, F-keys). Every macropad supports these. | LOW | Already working in existing code. Bridge must support full HID report: modifiers byte + up to 6 keycodes. |
| Media keys (consumer controls) | Play/pause, volume, next/prev. Every Stream Deck alternative includes these. Backup code already has them on page 3. | MEDIUM | Requires USB HID consumer control report descriptor on bridge, separate from keyboard report. |
| Button labels with icons | Users need to know what each button does at a glance. All competitors show icon + text label. | LOW | Existing backup uses LVGL symbols + text + shortcut sublabel. This is already good. |
| Connection status indicator | User must know if the display is actually connected to the PC. Wireless devices always show link status. | LOW | Stats header shows ESP-NOW link state. Green/red indicator. Simple boolean from heartbeat. |
| USB HID "just works" on plug-in | Bridge plugs into PC USB, recognized as keyboard immediately. No drivers, no pairing. | LOW | ESP32-S3 native USB with TinyUSB. Standard HID descriptor. Works on Linux/Windows/macOS out of box. |
| Persistent configuration | Hotkey assignments survive power cycles. Nobody re-configures every boot. | MEDIUM | Store config in NVS (ESP32 flash key-value store) or SPIFFS/LittleFS as JSON. NVS is simpler for structured key-value data, LittleFS for larger JSON config files. |
| Battery level display | Battery-powered device must show remaining charge. Every phone, tablet, wireless keyboard does this. | LOW | ADC read of battery voltage through divider. Map 3.0-4.2V to 0-100%. Show in stats header. |
| Brightness control | 7" display drains battery fast at full brightness. Users expect adjustable brightness. | LOW | PWM on GPIO 2 (backlight). Slider in settings or quick toggle in stats header. |

### Differentiators (Competitive Advantage)

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Live PC stats header (CPU, RAM, GPU, network, disk) | No DIY macropad does this. Stream Deck shows static info or requires plugins. Having a persistent always-visible hardware monitor bar on your desk is genuinely useful for power users. | HIGH | Companion app on PC reads stats (psutil on Linux, LibreHardwareMonitor on Windows), streams JSON over USB serial to bridge, bridge forwards via ESP-NOW/UART to display. Requires defining a stats protocol, display widget layout, and update cadence (~1-2 Hz). |
| Dual-link transport (ESP-NOW + UART) with seamless fallback | No competitor offers this. If wireless drops, wired picks up instantly. If cable unplugged, wireless continues. Zero user intervention. | HIGH | Both links active simultaneously. Command/stats packets sent on both. Display deduplicates by sequence number. Heartbeat on both channels. Link priority: UART preferred (lower latency, more reliable), ESP-NOW as backup. |
| Desktop GUI configuration editor | FreeTouchDeck uses a web configurator hosted on ESP32 (limited). Stream Deck uses a full desktop app. A desktop app with drag-and-drop button editing, icon selection, and page management is a strong UX advantage over web-on-ESP32. | HIGH | Desktop app (Python + Qt or Electron) connects to bridge via USB serial. Reads current config, provides visual editor, pushes updates. Config format is JSON. |
| Clock mode when PC is off | Display becomes a useful desk clock showing time + battery when PC is powered down. Not just a dead screen. | MEDIUM | Companion app sends shutdown signal before PC powers off. Display detects loss of heartbeat, transitions to clock mode with dimmed backlight. ESP-NOW listener stays active for fast wake when bridge comes back online. RTC or NTP-synced time (NTP requires WiFi, RTC chip preferred for offline). |
| Per-button color coding | Existing backup code already has this. Most DIY alternatives use uniform button colors. Color-coded buttons by category (blue=clipboard, red=destructive, green=media) aid muscle memory. | LOW | Already implemented. Each Hotkey struct has a color field. Carry forward. |
| Configurable button sizes | 7" screen (800x480) has enough space for variable button sizes. Some actions deserve bigger buttons (e.g., a large "Mute" button for video calls). | MEDIUM | LVGL flex layout supports variable sizes. Config format needs width/height per button or size presets (1x1, 2x1, 1x2, 2x2). Complicates grid packing algorithm. |
| Per-app profiles (auto-switching) | Stream Deck's killer feature. Buttons change automatically when you switch between apps (e.g., VS Code vs Firefox vs OBS). Companion app detects active window. | HIGH | Companion app monitors active window title/process, sends profile switch command to bridge, bridge relays to display. Requires multiple config sets stored on display. Defer to v2 -- complex and requires tight companion app integration. |

### Anti-Features (Commonly Requested, Often Problematic)

Features to deliberately NOT build.

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Web-based configurator on ESP32 | FreeTouchDeck does this. Seems convenient -- no app install needed. | ESP32 web server consumes RAM/flash, WiFi conflicts with ESP-NOW (same radio), limited UI capability, security concerns with open WiFi AP. CrowPanel already has memory pressure with LVGL + display buffers. | Desktop GUI app over USB serial. Richer UI, no ESP32 resource cost, no WiFi needed. |
| WiFi connectivity for stats streaming | "Just use WiFi, no bridge needed." | WiFi and ESP-NOW share the same radio on ESP32. Running both degrades ESP-NOW performance. WiFi requires network config, DHCP, firewall rules. USB serial is zero-config and reliable. WiFi also drains battery faster. | USB serial from PC to bridge. Bridge relays to display over ESP-NOW/UART. |
| OTA firmware updates (in v1) | Convenient for updates without USB cable. | Requires WiFi (conflicts with ESP-NOW), adds significant flash/RAM overhead, security implications, bricking risk. Two separate devices need coordinated OTA. | USB cable firmware upload via PlatformIO. Add OTA in a later version after core is stable. |
| Custom bitmap icons per button | "I want my app icons on the buttons." | 800x480 display at 16-bit color with 20+ button icons eats PSRAM/flash fast. Image decoding on ESP32 is slow. Icon management adds complexity to config editor. | Use LVGL built-in symbol font (already working) + text labels. Support a curated icon set compiled into firmware. Bitmap icons can be a v2 feature with SPIFFS/SD card. |
| Macro sequences (multi-step automation) | Stream Deck and DuckyPad support multi-action macros (type text, delay, press keys in sequence). | Significant complexity: needs a scripting engine or sequence player, timing management, error handling for failed steps. Scope creep magnet. | Single hotkey per button (modifier+key). Companion app can trigger complex macros on the PC side if needed -- the button just sends a signal, PC app executes the sequence. |
| Rotary encoder / physical buttons | DuckyPad Pro has rotary encoders. Adds tactile control for volume, scrolling. | CrowPanel is a sealed touchscreen unit. Adding physical inputs means external hardware, wiring, enclosure modification. Not practical for this hardware. | On-screen slider widgets for volume. Touch-and-hold for repeat actions (e.g., hold volume button to keep adjusting). |
| Deep sleep for battery savings | "Deep sleep uses almost no power." | Deep sleep kills ESP-NOW listener -- display cannot wake when bridge comes online. Wake from deep sleep is slow (full reboot). Clock mode becomes impossible. | Light sleep with periodic ESP-NOW wake, or just dim the display and reduce CPU frequency. The 7" backlight is the dominant power draw anyway; dimming it gets 80% of the savings. |

## Feature Dependencies

```
[USB HID Bridge Firmware]
    |-- requires --> [ESP-NOW Communication]
    |-- requires --> [UART Communication]
    |                    |
    |                    v
    |              [Dual-Link Transport Layer]
    |                    |
    |                    v
    |              [Hotkey Command Relay]
    |                    |
    |                    v
    |              [Display Button Grid + Touch]  (exists)
    |
    v
[Companion Desktop App]
    |-- requires --> [USB Serial Protocol Definition]
    |-- requires --> [USB HID Bridge Firmware]
    |
    |-- enables --> [Live PC Stats Streaming]
    |                   |
    |                   v
    |              [Stats Header Bar on Display]
    |
    |-- enables --> [GUI Hotkey Editor]
    |                   |
    |                   v
    |              [Persistent Config (NVS/LittleFS)]
    |                   |
    |                   v
    |              [Config Push to Display via Bridge]
    |
    |-- enables --> [Shutdown Signal / PC Power State]
                        |
                        v
                   [Clock Mode on Display]
                        |
                        v
                   [Battery Management + Charging]

[Battery Level Monitoring] -- enhances --> [Stats Header Bar]
[Brightness Control] -- enhances --> [Stats Header Bar]
[Connection Status] -- enhances --> [Stats Header Bar]

[Swipe Page Navigation] -- enhances --> [Multi-Page Button Layout]
[Per-Button Colors] -- enhances --> [Display Button Grid]  (exists)

[Per-App Profiles] -- requires --> [Companion Desktop App]
[Per-App Profiles] -- requires --> [Persistent Config]
[Per-App Profiles] -- conflicts with --> [Simple MVP scope]
```

### Dependency Notes

- **Dual-Link Transport requires both ESP-NOW and UART:** Both communication channels must be independently working before the fallback/deduplication logic can be built.
- **Stats Header requires Companion App:** PC stats only exist on the PC. No companion app = no stats to display. The stats header can show device-local info (battery, brightness, link status) without the companion app, but PC metrics need it.
- **Clock Mode requires Shutdown Signal:** Without the companion app sending a "PC shutting down" message, the display cannot distinguish between "PC off" and "USB cable unplugged" and "temporary link dropout." Graceful transition depends on explicit signaling.
- **GUI Hotkey Editor requires Config Protocol:** The desktop app needs a defined protocol to read/write button configurations on the display. This protocol must be designed before the editor can be built.
- **Per-App Profiles conflicts with MVP scope:** This feature requires companion app window monitoring, multiple stored configs, and profile switching protocol. Too complex for v1. Defer.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what is needed to validate the core value proposition ("tap button, keystroke fires").

- [ ] **ESP32-S3 USB HID bridge firmware** -- bridge plugs in, recognized as keyboard, receives commands, sends keystrokes
- [ ] **ESP-NOW bidirectional link** -- display sends hotkey commands wirelessly to bridge, bridge sends heartbeat/acks back
- [ ] **UART bidirectional link** -- same protocol over wired connection for reliability
- [ ] **Dual-link transport with fallback** -- both channels active, automatic failover, packet deduplication
- [ ] **Multi-page hotkey grid with touch** -- at least 3 pages of 12 buttons (4x3), tab or swipe navigation
- [ ] **Visual press feedback** -- button darkens/shrinks on press, status bar shows "Sent: Copy (Ctrl+C)"
- [ ] **Connection status in header** -- green/red indicator for ESP-NOW link health
- [ ] **Battery level display** -- percentage in stats header (even without full power management)
- [ ] **Brightness control** -- basic slider or button in header area
- [ ] **Hardcoded default hotkey layout** -- General, Windows, Media/Dev pages from existing backup code

### Add After Validation (v1.x)

Features to add once the core hotkey relay is proven reliable.

- [ ] **Companion desktop app (stats streaming)** -- Python app reads CPU/RAM/GPU via psutil, streams JSON over USB serial
- [ ] **Stats header bar with live PC metrics** -- CPU %, RAM %, GPU %, network up/down, disk usage
- [ ] **Persistent hotkey configuration** -- save/load config from NVS or LittleFS, survive power cycles
- [ ] **Desktop GUI hotkey editor** -- visual editor to customize buttons, push config to display
- [ ] **Clock mode** -- display time + battery when PC is off, wake on bridge reconnect
- [ ] **Media key support (consumer controls)** -- play/pause, volume, next/prev via USB consumer report
- [ ] **Configurable button sizes** -- support 1x1, 2x1 grid units for different button importance

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Per-app automatic profiles** -- companion app detects active window, switches button layout
- [ ] **Custom bitmap icons** -- user-uploaded icons stored in SPIFFS/SD card
- [ ] **OTA firmware updates** -- over-the-air update mechanism for both devices
- [ ] **Macro sequences** -- multi-step automation triggered by single button press
- [ ] **Plugin/extension system** -- companion app plugins for app-specific integrations

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| USB HID bridge firmware | HIGH | MEDIUM | P1 |
| ESP-NOW communication | HIGH | MEDIUM | P1 |
| UART communication | HIGH | LOW | P1 |
| Dual-link fallback | HIGH | HIGH | P1 |
| Multi-page hotkey grid | HIGH | LOW | P1 |
| Visual press feedback | MEDIUM | LOW | P1 |
| Connection status indicator | MEDIUM | LOW | P1 |
| Battery level display | MEDIUM | LOW | P1 |
| Brightness control | MEDIUM | LOW | P1 |
| Companion app (stats) | HIGH | HIGH | P2 |
| Live stats header | HIGH | MEDIUM | P2 |
| Persistent config | HIGH | MEDIUM | P2 |
| GUI hotkey editor | MEDIUM | HIGH | P2 |
| Clock mode | MEDIUM | MEDIUM | P2 |
| Media keys | MEDIUM | MEDIUM | P2 |
| Configurable button sizes | LOW | MEDIUM | P3 |
| Per-app profiles | HIGH | HIGH | P3 |
| Custom bitmap icons | LOW | MEDIUM | P3 |
| OTA updates | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch -- core hotkey relay loop
- P2: Should have, add once core is stable -- what makes this more than a simple macropad
- P3: Nice to have, future consideration -- competitive features

## Competitor Feature Analysis

| Feature | Stream Deck (Elgato) | FreeTouchDeck | DuckyPad Pro | InfiniteDeck | Our Approach |
|---------|---------------------|---------------|-------------|--------------|--------------|
| Connection | USB wired | BLE wireless | USB wired | USB wired | Dual ESP-NOW wireless + UART wired with fallback |
| Display size | 1.5-4" per-key LCD | 3.5" shared | 1.5" OLED | 3.5" shared | 7.0" shared touchscreen |
| Button count | 8-32 physical | 6-12 touch | 20 mechanical | 12+ touch | 12+ per page, unlimited pages |
| Configuration | Full desktop app | Web on ESP32 | Web GUI | SD card scripts | Desktop GUI app over USB |
| System stats | Via plugins | No | No | No | Built-in live stats header |
| Battery powered | No | No | No | No | Yes, with clock standby mode |
| Multi-page | Yes (profiles) | Yes (menus) | Yes (profiles) | Yes (profiles) | Yes (swipe/tab pages) |
| Per-app switching | Yes (auto) | No | No | No | Planned v2 |
| Media keys | Yes | Limited | Yes | Yes (DuckyScript) | Yes (consumer HID) |
| Price point | $80-250 | ~$25 DIY | $70 | ~$50 DIY | ~$60-80 DIY (display + bridge + battery) |

## Sources

- [FreeTouchDeck (Hackaday.io)](https://hackaday.io/project/175827-freetouchdeck) -- ESP32 touchscreen macropad, web configurator, BLE
- [FreeTouchDeck (GitHub)](https://github.com/DustinWatts/FreeTouchDeck) -- source code and configurator details
- [ESP32 Touch Display Multipage Macropad (Instructables)](https://www.instructables.com/ESP32-Touch-Display-Multipage-Macropad/) -- LVGL v8 multipage UI, USB HID
- [DuckyPad Pro (CNX Software)](https://www.cnx-software.com/2025/09/23/duckypad-pro-20-key-esp32-s3-macropad-supports-up-to-3700-macros-using-duckyscript-language/) -- ESP32-S3 macropad with DuckyScript
- [InfiniteDeck (Electromaker)](https://www.electromaker.io/project/view/streamdeck-alternative-infinitedeck) -- touchscreen SD-card-based macropad
- [ESP-NOW reliability (Espressif Developer Portal)](https://developer.espressif.com/blog/reliability-esp-now/) -- latency and packet loss measurements
- [ESP-NOW latency testing (Hackaday.io)](https://hackaday.io/project/164132-hello-world-for-esp-now/log/160572-latency-and-reliability-testing) -- sub-20ms latency benchmarks
- [Bluetooth System Monitor (GitHub)](https://github.com/DustinWatts/Bluetooth-System-Monitor) -- ESP32 + TFT system stats display
- [SmallOLED-PCMonitor (GitHub)](https://github.com/Keralots/SmallOLED-PCMonitor) -- Python psutil + ESP32 OLED stats display
- [Stream Deck Profiles/Pages/Folders (Elgato)](https://marketplace.elgato.com/learn/inspiration/Profiles-Pages-Folders) -- profile and navigation paradigms
- [Elgato Computex 2025 products](https://www.elgato.com/us/en/explorer/news/events/computex-2025-elgato-products-overview/) -- latest Stream Deck features
- [XDA: 5 Stream Deck alternatives](https://www.xda-developers.com/stream-deck-alternatives-you-can-build-yourself-cost-half-as-much/) -- DIY macropad comparison
- [ESP-NOW GitHub (Espressif)](https://github.com/espressif/esp-now) -- official ESP-NOW library
- [ESP32 sleep modes (Last Minute Engineers)](https://lastminuteengineers.com/esp32-sleep-modes-power-consumption/) -- power management options
- [Wireless latency comparison (Electric UI)](https://electricui.com/blog/latency-comparison) -- BLE vs ESP-NOW vs WiFi latency benchmarks

---
*Feature research for: Wireless desktop command center / configurable macropad with system monitoring*
*Researched: 2026-02-14*
