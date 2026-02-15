# Stack Research

**Domain:** Dual-ESP32 wireless command center / macropad with system monitoring
**Researched:** 2026-02-14
**Confidence:** MEDIUM-HIGH

## Existing Stack (Locked In)

These are already in the project and should NOT be changed. The new milestone builds on top of them.

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| PlatformIO | latest | Build system | Existing |
| espressif32 | 6.5.0 | Platform (Arduino 2.x / ESP-IDF 4.4) | Existing, see note below |
| Arduino framework | 2.x (via espressif32@6.5.0) | Application framework | Existing |
| LovyanGFX | 1.1.8 | Display driver for CrowPanel 7.0" RGB565 | Existing |
| LVGL | 8.3.11 | Touch UI framework | Existing |
| PCA9557 | local lib | I/O expander for touch reset | Existing |
| ESP32-BLE-Keyboard | local lib | BLE HID (running env) | Existing |
| USB.h + USBHIDKeyboard.h | built-in | USB HID (test env) | Existing |

### Critical Platform Decision: Stay on espressif32@6.5.0

**Recommendation: Do NOT upgrade to Arduino 3.x / pioarduino.** Confidence: HIGH

The official PlatformIO espressif32 platform stopped at Arduino 2.x support. Arduino 3.x requires the community-maintained pioarduino fork, which is a one-person effort with limited support. Upgrading risks breaking LovyanGFX and LVGL compatibility, the RGB panel bus driver, and the existing USB HID code. ESP-NOW, UART, deep sleep, and all features needed for this milestone work fine on Arduino 2.x / ESP-IDF 4.4. There is zero benefit and significant risk to upgrading.

Sources:
- [pioarduino/platform-espressif32 GitHub](https://github.com/pioarduino/platform-espressif32) -- community fork, "one man show"
- [PlatformIO issue #1225](https://github.com/platformio/platform-espressif32/issues/1225) -- official support stalled
- [espressif/arduino-esp32 discussion #10039](https://github.com/espressif/arduino-esp32/discussions/10039) -- community Arduino 3.x status

---

## New Stack: Bridge Unit (ESP32-S3 DevKitC-1)

The bridge plugs into the PC via USB. It receives hotkey commands from the display wirelessly (ESP-NOW) or wired (UART), translates them to USB HID keystrokes, and relays system stats from a desktop companion app back to the display.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| espressif32 | 6.5.0 | Same platform as display unit | Identical toolchain avoids cross-compilation headaches. Both units share the same PlatformIO project with env-per-target. |
| Arduino framework | 2.x | Application framework | Matches display unit. ESP-NOW and USB both have mature Arduino APIs on 2.x. |
| ESP-NOW (esp_now.h) | built-in | Wireless link display<->bridge | Sub-millisecond latency, no router needed, 250-byte packets (v1) sufficient for hotkey commands and stat payloads. Built into ESP-IDF, zero extra dependencies. |
| USB.h + USBHIDKeyboard.h | built-in | USB HID keyboard to PC | Already proven in the existing test env. Uses TinyUSB under the hood on ESP32-S3. No external library needed. |
| USBCDC (USB.h) | built-in | USB CDC serial to companion app | ESP32-S3 supports composite USB devices (HID + CDC simultaneously) via TinyUSB. The bridge appears as both a keyboard and a serial port to the PC. |
| HardwareSerial (Serial1/Serial2) | built-in | UART wired fallback link | ESP32-S3 has 3 UART peripherals. Use Serial1 on dedicated TX/RX pins for the wired link to the display. |

### USB Composite Device: HID + CDC

This is the trickiest part of the bridge firmware. The ESP32-S3 must present as TWO USB devices simultaneously:
1. **HID Keyboard** -- receives hotkey commands from display, sends keystrokes to PC
2. **CDC Serial** -- receives system stats from companion app, forwards to display

**Implementation approach:** Confidence: MEDIUM

The Arduino ESP32 2.x core supports composite USB via TinyUSB. The key is initialization order and build flags:

```cpp
#include <USB.h>
#include <USBHIDKeyboard.h>

USBHIDKeyboard Keyboard;
USBCDC USBSerial;  // Second CDC interface for companion app

void setup() {
  USB.productName("HotkeyBridge");
  USB.manufacturerName("Custom");
  Keyboard.begin();
  USBSerial.begin(115200);
  USB.begin();  // Must be called AFTER all USB classes are initialized
}
```

**Required build flags:**
```ini
build_flags =
    -DARDUINO_USB_MODE=0          ; Use USB-OTG (not JTAG)
    -DARDUINO_USB_CDC_ON_BOOT=0   ; Don't auto-create CDC, we manage it
```

**Risk:** The composite HID+CDC pattern is less documented than HID-only or CDC-only. The cnfatal/esp32-cdc-keyboard project proves it works with ESP-IDF directly, and the Arduino wrapper should support it, but this needs early prototyping.

Sources:
- [ESP-IDF USB Device Stack docs](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/usb_device.html) -- confirms composite device support
- [Arduino ESP32 USB API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/usb.html) -- USBCDC and HID classes
- [cnfatal/esp32-cdc-keyboard](https://github.com/cnfatal/esp32-cdc-keyboard) -- proven HID+CDC composite (ESP-IDF)
- [philippkueng.ch ESP32-S3 keyboard guide](https://philippkueng.ch/2025-06-16-creating-a-virtual-usb-keyboard-with-the-esp32-s3.html) -- HID-only Arduino approach

---

## New Stack: Display Unit Additions

The existing display firmware gets ESP-NOW receive, UART fallback, system stats rendering, battery monitoring, and deep sleep/clock mode.

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| esp_now.h | built-in | ESP-NOW wireless receive | Always -- primary communication with bridge |
| WiFi.h | built-in | Required to init ESP-NOW (sets WiFi to STA mode) | Init only -- WiFi.mode(WIFI_STA) then WiFi off, ESP-NOW runs independently |
| HardwareSerial | built-in | UART wired fallback | When USB cable connects display to bridge directly |
| esp_sleep.h | built-in | Deep sleep for battery conservation | When PC is off / no ESP-NOW heartbeat for N minutes |
| esp_adc_cal.h | built-in | Battery voltage reading via ADC | Continuous -- read battery pin for charge level display |
| time.h + esp_sntp.h | built-in | NTP time sync for clock mode | On WiFi connection at startup, then RTC maintains time in deep sleep |

### ESP-NOW Protocol Design

ESP-NOW v1 payload: 250 bytes max. This is plenty for the use case:

| Message Type | Direction | Payload | Size |
|-------------|-----------|---------|------|
| Hotkey press | Display -> Bridge | msg_type(1) + hotkey_id(1) + modifiers(1) + keycode(1) | 4 bytes |
| Hotkey ack | Bridge -> Display | msg_type(1) + status(1) | 2 bytes |
| System stats | Bridge -> Display | msg_type(1) + cpu%(1) + ram%(1) + gpu%(1) + temp_cpu(2) + temp_gpu(2) + net_up(4) + net_down(4) + disk%(1) | ~17 bytes |
| Heartbeat | Bridge -> Display | msg_type(1) + uptime(4) | 5 bytes |
| Config sync | Bridge -> Display | msg_type(1) + page_id(1) + hotkey_data(variable) | <200 bytes |

**Use struct packing with `__attribute__((packed))` and a shared header between both firmware targets.** Do NOT use JSON or msgpack on the ESP-NOW link -- raw structs are faster, smaller, and both sides compile from the same header.

Sources:
- [ESP-IDF ESP-NOW API Reference](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/network/esp_now.html) -- 250 byte limit, 20 peer max, CCMP encryption
- [Random Nerd Tutorials ESP-NOW guide](https://randomnerdtutorials.com/esp-now-esp32-arduino-ide/) -- Arduino API patterns

---

## New Stack: Desktop Companion App (Linux)

Two components: (1) a background daemon that streams system stats over USB serial, and (2) a GUI app for configuring hotkey layouts.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Application language | Ubiquitous on Linux, fast prototyping, excellent hardware/system libraries. Every similar project in this space uses Python. |
| pyserial | 3.5 | USB CDC serial communication | De facto standard for serial in Python. Stable, cross-platform, zero-hassle. |
| psutil | 5.9+ / 6.x | CPU, RAM, disk, network, temperature monitoring | The only serious option for cross-platform system monitoring in Python. Active development, 7.x now available. |
| nvidia-ml-py | 12.x | NVIDIA GPU monitoring | Official NVIDIA bindings (pynvml is deprecated). Reports GPU util, temp, VRAM, fan speed. |

**For AMD GPUs:** Use `/sys/class/drm/card*/device/gpu_busy_percent` and `sensors` command parsing. There is no equivalent to nvidia-ml-py for AMD -- you read sysfs directly. Confidence: MEDIUM (needs validation on specific AMD hardware).

### Stats Daemon

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Daemon runtime | Same as above |
| struct (stdlib) | built-in | Binary serialization for serial protocol | Matches the packed struct approach on the ESP32 side. Fast, no dependencies, deterministic size. |
| systemd unit | N/A | Auto-start daemon | Standard for Linux services. User-level unit (~/.config/systemd/user/) for non-root operation. |

**Serial protocol between companion app and bridge:**

Use Python `struct.pack` / `struct.unpack` with a simple framed protocol:

```
[START_BYTE(0xAA)] [MSG_TYPE(1)] [LENGTH(1)] [PAYLOAD(N)] [CRC8(1)]
```

Do NOT use JSON over serial -- it is slow to parse on the ESP32, wastes bandwidth, and has no framing. Do NOT use msgpack -- it adds a dependency on both sides for minimal benefit over raw structs. The message set is fixed and known at compile time.

### Configuration GUI

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | GUI runtime | Same interpreter as daemon |
| GTK4 + PyGObject | GTK4 4.x, PyGObject 3.48+ | Desktop GUI toolkit | Native look on Linux/GNOME/KDE. GTK4 is the current generation, actively maintained. PyGObject is the official Python binding. |
| Libadwaita | 1.x | Adaptive UI components | GNOME's UI library built on GTK4. Provides HeaderBar, PreferencesPage, and other polished widgets out of the box. |

Sources:
- [psutil docs](https://psutil.readthedocs.io/) -- version 7.2.3 currently on PyPI
- [pyserial docs](https://pyserial.readthedocs.io/en/latest/pyserial_api.html) -- stable at 3.5
- [nvidia-ml-py on PyPI](https://pypi.org/project/nvidia-ml-py/) -- official NVIDIA bindings
- [PyGObject getting started](https://pygobject.gnome.org/getting_started.html) -- GTK4 Python bindings
- [pythonguis.com 2026 comparison](https://www.pythonguis.com/faq/which-python-gui-library/) -- GTK4 recommended for Linux-native apps

---

## New Stack: Battery Management (Display Unit)

### Hardware

| Component | Purpose | Why |
|-----------|---------|-----|
| CrowPanel BAT connector | LiPo battery input | Built into the board. Uses LTC4054 or similar linear charger IC. Charges from USB 5V. |
| 3.7V LiPo battery (3000-5000mAh) | Power source when untethered | 7" display at 800x480 draws significant power. 3000mAh minimum for ~2-4 hours at reduced brightness. |
| ADC pin (battery voltage divider) | Battery level monitoring | CrowPanel has a voltage divider on the BAT line to an ADC-capable GPIO. Read with analogRead() and calibrate. |

### Software

| Technology | Purpose | Notes |
|------------|---------|-------|
| esp_adc_cal.h | Calibrated ADC readings | ESP32-S3 ADC is notoriously noisy. Use the calibration API and average over multiple samples. |
| esp_sleep.h | Deep sleep when idle | ~200uA in deep sleep. Wake on touch (via EXT1 wakeup from touch interrupt pin) or timer (for clock refresh). |
| RTC memory | Persist state across deep sleep | 8KB RTC FAST memory survives deep sleep. Store last known time, battery level, display state. |

Sources:
- [Elecrow CrowPanel 7.0 wiki](https://www.elecrow.com/wiki/esp32-display-702727-intelligent-touch-screen-wi-fi26ble-800480-hmi-display.html) -- BAT connector details
- [Elecrow forum - battery charging](https://forum.elecrow.com/discussion/548/enabling-lipo-battery-charger-in-esp32-s3-5-inch-display) -- LTC4054 charger IC
- [ESP32-S3 deep sleep guide](https://esp32.co.uk/esp32-battery-powered-sensors-deep-sleep-low-power-design-guide/) -- ~200uA deep sleep current

---

## Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| PlatformIO | Build, upload, monitor | Use multi-env platformio.ini: `[env:display]`, `[env:bridge]`, `[env:display-debug]` etc. |
| PlatformIO monitor filters | Debug both units | `pio device monitor --port /dev/ttyUSB0 --filter colorize` for each unit in separate terminals |
| Python venv | Isolate companion app deps | `python -m venv .venv && source .venv/bin/activate` |
| udev rules | Stable USB device names | Write rules so bridge always maps to `/dev/ttyHotkeyBridge` regardless of USB port. Critical for the companion daemon. |

---

## Installation

### ESP32 Firmware (both units)

```ini
; platformio.ini additions for bridge unit
[env:bridge]
board = esp32-s3-devkitc-1
framework = arduino
platform = espressif32@6.5.0
build_flags =
    -DBOARD_HAS_PSRAM
    -DARDUINO_USB_MODE=0
    -DARDUINO_USB_CDC_ON_BOOT=0
    -DBRIDGE_UNIT
    -I src
lib_deps =
    ; No external libs needed -- ESP-NOW, USB, UART are all built-in
```

### Desktop Companion App

```bash
# System dependencies (Arch Linux / CachyOS)
sudo pacman -S python python-gobject gtk4 libadwaita

# Python dependencies
pip install pyserial psutil nvidia-ml-py
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| ESP-NOW (wireless link) | BLE | ESP-NOW has sub-ms latency vs 7.5ms+ BLE connection interval. No pairing ceremony. Simpler API. BLE is overkill for 4-byte hotkey packets between two known devices. |
| ESP-NOW (wireless link) | WiFi TCP/UDP | Requires a router, adds connection management complexity, higher power draw. ESP-NOW operates at the data-link layer without WiFi stack overhead. |
| UART (wired fallback) | I2C | UART is full-duplex, faster (115200+ baud), longer cable runs, and does not require pull-up resistors. I2C is designed for on-board chip-to-chip, not inter-board communication. |
| UART (wired fallback) | SPI | SPI requires 4 wires + chip select, is master-slave only, and adds unnecessary complexity for a simple bidirectional serial link. |
| Packed C structs (protocol) | JSON | JSON parsing on ESP32 wastes CPU cycles and memory. The protocol is fixed at compile time with no dynamic fields. ArduinoJson would add ~30KB flash for zero benefit. |
| Packed C structs (protocol) | MessagePack | Adds a dependency (msgpack library) on both ESP32 and Python sides. For a fixed protocol with 5 message types, the overhead is not justified. |
| Packed C structs (protocol) | Protocol Buffers | Massive overkill. nanopb adds significant complexity for a handful of small fixed messages. |
| Python + psutil (stats) | C/C++ daemon | Python is fast enough for 1-2 Hz stat polling. C would be premature optimization. psutil handles all the sysfs/procfs parsing. |
| Python + psutil (stats) | Node.js | No equivalent to psutil in the Node ecosystem. Python is the standard for system tooling on Linux. |
| GTK4 (GUI) | Qt6/PySide6 | Qt6 works but is a 200MB+ dependency. GTK4 is native on GNOME/Linux, lighter weight, and PyGObject is simpler than PySide6's signal/slot boilerplate. |
| GTK4 (GUI) | Electron | 200MB+ RAM for a config panel is absurd. GTK4 native app uses ~30MB. |
| GTK4 (GUI) | Terminal UI (curses) | A hotkey configuration GUI genuinely benefits from drag-and-drop, color pickers, and visual grid layout. TUI cannot deliver this. |
| systemd user service (daemon) | cron | Stats need continuous 1-2 Hz streaming, not periodic batch runs. systemd handles restart-on-crash, logging, and dependency management. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pioarduino / Arduino 3.x | One-person community fork. Risks breaking LovyanGFX, LVGL, USB HID. No benefit for this project. | espressif32@6.5.0 (Arduino 2.x) |
| ArduinoJson | Adds flash overhead for parsing. Fixed protocol does not need dynamic serialization. | Packed C structs with shared header |
| BLE for display<->bridge link | Higher latency, complex pairing, connection-oriented overhead. Already abandoned in the project for good reason. | ESP-NOW |
| NimBLE-Arduino (for bridge link) | Same BLE problems. Keep it only if you resurrect direct-to-PC BLE mode on the display. | ESP-NOW for bridge link |
| pynvml | Deprecated. Use the official nvidia-ml-py package instead. | nvidia-ml-py |
| PyGTK / GTK3 | GTK3 is legacy. PyGTK has been dead since 2011. | GTK4 + PyGObject + Libadwaita |
| tkinter | Ugly, limited widgets, no native Linux integration. | GTK4 + PyGObject |
| WebSocket/HTTP server on ESP32 | Memory-hungry, requires WiFi stack, adds attack surface. Not needed when you have USB serial. | USB CDC serial for companion app communication |

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| espressif32@6.5.0 | LovyanGFX 1.1.8 | Proven in existing project |
| espressif32@6.5.0 | LVGL 8.3.11 | Proven in existing project |
| espressif32@6.5.0 | ESP-NOW (esp_now.h) | Built-in to ESP-IDF 4.4, no external dep |
| espressif32@6.5.0 | USB.h + USBHIDKeyboard.h + USBCDC | Built-in to Arduino ESP32 2.x core |
| Python 3.11+ | psutil 5.9+/6.x/7.x | All versions compatible |
| Python 3.11+ | pyserial 3.5 | Stable, no breaking changes |
| Python 3.11+ | PyGObject 3.48+ | Requires GTK4 system package |
| GTK4 4.12+ | Libadwaita 1.4+ | Both available in Arch/CachyOS repos |

---

## Stack Patterns by Variant

**If using NVIDIA GPU:**
- Use nvidia-ml-py for GPU stats (util%, temp, VRAM, fan speed)
- Import conditionally; skip gracefully if not installed

**If using AMD GPU:**
- Read `/sys/class/drm/card0/device/gpu_busy_percent` for utilization
- Read `/sys/class/hwmon/hwmon*/temp*_input` for temperature (match via `name` file)
- Use `sensors` command as fallback via subprocess
- Wrap in try/except; GPU stats are "nice to have," not critical

**If display unit is connected via USB cable (wired mode):**
- Use UART (Serial1) as primary link instead of ESP-NOW
- ESP-NOW remains active for heartbeat/presence detection
- UART is faster and more reliable when physically connected

**If display unit is on battery (wireless mode):**
- ESP-NOW is the only communication channel
- Reduce stat update frequency to 0.5 Hz to conserve power
- Enter deep sleep if no heartbeat from bridge for 5 minutes
- Wake on touch interrupt for on-demand use

---

## Sources

- [ESP-IDF ESP-NOW API Reference (v5.5.2)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/network/esp_now.html) -- protocol limits, encryption, peer management (HIGH confidence)
- [ESP-IDF USB Device Stack (v5.5.2)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/usb_device.html) -- composite device support (HIGH confidence)
- [Arduino ESP32 USB API docs](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/usb.html) -- USBCDC, HID classes (MEDIUM confidence -- docs are for latest, not pinned to 2.x)
- [cnfatal/esp32-cdc-keyboard](https://github.com/cnfatal/esp32-cdc-keyboard) -- proven HID+CDC composite on ESP32-S3 (MEDIUM confidence -- ESP-IDF not Arduino)
- [Elecrow CrowPanel 7.0 wiki](https://www.elecrow.com/wiki/esp32-display-702727-intelligent-touch-screen-wi-fi26ble-800480-hmi-display.html) -- board specs, BAT connector (HIGH confidence)
- [psutil documentation](https://psutil.readthedocs.io/) -- system monitoring API (HIGH confidence)
- [nvidia-ml-py on PyPI](https://pypi.org/project/nvidia-ml-py/) -- official NVIDIA GPU bindings (HIGH confidence)
- [PyGObject docs](https://pygobject.gnome.org/getting_started.html) -- GTK4 Python bindings (HIGH confidence)
- [pioarduino discussion](https://github.com/espressif/arduino-esp32/discussions/10039) -- Arduino 3.x PlatformIO status (HIGH confidence)
- [Random Nerd Tutorials ESP-NOW](https://randomnerdtutorials.com/esp-now-esp32-arduino-ide/) -- Arduino ESP-NOW patterns (MEDIUM confidence)
- [ESP32 Desktop Monitor project](https://github.com/tuckershannon/ESP32-Desktop-Monitor) -- similar companion app pattern (LOW confidence -- different hardware)

---
*Stack research for: Dual-ESP32 wireless command center with system monitoring*
*Researched: 2026-02-14*
