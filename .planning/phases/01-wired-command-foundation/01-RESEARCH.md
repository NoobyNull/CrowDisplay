# Phase 1: Wired Command Foundation - Research

**Researched:** 2026-02-14
**Domain:** UART communication, USB HID keyboard, LVGL multi-page UI, I2C mutex protection
**Confidence:** HIGH

## Summary

Phase 1 delivers end-to-end hotkey delivery: user taps a button on the CrowPanel 7.0" display, a UART message reaches the bridge ESP32-S3, and the bridge fires the corresponding USB HID keystroke on the PC. This phase also upgrades the display UI from a single-page 4x3 grid to a multi-page swipeable layout with icons, color coding, and press feedback.

The technical domain is well-understood. All required components (HardwareSerial UART, USB HID via TinyUSB, LVGL tabview/swipe, FreeRTOS mutex) are built-in to the existing platform (espressif32@6.5.0 / Arduino 2.x / ESP-IDF 4.4) and require zero external libraries. The existing codebase already has working USB HID code (backup/usb_hid.cpp), a working LVGL button grid (src/main.cpp), and proven GT911 touch input. Phase 1 is primarily an integration and restructuring effort, not a greenfield build.

**Primary recommendation:** Split the monolithic main.cpp into a dual-firmware project (display + bridge), implement a simple SOF-framed UART protocol with CRC8, and wrap I2C access in a FreeRTOS mutex from day one. Use LVGL's built-in tabview widget for multi-page navigation -- it provides swipe gestures out of the box.

## Standard Stack

### Core (All Built-In -- No New Dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| HardwareSerial (Serial1) | built-in | UART link between display and bridge | ESP32-S3 has 3 UART peripherals. Serial1 can be mapped to any free GPIO via IO matrix. |
| USB.h + USBHIDKeyboard.h | built-in | USB HID keyboard on bridge | Uses TinyUSB under the hood. Already proven in project's test env and backup code. |
| LVGL | 8.3.11 | Multi-page touch UI on display | Already in project. Tabview widget provides swipe navigation. |
| LovyanGFX | 1.1.8 | Display driver for CrowPanel RGB panel | Already in project. Handles RGB565 parallel bus. |
| FreeRTOS (xSemaphoreCreateMutex) | built-in | I2C bus mutex protection | Built into ESP-IDF/Arduino core. Priority inheritance prevents priority inversion. |
| Wire (I2C) | built-in | GT911 touch + PCA9557 I/O expander | Already in project. Needs mutex wrapping. |
| PCA9557 | local lib | Touch reset sequence | Already in project. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| USBHIDConsumerControl | built-in | Media key support on bridge | Phase 1 scope includes modifier+key combos. Media keys available in backup code but deferred to Phase 3 (BRDG-04). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom UART protocol | tinyproto library | tinyproto adds dependency and complexity. Our protocol has only 1-2 message types in Phase 1. Hand-rolled is simpler and fully understood. |
| LVGL tabview (swipe) | LVGL tileview | Tileview supports 2D navigation but tabview is the standard for horizontal page swiping with tab indicators. Tabview is simpler and matches the UX. |
| Manual button grid layout | LVGL btnmatrix | Btnmatrix uses less memory but does not support per-button styling, individual icons, or complex layouts. Regular buttons in a grid are needed for the design requirements. |

### Installation

No new dependencies required. All components are built-in to espressif32@6.5.0.

```ini
; Bridge env addition to platformio.ini
[env:bridge]
platform = espressif32@6.5.0
board = esp32-s3-devkitc-1
framework = arduino
build_flags =
    -DARDUINO_USB_MODE=0
    -DARDUINO_USB_CDC_ON_BOOT=0
    -DBRIDGE_UNIT
monitor_speed = 115200
```

## Architecture Patterns

### Recommended Project Structure

```
/data/Elcrow-Display-hotkeys/
├── platformio.ini              # Multi-env: display, bridge, running (legacy)
├── shared/                     # Code shared between display and bridge
│   └── protocol.h              # Message types, SOF framing, CRC8
├── display/                    # CrowPanel firmware (env:display)
│   ├── main.cpp                # Setup/loop, module init
│   ├── ui.h / ui.cpp           # LVGL UI: tabview, hotkey pages, button creation
│   ├── touch.h / touch.cpp     # GT911 I2C polling with mutex
│   ├── display_hw.h / .cpp     # LovyanGFX init, LVGL driver setup
│   └── uart_link.h / .cpp      # UART send/receive with protocol framing
├── bridge/                     # Bridge firmware (env:bridge)
│   ├── main.cpp                # Setup/loop
│   ├── usb_hid.h / .cpp        # USB HID keyboard output
│   └── uart_link.h / .cpp      # UART receive with protocol framing
├── src/                        # Legacy (current monolithic code)
│   ├── main.cpp
│   └── lv_conf.h               # Stays here -- LVGL expects -I src
├── backup/                     # Previous modular version (reference)
└── lib/                        # Local libraries (PCA9557, etc.)
```

### Pattern 1: SOF-Framed Binary Protocol

**What:** All UART communication uses a simple framed binary protocol with Start-of-Frame byte, length, type, payload, and CRC8.

**When to use:** Every message between display and bridge.

**Frame format:**
```
┌──────┬────────┬──────┬─────────────┬──────┐
│ SOF  │ LENGTH │ TYPE │   PAYLOAD   │ CRC8 │
│ 0xAA │ 1 byte │ 1 b  │ 0-250 bytes │ 1 b  │
└──────┴────────┴──────┴─────────────┴──────┘
```

- **SOF (0xAA):** Start-of-frame marker for byte-level sync
- **LENGTH:** Payload length only (0-250)
- **TYPE:** Message type enum (see Message Types below)
- **PAYLOAD:** Type-specific packed struct data
- **CRC8:** CRC8/CCITT (polynomial 0x07) over LENGTH + TYPE + PAYLOAD bytes

**Why this design:**
- SOF byte enables recovery from partial reads or noise
- CRC8 catches corruption (essential on UART, which has no built-in integrity)
- Binary is compact and fast to parse on ESP32 -- no string allocation, no JSON parsing
- Same protocol will be reused for ESP-NOW in Phase 2 (just swap the transport)
- Shared header between display and bridge ensures protocol stays in sync

**Confidence:** HIGH -- this is a standard pattern for embedded UART communication.

### Pattern 2: Message Types for Phase 1

| Type ID | Name | Direction | Payload | Size |
|---------|------|-----------|---------|------|
| 0x01 | MSG_HOTKEY | Display -> Bridge | modifier_mask(1B) + keycode(1B) | 2 bytes |
| 0x02 | MSG_HOTKEY_ACK | Bridge -> Display | status(1B): 0=ok, 1=fail | 1 byte |

**Total frame sizes:**
- HOTKEY: SOF(1) + LEN(1) + TYPE(1) + modifier(1) + keycode(1) + CRC(1) = 6 bytes
- ACK: SOF(1) + LEN(1) + TYPE(1) + status(1) + CRC(1) = 5 bytes

At 115200 baud, 6 bytes takes ~0.5ms to transmit. Well within the 50ms latency budget.

**Phase 2 will add:** MSG_PING (0x06), MSG_PONG (0x07), MSG_STATS (0x02 repurposed), etc. The protocol is designed to be extensible by adding new type IDs.

### Pattern 3: I2C Mutex Wrapping

**What:** A FreeRTOS mutex (`SemaphoreHandle_t`) protects all I2C bus access. Every I2C transaction sequence (the complete read-modify-write for GT911, or PCA9557 operations) acquires the mutex before touching Wire and releases it after.

**When to use:** Every I2C access on the display unit. This means wrapping the GT911 polling, the PCA9557 init sequence, and any future I2C device.

**Example:**
```cpp
// Global
SemaphoreHandle_t i2c_mutex = NULL;

void setup() {
    i2c_mutex = xSemaphoreCreateMutex();
    // ...
}

// In touch polling
void poll_touch() {
    if (xSemaphoreTake(i2c_mutex, pdMS_TO_TICKS(10)) != pdTRUE) return;

    // Entire GT911 read sequence is atomic:
    Wire.beginTransmission(gt911_addr);
    Wire.write(0x81); Wire.write(0x4E);
    Wire.endTransmission();
    // ... read touch data ...
    // ... clear status register ...

    xSemaphoreGive(i2c_mutex);
}
```

**Confidence:** HIGH -- standard FreeRTOS pattern. The existing code already has I2C contention issues documented in CONCERNS.md.

### Pattern 4: LVGL Tabview for Multi-Page Navigation

**What:** Use LVGL's `lv_tabview_create()` with `LV_DIR_BOTTOM` for tab buttons at the bottom. Each tab holds a 4x3 grid of hotkey buttons. Tabview provides built-in swipe navigation between pages.

**When to use:** The main hotkey UI on the display.

**Key implementation details:**
- Create tabview with `lv_tabview_create(parent, LV_DIR_BOTTOM, tab_height)` -- this gives horizontal swipe between pages plus clickable tab buttons at the bottom
- Use `lv_tabview_add_tab(tabview, "Page Name")` for each page
- Each tab's content is a flex-wrapped row of buttons
- The backup code (backup/main.cpp) already has a working tabview implementation with 3 pages -- this is directly reusable
- All pages and buttons are created at startup, not dynamically -- avoids LVGL heap fragmentation

**Confidence:** HIGH -- the backup code already demonstrates this exact pattern working on this hardware.

### Pattern 5: Button Press Feedback (Darken + Shrink)

**What:** Each button has a `LV_STATE_PRESSED` style that darkens the background color and applies a negative transform (shrink effect).

**Example from backup code (already proven):**
```cpp
// Darken on press
lv_obj_set_style_bg_color(btn, lv_color_darken(lv_color_hex(hk->color), LV_OPA_30),
                          LV_STATE_PRESSED);
// Shrink on press
lv_obj_set_style_transform_width(btn, -3, LV_STATE_PRESSED);
lv_obj_set_style_transform_height(btn, -3, LV_STATE_PRESSED);
```

**Note:** `lv_obj_set_style_transform_width/height` is a visual-only effect in LVGL 8 -- it does not affect layout or scrollbars. This is the intended behavior for press feedback.

**Confidence:** HIGH -- already working in backup/main.cpp.

### Anti-Patterns to Avoid

- **Monolithic main.cpp with #ifdef DISPLAY / #ifdef BRIDGE:** The display and bridge have zero shared application logic. Separate firmware targets with separate main.cpp files. Shared protocol header is the only common code.

- **JSON or string-based UART protocol:** Binary packed structs are faster, smaller, and avoid heap allocation. The protocol is fixed at compile time with no dynamic fields.

- **Calling LVGL functions from UART receive callbacks or ISRs:** All LVGL calls must happen from the main loop (or a single dedicated task). Use a flag or FreeRTOS queue to signal that a UART message arrived, then process it in the LVGL task.

- **delay() in main loop for touch polling:** Replace with FreeRTOS task or millis()-based non-blocking timing. The existing `delay(50)` between touch polls blocks LVGL rendering. The existing `delay(1)` inside GT911 reads is acceptable but should be `vTaskDelay(pdMS_TO_TICKS(2))` if running in a FreeRTOS task.

- **Creating/destroying LVGL screens dynamically:** Create all 3+ pages at startup. Use tabview's built-in page switching. Dynamic screen creation fragments LVGL's internal heap.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-page swipe navigation | Custom gesture detection + screen switching | LVGL tabview widget | Tabview handles swipe gestures, page indicators, smooth scrolling, and keyboard/encoder navigation out of the box. Custom swipe detection is error-prone. |
| CRC8 calculation | Internet-copied snippet | Standard CRC8/CCITT with polynomial 0x07 and lookup table | Many CRC8 variants exist (CRC8-MAXIM, CRC8-CCITT, etc.) with different polynomials. Using the wrong one creates subtle bugs. Pick CRC8/CCITT (poly 0x07, init 0x00) and implement a 256-byte lookup table for speed. |
| USB HID keyboard | Raw TinyUSB descriptors | Arduino USBHIDKeyboard library | The library handles HID report descriptor, endpoint configuration, and modifier+key combo encoding. Raw TinyUSB is only needed for composite devices (deferred). |
| I2C bus arbitration | Custom lock flags | FreeRTOS mutex (xSemaphoreCreateMutex) | Mutexes provide priority inheritance, timeout support, and correct semantics for resource protection. Boolean flags are not thread-safe and do not prevent priority inversion. |

**Key insight:** Phase 1 uses only built-in platform components. The temptation is to add libraries, but there is nothing here that requires an external dependency.

## Common Pitfalls

### Pitfall 1: UART Byte Stream Has No Message Boundaries

**What goes wrong:** Developer sends a struct over UART and reads it on the other side, but bytes arrive fragmented or merged. The receiver reads partial messages or misaligns fields.

**Why it happens:** UART is a byte stream, not a message-oriented protocol. `Serial1.write(buf, len)` may be received as multiple smaller reads on the other side. There is no guarantee that one write maps to one read.

**How to avoid:** Use SOF-framed protocol (described above). The receiver runs a state machine: WAIT_SOF -> READ_LENGTH -> READ_TYPE -> READ_PAYLOAD -> READ_CRC -> VALIDATE. On CRC failure or timeout, discard and return to WAIT_SOF. Never assume a complete frame arrives in one read.

**Warning signs:** Hotkeys fire the wrong shortcut intermittently. Works at low frequency but breaks under sustained use. Adding Serial.println() debug output "fixes" timing (masks the real problem).

### Pitfall 2: GT911 I2C Sequence Interrupted by Concurrent Access

**What goes wrong:** Touch stops responding after adding UART communication or any new I2C device. The GT911 requires a multi-step I2C transaction (write register address -> delay -> read data -> write clear flag). If another I2C operation interrupts this sequence, the GT911 enters an undefined state.

**Why it happens:** The current code has no I2C bus protection. Everything runs in `loop()` sequentially, which works today by accident. The moment UART receive handling or a FreeRTOS task touches the I2C bus during a GT911 transaction, corruption occurs.

**How to avoid:** Implement FreeRTOS mutex around ALL I2C access from day one (Pattern 3 above). This is DISP-12 and is a Phase 1 requirement specifically because this problem was already observed during development.

**Warning signs:** I2C errors (Wire.endTransmission() returns non-zero). GT911 needs re-discovery. Touch works for minutes then stops. Rebooting temporarily fixes it.

### Pitfall 3: USB HID Not Recognized When Build Flags Are Wrong

**What goes wrong:** The bridge ESP32-S3 compiles and uploads successfully, but the PC does not recognize it as a USB HID keyboard. `lsusb` may show an Espressif device but no HID interface.

**Why it happens:** The ESP32-S3 Arduino core requires specific build flags to enable USB OTG mode:
- `ARDUINO_USB_MODE=0` -- use USB-OTG peripheral (not JTAG)
- `ARDUINO_USB_CDC_ON_BOOT=0` -- do not auto-create CDC serial (we want HID-only)

If these flags are missing or wrong, the USB stack initializes in the wrong mode. The existing project already has these flags in `[env:test]` but they must be copied to the new `[env:bridge]`.

**How to avoid:** Verify build flags in platformio.ini for the bridge environment. Test USB HID recognition before building the full protocol stack. The bridge should appear as a standard USB HID keyboard in `lsusb` output.

**Warning signs:** `lsusb` shows "Espressif USB JTAG/serial debug unit" instead of an HID device. `dmesg` shows no "input:" line for the device.

### Pitfall 4: UART RX Pin Conflict With Flash on ESP32 (Not S3)

**What goes wrong:** Developers read that GPIO 10 and 11 conflict with SPI flash and avoid using them, even on the ESP32-S3.

**Why it happens:** The original ESP32 uses GPIO 6-11 for SPI flash. The ESP32-S3 does NOT have this restriction -- GPIO 10, 11, 12, 13 are free general-purpose I/O on the S3. The S3 uses GPIO 26-32 for flash/PSRAM (and GPIO 33-37 in octal mode). Verified from ESP-IDF GPIO documentation.

**How to avoid:** Use GPIO 10 (TX) and GPIO 11 (RX) on the CrowPanel for UART1 to the bridge. These pins are confirmed free on the ESP32-S3 and are not used by the CrowPanel's RGB display bus, I2C bus, or backlight control.

**Warning signs:** Working code that unnecessarily avoids perfectly good GPIO pins, leading to awkward wiring.

### Pitfall 5: Bridge HID-Only Means No Debug Serial Over USB

**What goes wrong:** Developer configures bridge as HID-only (`ARDUINO_USB_CDC_ON_BOOT=0`), then has no way to see debug output from the bridge. `Serial.println()` goes nowhere because the USB CDC serial is not initialized.

**Why it happens:** The prior decision (STATE.md) is "Bridge is HID-only to PC (avoids documented USB HID+CDC composite stall bug)." This means the bridge's native USB port is purely HID -- no serial console.

**How to avoid:** Use UART0 (GPIO 43/44 on the DevKitC-1) for debug serial output. Connect a USB-to-serial adapter (or use PlatformIO's monitor port pointing at the UART0 serial adapter) for development. The bridge's native USB is HID-only to the PC; debug output goes through a separate serial connection.

**Warning signs:** "My bridge code is running but I can't see any Serial output" during development.

## Code Examples

### UART Protocol -- Shared Header (shared/protocol.h)

```cpp
// Source: Standard embedded UART framing pattern
#pragma once
#include <stdint.h>

// Frame structure: [SOF][LEN][TYPE][PAYLOAD...][CRC8]
#define PROTO_SOF       0xAA
#define PROTO_MAX_PAYLOAD 250

// Message types
enum MsgType : uint8_t {
    MSG_HOTKEY     = 0x01,  // Display -> Bridge: fire keystroke
    MSG_HOTKEY_ACK = 0x02,  // Bridge -> Display: keystroke delivered
};

// MSG_HOTKEY payload
struct __attribute__((packed)) HotkeyMsg {
    uint8_t modifiers;  // MOD_CTRL | MOD_SHIFT | MOD_ALT | MOD_GUI
    uint8_t keycode;    // ASCII key or special key code
};

// MSG_HOTKEY_ACK payload
struct __attribute__((packed)) HotkeyAckMsg {
    uint8_t status;  // 0 = success, 1 = error
};

// CRC8/CCITT (poly 0x07, init 0x00)
static const uint8_t crc8_table[256] = {
    0x00, 0x07, 0x0E, 0x09, 0x1C, 0x1B, 0x12, 0x15,
    0x38, 0x3F, 0x36, 0x31, 0x24, 0x23, 0x2A, 0x2D,
    0x70, 0x77, 0x7E, 0x79, 0x6C, 0x6B, 0x62, 0x65,
    0x48, 0x4F, 0x46, 0x41, 0x54, 0x53, 0x5A, 0x5D,
    0xE0, 0xE7, 0xEE, 0xE9, 0xFC, 0xFB, 0xF2, 0xF5,
    0xD8, 0xDF, 0xD6, 0xD1, 0xC4, 0xC3, 0xCA, 0xCD,
    0x90, 0x97, 0x9E, 0x99, 0x8C, 0x8B, 0x82, 0x85,
    0xA8, 0xAF, 0xA6, 0xA1, 0xB4, 0xB3, 0xBA, 0xBD,
    0xC7, 0xC0, 0xC9, 0xCE, 0xDB, 0xDC, 0xD5, 0xD2,
    0xFF, 0xF8, 0xF1, 0xF6, 0xE3, 0xE4, 0xED, 0xEA,
    0xB7, 0xB0, 0xB9, 0xBE, 0xAB, 0xAC, 0xA5, 0xA2,
    0x8F, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9D, 0x9A,
    0x27, 0x20, 0x29, 0x2E, 0x3B, 0x3C, 0x35, 0x32,
    0x1F, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0D, 0x0A,
    0x57, 0x50, 0x59, 0x5E, 0x4B, 0x4C, 0x45, 0x42,
    0x6F, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7D, 0x7A,
    0x89, 0x8E, 0x87, 0x80, 0x95, 0x92, 0x9B, 0x9C,
    0xB1, 0xB6, 0xBF, 0xB8, 0xAD, 0xAA, 0xA3, 0xA4,
    0xF9, 0xFE, 0xF7, 0xF0, 0xE5, 0xE2, 0xEB, 0xEC,
    0xC1, 0xC6, 0xCF, 0xC8, 0xDD, 0xDA, 0xD3, 0xD4,
    0x69, 0x6E, 0x67, 0x60, 0x75, 0x72, 0x7B, 0x7C,
    0x51, 0x56, 0x5F, 0x58, 0x4D, 0x4A, 0x43, 0x44,
    0x19, 0x1E, 0x17, 0x10, 0x05, 0x02, 0x0B, 0x0C,
    0x21, 0x26, 0x2F, 0x28, 0x3D, 0x3A, 0x33, 0x34,
    0x4E, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5C, 0x5B,
    0x76, 0x71, 0x78, 0x7F, 0x6A, 0x6D, 0x64, 0x63,
    0x3E, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2C, 0x2B,
    0x06, 0x01, 0x08, 0x0F, 0x1A, 0x1D, 0x14, 0x13,
    0xAE, 0xA9, 0xA0, 0xA7, 0xB2, 0xB5, 0xBC, 0xBB,
    0x96, 0x91, 0x98, 0x9F, 0x8A, 0x8D, 0x84, 0x83,
    0xDE, 0xD9, 0xD0, 0xD7, 0xC2, 0xC5, 0xCC, 0xCB,
    0xE6, 0xE1, 0xE8, 0xEF, 0xFA, 0xFD, 0xF4, 0xF3
};

inline uint8_t crc8_calc(const uint8_t* data, size_t len) {
    uint8_t crc = 0x00;
    for (size_t i = 0; i < len; i++) {
        crc = crc8_table[crc ^ data[i]];
    }
    return crc;
}
```

### UART Send Function (display side)

```cpp
// Source: Standard embedded UART framing
#include <HardwareSerial.h>
#include "protocol.h"

// Display UART1: TX=GPIO10, RX=GPIO11
#define UART_TX_PIN 10
#define UART_RX_PIN 11
#define UART_BAUD   115200

HardwareSerial BridgeSerial(1);  // UART1

void uart_init() {
    BridgeSerial.begin(UART_BAUD, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
}

bool uart_send(MsgType type, const uint8_t* payload, uint8_t len) {
    uint8_t frame[4 + len];  // SOF + LEN + TYPE + payload + CRC
    frame[0] = PROTO_SOF;
    frame[1] = len;
    frame[2] = (uint8_t)type;
    if (len > 0) memcpy(&frame[3], payload, len);
    frame[3 + len] = crc8_calc(&frame[1], 2 + len);  // CRC over LEN+TYPE+PAYLOAD

    return BridgeSerial.write(frame, 4 + len) == (4 + len);
}

// Example: send hotkey
void send_hotkey_to_bridge(uint8_t modifiers, uint8_t keycode) {
    HotkeyMsg msg = { modifiers, keycode };
    uart_send(MSG_HOTKEY, (uint8_t*)&msg, sizeof(msg));
}
```

### UART Receive State Machine (bridge side)

```cpp
// Source: Standard embedded UART framing with state machine
enum RxState { WAIT_SOF, READ_LEN, READ_TYPE, READ_PAYLOAD, READ_CRC };

struct FrameParser {
    RxState state = WAIT_SOF;
    uint8_t len = 0;
    uint8_t type = 0;
    uint8_t payload[PROTO_MAX_PAYLOAD];
    uint8_t payload_idx = 0;

    // Returns true when a valid frame is received
    bool feed(uint8_t byte) {
        switch (state) {
            case WAIT_SOF:
                if (byte == PROTO_SOF) state = READ_LEN;
                break;
            case READ_LEN:
                len = byte;
                if (len > PROTO_MAX_PAYLOAD) { state = WAIT_SOF; break; }
                state = READ_TYPE;
                break;
            case READ_TYPE:
                type = byte;
                payload_idx = 0;
                state = (len > 0) ? READ_PAYLOAD : READ_CRC;
                break;
            case READ_PAYLOAD:
                payload[payload_idx++] = byte;
                if (payload_idx >= len) state = READ_CRC;
                break;
            case READ_CRC: {
                // Verify CRC over LEN + TYPE + PAYLOAD
                uint8_t check_buf[2 + len];
                check_buf[0] = len;
                check_buf[1] = type;
                memcpy(&check_buf[2], payload, len);
                uint8_t expected = crc8_calc(check_buf, 2 + len);
                state = WAIT_SOF;
                return (byte == expected);
            }
        }
        return false;
    }
};
```

### USB HID on Bridge (adapted from backup/usb_hid.cpp)

```cpp
// Source: Existing project backup/usb_hid.cpp + Arduino ESP32 USB API
#include <USB.h>
#include <USBHIDKeyboard.h>

USBHIDKeyboard Keyboard;

void usb_hid_init() {
    Keyboard.begin();
    USB.productName("HotkeyBridge");
    USB.manufacturerName("CrowPanel");
    USB.begin();
    // Note: No delay(500) -- USB enumeration happens asynchronously
}

void fire_keystroke(uint8_t modifiers, uint8_t keycode) {
    if (modifiers & MOD_CTRL)  Keyboard.press(KEY_LEFT_CTRL);
    if (modifiers & MOD_SHIFT) Keyboard.press(KEY_LEFT_SHIFT);
    if (modifiers & MOD_ALT)   Keyboard.press(KEY_LEFT_ALT);
    if (modifiers & MOD_GUI)   Keyboard.press(KEY_LEFT_GUI);
    Keyboard.press(keycode);
    delay(20);  // Minimum hold time for host to register
    Keyboard.releaseAll();
}
```

### I2C Mutex Setup

```cpp
// Source: ESP32 Arduino FreeRTOS examples + Random Nerd Tutorials
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

SemaphoreHandle_t i2c_mutex = NULL;

void setup() {
    i2c_mutex = xSemaphoreCreateMutex();
    configASSERT(i2c_mutex != NULL);
    // ... rest of init
}

// Wrapper for any I2C operation
bool i2c_take(TickType_t timeout_ms = 10) {
    return xSemaphoreTake(i2c_mutex, pdMS_TO_TICKS(timeout_ms)) == pdTRUE;
}

void i2c_give() {
    xSemaphoreGive(i2c_mutex);
}
```

### LVGL Tabview with Hotkey Pages (adapted from backup/main.cpp)

```cpp
// Source: Existing project backup/main.cpp -- already proven on this hardware
static void create_ui() {
    lv_obj_set_style_bg_color(lv_scr_act(), lv_color_hex(0x0f0f23), LV_PART_MAIN);

    // Tab view with tabs at bottom, 45px tab bar height
    lv_obj_t *tabview = lv_tabview_create(lv_scr_act(), LV_DIR_BOTTOM, 45);
    lv_obj_set_size(tabview, 800, 480);

    // Style tab buttons
    lv_obj_t *tab_btns = lv_tabview_get_tab_btns(tabview);
    lv_obj_set_style_bg_color(tab_btns, lv_color_hex(0x16213e), LV_PART_MAIN);
    lv_obj_set_style_text_color(tab_btns, lv_color_hex(0xBBBBBB), LV_PART_MAIN);
    lv_obj_set_style_text_color(tab_btns, lv_color_hex(0x3498DB),
                                LV_PART_ITEMS | LV_STATE_CHECKED);

    // Create pages
    for (int p = 0; p < NUM_PAGES; p++) {
        lv_obj_t *tab = lv_tabview_add_tab(tabview, pages[p].name);
        lv_obj_set_flex_flow(tab, LV_FLEX_FLOW_ROW_WRAP);
        lv_obj_set_flex_align(tab, LV_FLEX_ALIGN_SPACE_EVENLY,
                              LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_SPACE_EVENLY);

        for (int i = 0; i < pages[p].count; i++) {
            create_hotkey_button(tab, &pages[p].hotkeys[i]);
        }
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BLE keyboard on display | USB HID via bridge ESP32 | Project decision | Lower latency, no pairing, more reliable |
| Single monolithic main.cpp | Split display/bridge firmware | Phase 1 | Two PlatformIO environments, shared protocol header |
| Unprotected I2C access | FreeRTOS mutex-wrapped I2C | Phase 1 | Prevents GT911 touch corruption under concurrent access |
| Single-page 4x3 grid | Multi-page tabview with swipe | Phase 1 | Supports 3+ pages of 12 hotkeys each |
| Direct USB HID on display | UART -> Bridge -> USB HID | Phase 1 | Decouples display from PC USB, enables wireless in Phase 2 |

**Deprecated/outdated:**
- ESP32-BLE-Keyboard library: No longer used for PC connection. Bridge uses Arduino USBHIDKeyboard instead.
- NimBLE-Arduino: Only in legacy `[env:running]`. Not used in Phase 1.

## Open Questions

1. **CrowPanel GPIO 10/11 physical access**
   - What we know: GPIO 10 and 11 are free on the ESP32-S3 (confirmed via ESP-IDF docs). The CrowPanel has a UART header but it exposes GPIO 43/44 (UART0).
   - What's unclear: Whether GPIO 10/11 are physically accessible on the CrowPanel board -- they may need soldering to test pads or require using the GPIO expansion header (if it exposes these pins). The Elecrow wiki mentions a "GPIO_D" header with IO38.
   - Recommendation: Inspect the physical CrowPanel board for GPIO 10/11 access. If not accessible, use GPIO 17/18 (if exposed) or the existing UART header on GPIO 43/44 (sacrificing debug serial during runtime). **This must be verified before wiring the UART link.**
   - Confidence: MEDIUM -- the ESP32-S3 definitely supports UART1 on GPIO 10/11, but physical board access is unverified.

2. **UART baud rate selection**
   - What we know: 115200 baud is standard, reliable, and fast enough (6-byte hotkey frame transmits in ~0.5ms).
   - What's unclear: Whether higher baud rates (230400, 460800, 921600) would work reliably over a short cable (30cm). Higher rates leave more headroom for Phase 2 stats messages.
   - Recommendation: Start with 115200. Test higher rates during development. The 50ms latency budget is easily met at any baud rate for the Phase 1 message set.
   - Confidence: HIGH for 115200, MEDIUM for higher rates.

3. **Bridge debug serial access**
   - What we know: Bridge is HID-only (no USB CDC). UART0 on GPIO 43/44 is available for debug.
   - What's unclear: Whether the ESP32-S3 DevKitC-1 has a built-in USB-to-serial chip on UART0 (some DevKitC-1 variants do, others use native USB only).
   - Recommendation: Check the specific bridge board. If it has a CP2102/CH340 on UART0, use that for debug. If not, use a separate USB-to-serial adapter connected to GPIO 43/44.
   - Confidence: MEDIUM -- depends on specific DevKitC-1 variant purchased.

4. **Hotkey definition data structure**
   - What we know: Phase 1 uses hardcoded hotkey definitions (acceptable per STATE.md). Phase 5 adds persistent config.
   - What's unclear: Whether to use the compact `HotkeyDef` struct from current main.cpp (label + modifiers + key) or the richer `Hotkey` struct from backup (label + description + modifiers + key + color + icon).
   - Recommendation: Use the richer struct from backup since Phase 1 requires per-button color coding (DISP-04) and icons (DISP-05). The struct needs: label, modifiers, keycode, color, icon. Description is optional.
   - Confidence: HIGH -- the backup struct maps directly to requirements.

## Sources

### Primary (HIGH confidence)
- ESP-IDF GPIO Reference (v5.5.2): https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/gpio.html -- confirmed GPIO 10-13 are free on ESP32-S3
- ESP-IDF SPI Flash/PSRAM Config: https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/flash_psram_config.html -- GPIO 26-32 for flash, GPIO 33-37 for octal mode
- Arduino ESP32 Serial (UART) API: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/serial.html -- HardwareSerial with custom pins
- LVGL 8.3 Style Properties: https://docs.lvgl.io/8.3/overview/style-props.html -- transform_width/height for press feedback
- LVGL 8.3 Tabview: https://docs.lvgl.io/8.3/examples.html -- tabview with swipe
- Existing project backup/main.cpp, backup/usb_hid.cpp -- proven USB HID + tabview code
- Existing project src/main.cpp -- proven GT911 touch, LovyanGFX, LVGL display driver

### Secondary (MEDIUM confidence)
- Random Nerd Tutorials ESP32 UART: https://randomnerdtutorials.com/esp32-uart-communication-serial-arduino/ -- UART1 custom pin examples
- Random Nerd Tutorials ESP32 FreeRTOS Mutex: https://randomnerdtutorials.com/esp32-freertos-mutex-arduino/ -- mutex patterns
- GitHub I2C mutex gist: https://gist.github.com/cibomahto/41c0d5703782938108408d9f02c25d13 -- I2C bus sharing with mutex
- Philippe Kueng ESP32-S3 USB keyboard guide: https://philippkueng.ch/2025-06-16-creating-a-virtual-usb-keyboard-with-the-esp32-s3.html -- HID-only setup
- CRC8 implementation: https://github.com/UlrikHjort/CRC8/blob/master/crc8.c -- reference CRC8 code
- Elecrow CrowPanel 7.0" wiki: https://www.elecrow.com/wiki/esp32-display-702727-intelligent-touch-screen-wi-fi26ble-800480-hmi-display.html -- board pinout

### Tertiary (LOW confidence)
- ESP32 Forum UART1 default pin conflicts: https://esp32.com/viewtopic.php?t=28800 -- discusses original ESP32, NOT ESP32-S3. GPIO 10/11 conflict is ESP32-only.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all components are built-in, no new dependencies, several already proven in the existing codebase
- Architecture: HIGH -- the dual-firmware structure and UART protocol are standard embedded patterns; backup code demonstrates the UI pattern
- Pitfalls: HIGH -- I2C mutex, UART framing, and USB build flags are well-documented issues with clear solutions
- GPIO pin availability: MEDIUM -- ESP32-S3 docs confirm GPIO 10/11 are free, but CrowPanel physical access needs board inspection
- UART protocol: HIGH -- standard SOF+CRC framing is the canonical approach for embedded serial communication

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (stable domain, no fast-moving dependencies)
