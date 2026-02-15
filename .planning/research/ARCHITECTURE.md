# Architecture Research

**Domain:** Dual-ESP32 wireless command center with USB HID bridging and desktop companion
**Researched:** 2026-02-14
**Confidence:** MEDIUM-HIGH

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DESKTOP PC (Linux)                          │
│                                                                     │
│  ┌──────────────────────────────┐                                   │
│  │     Companion App (Python)   │                                   │
│  │  ┌────────┐  ┌────────────┐  │                                   │
│  │  │ Stats  │  │  Hotkey    │  │                                   │
│  │  │Collect │  │  Editor    │  │                                   │
│  │  └───┬────┘  └─────┬──────┘  │                                   │
│  │      │             │         │                                   │
│  │  ┌───┴─────────────┴──────┐  │                                   │
│  │  │   USB Serial (CDC)     │  │                                   │
│  │  └───────────┬────────────┘  │                                   │
│  └──────────────┼───────────────┘                                   │
│                 │ /dev/ttyACMx                                       │
│  ┌──────────────┴───────────────┐                                   │
│  │    OS HID Subsystem          │  (receives keystrokes)            │
│  └──────────────────────────────┘                                   │
└─────────────────┬───────────────────────────────────────────────────┘
                  │ USB cable (single)
                  │ Composite device: HID + CDC
┌─────────────────┴───────────────────────────────────────────────────┐
│              BRIDGE UNIT (ESP32-S3 DevKitC-1)                       │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ USB HID  │  │ USB CDC  │  │  ESP-NOW     │  │    UART      │   │
│  │ Keyboard │  │ Serial   │  │  Transceiver │  │  Transceiver │   │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  └──────┬───────┘   │
│       │             │               │                  │           │
│  ┌────┴─────────────┴───────────────┴──────────────────┴────────┐  │
│  │                   Message Router                              │  │
│  │         (routes between USB, ESP-NOW, UART)                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                  │                          │
                  │ ESP-NOW (wireless)       │ UART (wired, 3 wires)
                  │ 250 byte packets         │ TX/RX + GND
                  │                          │
┌─────────────────┴──────────────────────────┴────────────────────────┐
│             DISPLAY UNIT (CrowPanel 7.0" ESP32-S3)                  │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐                                │
│  │  ESP-NOW     │  │    UART      │                                │
│  │  Transceiver │  │  Transceiver │                                │
│  └──────┬───────┘  └──────┬───────┘                                │
│         │                 │                                        │
│  ┌──────┴─────────────────┴──────────────────────────────────────┐ │
│  │              Transport Layer (dual-link abstraction)           │ │
│  └──────────────────────────┬────────────────────────────────────┘ │
│                             │                                      │
│  ┌──────────────────────────┴────────────────────────────────────┐ │
│  │                    Application Layer                           │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │ │
│  │  │  Hotkey  │  │  Stats   │  │  Config  │  │   Power      │  │ │
│  │  │  Sender  │  │ Display  │  │  Store   │  │   Manager    │  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                             │                                      │
│  ┌──────────────────────────┴────────────────────────────────────┐ │
│  │                    LVGL UI Layer                               │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐                │ │
│  │  │  Stats   │  │ Hotkey   │  │  Clock Mode  │                │ │
│  │  │  Header  │  │ Grid +   │  │  (low power) │                │ │
│  │  │  Bar     │  │ Pages    │  │              │                │ │
│  │  └──────────┘  └──────────┘  └──────────────┘                │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Hardware Drivers: LovyanGFX, GT911 I2C, PCA9557, PCF8575,  │ │
│  │  Backlight PWM, Battery ADC/Fuel Gauge                        │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Physical Units

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Display Unit** (CrowPanel 7.0") | Touch UI, hotkey grid rendering, stats display, battery management, clock mode | Bridge via ESP-NOW + UART |
| **Bridge Unit** (ESP32-S3 DevKitC-1) | USB HID keyboard output, USB CDC serial to companion, message routing between PC and Display | Display via ESP-NOW + UART; PC via USB composite |
| **Companion App** (Linux desktop) | System stats collection, hotkey layout editor GUI, config push, power state signaling | Bridge via USB CDC serial (/dev/ttyACMx) |

### Firmware Modules (Display Unit)

| Module | Responsibility | Dependencies |
|--------|---------------|-------------|
| **Transport Layer** | Abstracts ESP-NOW and UART into single send/receive API with automatic failover | ESP-NOW driver, UART driver |
| **Hotkey Sender** | Serializes hotkey press events into messages, sends via transport | Transport Layer |
| **Stats Display** | Receives PC stats messages, updates LVGL header bar widgets | Transport Layer, LVGL UI |
| **Config Store** | Receives config from companion app, persists to NVS/SPIFFS, rebuilds UI | Transport Layer, NVS |
| **Power Manager** | Battery level monitoring, backlight control, clock mode transitions, sleep/wake | ADC or fuel gauge I2C, backlight PWM, transport (for power signals) |
| **LVGL UI** | Screen rendering, touch input, page management, widget lifecycle | LovyanGFX, GT911 driver |

### Firmware Modules (Bridge Unit)

| Module | Responsibility | Dependencies |
|--------|---------------|-------------|
| **USB HID** | Sends keystroke reports to PC when hotkey messages arrive from display | TinyUSB HID |
| **USB CDC** | Serial channel to companion app for stats, config, power signals | TinyUSB CDC |
| **ESP-NOW Transceiver** | Wireless link to display unit | ESP-NOW driver |
| **UART Transceiver** | Wired link to display unit | Hardware UART |
| **Message Router** | Routes messages between USB-side and display-side based on message type | All transport modules |

### Desktop Companion App

| Module | Responsibility | Dependencies |
|--------|---------------|-------------|
| **Stats Collector** | Polls CPU, RAM, GPU, network, disk metrics at configurable interval | psutil, GPUtil or similar |
| **Serial Transport** | Opens /dev/ttyACMx, sends/receives framed messages to bridge | pyserial |
| **Hotkey Editor GUI** | Visual drag-and-drop grid editor for hotkey layout and pages | Qt6 (PySide6) or GTK |
| **Config Manager** | Serializes hotkey config, pushes to bridge, loads/saves local files | JSON, serial transport |
| **Power Monitor** | Detects shutdown/suspend, sends power-off signal to bridge before OS goes down | D-Bus (systemd-logind) |

## Data Flow

### Flow 1: Hotkey Press (Display to PC)

```
User taps button on Display
    |
    v
LVGL event callback fires
    |
    v
Hotkey Sender serializes: {type: HOTKEY, key: 'c', mods: CTRL}
    |
    v
Transport Layer sends via preferred link (UART if wired, ESP-NOW if wireless)
    |
    v
Bridge Message Router receives, identifies HOTKEY type
    |
    v
USB HID module sends keystroke report to PC
    |
    v
OS registers Ctrl+C keystroke
```

**Latency budget:** Target under 50ms end-to-end. ESP-NOW adds ~2-5ms. UART at 115200 adds ~1ms for small packets. USB HID poll interval is typically 1-10ms.

### Flow 2: System Stats (PC to Display)

```
Companion App Stats Collector samples CPU/RAM/GPU/etc
    |
    v
Serializes: {type: STATS, cpu: 45, ram: 62, gpu: 38, net_up: 1200, net_dn: 45000}
    |
    v
USB CDC serial write to /dev/ttyACMx
    |
    v
Bridge USB CDC receives, Router identifies STATS type
    |
    v
Forwards to Display via Transport (ESP-NOW or UART)
    |
    v
Display Stats Display module parses, updates LVGL header bar labels
```

**Update rate:** 1-2 Hz is sufficient. Higher rates waste bandwidth and power.

### Flow 3: Config Push (PC to Display)

```
User edits hotkey layout in Companion App GUI
    |
    v
Config Manager serializes full config as JSON
    |
    v
Sends chunked via USB CDC (config may exceed 250 byte ESP-NOW limit)
    |
    v
Bridge forwards chunks to Display
    |
    v
Display Config Store reassembles, validates, persists to NVS/SPIFFS
    |
    v
Display rebuilds LVGL hotkey grid from new config
```

**Chunking required:** ESP-NOW max payload is 250 bytes. A full config with multiple pages of hotkeys will exceed this. Use a simple chunked transfer protocol with sequence numbers and ACKs.

### Flow 4: Power State (PC to Display)

```
Companion App detects impending shutdown via D-Bus (PrepareForShutdown signal)
    |
    v
Sends: {type: POWER, state: SHUTTING_DOWN}
    |
    v
Bridge forwards to Display
    |
    v
Display Power Manager transitions to Clock Mode:
  - Dims backlight to minimum
  - Switches UI to clock + battery display
  - Reduces ESP-NOW polling interval (or enters listen-only mode)
```

```
Bridge boots (PC turned on, USB enumerated)
    |
    v
Bridge sends: {type: POWER, state: ONLINE} via ESP-NOW/UART
    |
    v
Display wakes from clock mode, restores full UI
```

## Message Protocol Design

### Framing

Use a simple binary framing protocol shared across both transports:

```
┌──────┬────────┬──────┬─────────────┬──────┐
│ SOF  │ LENGTH │ TYPE │   PAYLOAD   │ CRC8 │
│ 0xAA │ 1 byte │ 1 b  │ 0-246 bytes │ 1 b  │
└──────┴────────┴──────┴─────────────┴──────┘
```

- **SOF (Start of Frame):** 0xAA - byte-level sync
- **LENGTH:** Payload length (0-246), keeping total under 250 for ESP-NOW
- **TYPE:** Message type enum (HOTKEY, STATS, CONFIG_CHUNK, CONFIG_ACK, POWER, PING, PONG)
- **PAYLOAD:** Type-specific data
- **CRC8:** Simple CRC for integrity (essential over UART, still useful for ESP-NOW)

**Why this over JSON:** Binary is compact (fits in single ESP-NOW frame), fast to parse on ESP32, and avoids string allocation in the hot path. JSON is fine for config storage on disk but not for real-time message passing.

### Message Types

| Type ID | Name | Direction | Payload |
|---------|------|-----------|---------|
| 0x01 | HOTKEY | Display -> Bridge | modifier_mask (1B) + keycode (1B) |
| 0x02 | STATS | Bridge -> Display | Packed struct: cpu(1B) + ram(1B) + gpu(1B) + net_up(2B) + net_dn(2B) + disk(1B) |
| 0x03 | CONFIG_CHUNK | Bridge -> Display | seq(2B) + total(2B) + data(up to 242B) |
| 0x04 | CONFIG_ACK | Display -> Bridge | seq(2B) + status(1B) |
| 0x05 | POWER | Bridge -> Display | state enum (1B) |
| 0x06 | PING | Either -> Either | timestamp(4B) |
| 0x07 | PONG | Either -> Either | echoed timestamp(4B) |

### Dual-Link Transport Strategy

**Primary/fallback model, not redundant sending:**

1. If UART is physically connected (detected via initial handshake or pin state), use UART as primary. It is faster, lower latency, zero packet loss, full-duplex.
2. ESP-NOW is always-on as fallback. If UART link drops (no PONG within timeout), switch to ESP-NOW automatically.
3. When UART reconnects (PING succeeds), switch back to UART.
4. Never send the same message on both links simultaneously -- this wastes power and creates dedup complexity.

**Link detection:** On boot, both sides send PING on both transports. First PONG received establishes preferred link. Periodic PINGs (every 2-5 seconds) monitor link health.

## Hardware Pin Allocation

### CrowPanel 7.0" - GPIO Budget

| GPIO | Current Use | Available? |
|------|------------|------------|
| 0 | RGB PCLK | No |
| 1, 3, 4, 5, 6, 7, 8, 9 | RGB data bus | No |
| 2 | Backlight PWM | No |
| 14, 15, 16, 21 | RGB data bus | No |
| 19, 20 | I2C SDA/SCL | No |
| 38 | PCA9557/touch related | No |
| 39, 40, 41 | RGB HSYNC/VSYNC/HENABLE | No |
| 45, 46, 47, 48 | RGB data bus | No |
| **10** | Free | **UART TX to bridge** |
| **11** | Free | **UART RX from bridge** |
| **12, 13** | Free | Reserve (future use) |
| **17, 18** | Free | Reserve (battery ADC or fuel gauge INT) |
| **35, 36, 37** | Free (JTAG by default) | Available if JTAG not needed |
| **42** | Free | Reserve |
| **43, 44** | Default UART0 TX/RX | Used by Serial (debug/upload) |

**UART for bridge link:** Use UART1 on GPIO 10 (TX) and GPIO 11 (RX). These are free, not used by the RGB bus or I2C. UART0 (GPIO 43/44) stays as debug serial.

**Battery monitoring:** GPIO 17 or 18 for ADC reading (if using resistor divider) or keep free for I2C fuel gauge interrupt pin. The I2C fuel gauge can share the existing I2C bus (pins 19/20) since it uses a different address.

### Bridge Unit (ESP32-S3 DevKitC-1) - GPIO Budget

The DevKitC-1 has most GPIOs available since it has no display.

| Function | GPIO |
|----------|------|
| USB D-/D+ | 19, 20 (native USB, fixed) |
| UART to Display TX | Any free (e.g., GPIO 17) |
| UART to Display RX | Any free (e.g., GPIO 18) |
| UART0 TX/RX | GPIO 43/44 (debug serial, keep for development) |
| ESP-NOW | Uses WiFi radio, no dedicated GPIO |

## Recommended Project Structure

```
/data/Elcrow-Display-hotkeys/
├── platformio.ini              # Multi-environment: display, bridge
├── shared/                     # Code shared between display and bridge
│   ├── protocol.h              # Message types, framing, CRC
│   ├── transport.h             # Transport interface (abstract)
│   └── config_types.h          # Hotkey config struct definitions
├── display/                    # CrowPanel firmware
│   ├── main.cpp                # Setup/loop, ties modules together
│   ├── ui/                     # LVGL screens and widgets
│   │   ├── hotkey_grid.cpp/h   # Swipeable hotkey button pages
│   │   ├── stats_header.cpp/h  # Persistent stats bar at top
│   │   └── clock_mode.cpp/h    # Low-power clock display
│   ├── transport/              # Dual-link transport
│   │   ├── transport.cpp/h     # Abstraction layer with failover
│   │   ├── espnow_link.cpp/h   # ESP-NOW specifics
│   │   └── uart_link.cpp/h     # UART specifics
│   ├── power/                  # Battery and power management
│   │   ├── battery.cpp/h       # ADC/fuel gauge reading
│   │   └── power_mgr.cpp/h     # Sleep modes, backlight, clock mode
│   ├── config/                 # Persistent configuration
│   │   └── config_store.cpp/h  # NVS/SPIFFS read/write
│   └── drivers/                # Hardware abstraction
│       ├── display_driver.cpp/h # LovyanGFX setup (extracted from main)
│       └── touch_driver.cpp/h   # GT911 polling (extracted from main)
├── bridge/                     # Bridge firmware
│   ├── main.cpp                # Setup/loop
│   ├── usb/                    # USB composite device
│   │   ├── usb_hid.cpp/h      # HID keyboard reports
│   │   └── usb_cdc.cpp/h      # CDC serial to companion
│   ├── transport/              # Links to display
│   │   ├── espnow_link.cpp/h
│   │   └── uart_link.cpp/h
│   └── router.cpp/h           # Message routing logic
├── companion/                  # Desktop app
│   ├── main.py                 # Entry point
│   ├── serial_transport.py     # USB serial framing
│   ├── stats_collector.py      # psutil-based stats gathering
│   ├── hotkey_editor.py        # GUI editor (PySide6)
│   ├── config_manager.py       # Config serialization
│   └── power_monitor.py        # D-Bus shutdown detection
└── backup/                     # Existing backup code (keep)
```

### Structure Rationale

- **shared/:** The protocol definitions and message types MUST be identical on display and bridge. A shared directory avoids drift. PlatformIO can include this via `lib_extra_dirs` or build flags.
- **display/ and bridge/ as separate firmware targets:** Each gets its own PlatformIO environment. They share protocol but have entirely different hardware drivers and responsibilities.
- **companion/ as a separate Python project:** Not built by PlatformIO. Has its own dependencies (pyserial, psutil, PySide6). Could be packaged as a standalone app later.
- **Flat module structure within firmware:** ESP32 Arduino projects do not benefit from deep nesting. Keep it one level of folders.

### PlatformIO Multi-Target Configuration

```ini
[env]
platform = espressif32@6.5.0
framework = arduino
board_build.arduino.memory_type = qio_opi
monitor_speed = 115200

[env:display]
board = esp32-s3-devkitc-1
build_src_filter = +<../display/> +<../shared/>
upload_port = /dev/ttyUSB1
build_flags =
    -DBOARD_HAS_PSRAM
    -DLV_CONF_INCLUDE_SIMPLE
    -I display
    -I shared

lib_deps =
    lovyan03/LovyanGFX@^1.1.8
    https://github.com/lvgl/lvgl.git#v8.3.11

[env:bridge]
board = esp32-s3-devkitc-1
build_src_filter = +<../bridge/> +<../shared/>
upload_port = /dev/ttyUSB0
build_flags =
    -DARDUINO_USB_MODE=0
    -DARDUINO_USB_CDC_ON_BOOT=0
    -I bridge
    -I shared
```

## Architectural Patterns

### Pattern 1: Transport Abstraction with Failover

**What:** A single `Transport` class that wraps both ESP-NOW and UART, exposing `send(msg)` and `onReceive(callback)`. Internally tracks link health and fails over automatically.

**When to use:** Every module that communicates between display and bridge uses this, never raw ESP-NOW or UART directly.

**Trade-offs:** Adds a layer of indirection. Worth it because it prevents every module from needing failover logic. Also makes testing easier (can mock transport).

```cpp
// shared/transport.h
enum class LinkType : uint8_t { UART, ESPNOW };

class Transport {
public:
    bool send(const uint8_t* data, size_t len);  // sends on preferred link
    void setReceiveCallback(void (*cb)(const uint8_t* data, size_t len));
    LinkType activeLink() const;
    bool isConnected() const;
    void poll();  // call from loop(), handles PINGs and failover
private:
    UartLink uart;
    EspNowLink espnow;
    LinkType preferred = LinkType::UART;
    uint32_t lastPong = 0;
};
```

### Pattern 2: Message-Oriented Protocol

**What:** All communication uses typed, framed messages rather than raw byte streams. Both sides parse frames identically using shared code.

**When to use:** All inter-device communication. The companion app implements the same framing in Python.

**Trade-offs:** Slightly more overhead than raw bytes, but prevents framing errors, enables message-type routing, and makes debugging much easier (can log message types).

### Pattern 3: State Machine for Power Modes

**What:** Display unit power management as an explicit state machine: ACTIVE -> DIMMED -> CLOCK_MODE, with transitions triggered by timeout and power signals.

**When to use:** Power Manager module on the display unit.

**Trade-offs:** More code than simple if/else chains, but prevents invalid state combinations (e.g., full brightness in clock mode) and makes the transition logic testable.

```
                    ┌──────────┐
         PC online  │  ACTIVE  │  touch activity resets timer
         ──────────>│          │<────────────────────┐
                    └────┬─────┘                     │
                         │ no touch for 30s          │ touch
                         v                           │
                    ┌──────────┐                     │
                    │  DIMMED  │─────────────────────┘
                    └────┬─────┘
                         │ no touch for 2min OR power_off signal
                         v
                    ┌──────────┐
                    │  CLOCK   │  ESP-NOW listen only
                    │  MODE    │  minimal backlight
                    └──────────┘
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Composite USB HID+CDC on Arduino Core 2.x

**What people do:** Use Arduino-ESP32 core's built-in `USBHIDKeyboard` and `Serial` (CDC) simultaneously on the bridge, expecting them to work as a composite device out of the box.

**Why it's wrong:** There is a documented open issue (espressif/arduino-esp32#10307) where simultaneous CDC and HID traffic causes stalls. The Arduino core's TinyUSB integration has known bugs in this area as of core 2.0.x and early 3.x releases. One or both channels will stop responding after sustained traffic.

**Do this instead:** Either (a) use ESP-IDF directly with TinyUSB for the bridge firmware (more control over USB descriptors, proven composite device examples), or (b) test thoroughly with Arduino Core 3.x RC releases which claim to fix TinyUSB issues, and have a fallback plan. The bridge firmware is simple enough that ESP-IDF is feasible even if the display stays on Arduino. Alternatively, avoid simultaneous high-frequency traffic on both channels -- send stats in bursts, not continuously.

**Confidence:** MEDIUM. The issue is documented but may be resolved in newer core versions. Must be validated during implementation.

### Anti-Pattern 2: JSON Over ESP-NOW

**What people do:** Send JSON-encoded messages over ESP-NOW for "readability."

**Why it's wrong:** ESP-NOW max payload is 250 bytes. A JSON stats message like `{"type":"stats","cpu":45,"ram":62,"gpu":38,"net_up":1200,"net_dn":45000,"disk":78}` is ~80 bytes and grows fast with more fields. Config messages will require heavy chunking. JSON parsing also uses heap allocations on the ESP32, causing fragmentation over time.

**Do this instead:** Binary protocol with packed structs for real-time messages. JSON is fine for config files stored on SPIFFS and for the companion app's local config format, but never for the wire protocol.

### Anti-Pattern 3: Polling Both Links for Every Message

**What people do:** Send every message on both UART and ESP-NOW to "make sure it gets through."

**Why it's wrong:** Doubles power consumption (ESP-NOW TX is expensive for battery operation), creates message deduplication complexity, and can cause double-firing of keystrokes on the PC.

**Do this instead:** Single preferred link with failover. Use heartbeat PINGs to detect link failure, then switch. Only one link carries application messages at a time.

### Anti-Pattern 4: Monolithic main.cpp for Two Firmware Targets

**What people do:** Keep everything in one main.cpp with `#ifdef DISPLAY` / `#ifdef BRIDGE` conditionals.

**Why it's wrong:** The display and bridge have almost zero shared application logic. Conditionals grow exponentially. Impossible to reason about. The existing 470-line monolithic main.cpp is already at the pain threshold for a single device; two devices in one file would be unmanageable.

**Do this instead:** Separate firmware projects with shared protocol library. Each target has its own main.cpp and module structure.

## Integration Points

### USB Composite Device (Bridge)

| Interface | Protocol | Data Rate | Notes |
|-----------|----------|-----------|-------|
| HID Keyboard | USB HID 1.1 | 1000 Hz max poll | Standard 6-key rollover report |
| CDC Serial | USB CDC ACM | 115200+ effective | Framed binary messages to companion app |

**Critical concern:** The HID+CDC composite device stalling issue on Arduino-ESP32. If using Arduino framework for bridge, test this early in development. If it fails, the bridge may need to be built with ESP-IDF.

**Fallback approach:** If composite USB proves unreliable, use two physical USB connections (HID on native USB pins, CDC via UART-to-USB adapter like CP2102). This is uglier but guaranteed to work.

### ESP-NOW Link

| Parameter | Value | Notes |
|-----------|-------|-------|
| Max payload | 250 bytes | Including ESP-NOW overhead |
| Latency | 2-5ms typical | Measured peer-to-peer, no AP |
| Range | 30-100m (open air) | Adequate for desk use |
| Channel | Must match on both units | Default channel 1, configurable |
| Encryption | Optional (PMK + LMK) | Use unencrypted for now, add later if needed |
| Peers | 1 (point-to-point) | Only two devices in system |

**WiFi coexistence:** ESP-NOW and WiFi share the radio. If either unit ever needs WiFi (e.g., NTP for clock mode), they must be on the same channel. For now, no WiFi needed -- bridge gets time from companion app.

### UART Link

| Parameter | Value | Notes |
|-----------|-------|-------|
| Baud rate | 115200 | Standard, reliable, fast enough for all message types |
| Data bits | 8N1 | Standard |
| Flow control | None | Not needed at this data rate with small messages |
| Display pins | GPIO 10 (TX), GPIO 11 (RX) | UART1 on CrowPanel |
| Bridge pins | GPIO 17 (TX), GPIO 18 (RX) | Any free GPIOs, configurable |
| Wiring | 3 wires: TX-RX crossover + GND | No level shifting needed (both 3.3V) |

### Companion App to Bridge (USB Serial)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Device | /dev/ttyACMx | CDC ACM device, auto-detected |
| Baud rate | 115200 | Convention, actual USB speed is much higher |
| Protocol | Same binary framing as ESP-NOW/UART | Shared protocol across all links |
| Detection | pyserial list_ports, match VID/PID | ESP32-S3 has Espressif VID 0x303A |

## Build Order and Dependencies

The components have clear dependency ordering that dictates build phases:

```
shared/protocol.h          <-- must exist first, everything depends on it
    |
    ├── UART link (display) + UART link (bridge)     <-- simplest transport, test first
    |       |
    |       └── Message routing (bridge)             <-- prove end-to-end with UART
    |               |
    |               ├── USB HID (bridge)             <-- prove hotkeys reach PC
    |               |
    |               └── USB CDC (bridge)             <-- prove serial to companion
    |
    ├── ESP-NOW link (display) + ESP-NOW link (bridge)  <-- add wireless after wired works
    |       |
    |       └── Transport abstraction + failover      <-- dual-link logic
    |
    ├── Stats display (display UI)                    <-- needs transport working
    |
    ├── Config store + config push                    <-- needs chunked transfer working
    |
    ├── Companion app (stats + editor)                <-- needs USB CDC working
    |
    └── Power management + clock mode                 <-- last, most independent
```

**Key insight:** Build wired (UART) end-to-end first. It is deterministic, debuggable with a logic analyzer, and removes wireless uncertainty from early development. Once hotkeys flow Display->Bridge->PC over UART, add ESP-NOW as the second transport. The transport abstraction layer can be built once both individual links work.

## Scalability Considerations

This is a single-user embedded system, not a web service. "Scalability" here means:

| Concern | Current Design | If It Grows |
|---------|---------------|-------------|
| Number of hotkey pages | 4-8 pages in SPIFFS config | SPIFFS limit (~1MB), could support 50+ pages |
| Stats update rate | 1-2 Hz | ESP-NOW bandwidth supports up to ~50 Hz if ever needed |
| Config size | ~2-5 KB JSON | Chunked transfer handles up to ~64 KB |
| Multiple displays | Not supported | Would need ESP-NOW broadcast + addressing scheme |
| Multiple PCs | Not supported | Would need multiple bridge units |

## Sources

- [ESP-NOW Arduino API documentation](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/espnow.html) -- MEDIUM confidence (official docs)
- [ESP32 USB Device Stack](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/peripherals/usb_device.html) -- HIGH confidence (official ESP-IDF docs)
- [ESP32-S3 CDC+HID stall issue #10307](https://github.com/espressif/arduino-esp32/issues/10307) -- HIGH confidence (documented bug)
- [esp32-cdc-keyboard composite device example](https://github.com/cnfatal/esp32-cdc-keyboard) -- MEDIUM confidence (working project)
- [ESP-NOW two-way communication](https://randomnerdtutorials.com/esp-now-two-way-communication-esp32/) -- MEDIUM confidence (tutorial, verified with official docs)
- [ESP32 UART documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/uart.html) -- HIGH confidence (official)
- [Bluetooth System Monitor project](https://github.com/DustinWatts/Bluetooth-System-Monitor) -- LOW confidence (similar concept, different implementation)
- Existing codebase analysis: `src/main.cpp`, `backup/`, `elecrow-Info/Code/` -- HIGH confidence (direct inspection)

---
*Architecture research for: CrowPanel Command Center dual-ESP32 system*
*Researched: 2026-02-14*
