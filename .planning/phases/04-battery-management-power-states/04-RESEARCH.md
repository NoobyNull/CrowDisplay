# Phase 4: Battery Management + Power States - Research

**Researched:** 2026-02-15
**Domain:** LiPo battery monitoring, ESP32-S3 ADC/I2C fuel gauge, PWM backlight control, power state machine, D-Bus shutdown signaling, ESP-NOW wake detection
**Confidence:** MEDIUM

## Summary

Phase 4 adds untethered battery operation, a power state machine (ACTIVE -> DIMMED -> CLOCK_MODE), brightness control, and shutdown/wake signaling. The central technical challenge is battery voltage monitoring: the CrowPanel 7.0" schematic shows a battery charging circuit (TP4056-class charger at 500mA via JST PH2.0-2P BAT connector) but Elecrow has explicitly confirmed on their forums that the board does NOT route battery voltage to any ADC-readable GPIO pin. This means battery monitoring requires either (a) adding an external I2C fuel gauge module (MAX17048) on the existing I2C bus, or (b) soldering a voltage divider wire from the BAT+ pad to a free GPIO with ADC capability. Both approaches require hardware modification.

The other subsystems are more straightforward. Backlight brightness is already configured in firmware via LovyanGFX's `Light_PWM` on GPIO 2, and the library provides `lcd.setBrightness(0-255)`. The power state machine is pure firmware logic with no external dependencies. The companion app shutdown signal uses systemd-logind's `PrepareForShutdown` D-Bus signal, which is well-documented and requires only the `dbus-next` Python library. A new `MSG_POWER_STATE` message type in the protocol enables the bridge to relay shutdown signals to the display.

**Primary recommendation:** Use an I2C MAX17048 fuel gauge breakout connected to the existing I2C bus (SDA=19, SCL=20) with I2C mutex protection. This avoids the CrowPanel's lack of battery ADC, provides accurate percentage readings via ModelGauge algorithm (no voltage-to-percentage lookup table needed), and uses the already-proven I2C infrastructure. If the user prefers a simpler approach, a voltage divider from BAT+ to GPIO 13 (one of the few free GPIOs) with `analogRead()` is possible but less accurate.

## Standard Stack

### Core (Display Firmware Additions)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SparkFun MAX1704x | 1.0.4+ | I2C fuel gauge for battery % and voltage | Widely used, supports MAX17048, simple API: `cellPercent()`, `cellVoltage()` |
| LovyanGFX Light_PWM | 1.1.8 (existing) | Backlight brightness PWM on GPIO 2 | Already configured in display_hw.cpp, `lcd.setBrightness(0-255)` |

### Core (Companion App Additions)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dbus-next | 0.2.3+ | Async D-Bus client for PrepareForShutdown signal | Pure Python, asyncio-native, no compiled deps, maintained |

### Core (Protocol Additions)
| Component | Details | Purpose |
|-----------|---------|---------|
| MSG_POWER_STATE | New message type 0x05 | Bridge -> Display: PC power state (shutdown, wake) |
| MSG_BRIGHTNESS | New message type 0x06 | (Optional) if brightness needs sync |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| MAX17048 I2C fuel gauge | Voltage divider + ADC | Simpler hardware but inaccurate % due to non-linear LiPo discharge curve; ESP32-S3 ADC also non-linear; requires calibration |
| MAX17048 I2C fuel gauge | MAX17043 | MAX17043 is older, same I2C address (0x36), same library; MAX17048 is newer with better accuracy |
| dbus-next | dbus-python (legacy) | dbus-python is C-based, harder to install, no asyncio support. dbus-next is pure Python |
| dbus-next | dasbus | Also pure Python, but less maintained than dbus-next |

**Installation (companion addition):**
```bash
pip install dbus-next
```

**Installation (fuel gauge library in platformio.ini):**
```ini
lib_deps =
    sparkfun/SparkFun MAX1704x Fuel Gauge Arduino Library@^1.0.4
```

## Architecture Patterns

### Power State Machine

The display firmware maintains a three-state power state machine:

```
                  ┌─────────────┐
     touch/msg    │             │  idle timeout
    ┌────────────►│   ACTIVE    ├──────────────┐
    │             │ (full bright)│              │
    │             └──────┬──────┘              ▼
    │                    │              ┌──────────────┐
    │                    │  MSG_POWER   │   DIMMED     │
    │                    │  _STATE      │ (low bright) │
    │                    │  shutdown    └──────┬───────┘
    │                    │                     │ MSG_POWER_STATE
    │                    ▼                     │ shutdown (or timeout)
    │             ┌──────────────┐             │
    │             │  CLOCK_MODE  │◄────────────┘
    │             │ (minimal UI) │
    │             └──────┬───────┘
    │                    │ bridge heartbeat
    │                    │ detected (MSG_STATS
    │                    │ or MSG_HOTKEY_ACK)
    └────────────────────┘
```

**States:**
- `ACTIVE`: Full brightness, stats header visible, hotkey grid active, touch responsive
- `DIMMED`: Reduced brightness (e.g., 30%), all UI still functional, triggered by idle timeout (configurable, e.g., 60s no touch)
- `CLOCK_MODE`: Minimal brightness (e.g., 10%), simplified UI showing only time + battery %, ESP-NOW listener remains active, triggered by explicit shutdown signal from companion

**Transitions:**
- ACTIVE -> DIMMED: No touch input for `IDLE_TIMEOUT_MS` (60000ms)
- DIMMED -> ACTIVE: Any touch input or incoming message
- DIMMED -> CLOCK_MODE: `MSG_POWER_STATE` with shutdown flag received
- ACTIVE -> CLOCK_MODE: `MSG_POWER_STATE` with shutdown flag received
- CLOCK_MODE -> ACTIVE: Any incoming ESP-NOW message from bridge (indicates PC is back online)

### Idle Activity Tracking

```cpp
// In main loop, track last activity time
static uint32_t last_activity = 0;

// Update on touch
void on_touch() { last_activity = millis(); }

// Update on message receive
void on_message() { last_activity = millis(); }

// In loop: check idle
if (power_state == ACTIVE && millis() - last_activity > IDLE_TIMEOUT_MS) {
    transition_to(DIMMED);
}
```

### Clock Mode UI Pattern

Clock mode replaces the hotkey grid with a minimal screen:

```
┌─────────────────────────────┐
│                             │
│         14:32               │  (large time, lv_font_montserrat_48)
│                             │
│        85%  🔋              │  (battery percentage)
│                             │
└─────────────────────────────┘
```

Implementation: Create a dedicated LVGL screen object at startup. Switch between main screen and clock screen using `lv_scr_load()`. Never create/destroy screens dynamically (LVGL memory fragmentation).

### D-Bus Shutdown Signal Flow

```
PC prepares to shut down
    │
    ▼
systemd-logind emits PrepareForShutdown(true)
    │
    ▼
Companion app receives signal via dbus-next
    │
    ▼
Companion sends MSG_POWER_STATE {state=SHUTDOWN} to bridge via HID output report
    │
    ▼
Bridge relays MSG_POWER_STATE over ESP-NOW to display
    │
    ▼
Display transitions to CLOCK_MODE
    │
    ▼
PC powers off (bridge loses USB power)
...
PC powers on
    │
    ▼
Bridge boots, starts ESP-NOW, begins sending heartbeats/stats
    │
    ▼
Display receives ESP-NOW message, transitions CLOCK_MODE -> ACTIVE
```

### Stats Header Enhancement for Device Status (DISP-08)

The existing stats header (90px, two rows) needs a third row or sidebar for device status indicators. Recommended approach: add device status to the existing header bar (45px title bar at top):

```
┌─────────────────────────────────────────────────┐
│ ⌨ Hyprland Hotkeys    🔋 85%  📶  ☀ ████░░  │  <- Title bar + status
├─────────────────────────────────────────────────┤
│ CPU 42%  RAM 67%  GPU 31%  CPU 52°C  GPU 61°C │  <- Stats row 1
│ ↑ 12 KB/s  ↓ 340 KB/s  Disk 45%               │  <- Stats row 2
└─────────────────────────────────────────────────┘
```

- Battery: percentage + icon (color-coded: green >50%, yellow 20-50%, red <20%)
- ESP-NOW link: icon that pulses/grays based on last received message age
- Brightness: tappable slider or +/- buttons in header

### Brightness Control UI

The brightness control in the header should be a simple tappable interface. Options:

**Recommended: Tap-cycle brightness levels**
- Three brightness presets: HIGH (255), MEDIUM (128), LOW (32)
- Tapping the brightness icon cycles through levels
- Minimal UI space, simple implementation, no drag gesture conflicts with tabview

**Alternative: LVGL slider**
- `lv_slider_create()` in header row
- Maps slider value (0-255) to `lcd.setBrightness()`
- More precise but takes more header space and may conflict with touch gestures

### Bridge Protocol Extension

New message type for power state signaling:

```cpp
// In protocol.h
enum MsgType : uint8_t {
    MSG_HOTKEY      = 0x01,
    MSG_HOTKEY_ACK  = 0x02,
    MSG_STATS       = 0x03,
    MSG_MEDIA_KEY   = 0x04,
    MSG_POWER_STATE = 0x05,  // NEW: Bridge -> Display: power state change
};

struct __attribute__((packed)) PowerStateMsg {
    uint8_t state;  // 0 = PC_SHUTDOWN, 1 = PC_WAKE
};
```

The bridge needs a handler: when it receives `MSG_POWER_STATE` from companion via vendor HID, relay it to display via ESP-NOW. The companion sends this before shutdown and potentially on startup.

### Recommended File Structure Changes

```
display/
├── display_hw.cpp    # Add: setBrightness() wrapper, expose lcd reference
├── display_hw.h      # Add: set_backlight(uint8_t level), get_backlight()
├── battery.cpp       # NEW: I2C fuel gauge polling, voltage-to-% (if ADC), charge detection
├── battery.h         # NEW: battery_init(), battery_read() -> {percent, voltage, charging}
├── power.cpp         # NEW: Power state machine (ACTIVE/DIMMED/CLOCK_MODE)
├── power.h           # NEW: power_init(), power_update(), power_state(), PowerState enum
├── ui.cpp            # Modify: add clock screen, device status in header, brightness control
├── ui.h              # Modify: add show_clock_mode(), set_brightness_level()
├── espnow_link.cpp   # Modify: handle MSG_POWER_STATE
├── main.cpp          # Modify: integrate power state machine into loop
shared/
├── protocol.h        # Modify: add MSG_POWER_STATE, PowerStateMsg
companion/
├── hotkey_companion.py  # Modify: add D-Bus shutdown listener, send MSG_POWER_STATE
```

### Anti-Patterns to Avoid
- **Creating/destroying LVGL screens dynamically:** Causes heap fragmentation. Create all screens at startup, switch with `lv_scr_load()`.
- **Reading I2C fuel gauge from ESP-NOW callback:** ESP-NOW callbacks run in WiFi task context. Queue the request, read in main loop with I2C mutex.
- **Blocking `delay()` in power state transitions:** Use non-blocking millis()-based transitions. Fading brightness should be incremental in the main loop.
- **Deep sleep for clock mode:** Kills ESP-NOW listener, prevents fast wake. Light sleep also problematic with RGB display bus. Stay in active mode with reduced backlight.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Battery % from voltage | Custom LiPo discharge curve lookup | MAX17048 fuel gauge IC | LiPo discharge is highly non-linear; ESP32 ADC is also non-linear; fuel gauge uses coulomb counting + ModelGauge for accurate % |
| D-Bus signal handling | Raw socket/file descriptor D-Bus protocol | dbus-next library | D-Bus wire protocol is complex, authentication is tricky, signal matching is error-prone |
| Backlight PWM | Manual LEDC channel setup | LovyanGFX `lcd.setBrightness(0-255)` | Already configured via Light_PWM in display_hw.cpp; handles LEDC timer and channel internally |
| Time display (clock mode) | NTP sync / WiFi time | ESP32 internal millis() counter + initial time from companion | WiFi kills ESP-NOW; millis() drifts but is good enough for a clock that resyncs when PC wakes |

**Key insight:** The biggest "don't hand-roll" item is battery percentage calculation. A $2 MAX17048 breakout board saves hours of calibration and provides genuinely accurate readings. The alternative (voltage divider + lookup table) requires empirical calibration for each battery and degrades with battery age.

## Common Pitfalls

### Pitfall 1: CrowPanel Has No Battery ADC Pin
**What goes wrong:** Developer assumes the BAT connector includes a voltage divider to an ADC-readable GPIO, writes `analogRead()` code, gets zero or garbage.
**Why it happens:** The CrowPanel 7.0" V2.2 schematic shows the BAT connector goes to a TP4056-class charger IC whose output feeds the 3.3V regulator. No voltage divider to any ESP32 GPIO exists on the PCB.
**How to avoid:** Use an I2C fuel gauge (MAX17048) on the existing I2C bus (SDA=19, SCL=20), OR solder a wire from BAT+ through a voltage divider to a free GPIO.
**Warning signs:** `analogRead()` returns 0 or 4095 regardless of battery state.

### Pitfall 2: I2C Bus Contention with Fuel Gauge
**What goes wrong:** Adding a fuel gauge to the I2C bus causes touch glitches or fuel gauge reads return stale data.
**Why it happens:** GT911 touch controller, PCA9557, PCF8575, and now MAX17048 all share I2C on pins 19/20. If fuel gauge read interrupts a GT911 multi-byte register sequence, both devices get confused.
**How to avoid:** ALL I2C access MUST go through the existing FreeRTOS mutex (already implemented in touch.cpp). Poll fuel gauge infrequently (every 10-30 seconds, not every loop iteration). Never read fuel gauge from ISR or callback.
**Warning signs:** Touch stops responding intermittently; fuel gauge returns 0xFF or NaN.

### Pitfall 3: Backlight PWM Conflict with RGB Bus
**What goes wrong:** Calling `analogWrite()` on GPIO 2 directly interferes with the LovyanGFX Light_PWM configuration and causes display flicker.
**Why it happens:** LovyanGFX's Light_PWM allocates a specific LEDC channel for GPIO 2 during `lcd.begin()`. If you configure the same pin with a different LEDC channel or `analogWrite()`, the two PWM sources conflict.
**How to avoid:** Always use `lcd.setBrightness(value)` from LovyanGFX. Never touch GPIO 2 directly for PWM.
**Warning signs:** Display flickers, backlight stuck at one level, or display goes completely dark.

### Pitfall 4: Time Source for Clock Mode
**What goes wrong:** Clock mode shows wrong time because ESP32 has no RTC and WiFi (for NTP) kills ESP-NOW.
**Why it happens:** The CrowPanel 7.0" V2.2 schematic does NOT show an onboard RTC (unlike the Advance model). The ESP32's internal clock drifts ~20 ppm (~1.7 seconds/day). WiFi for NTP is incompatible with ESP-NOW.
**How to avoid:** Sync time from the companion app: add a `MSG_TIME_SYNC` message sent periodically (e.g., every stats update) carrying epoch seconds. Display firmware uses this to set `struct timeval` via `settimeofday()`. Clock mode uses `gettimeofday()` for display. Drift during clock mode (PC off) is acceptable -- a few seconds over hours.
**Warning signs:** Clock shows 00:00 or grossly wrong time after running for days.

### Pitfall 5: PrepareForShutdown Signal Timing
**What goes wrong:** Companion app sends shutdown signal but the HID write fails because USB is already being torn down.
**Why it happens:** systemd shutdown sequence can be fast. By the time PrepareForShutdown fires and the companion processes it, USB devices may already be in the process of disconnecting.
**How to avoid:** Use an inhibitor lock. Before listening, call `Inhibit("shutdown", "HotkeyCompanion", "Sending shutdown signal to display", "delay")`. When PrepareForShutdown(true) fires, send the HID message, then close the inhibitor fd to allow shutdown to proceed. Default inhibitor timeout is 5 seconds, which is plenty.
**Warning signs:** Bridge never receives shutdown signal; display stays in ACTIVE mode after PC powers off.

### Pitfall 6: ESP-NOW Listener Power in Clock Mode
**What goes wrong:** Clock mode consumes nearly as much power as active mode because WiFi radio stays fully active.
**Why it happens:** ESP-NOW requires the WiFi radio to be on. Even with `WiFi.setSleep(true)`, the radio must wake periodically to receive broadcasts.
**How to avoid:** This is an accepted tradeoff (documented in PROJECT.md Key Decisions). Mitigation: reduce display backlight to minimum (e.g., 5-10), disable LVGL tick rate (or reduce to 1Hz), reduce main loop frequency with longer delays. The 7" LCD backlight is by far the biggest power consumer, not the radio.
**Warning signs:** Battery drains in <4 hours in clock mode. If this happens, reduce backlight further or add a physical power switch.

## Code Examples

### Battery Reading with MAX17048 (I2C Fuel Gauge)

```cpp
// Source: SparkFun MAX1704x library examples + I2C mutex pattern from project
#include <SparkFun_MAX1704x_Fuel_Gauge_Arduino_Library.h>
#include "touch.h"  // For i2c_mutex

static SFE_MAX1704X lipo(MAX1704X_MAX17048);

bool battery_init() {
    if (xSemaphoreTake(i2c_mutex, pdMS_TO_TICKS(50))) {
        bool ok = lipo.begin();  // Uses Wire (SDA=19, SCL=20), address 0x36
        xSemaphoreGive(i2c_mutex);
        if (ok) {
            Serial.println("MAX17048 fuel gauge found");
            return true;
        }
    }
    Serial.println("MAX17048 not found -- battery monitoring unavailable");
    return false;
}

struct BatteryState {
    uint8_t  percent;    // 0-100, or 0xFF if unavailable
    float    voltage;    // Volts (e.g., 3.85)
    bool     available;  // false if no fuel gauge detected
};

BatteryState battery_read() {
    BatteryState state = {0xFF, 0.0f, false};
    if (xSemaphoreTake(i2c_mutex, pdMS_TO_TICKS(50))) {
        float v = lipo.getVoltage();
        float p = lipo.getSOC();  // State of charge (0-100)
        xSemaphoreGive(i2c_mutex);

        if (v > 0) {
            state.available = true;
            state.voltage = v;
            state.percent = (uint8_t)constrain(p, 0, 100);
        }
    }
    return state;
}
```

### Alternative: Voltage Divider on Free GPIO (If No Fuel Gauge)

```cpp
// If user solders a voltage divider from BAT+ to GPIO 13:
//   BAT+ ---[100K]---+---[100K]--- GND
//                     |
//                   GPIO 13
//
// At 4.2V battery: GPIO sees 2.1V (within ADC range)
// At 3.0V battery: GPIO sees 1.5V

#define BATTERY_ADC_PIN 13
#define DIVIDER_RATIO   2.0   // (R1+R2)/R2 = (100K+100K)/100K
#define ADC_REF_MV      3300  // 3.3V reference
#define ADC_MAX         4095  // 12-bit ADC

uint8_t battery_read_adc_percent() {
    int raw = analogRead(BATTERY_ADC_PIN);
    float voltage = (raw * ADC_REF_MV / ADC_MAX) * DIVIDER_RATIO / 1000.0;

    // Simple linear mapping (inaccurate but functional)
    // 4.2V = 100%, 3.3V = 0%
    float pct = (voltage - 3.3) / (4.2 - 3.3) * 100.0;
    return (uint8_t)constrain(pct, 0, 100);
}
```

### Backlight Brightness Control via LovyanGFX

```cpp
// Source: LovyanGFX documentation, existing display_hw.cpp Light_PWM config
// The LGFX class in display_hw.cpp already configures Light_PWM on GPIO 2.
// After lcd.begin(), simply call:

// Global brightness control
static uint8_t current_brightness = 200;  // Default high

void set_backlight(uint8_t level) {
    current_brightness = level;
    lcd.setBrightness(level);  // 0 = off, 255 = max
    Serial.printf("Backlight: %d\n", level);
}

uint8_t get_backlight() {
    return current_brightness;
}

// Brightness presets for tap-cycle UI
enum BrightnessLevel { BRIGHT_HIGH = 0, BRIGHT_MED, BRIGHT_LOW, BRIGHT_COUNT };
static const uint8_t brightness_values[] = {255, 128, 32};
static uint8_t brightness_idx = 0;

void cycle_brightness() {
    brightness_idx = (brightness_idx + 1) % BRIGHT_COUNT;
    set_backlight(brightness_values[brightness_idx]);
}
```

### D-Bus PrepareForShutdown Listener (Companion App)

```python
# Source: systemd logind D-Bus API, dbus-next library
# https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html

import asyncio
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def listen_for_shutdown(on_shutdown_callback):
    """Listen for systemd PrepareForShutdown signal.

    Uses an inhibitor lock to delay shutdown long enough to send
    the signal to the bridge.
    """
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # Get logind manager proxy
    introspection = await bus.introspect(
        'org.freedesktop.login1',
        '/org/freedesktop/login1'
    )
    proxy = bus.get_proxy_object(
        'org.freedesktop.login1',
        '/org/freedesktop/login1',
        introspection
    )
    manager = proxy.get_interface('org.freedesktop.login1.Manager')

    # Take a delay inhibitor lock
    inhibit_fd = await manager.call_inhibit(
        'shutdown',             # what
        'HotkeyCompanion',     # who
        'Sending shutdown signal to display bridge',  # why
        'delay'                # mode
    )

    # Listen for PrepareForShutdown signal
    def on_prepare_for_shutdown(start):
        if start:  # true = shutdown starting
            asyncio.get_event_loop().call_soon_threadsafe(
                on_shutdown_callback
            )
            # Close inhibitor fd to allow shutdown to proceed
            import os
            os.close(inhibit_fd)

    manager.on_prepare_for_shutdown(on_prepare_for_shutdown)

    # Keep listening
    await bus.wait_for_disconnect()
```

### Power State Machine Implementation

```cpp
// Source: Project architecture pattern
enum PowerState { POWER_ACTIVE, POWER_DIMMED, POWER_CLOCK };

static PowerState power_state = POWER_ACTIVE;
static uint32_t last_activity_ms = 0;
static const uint32_t IDLE_TIMEOUT_MS = 60000;  // 60s to dim
static const uint8_t BRIGHTNESS_ACTIVE = 200;
static const uint8_t BRIGHTNESS_DIMMED = 64;
static const uint8_t BRIGHTNESS_CLOCK  = 16;

void power_activity() {
    last_activity_ms = millis();
    if (power_state == POWER_DIMMED) {
        power_state = POWER_ACTIVE;
        set_backlight(BRIGHTNESS_ACTIVE);
        // UI: ensure hotkey view is showing
    }
}

void power_shutdown_received() {
    power_state = POWER_CLOCK;
    set_backlight(BRIGHTNESS_CLOCK);
    // UI: switch to clock screen
    show_clock_mode();
}

void power_wake_detected() {
    if (power_state == POWER_CLOCK) {
        power_state = POWER_ACTIVE;
        set_backlight(BRIGHTNESS_ACTIVE);
        // UI: switch back to hotkey view
        show_hotkey_view();
    }
}

void power_update() {
    if (power_state == POWER_ACTIVE) {
        if (millis() - last_activity_ms > IDLE_TIMEOUT_MS) {
            power_state = POWER_DIMMED;
            set_backlight(BRIGHTNESS_DIMMED);
        }
    }
}
```

### Time Sync from Companion

```cpp
// Source: ESP-IDF settimeofday API
#include <sys/time.h>

struct __attribute__((packed)) TimeSyncMsg {
    uint32_t epoch_seconds;  // Unix timestamp from companion
};

void handle_time_sync(const TimeSyncMsg *msg) {
    struct timeval tv;
    tv.tv_sec = msg->epoch_seconds;
    tv.tv_usec = 0;
    settimeofday(&tv, nullptr);
    Serial.printf("Time synced: %lu\n", msg->epoch_seconds);
}

// In clock mode UI:
void update_clock_display(lv_obj_t *time_label) {
    time_t now;
    time(&now);
    struct tm *local = localtime(&now);
    lv_label_set_text_fmt(time_label, "%02d:%02d", local->tm_hour, local->tm_min);
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Voltage divider + lookup table for battery % | I2C fuel gauge (MAX17048/LC709203F) | 2020+ | Accurate % without per-battery calibration |
| Manual LEDC setup for backlight | LovyanGFX Light_PWM + `setBrightness()` | LovyanGFX 1.0+ | One-line brightness control, no LEDC conflicts |
| dbus-python (C bindings) | dbus-next (pure Python, asyncio) | 2020+ | No compiled dependencies, works in venvs, async-native |
| Deep sleep for power saving | Light sleep or active-dim with reduced backlight | Always for ESP-NOW | ESP-NOW requires active WiFi radio; deep sleep kills it |

**Deprecated/outdated:**
- `dbus-python`: Legacy D-Bus bindings, hard to install in venvs, no asyncio
- `analogWrite()` on ESP32: Deprecated in Arduino-ESP32 2.x+; use LEDC API or LovyanGFX wrapper

## Open Questions

1. **Which battery monitoring approach will the user choose?**
   - What we know: CrowPanel has no built-in battery ADC. Two options: I2C fuel gauge (MAX17048, ~$2-5) or voltage divider (requires soldering to BAT+ pad).
   - What's unclear: Whether the user has a MAX17048 breakout available, or prefers the simpler voltage divider approach.
   - Recommendation: Plan for both. Implement battery.cpp with an abstract interface; concrete implementation selected at compile time via `#define`. Default to fuel gauge if detected on I2C scan, fall back to ADC if configured.

2. **CrowPanel battery capacity and expected runtime**
   - What we know: The BAT connector accepts standard 3.7V LiPo with JST PH2.0-2P. Charging at 500mA. The 7" LCD backlight is the dominant power consumer.
   - What's unclear: What capacity LiPo the user plans to use, and how long it will last. A 2000mAh cell might last 2-4 hours at full brightness, much longer in clock mode.
   - Recommendation: This is a user characterization task. Plan a verification step where the user measures actual runtime with their chosen battery.

3. **Free GPIO for voltage divider (if no fuel gauge)**
   - What we know: Most GPIOs are consumed by the RGB display bus. GPIO 13 appears to be free (not in the pin list for display bus, I2C, UART, or backlight). GPIO 10/11 are used for UART but have ADC1 capability. The GPIO D connector exposes GPIO 38 but it controls the power rail.
   - What's unclear: Whether GPIO 13 is truly free and routed to a pad on the CrowPanel PCB. Needs physical board inspection.
   - Recommendation: If fuel gauge is not available, GPIO 13 with ADC2_CH2 is the best candidate, but note ADC2 is unreliable with WiFi active. Better to use I2C fuel gauge which avoids this entirely.

4. **Clock mode time accuracy requirements**
   - What we know: ESP32 internal oscillator drifts ~20 ppm. No onboard RTC on CrowPanel 7.0" V2.2. WiFi/NTP incompatible with ESP-NOW.
   - What's unclear: How long the display will be in clock mode (hours? days?). Drift of 1.7s/day may or may not matter.
   - Recommendation: Add `MSG_TIME_SYNC` to protocol. Companion sends current epoch time with each stats update (1 Hz). In clock mode, drift is acceptable. If user needs better accuracy, an external I2C RTC (DS3231) could be added to the same I2C bus.

5. **Companion app architecture change for async D-Bus**
   - What we know: Current companion is synchronous (blocking `time.sleep()` loop). dbus-next requires asyncio event loop.
   - What's unclear: Best way to integrate async D-Bus with the existing sync HID write loop.
   - Recommendation: Run D-Bus listener in a separate thread, or convert the main loop to asyncio with `asyncio.sleep()`. The simpler approach: use a threading.Thread for the D-Bus listener that sets a threading.Event when shutdown is detected. Main loop checks the event each iteration.

## Sources

### Primary (HIGH confidence)
- [ESP-IDF v4.4 ADC Documentation](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32s3/api-reference/peripherals/adc.html) - ESP32-S3 ADC1 channel/GPIO mapping, WiFi restrictions
- [org.freedesktop.login1 D-Bus API](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html) - PrepareForShutdown signal, Inhibit() method, shutdown flow
- [Elecrow CrowPanel 7.0" Wiki](https://www.elecrow.com/wiki/esp32-display-702727-intelligent-touch-screen-wi-fi26ble-800480-hmi-display.html) - BAT connector (PH2.0-2P), GPIO D (IO38), backlight on GPIO 2
- [CrowPanel 7.0" V2.2 Schematic PDF](elecrow-Info/File/Circuit%20Schematic%20Diagram/) - Battery charging circuit, no ADC tap on BAT line
- [Elecrow Forum: Batterie Status](https://forum.elecrow.com/discussion/914/batterie-status) - Confirmed: "Product does not support battery voltage from analog input"
- Project codebase: display_hw.cpp (Light_PWM config on GPIO 2), espnow_link.cpp (message handling pattern), protocol.h (message types)

### Secondary (MEDIUM confidence)
- [SparkFun MAX1704x Library](https://github.com/sparkfun/SparkFun_MAX1704x_Fuel_Gauge_Arduino_Library) - Arduino library API for MAX17048
- [Adafruit MAX17048 Guide](https://learn.adafruit.com/adafruit-max17048-lipoly-liion-fuel-gauge-and-battery-monitor/arduino) - Wiring, I2C address (0x36), example code
- [LovyanGFX setBrightness](https://github.com/lovyan03/LovyanGFX/discussions/537) - Light_PWM usage, 0-255 range confirmed
- [dbus-next GitHub](https://github.com/altdesktop/python-dbus-next) - Pure Python async D-Bus client
- [systemd Inhibitor Locks](https://systemd.io/INHIBITOR_LOCKS/) - Delay lock mechanism for shutdown signaling

### Tertiary (LOW confidence)
- [ESP32 Forum: LiPo voltage measurement](https://esp32.com/viewtopic.php?t=881) - Community approaches to voltage divider battery monitoring (varied quality)
- [Random Nerd Tutorials: ESP32 ADC](https://randomnerdtutorials.com/esp32-adc-analog-read-arduino-ide/) - General ESP32 ADC usage (not S3-specific)

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM-HIGH - Core libraries verified (LovyanGFX brightness, dbus-next, SparkFun fuel gauge). Battery monitoring approach depends on user hardware choice.
- Architecture: HIGH - Power state machine is well-understood; D-Bus shutdown flow is well-documented; all patterns follow existing codebase conventions.
- Pitfalls: HIGH - Critical "no battery ADC" finding verified from multiple sources (schematic, Elecrow forum). I2C contention well-understood from prior phases.
- Hardware characterization: LOW - CrowPanel battery circuit details partially visible from schematic but not fully documented. Free GPIO identification needs physical board verification.

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (hardware details are stable; library versions may update)
