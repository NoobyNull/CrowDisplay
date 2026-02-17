# Phase 11: Hardware Buttons + System Actions - Research

**Researched:** 2026-02-17
**Domain:** I2C I/O expander button/encoder reading, system action framework, editor UI extensions
**Confidence:** HIGH

## Summary

Phase 11 adds hardware input support (4 push buttons + 1 rotary encoder with push) via a PCF8575 I2C I/O expander on TCA9548A mux channel 0, extends the action system with new "system" action types (page nav, mode cycle, config mode, brightness), adds an editor UI section for hardware button configuration below the canvas, and creates a settings tab for display function configuration (clock, slideshow, power, mode cycle, SD card management).

The existing codebase already has the I2C bus infrastructure (Wire on SDA=19, SCL=20), an I2C mutex in `touch.cpp`, a rotary encoder module (`rotary_encoder.h/cpp`) that will be replaced, brightness control via LovyanGFX PWM on GPIO 2, display mode switching (MODE_HOTKEYS/CLOCK/PICTURE_FRAME/STANDBY), and a config server with HTTP endpoints on WebServer. The companion editor has a properties panel, canvas scene, page toolbar, and right-side tabbed panels. All of these are extension points, not greenfield work.

**Primary recommendation:** Use direct PCF8575 I2C register reads (2-byte read for all 16 pins) via the TCA9548A mux rather than a library. Implement quadrature decoding with a state machine in the polling loop. Extend ActionType enum and VALID_ACTION_TYPES for system actions. Add hardware button config as a new JSON section in config.json.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- PCF8575 I/O expander on TCA9548A mux channel 0
- PCF8575 I2C address: auto-detect (likely 0x20 default)
- Button 1: P1 (active low, depressed connects to ground)
- Button 2: P2 (active low)
- Button 3: P3 (active low)
- Button 4: P4 (active low)
- Encoder push/switch: P0 (active low)
- Encoder CLK: P11
- Encoder DT: P10
- All inputs are active low (pull-up, grounded when pressed)
- All 4 buttons are fully configurable -- same action system as touchscreen widgets
- No fixed-function buttons; user assigns any action type per button in editor
- Single press only, no long-press support
- Hardware buttons reuse the existing properties panel (action type dropdown with all action types including new system actions)
- Encoder is a single configurable input with push as its own action
- CW/CCW represent positive/negative of the assigned action (e.g., volume +/-, page next/prev, workspace slide left/right)
- One action per detent (no continuous/rapid-fire)
- "App select" encoder mode: rotation cycles through and highlights widgets on the current page, wrapping at the end; encoder push fires the highlighted widget's action
- New action types available for BOTH hardware buttons AND touchscreen widgets: page navigation (next/prev/goto N), mode switch (cycle through configurable set), config mode (enter SoftAP), brightness (PWM if works, else on/off toggle)
- All system actions execute locally on the display firmware (no PC/companion needed)
- All 4 display modes available for mode cycle: hotkeys, clock, slideshow, standby
- User configures which modes are in the rotation and their order
- Hardware buttons and encoder appear on the canvas BELOW the 800x480 display area, simulating physical position
- Clicking a hardware button opens the same properties panel as touchscreen widgets
- Encoder shown as a single widget; properties panel shows push action + CW/CCW action assignment
- Dedicated settings tab alongside page tabs at the top of the editor
- Clock settings: analog+digital style, 12/24h, color theme
- Slideshow settings: interval, transition effect; images in /slideshow/ root folder on SD card
- Power settings: dim timeout, sleep timeout, wake-on-touch
- Mode cycle settings: which modes are enabled and their rotation order
- SD card management: show capacity/usage, list files, delete files from companion app
- Companion editor manages SD card contents over WiFi
- HTTP endpoints on existing config server for file listing, usage stats, and file deletion

### Claude's Discretion
- Config storage approach (same config.json vs separate settings file)
- SD card HTTP API endpoint design (/api/sd/list, /api/sd/usage, /api/sd/delete or similar)
- Encoder debounce and quadrature decode implementation
- PCF8575 polling interval vs interrupt-driven approach
- Visual representation of hardware buttons below canvas (styling, layout)
- Brightness PWM GPIO pin and implementation (if available)

### Deferred Ideas (OUT OF SCOPE)
- None -- discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LovyanGFX | ^1.1.8 | Display driver, backlight PWM | Already used, `Light_PWM` on GPIO 2 provides brightness control |
| LVGL | v8.3.11 | UI framework | Already used, v8 API throughout |
| ArduinoJson | ^7.4.0 | JSON config serialization | Already used with PSRAM allocator |
| Wire (Arduino) | built-in | I2C communication | Already used for GT911 touch, PCA9557 |
| SD (Arduino) | built-in | SD card file operations | Already used for config storage |
| WebServer (ESP32) | built-in | HTTP endpoints for config server | Already used for config upload, OTA, image upload |
| PySide6 | system | Companion editor GUI | Already used |
| requests | system | HTTP client for companion | Already used |

### New (no additional libraries needed)
The PCF8575 and TCA9548A can be driven with raw Wire I2C calls (2-3 lines each). No external library is needed. The existing PCA9557 library is only used for touch reset and is separate.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw Wire for PCF8575 | xreef/PCF8575_library | Library adds encoder support but is overkill for 2-byte register reads; raw Wire is simpler, no dependency |
| Raw Wire for TCA9548A | RobTillaart/TCA9548 | Library wraps a single `Wire.write(1 << channel)` -- trivially done inline |
| Polling PCF8575 | Interrupt-driven via INT pin | Interrupt requires a free GPIO and ISR; polling at 20Hz is sufficient for human input and matches existing touch polling rate |

## Architecture Patterns

### Existing Code Structure (extension points)
```
display/
  config.h       # AppConfig, ActionType enum, WidgetConfig -- ADD new ActionTypes, hardware config structs
  config.cpp     # JSON ser/deser -- ADD hardware config sections
  ui.h           # UI public API -- ADD hardware highlight/focus functions
  ui.cpp         # Widget rendering, btn_event_cb -- EXTEND for system actions
  main.cpp       # Main loop, encoder polling -- REPLACE encoder section with PCF8575 polling
  power.h/cpp    # DisplayMode, PowerState -- ADD mode cycling function
  config_server.h/cpp  # HTTP endpoints -- ADD SD card management endpoints
  rotary_encoder.h/cpp # REPLACE entirely (currently AS5600-based, not PCF8575)
  touch.h/cpp    # I2C mutex (i2c_take/i2c_give) -- REUSE for PCF8575 access
  sdcard.h/cpp   # SD card file I/O -- ADD directory listing, usage stats

companion/
  config_manager.py   # Config model, action types -- ADD new action types, hardware config
  ui/editor_main.py   # Editor window -- ADD hardware section below canvas, settings tab
  action_executor.py  # Action dispatch -- ADD system action handling (display-local, no PC exec)
  http_client.py      # Device HTTP client -- ADD SD card management API methods
```

### Pattern 1: TCA9548A Channel Selection
**What:** Select I2C mux channel before accessing PCF8575
**When to use:** Every time before reading PCF8575
**Example:**
```cpp
// Source: TCA9548A datasheet, verified via web search
#define TCA9548A_ADDR 0x70  // Default address, A0-A2 = LOW
#define PCF8575_CHANNEL 0   // Mux channel 0

void tca_select(uint8_t channel) {
    Wire.beginTransmission(TCA9548A_ADDR);
    Wire.write(1 << channel);
    Wire.endTransmission();
}
```

### Pattern 2: PCF8575 16-bit Read
**What:** Read all 16 pins in a single 2-byte I2C read
**When to use:** Button/encoder polling
**Example:**
```cpp
// PCF8575: read 2 bytes = 16 bits of pin state
// Pins are active-low (pulled up internally, grounded when pressed)
#define PCF8575_ADDR 0x20  // Default, auto-detect at startup

uint16_t pcf8575_read() {
    Wire.requestFrom((uint8_t)PCF8575_ADDR, (uint8_t)2);
    if (Wire.available() < 2) return 0xFFFF;  // All high = nothing pressed
    uint8_t lo = Wire.read();
    uint8_t hi = Wire.read();
    return (uint16_t)hi << 8 | lo;
}

// Extract individual pins:
// Button 1 (P1):  !(pins & (1 << 1))  // active low, so invert
// Button 2 (P2):  !(pins & (1 << 2))
// Button 3 (P3):  !(pins & (1 << 3))
// Button 4 (P4):  !(pins & (1 << 4))
// Enc SW (P0):    !(pins & (1 << 0))
// Enc CLK (P11):  (pins >> 11) & 1
// Enc DT (P10):   (pins >> 10) & 1
```

### Pattern 3: Quadrature Encoder State Machine
**What:** Decode CW/CCW rotation from CLK/DT signals via state machine
**When to use:** Encoder polling (20Hz)
**Example:**
```cpp
// Source: Standard Gray code quadrature decoder
// State transitions: [prev_CLK,prev_DT] -> [curr_CLK,curr_DT]
// Valid CW sequence:  00->01->11->10->00
// Valid CCW sequence: 00->10->11->01->00

static uint8_t enc_prev_state = 0;
static int8_t enc_count = 0;

// Transition table: index = (prev_state << 2) | curr_state
// Values: 0=no move, 1=CW, -1=CCW, 2=invalid (skip)
static const int8_t enc_table[16] = {
     0, -1,  1,  2,
     1,  0,  2, -1,
    -1,  2,  0,  1,
     2,  1, -1,  0
};

int8_t encoder_decode(bool clk, bool dt) {
    uint8_t curr_state = (clk << 1) | dt;
    uint8_t index = (enc_prev_state << 2) | curr_state;
    int8_t result = enc_table[index];
    enc_prev_state = curr_state;

    if (result == 1 || result == -1) {
        return result;  // +1 = CW, -1 = CCW
    }
    return 0;  // No valid transition or invalid
}
```

### Pattern 4: System Action Extension
**What:** Add new ActionType values and handle them in btn_event_cb
**When to use:** Adding page nav, mode cycle, config mode, brightness actions
**Example:**
```cpp
// In config.h -- extend ActionType enum:
enum ActionType : uint8_t {
    ACTION_HOTKEY = 0,
    ACTION_MEDIA_KEY = 1,
    ACTION_LAUNCH_APP = 2,
    ACTION_SHELL_CMD = 3,
    ACTION_OPEN_URL = 4,
    ACTION_DISPLAY_SETTINGS = 5,  // existing
    ACTION_DISPLAY_CLOCK = 6,     // existing
    ACTION_DISPLAY_PICTURE = 7,   // existing
    // NEW system actions:
    ACTION_PAGE_NEXT = 8,
    ACTION_PAGE_PREV = 9,
    ACTION_PAGE_GOTO = 10,        // uses keycode field as page number
    ACTION_MODE_CYCLE = 11,       // cycle through configured modes
    ACTION_BRIGHTNESS = 12,       // cycle brightness presets
    ACTION_CONFIG_MODE = 13,      // enter SoftAP config mode
};

// In ui.cpp btn_event_cb -- add cases:
case ACTION_PAGE_NEXT: ui_next_page(); return;
case ACTION_PAGE_PREV: ui_prev_page(); return;
case ACTION_PAGE_GOTO: show_page(bed->keycode); return;
case ACTION_MODE_CYCLE: mode_cycle_next(); return;
case ACTION_BRIGHTNESS: power_cycle_brightness(); return;
case ACTION_CONFIG_MODE: /* same as ACTION_DISPLAY_SETTINGS */ return;
```

### Pattern 5: Hardware Config in JSON
**What:** Store hardware button/encoder assignments in config.json
**When to use:** Persistent configuration
**Example:**
```json
{
  "version": 3,
  "hardware_buttons": {
    "button_1": { "action_type": 8, "label": "Next Page" },
    "button_2": { "action_type": 9, "label": "Prev Page" },
    "button_3": { "action_type": 11, "label": "Mode" },
    "button_4": { "action_type": 13, "label": "Config" },
    "encoder_push": { "action_type": 12, "label": "Brightness" },
    "encoder_rotate": { "action_type": 8, "mode": "page_nav" }
  },
  "mode_cycle": {
    "enabled_modes": [0, 1, 2],
    "order": [0, 1, 2]
  },
  "display_settings": {
    "dim_timeout_sec": 60,
    "sleep_timeout_sec": 300,
    "wake_on_touch": true,
    "clock_24h": true,
    "clock_color_theme": 16777215,
    "slideshow_interval_sec": 30,
    "slideshow_transition": "fade"
  }
}
```

### Pattern 6: SD Card Management HTTP API
**What:** HTTP endpoints for SD card file listing, usage, and deletion
**When to use:** Companion app settings tab
**Example:**
```cpp
// GET /api/sd/usage -> {"total_mb": 7432, "used_mb": 156, "free_mb": 7276}
// GET /api/sd/list?path=/slideshow -> {"files": [{"name": "img1.png", "size": 45320}, ...]}
// DELETE /api/sd/delete?path=/slideshow/img1.png -> {"success": true}

static void handle_sd_usage() {
    if (!sdcard_mounted()) {
        web_server->send(503, "application/json", "{\"error\":\"SD not mounted\"}");
        return;
    }
    uint64_t total = SD.cardSize() / (1024 * 1024);
    uint64_t used = SD.usedBytes() / (1024 * 1024);
    String json = "{\"total_mb\":" + String((uint32_t)total) +
                  ",\"used_mb\":" + String((uint32_t)used) +
                  ",\"free_mb\":" + String((uint32_t)(total - used)) + "}";
    web_server->send(200, "application/json", json);
}
```

### Anti-Patterns to Avoid
- **Don't use interrupts for PCF8575:** The INT output requires a free GPIO pin and ISR handler. Polling at 20Hz is plenty fast for human input (50ms latency) and avoids I2C-from-ISR complexity.
- **Don't read individual PCF8575 pins:** Always read all 16 bits in one 2-byte I2C transaction. Individual pin reads are not supported by the hardware.
- **Don't add encoder library dependency:** The quadrature decode is 10 lines of state machine code. A library adds unnecessary complexity for a single encoder.
- **Don't make hardware buttons a new widget type:** Hardware buttons are not rendered on the display canvas. They exist only in config and are mapped to actions. The editor shows them below the canvas as a separate UI section.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| I2C mutex | Custom lock | Existing `i2c_take()`/`i2c_give()` in touch.cpp | Already handles GT911 contention, PCF8575 reads must use same mutex |
| JSON serialization | String concatenation | ArduinoJson v7 (already used) | Escape handling, nested objects, memory management |
| HTTP server | Raw socket handling | WebServer (already used) | Route handling, multipart parsing already working |
| Brightness control | LEDC PWM setup | `set_backlight()` / `lcd.setBrightness()` | LovyanGFX already configures Light_PWM on GPIO 2 |
| Config persistence | Custom file format | config.json extension (already atomic write) | Existing `config_save()` handles backup, verify, atomic rename |

**Key insight:** Nearly every low-level subsystem needed already exists. This phase is primarily about wiring them together and extending the action/config model.

## Common Pitfalls

### Pitfall 1: I2C Bus Contention with GT911 Touch
**What goes wrong:** PCF8575 reads corrupt GT911 touch polling or vice versa, causing ghost touches or missed button presses.
**Why it happens:** Both devices share the same I2C bus (Wire on SDA=19, SCL=20). Without mutex protection, concurrent transactions interleave.
**How to avoid:** Always wrap TCA9548A channel select + PCF8575 read in a single `i2c_take()`/`i2c_give()` block. The channel select and read must be atomic (no mutex release between them).
**Warning signs:** Intermittent touch failures, ghost presses, I2C NACK errors in serial log.

### Pitfall 2: TCA9548A Channel Left on Wrong Bus
**What goes wrong:** After reading PCF8575 on mux channel 0, subsequent GT911 touch reads fail because the mux is still routing channel 0.
**Why it happens:** TCA9548A latches the last channel selection. If GT911 is on a different channel (or directly on the bus without going through the mux), the mux state doesn't matter. However, if the mux routes channel 0 to the same bus as GT911, address conflicts could occur.
**How to avoid:** After reading PCF8575, either deselect all mux channels (`Wire.write(0)`) or verify that GT911 is on the main I2C bus, not behind the mux. The PCA9557 (0x18-0x1F range) and GT911 (0x5D/0x14) are directly on the bus based on existing code -- the TCA9548A (0x70) is a separate device.
**Warning signs:** GT911 stops responding after hardware button polling starts.

### Pitfall 3: Encoder Bounce Causing Double Detents
**What goes wrong:** A single encoder detent registers as 2 or more events, causing double page navigation or double brightness changes.
**Why it happens:** Mechanical encoder contacts bounce, producing multiple transitions per detent. Polling at 20Hz can catch bounce transitions.
**How to avoid:** The state machine approach inherently filters most bounce. Additionally, add a minimum time between valid encoder events (~80ms) to debounce at the application level.
**Warning signs:** Rotating one click produces 2-3 events in serial log.

### Pitfall 4: Button Debounce on Press/Release
**What goes wrong:** A single button press fires the action 2-3 times.
**Why it happens:** Mechanical switch contacts bounce for 5-20ms after state change.
**How to avoid:** Track last state change time per button. Ignore transitions within 50ms of the last valid transition. Only fire action on press (not release) for single-press mode.
**Warning signs:** Serial log shows multiple "button pressed" messages for a single physical press.

### Pitfall 5: Config Version Bump Breaking Existing Configs
**What goes wrong:** Adding `hardware_buttons` and `display_settings` to config.json causes old configs without these fields to fail validation.
**Why it happens:** Config loader expects fields that don't exist in older JSON files.
**How to avoid:** Make all new config sections optional with sensible defaults. Use `doc["field"] | default_value` pattern (already used throughout config.cpp). DO NOT bump CONFIG_VERSION unless schema is truly incompatible -- new optional fields don't require a version bump.
**Warning signs:** Device falls back to defaults after firmware update.

### Pitfall 6: SD.usedBytes() Undercounting
**What goes wrong:** SD card usage reported to companion is wrong (misses subdirectory contents).
**Why it happens:** `SD.usedBytes()` on some ESP32 Arduino implementations only counts root directory.
**How to avoid:** For accurate usage, use `SD.totalBytes() - SD.usedBytes()` for free space, or iterate directories recursively to sum file sizes. Alternatively, use `SD.cardSize()` for total and accept the approximation.
**Warning signs:** Usage shows much less than expected despite many files in subdirectories.

## Code Examples

### Complete PCF8575 Polling with TCA9548A Mux
```cpp
// Source: Datasheet patterns + existing codebase patterns

#define TCA9548A_ADDR 0x70
#define PCF8575_MUX_CH 0
#define PCF8575_ADDR 0x20

// Pin masks for 16-bit register
#define BTN1_MASK  (1 << 1)   // P1
#define BTN2_MASK  (1 << 2)   // P2
#define BTN3_MASK  (1 << 3)   // P3
#define BTN4_MASK  (1 << 4)   // P4
#define ENC_SW_MASK (1 << 0)  // P0
#define ENC_CLK_MASK (1 << 11) // P11
#define ENC_DT_MASK  (1 << 10) // P10

static uint16_t prev_pins = 0xFFFF;
static uint32_t btn_debounce_ms[5] = {0};  // 4 buttons + encoder switch
static const uint32_t DEBOUNCE_MS = 50;

bool hw_input_poll(uint16_t &pins_out) {
    if (!i2c_take(10)) return false;

    // Select TCA9548A channel 0
    Wire.beginTransmission(TCA9548A_ADDR);
    Wire.write(1 << PCF8575_MUX_CH);
    if (Wire.endTransmission() != 0) {
        i2c_give();
        return false;
    }

    // Read PCF8575 16-bit register
    if (Wire.requestFrom((uint8_t)PCF8575_ADDR, (uint8_t)2) != 2) {
        i2c_give();
        return false;
    }
    uint8_t lo = Wire.read();
    uint8_t hi = Wire.read();
    pins_out = ((uint16_t)hi << 8) | lo;

    // Deselect mux (optional safety)
    Wire.beginTransmission(TCA9548A_ADDR);
    Wire.write(0);
    Wire.endTransmission();

    i2c_give();
    return true;
}
```

### Hardware Button Config Structure (firmware side)
```cpp
// Extends AppConfig in config.h

struct HwButtonConfig {
    ActionType action_type;
    std::string label;
    uint8_t keycode;       // For ACTION_PAGE_GOTO (page number)
    uint16_t consumer_code; // For ACTION_MEDIA_KEY
    uint8_t modifiers;     // For ACTION_HOTKEY

    HwButtonConfig() : action_type(ACTION_PAGE_NEXT), label(""), keycode(0),
                       consumer_code(0), modifiers(0) {}
};

struct EncoderConfig {
    ActionType push_action;
    std::string push_label;
    uint8_t encoder_mode;     // 0=page_nav, 1=volume, 2=brightness, 3=app_select, 4=mode_cycle

    EncoderConfig() : push_action(ACTION_BRIGHTNESS), push_label(""),
                      encoder_mode(0) {}
};

struct ModeCycleConfig {
    std::vector<uint8_t> enabled_modes;  // DisplayMode values in rotation order

    ModeCycleConfig() : enabled_modes({0, 1, 2, 3}) {}  // All modes by default
};

// Add to AppConfig:
// HwButtonConfig hw_buttons[4];
// EncoderConfig encoder;
// ModeCycleConfig mode_cycle;
// uint16_t dim_timeout_sec;
// uint16_t sleep_timeout_sec;
// bool wake_on_touch;
// bool clock_24h;
// uint32_t clock_color_theme;
```

### Encoder "App Select" Mode (widget focus cycling)
```cpp
// In ui.cpp or a new hw_input.cpp

static int focused_widget_idx = -1;  // -1 = no focus

void ui_focus_next_widget() {
    if (page_containers.empty()) return;
    int widget_count = /* number of actionable widgets on current page */;
    if (widget_count == 0) return;
    focused_widget_idx = (focused_widget_idx + 1) % widget_count;
    // Apply visual highlight (border glow) to focused widget
    ui_apply_focus_highlight(focused_widget_idx);
}

void ui_focus_prev_widget() {
    if (page_containers.empty()) return;
    int widget_count = /* number of actionable widgets on current page */;
    if (widget_count == 0) return;
    focused_widget_idx = (focused_widget_idx - 1 + widget_count) % widget_count;
    ui_apply_focus_highlight(focused_widget_idx);
}

void ui_activate_focused_widget() {
    if (focused_widget_idx < 0) return;
    // Fire the focused widget's action as if it was touched
    // Reuse btn_event_cb logic with the focused widget's ButtonEventData
}
```

### SD Card Directory Listing (firmware HTTP endpoint)
```cpp
static void handle_sd_list() {
    last_activity_time = millis();
    if (!sdcard_mounted()) {
        web_server->send(503, "application/json", "{\"error\":\"SD not mounted\"}");
        return;
    }

    String path = web_server->hasArg("path") ? web_server->arg("path") : "/";
    File dir = SD.open(path);
    if (!dir || !dir.isDirectory()) {
        web_server->send(404, "application/json", "{\"error\":\"Not a directory\"}");
        return;
    }

    String json = "{\"path\":\"" + path + "\",\"files\":[";
    bool first = true;
    File entry;
    while ((entry = dir.openNextFile())) {
        if (!first) json += ",";
        first = false;
        json += "{\"name\":\"" + String(entry.name()) + "\"";
        json += ",\"size\":" + String(entry.size());
        json += ",\"dir\":" + String(entry.isDirectory() ? "true" : "false");
        json += "}";
        entry.close();
    }
    json += "]}";
    dir.close();

    web_server->send(200, "application/json", json);
}
```

## Discretion Recommendations

### Config Storage: Same config.json (RECOMMENDED)
**Recommendation:** Add `hardware_buttons`, `encoder`, `mode_cycle`, and `display_settings` as top-level keys in the existing `config.json`. No separate settings file.

**Rationale:**
- Single atomic write/backup mechanism already works
- Companion editor already uploads/downloads one file
- All new fields are optional with defaults -- backward compatible
- CONFIG_VERSION bump not needed (optional fields)
- Keeps deployment simple: one file = one upload

### SD Card HTTP API Design (RECOMMENDED)
```
GET  /api/sd/usage                    -> {"total_mb": N, "used_mb": N, "free_mb": N}
GET  /api/sd/list?path=/slideshow     -> {"path": "/slideshow", "files": [...]}
POST /api/sd/delete  body: {"path": "/slideshow/img1.png"} -> {"success": true}
```

**Rationale:**
- Consistent with existing `/api/config/upload` and `/api/image/upload` patterns
- GET for reads, POST for mutations (not DELETE verb, since WebServer makes DELETE methods awkward)
- Path as query param for list, JSON body for delete (allows batch delete later)

### PCF8575 Polling Interval: 20Hz / 50ms (RECOMMENDED)
**Recommendation:** Poll at the same rate as touch (50ms), within the existing encoder polling timer in `main.cpp`.

**Rationale:**
- Human button press duration is 80-150ms; 50ms polling catches every press
- Encoder at 20Hz handles normal rotation speed (even fast rotation rarely exceeds 10 detents/second)
- Matches existing polling architecture
- Single I2C read (2 bytes) takes ~0.5ms at 100kHz -- negligible overhead
- No interrupt pin needed, no ISR complexity

### Encoder Debounce: State Machine + Time Guard (RECOMMENDED)
**Recommendation:** Use the Gray code state machine (Pattern 3 above) which inherently rejects most bounce. Add an 80ms minimum interval between valid rotation events for mechanical debounce.

### Visual Hardware Buttons Below Canvas (RECOMMENDED)
**Recommendation:** Add a horizontal strip below the 800x480 canvas area, approximately 80px tall, showing:
- 4 rectangular buttons labeled "B1" through "B4" in a row
- 1 circular encoder widget showing "ENC" with rotation arrows
- Clicking any opens the same properties panel used for touchscreen widgets
- Use a muted color scheme (dark gray) to distinguish from the live display area

### Brightness: Already Working via PWM (CONFIRMED)
The existing `set_backlight()` function in `display_hw.cpp` wraps LovyanGFX's `lcd.setBrightness()` which uses `Light_PWM` on GPIO 2. The `power_cycle_brightness()` function in `power.cpp` already cycles through 3 presets (255, 180, 100). Brightness control is fully functional -- the new ACTION_BRIGHTNESS just needs to call `power_cycle_brightness()`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| AS5600 magnetic encoder (rotary_encoder.cpp) | PCF8575 mechanical encoder via I2C mux | Phase 11 | Complete rewrite of rotary_encoder module |
| Fixed encoder = page nav only | Configurable encoder actions | Phase 11 | Encoder becomes a general-purpose input |
| Touch-only action triggers | Touch + hardware button triggers | Phase 11 | Action system becomes input-agnostic |
| 3 display-local actions (settings/clock/picture) | 6+ system actions (+ page nav, mode cycle, brightness) | Phase 11 | richer local control without PC |

**Deprecated/outdated:**
- `rotary_encoder.h/cpp`: Currently implements AS5600 magnetic encoder protocol. Will be completely replaced with PCF8575-based quadrature decoder.
- Hardcoded encoder-to-page-nav mapping in `main.cpp` lines 187-214: Will be replaced with configurable action dispatch.

## Open Questions

1. **TCA9548A Relationship to Existing I2C Devices**
   - What we know: GT911 touch (0x5D/0x14) and PCA9557 (0x18) are accessed directly on Wire without mux selection. PCF8575 is on TCA9548A channel 0.
   - What's unclear: Is the TCA9548A already initialized? Does selecting channel 0 affect access to GT911/PCA9557 on the main bus?
   - Recommendation: At startup, probe TCA9548A at 0x70. If found, select channel 0 and probe for PCF8575 at 0x20 (and auto-scan 0x20-0x27). Deselect mux after each PCF8575 access to avoid interfering with main bus devices. Test GT911 touch still works after mux operations.

2. **PCF8575 Address Auto-Detection Range**
   - What we know: Default is 0x20. Address pins A0-A2 allow 0x20-0x27.
   - What's unclear: Which address the CrowPanel's PCF8575 uses. PROJECT.md notes "PCF8575 detected at I2C 0x27" from earlier investigation.
   - Recommendation: Scan 0x20-0x27 on TCA9548A channel 0 at startup. Log the detected address. Fall back gracefully if not found (hardware buttons disabled, no error).

3. **SD.usedBytes() Accuracy**
   - What we know: Some ESP32 Arduino SD library versions undercount used bytes.
   - What's unclear: Whether the current platform version has this bug.
   - Recommendation: Use `SD.totalBytes()` for total and `SD.usedBytes()` for used. If usedBytes seems wrong, fall back to `SD.cardSize()` for total capacity and accept the approximation. The exact free space is informational, not critical.

## Sources

### Primary (HIGH confidence)
- Existing codebase analysis: `display/config.h`, `display/config.cpp`, `display/ui.cpp`, `display/main.cpp`, `display/power.h/cpp`, `display/config_server.cpp`, `display/display_hw.cpp`, `display/touch.cpp`, `display/rotary_encoder.h/cpp`, `display/sdcard.cpp`, `companion/config_manager.py`, `companion/ui/editor_main.py`, `companion/http_client.py`
- PCF8575 datasheet (NXP) -- 16-bit I2C I/O expander, 2-byte register read/write protocol
- TCA9548A datasheet (TI) -- single-byte channel select via I2C write

### Secondary (MEDIUM confidence)
- [xreef/PCF8575_library](https://github.com/xreef/PCF8575_library) -- encoder support reference, version 2.0.1
- [RobTillaart/PCF8575](https://github.com/RobTillaart/PCF8575) -- read16() API reference
- [Random Nerd Tutorials: TCA9548A](https://randomnerdtutorials.com/tca9548a-i2c-multiplexer-esp32-esp8266-arduino/) -- ESP32 channel selection example
- [maxgerhardt/rotary-encoder-over-mcp23017](https://github.com/maxgerhardt/rotary-encoder-over-mcp23017) -- quadrature decode via I2C expander pattern

### Tertiary (LOW confidence)
- [CrowPanel backlight versions](https://www.haraldkreuzer.net/en/news/crowpanel-advance-70-update-changes-versions-12-and-13) -- version 1.2/1.3 have different backlight controllers (STC8H1K28), but our codebase uses Light_PWM on GPIO 2 which already works

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries needed, all extension of existing code
- Architecture: HIGH -- patterns derived from direct codebase analysis, well-understood I2C protocols
- Pitfalls: HIGH -- I2C contention is a known issue in this codebase (solved with existing mutex), encoder debounce is well-documented
- Editor UI: MEDIUM -- PySide6 canvas extension is straightforward but hardware section below canvas is novel UI pattern for this codebase
- SD card management: MEDIUM -- SD.usedBytes() accuracy needs runtime verification

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable domain, hardware protocols don't change)
