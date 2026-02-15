# Project Research Summary

**Project:** Elcrow-Display-hotkeys
**Domain:** Dual-ESP32 wireless command center / macropad with system monitoring
**Researched:** 2026-02-14
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project transforms a CrowPanel 7.0" ESP32-S3 touchscreen into a wireless desktop command center with live system monitoring. Expert builders in this domain consistently use a dual-device architecture: one unit for the touch UI, and a separate ESP32 acting as a USB HID bridge to the PC. This separation is necessary because the CrowPanel's USB port is wired through a CH340 serial adapter, not the ESP32-S3's native USB OTG peripheral (GPIO 19/20 are hardwired to I2C for the touch controller). The recommended approach uses ESP-NOW for wireless communication between units with UART as a wired fallback, avoiding BLE's higher latency and connection overhead.

The core technical challenge is reliable message delivery in a dual-link system while managing I2C bus contention (GT911 touch, PCA9557, PCF8575 all share one bus). Critical findings: ESP-NOW and WiFi cannot coexist reliably due to radio contention (80%+ packet loss when WiFi is connected); USB composite HID+CDC devices stall on ESP32-S3 (documented bug marked "Won't Do" by Espressif); and LVGL's 96KB memory pool will exhaust quickly with multi-page UI. The existing codebase uses Arduino framework on espressif32@6.5.0, and this must NOT be upgraded to Arduino 3.x / pioarduino -- the official PlatformIO support stopped at Arduino 2.x, and the community fork is a one-person effort that risks breaking LovyanGFX and LVGL compatibility.

Key mitigations: keep both ESP32 units on Arduino 2.x / ESP-IDF 4.4; use ESP-NOW exclusively (no concurrent WiFi); implement I2C mutex before adding any new peripherals or tasks; separate HID and CDC concerns across devices (bridge does HID-only to PC, companion app uses bridge's serial); increase LVGL memory pool to 128KB+ or switch to PSRAM-backed allocator; and build wired (UART) transport first to remove wireless uncertainty from early development.

## Key Findings

### Recommended Stack

The project must build on the existing locked-in stack (espressif32@6.5.0, Arduino 2.x, LovyanGFX 1.1.8, LVGL 8.3.11) without upgrades. The bridge unit uses the same platform version to avoid cross-compilation issues. Communication between devices uses built-in ESP-NOW (sub-millisecond latency, 250-byte packets, zero external dependencies) with UART fallback over 3 wires (TX/RX/GND at 115200 baud). The companion desktop app is Python-based, using psutil for system monitoring, pyserial for USB serial communication, and GTK4 with PyGObject for the configuration GUI.

**Core technologies:**
- **espressif32@6.5.0 (Arduino 2.x):** Proven with existing display drivers, ESP-NOW and USB HID both mature on this platform. Do NOT upgrade to Arduino 3.x.
- **ESP-NOW (esp_now.h):** Built-in wireless link with <5ms latency, no router needed, 250-byte payload sufficient for hotkey commands and stats.
- **USB HID (USBHIDKeyboard.h):** Bridge unit sends keystrokes to PC. ESP32-S3 native USB via TinyUSB, no external library needed.
- **UART (HardwareSerial):** Wired fallback link at 115200 baud on dedicated GPIOs (display: 10/11, bridge: 17/18).
- **Python 3.11+ with psutil:** Desktop companion app for stats collection and configuration GUI. Standard for Linux system tooling.
- **Binary protocol with packed C structs:** Shared header between both firmware targets. Fast parsing, compact, avoids JSON overhead and heap fragmentation.

**Critical constraint:** CrowPanel USB-C port cannot serve USB HID directly (GPIO 19/20 used for I2C). Two-ESP32 architecture is mandatory, not optional.

### Expected Features

Research across Stream Deck, FreeTouchDeck, DuckyPad Pro, and InfiniteDeck reveals clear feature expectations for this device category.

**Must have (table stakes):**
- **Reliable hotkey delivery (<50ms perceived):** Core function. Users expect tap-to-keystroke without failure.
- **Visual press feedback:** Every competitor provides button animation/color change on touch.
- **Multi-page layout:** 3+ pages minimum, swipe or tab navigation.
- **Modifier+key combos:** Ctrl+C, Win+D, Alt+Tab, F-keys — standard keyboard shortcuts.
- **Media keys:** Play/pause, volume, next/prev via USB consumer control report.
- **Connection status indicator:** Wireless devices always show link state. Must be obvious when disconnected.
- **Battery level display:** Users expect remaining charge indicator.
- **Brightness control:** 7" display drains battery fast at full brightness.
- **Persistent configuration:** Hotkey assignments survive power cycles (store in NVS or LittleFS).

**Should have (competitive advantage):**
- **Live PC stats header:** CPU/RAM/GPU/network/disk in persistent always-visible bar. No DIY macropad does this. Strong differentiator for power users.
- **Dual-link transport (ESP-NOW + UART) with seamless fallback:** Wireless drops → wired picks up instantly, zero user intervention. Unique feature.
- **Desktop GUI configuration editor:** Better UX than web-on-ESP32 configurators used by FreeTouchDeck.
- **Clock mode when PC is off:** Display becomes desk clock showing time + battery. Not just a dead screen.
- **Per-button color coding:** Existing backup already has this. Aids muscle memory.

**Defer (v2+):**
- **Per-app automatic profiles:** Stream Deck's killer feature, but requires complex companion app window monitoring and multiple stored configs.
- **Custom bitmap icons:** Image decoding and storage management adds significant complexity for v1.
- **OTA firmware updates:** Requires WiFi (conflicts with ESP-NOW), bricking risk, coordinated updates across two devices. Add after core is stable.
- **Macro sequences (multi-step):** Needs scripting engine. Let companion app handle complex sequences PC-side.

### Architecture Approach

The system uses three physical components: the CrowPanel display unit (ESP32-S3 with 7" touchscreen), a USB bridge unit (ESP32-S3 DevKitC-1), and a Linux desktop companion app (Python). The bridge sits between display and PC, routing messages bidirectionally: hotkey commands flow Display → Bridge → PC (USB HID), while system stats flow PC → Bridge → Display. Both ESP32 units run separate firmware built from a shared protocol library. The display firmware adds ESP-NOW receive, UART fallback, stats rendering, battery monitoring, and power management to the existing LVGL touch UI. The bridge firmware is new, implementing USB HID keyboard output, message routing, and dual-link transport.

**Major components:**
1. **Transport Abstraction Layer (both units):** Wraps ESP-NOW and UART behind single send/receive API with automatic failover. Primary/fallback model, not redundant sending. UART preferred when connected (faster, zero packet loss), ESP-NOW as wireless backup.
2. **Message Router (bridge unit):** Routes typed binary messages between USB-side (HID keyboard + CDC serial to companion app) and display-side (ESP-NOW + UART). All messages use shared framing protocol: SOF(0xAA) + LENGTH + TYPE + PAYLOAD + CRC8.
3. **LVGL UI Layer (display unit):** Stats header bar (persistent at top), hotkey grid with swipeable pages, and clock mode (low-power state). Stats header updated via parsed messages from bridge. Hotkey grid triggers send via transport layer.
4. **Desktop Companion App:** Stats collector daemon (psutil polling at 1-2 Hz), GUI hotkey editor (GTK4/PyGObject), and power monitor (D-Bus shutdown detection). Communicates with bridge via USB CDC serial using same binary protocol.

**Key architectural decisions:**
- **Shared protocol library:** Both ESP32 firmware targets include `shared/protocol.h` with identical message types, framing, and CRC. Prevents drift.
- **Multi-environment PlatformIO project:** Single platformio.ini with `[env:display]` and `[env:bridge]`. Same platform version, shared includes.
- **Build wired first:** UART transport developed and proven before adding ESP-NOW. Removes wireless uncertainty from early debugging.
- **I2C mutex from day one:** All I2C access wrapped in FreeRTOS mutex before adding ESP-NOW callbacks or battery monitoring tasks. Prevents GT911 touch corruption.

### Critical Pitfalls

1. **ESP-NOW + WiFi radio contention destroys reliability:** WiFi and ESP-NOW share the same 2.4 GHz radio. When WiFi STA is connected, ESP-NOW packet loss jumps to 80%+. Both devices must use `WIFI_MODE_STA` with no active AP connection, pin to same channel, and disable WiFi power save (`esp_wifi_set_ps(WIFI_PS_NONE)`). Never connect to WiFi while ESP-NOW is active. If WiFi needed (NTP, OTA), disconnect before resuming ESP-NOW.

2. **USB HID + CDC composite device stalls on ESP32-S3:** Running USB HID keyboard and USB CDC serial simultaneously causes USB stack deadlock after extended use (arduino-esp32 #10307, marked "Won't Do" by Espressif). The bridge firmware must be HID-only to PC. Companion app communication goes over separate channel (or use CDC-only with no HID on same device). Do NOT attempt composite USB on the bridge.

3. **I2C bus contention breaks touch after adding new peripherals:** GT911 touch, PCA9557, PCF8575 share I2C on pins 19/20. ESP-NOW callbacks or battery monitoring via I2C (fuel gauges) create timing conflicts if they interrupt GT911's multi-step I2C register read sequence. Wrap ALL I2C access in FreeRTOS mutex. Never call `Wire` functions from ESP-NOW callbacks — copy to queue, process in main loop.

4. **LVGL 96KB memory pool exhaustion with multi-page UI:** Current pool size is 96KB. Adding stats pages, settings screens, animations will exhaust LVGL's internal heap. LVGL fails silently (returns NULL, crashes on NULL object use). Increase `LV_MEM_SIZE` to 128KB minimum, or switch to `LV_MEM_CUSTOM` with PSRAM-backed allocator. Create all screens at startup, switch with `lv_scr_load()`, never create/destroy dynamically (causes fragmentation).

5. **ESP-NOW message reliability without ACK protocol:** ESP-NOW's MAC-layer ACK only confirms "radio received," not "application processed." If receiver is busy (USB HID, I2C, critical section), data gets dropped. Implement application-layer ACK: sender includes sequence number, receiver sends ACK after processing, sender retries 2-3 times with 20ms timeout. Keep ESP-NOW callbacks minimal (copy to queue, return immediately), process in main loop.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Wired Command Foundation
**Rationale:** Build UART transport and end-to-end hotkey delivery before introducing wireless complexity. UART is deterministic, debuggable with logic analyzer, and validates the message protocol and USB HID integration. Establishes the command flow (Display → Bridge → PC) that all later phases depend on.

**Delivers:**
- UART bidirectional link between display and bridge (GPIO 10/11 on display, GPIO 17/18 on bridge)
- Shared binary protocol library with framing and CRC
- Bridge firmware: USB HID keyboard output to PC
- Display firmware: hotkey sender via UART
- Basic LVGL UI modification: send commands on button press
- I2C mutex implementation on display unit

**Addresses:**
- Reliable hotkey delivery (table stakes)
- Modifier+key combos (table stakes)
- I2C bus contention pitfall (critical)

**Avoids:**
- ESP-NOW/WiFi radio contention (not introduced yet)
- USB HID+CDC composite stall (bridge does HID-only)

### Phase 2: Wireless Link + Dual Transport
**Rationale:** Add ESP-NOW after wired link is proven. Implement transport abstraction layer that handles automatic failover between UART (preferred) and ESP-NOW (wireless backup). This phase delivers the core differentiator (dual-link with seamless fallback) while mitigating ESP-NOW reliability pitfalls discovered in research.

**Delivers:**
- ESP-NOW point-to-point communication (display ↔ bridge)
- Transport abstraction layer with primary/fallback logic
- Link health monitoring via PING/PONG heartbeat
- Application-layer ACK protocol with retries
- Connection status indicator in display UI

**Uses:**
- Built-in esp_now.h (ESP-IDF 4.4)
- Shared protocol library from Phase 1

**Implements:**
- Transport Abstraction Layer (architecture component)

**Avoids:**
- ESP-NOW/WiFi radio contention: no WiFi enabled, both units pinned to channel 1, power save disabled
- ESP-NOW reliability: ACK protocol with sequence numbers and retries
- Redundant sending: single preferred link at a time

### Phase 3: Stats Display + Companion App Foundation
**Rationale:** Once bidirectional communication is stable, add the second data flow (PC → Display for stats). This phase builds the companion app daemon and stats header UI, delivering the key competitive advantage (live system monitoring on desk hardware). Stats update at low frequency (1-2 Hz), reducing risk of overwhelming the transport.

**Delivers:**
- Desktop companion app stats collector (Python + psutil)
- USB CDC serial communication (bridge to companion app)
- Binary protocol implementation in Python
- Stats header bar in LVGL UI (persistent at top)
- Stats message routing through bridge

**Uses:**
- Python 3.11+, psutil, pyserial (stack elements)
- Binary protocol with struct packing (architecture pattern)

**Implements:**
- Desktop Companion App (architecture component)
- Message Router on bridge (architecture component)

**Avoids:**
- USB HID+CDC composite stall: bridge firmware is HID-only, companion app talks via a different interface or second serial device

### Phase 4: Battery Management + Power States
**Rationale:** Power management comes after core functionality is working. Requires hardware characterization of CrowPanel's voltage regulator and battery circuit. Delivers battery-powered wireless operation and clock mode (desk clock when PC is off). Independent of hotkey/stats flows, lowest risk to existing functionality.

**Delivers:**
- Battery voltage monitoring via ADC or I2C fuel gauge
- Battery level display in stats header
- Brightness control via backlight PWM
- Power state machine (ACTIVE → DIMMED → CLOCK_MODE)
- Clock mode UI with minimal backlight
- Shutdown signal from companion app (D-Bus)

**Uses:**
- esp_adc_cal.h or I2C fuel gauge on shared bus with mutex
- esp_sleep.h for light sleep modes
- Power Monitor module in companion app

**Implements:**
- Power Manager (architecture component on display unit)

**Avoids:**
- Battery over-discharge: monitor voltage, shutdown at 3.2V
- Brownout during radio TX: add capacitor on 3.3V rail
- Deep sleep killing ESP-NOW: use light sleep or dim+reduce CPU frequency

### Phase 5: Configuration Persistence + GUI Editor
**Rationale:** After all runtime features work, add persistent configuration and the desktop GUI editor. This phase removes the hardcoded hotkey layout and enables user customization. Config transfer uses chunked protocol over the proven transport. Deferred to late phases because core functionality works without it (hardcoded layout is acceptable for MVP validation).

**Delivers:**
- Config storage in NVS or LittleFS on display unit
- Chunked config transfer protocol (handles >250 byte configs)
- Desktop GUI hotkey editor (GTK4 + PyGObject)
- Visual drag-and-drop button editor
- Config push from companion app to display via bridge
- Multi-page hotkey layout management

**Uses:**
- GTK4, PyGObject, Libadwaita (stack elements)
- NVS or LittleFS (ESP32 persistent storage)

**Implements:**
- Config Store (architecture component on display)
- GUI Hotkey Editor (companion app module)

**Addresses:**
- Persistent configuration (table stakes)
- Desktop GUI configuration editor (competitive advantage)

### Phase Ordering Rationale

- **Wired before wireless:** UART is deterministic and debuggable. Proving the message protocol and USB HID integration over UART removes variables when adding ESP-NOW. Wireless brings radio contention, packet loss, and timing complexity — tackle after the simple case works.
- **Communication before features:** Phases 1-2 establish reliable bidirectional transport. Phases 3-5 build features on top of proven communication. This avoids debugging whether a problem is "transport broken" vs "feature logic wrong."
- **Stats before config:** Stats display (Phase 3) validates the PC → Display data flow and companion app integration with simpler, smaller messages (stats update ~17 bytes). Config push (Phase 5) uses the same mechanisms but with chunked transfer (large JSON blobs). Build simple first.
- **Battery last in core phases:** Power management is hardware-dependent and requires characterization testing. It's also independent — hotkeys and stats work fine on USB power. Deferring battery allows validating core functionality without power circuit complications.
- **Architecture constraints enforced early:** I2C mutex (Phase 1), ESP-NOW channel pinning and power save disable (Phase 2), HID-only on bridge (Phase 1) — these mitigate critical pitfalls before they become problems.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Stats + Companion App):** Desktop app architecture decisions (daemon vs single-process, systemd integration, udev rules for stable device naming). GPU monitoring varies by vendor (NVIDIA vs AMD). Needs platform-specific research.
- **Phase 4 (Battery Management):** CrowPanel-specific power circuit reverse-engineering. Fuel gauge options (ADC vs I2C IC). Sleep mode trade-offs (deep sleep kills ESP-NOW listener, light sleep effectiveness). Hardware-specific, needs hands-on testing.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Wired UART):** Well-documented pattern. ESP32 UART is mature, framing protocols are standard practice.
- **Phase 2 (ESP-NOW):** ESP-NOW API is well-documented, dual-link pattern proven in existing projects (ESP32 Desktop Monitor, similar DIY macropads).
- **Phase 5 (Config Persistence):** NVS/LittleFS are standard ESP32 storage, GTK4 GUI patterns are well-established.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | espressif32@6.5.0 proven in existing code. ESP-NOW, UART, USB HID all have official docs and working examples. Python stack is standard for Linux system tools. |
| Features | **MEDIUM-HIGH** | Feature expectations validated across 5+ competitor products and community projects. MVP scope is conservative. Deferred features (per-app profiles, OTA, macros) clearly identified. |
| Architecture | **MEDIUM-HIGH** | Dual-device separation is proven pattern. Message-oriented protocol is standard. I2C mutex, transport abstraction, power state machine are well-established patterns. USB HID+CDC composite stall is documented bug — mitigation (HID-only bridge) is clear. |
| Pitfalls | **MEDIUM-HIGH** | Critical pitfalls verified across multiple sources (ESP-NOW/WiFi contention in Espressif forums, USB composite stall in GitHub issues, I2C bus lockup in community discussions). Existing codebase confirms I2C sharing and memory constraints. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **USB CDC on bridge without HID:** Research confirmed HID+CDC composite is problematic, but bridge needs *some* way for companion app to talk to it. Likely solutions: (1) use UART-to-USB adapter (CP2102) for companion app serial, keep native USB for HID only, or (2) validate if CDC-only works reliably when HID is disabled, then use ESP-NOW as primary bridge↔display link. **Handle during Phase 1 architecture finalization.**

- **AMD GPU monitoring strategy:** psutil covers CPU/RAM/disk/network. NVIDIA GPUs use nvidia-ml-py. AMD requires sysfs reads (`/sys/class/drm/card*/device/gpu_busy_percent`) or parsing `sensors` command output. No equivalent to nvidia-ml-py for AMD. **Validate during Phase 3 with target hardware.**

- **CrowPanel battery charging circuit details:** Elecrow wiki mentions "LTC4054 or similar linear charger IC" but exact circuit unknown. Need to confirm: (1) ADC pin for voltage monitoring exists and which GPIO, (2) regulator dropout voltage, (3) whether built-in charger IC has overcharge/over-discharge protection. **Characterize during Phase 4 planning.**

- **FreeRTOS task structure:** Current code runs in single `loop()`. Adding ESP-NOW callbacks, stats rendering, battery monitoring, and touch polling concurrently needs FreeRTOS tasks with proper core pinning (LVGL on one core, radio/I2C on the other). Task priority and stack sizes need profiling. **Design during Phase 1 architecture, validate in Phase 2.**

- **LVGL memory allocation strategy:** Increasing `LV_MEM_SIZE` to 128KB+ uses internal SRAM. Switching to `LV_MEM_CUSTOM` with PSRAM gives unlimited space but slower widget operations (not rendering). Trade-off needs measurement on actual UI complexity. **Test during Phase 2 UI expansion, decide before Phase 3 stats header.**

## Sources

### Primary (HIGH confidence)
- [ESP-IDF ESP-NOW API Reference v5.5.2](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/network/esp_now.html) — protocol limits, encryption, peer management
- [ESP-IDF USB Device Stack v5.5.2](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/usb_device.html) — composite device support
- [ESP32-S3 HID+CDC stall issue #10307](https://github.com/espressif/arduino-esp32/issues/10307) — documented bug, marked "Won't Do"
- [ESP32-S3 UART documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/uart.html) — UART API and hardware
- [Elecrow CrowPanel 7.0 wiki](https://www.elecrow.com/wiki/esp32-display-702727-intelligent-touch-screen-wi-fi26ble-800480-hmi-display.html) — board specs, BAT connector, I2C pinout
- [psutil documentation v7.2.3](https://psutil.readthedocs.io/) — system monitoring API
- [pyserial documentation v3.5](https://pyserial.readthedocs.io/en/latest/pyserial_api.html) — serial communication
- [PyGObject getting started](https://pygobject.gnome.org/getting_started.html) — GTK4 Python bindings
- Existing codebase analysis: `src/main.cpp`, `platformio.ini`, `lv_conf.h`, `backup/` — HIGH confidence (direct inspection)

### Secondary (MEDIUM confidence)
- [ESP-NOW + WiFi coexistence — ESP32 Forum](https://www.esp32.com/viewtopic.php?t=12772) — 80%+ packet loss when WiFi STA connected
- [ESP-NOW latency testing — Hackaday.io](https://hackaday.io/project/164132-hello-world-for-esp-now/log/160572-latency-and-reliability-testing) — sub-20ms latency benchmarks
- [cnfatal/esp32-cdc-keyboard](https://github.com/cnfatal/esp32-cdc-keyboard) — proven HID+CDC composite on ESP32-S3 (ESP-IDF not Arduino)
- [Random Nerd Tutorials ESP-NOW](https://randomnerdtutorials.com/esp-now-esp32-arduino-ide/) — Arduino ESP-NOW patterns
- [FreeTouchDeck GitHub](https://github.com/DustinWatts/FreeTouchDeck) — competitor feature analysis
- [DuckyPad Pro — CNX Software](https://www.cnx-software.com/2025/09/23/duckypad-pro-20-key-esp32-s3-macropad-supports-up-to-3700-macros-using-duckyscript-language/) — competitor ESP32-S3 macropad
- [LVGL memory and ESP32 — LVGL Forum](https://forum.lvgl.io/t/memory-and-esp32/4050) — memory management strategies
- [ESP32 battery low voltage issues — espboards.dev](https://www.espboards.dev/troubleshooting/issues/power/esp32-battery-low-voltage/) — under-voltage protection

### Tertiary (LOW confidence)
- [ESP32 Desktop Monitor project](https://github.com/tuckershannon/ESP32-Desktop-Monitor) — similar companion app pattern (different hardware)
- [Bluetooth System Monitor project](https://github.com/DustinWatts/Bluetooth-System-Monitor) — ESP32 + TFT stats display (BLE instead of ESP-NOW)
- [pioarduino discussion](https://github.com/espressif/arduino-esp32/discussions/10039) — Arduino 3.x PlatformIO status (community fork concerns)

---
*Research completed: 2026-02-14*
*Ready for roadmap: yes*
