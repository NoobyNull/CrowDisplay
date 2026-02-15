# Testing Patterns

**Analysis Date:** 2026-02-12

## Test Framework

**Status:** No automated testing framework configured

**Current State:**
- No test files found in source tree (`.test.*`, `.spec.*` patterns absent)
- No test runners configured (no Jest, Catch2, gtest, etc.)
- No test configuration files (no `jest.config.js`, `CMakeLists.txt` for testing, etc.)
- This is an embedded C++ project for ESP32-S3; unit testing infrastructure not present

**Build System:**
- PlatformIO (Arduino framework)
- Config: `platformio.ini`
- No testing framework specified in `lib_deps`

**Libraries Used:**
- LovyanGFX - Display graphics library
- LVGL v8.3.11 - UI framework
- USB HID native ESP32-S3 support

## Test File Organization

**Location:** Not applicable - no test files present

**Pattern (for future):** Would follow Arduino/PlatformIO convention
- Test files placed in `test/` directory (PlatformIO standard)
- Naming: `test_*.cpp` or `*_test.cpp`
- Build via PlatformIO test command

**Example Structure (if testing were added):**
```
project/
├── src/
│   ├── main.cpp
│   ├── display_driver.cpp
│   ├── usb_hid.cpp
│   └── *.h
└── test/
    ├── test_usb_hid.cpp
    ├── test_display_driver.cpp
    └── common/
        └── test_fixtures.h
```

## Test Structure

**Current Approach:** Manual integration testing via hardware

**Verification Method:**
- Serial monitor output for initialization status
- Visual testing on hardware display
- Physical touch input testing
- USB HID output testing (manual keyboard detection on host)

**Example Serial Output Logged:**
```cpp
Serial.println("Display initialized");
Serial.println("LVGL initialized");
Serial.println("USB HID initialized");
Serial0.println("I2C scan on SDA=19 SCL=20:");
Serial0.printf("  FOUND: 0x%02X\n", addr);
```

**Debug Points in Code:**
```cpp
// From btn_event_cb - logs hotkey sent
Serial.printf("Sending: %s (%s)\n", hk->label, hk->description);

// From touchpad_read_cb - logs touch events
Serial0.printf("TOUCH: x=%d y=%d\n", x, y);
Serial0.println("touch: polling (no touch)");  // Once every 3 seconds
```

**Touch Testing Pattern:**
```cpp
// display_driver.cpp touchpad_read_cb shows polling approach
if (tft.getTouch(&x, &y)) {
    data->state = LV_INDEV_STATE_PR;
    data->point.x = x;
    data->point.y = y;
    Serial0.printf("TOUCH: x=%d y=%d\n", x, y);
} else {
    data->state = LV_INDEV_STATE_REL;
}
```

## Mocking

**Framework:** Not applicable (no test framework)

**Hardware Abstraction:**
- Display operations abstracted in `display_driver.cpp`
- USB HID operations abstracted in `usb_hid.cpp`
- These could be mocked if unit testing framework were added

**Current Approach:**
- Direct hardware calls via LVGL and LovyanGFX
- Serial logging for debugging instead of test assertions

## Fixtures and Factories

**Test Data Structure:** Hotkey definitions serve as test data

**Location:** `src/main.cpp` lines 25-83
```cpp
static const Hotkey page1_hotkeys[] = {
    {"Copy",      "Ctrl+C",         MOD_CTRL,             'c', CLR_BLUE,   LV_SYMBOL_COPY},
    {"Paste",     "Ctrl+V",         MOD_CTRL,             'v', CLR_GREEN,  LV_SYMBOL_PASTE},
    // ... 10 more hotkeys
};

static const Hotkey page2_hotkeys[] = {
    {"Desktop",   "Win+D",          MOD_GUI,              'd', CLR_BLUE,   LV_SYMBOL_HOME},
    // ... 11 more hotkeys
};

static const Hotkey page3_hotkeys[] = {
    {"Play/Pause","Media Play",     MOD_CONSUMER,         MEDIA_PLAY_PAUSE, CLR_GREEN,  LV_SYMBOL_PLAY},
    // ... 11 more hotkeys
};
```

**Test Data Organization:**
- Three pages with 12 hotkeys each (36 total)
- Each hotkey includes: label, description, modifier mask, key code, color, icon
- Covers three categories: General shortcuts, Window management, Media/Dev keys

**Page Configuration:**
```cpp
struct HotkeyPage {
    const char *name;
    const Hotkey *hotkeys;
    uint8_t count;
};

static const HotkeyPage pages[] = {
    {"General",   page1_hotkeys, sizeof(page1_hotkeys) / sizeof(Hotkey)},
    {"Windows",   page2_hotkeys, sizeof(page2_hotkeys) / sizeof(Hotkey)},
    {"Media/Dev", page3_hotkeys, sizeof(page3_hotkeys) / sizeof(Hotkey)},
};
```

## Coverage

**Requirements:** None enforced

**Analysis:**
- No code coverage tool configured
- No coverage thresholds set
- Hardware-dependent code (display, USB HID) difficult to unit test

**Key Testable Functions (if framework added):**
- `send_hotkey(const Hotkey &hk)` - modifier and key sending
- `send_key_combo(uint8_t modifiers, uint16_t key)` - keyboard input
- UI callbacks: `btn_event_cb()`, `disp_flush_cb()`, `touchpad_read_cb()`

**Hardware-Dependent (would need mocking):**
- `display_init()` - requires LovyanGFX hardware
- `lvgl_init()` - requires display driver
- `usb_hid_init()` - requires USB stack
- LVGL object creation and styling

## Test Types

**Unit Tests:** Not implemented

**Would test (if framework added):**
- Hotkey modifier composition: `send_key_combo()` with various MOD_* combinations
- USB HID mapping: verify correct key codes sent for each hotkey
- Struct composition: verify Hotkey array is correctly sized

**Integration Tests:** Currently performed manually

**Hardware Testing:**
1. Display initialization and rendering
2. Touch input detection and button response
3. USB HID keyboard output (manual host-side verification)
4. Multi-page tab navigation
5. Status bar feedback updates

**Testing Procedure (Manual):**
```
1. Deploy firmware to ESP32-S3
2. Open Serial monitor at 115200 baud
3. Verify initialization sequence:
   - "Display initialized"
   - "LVGL initialized"
   - "USB HID initialized"
   - "I2C scan done" with GT911 touchscreen address found
4. Touch buttons on screen
5. Verify Serial output: "TOUCH: x=... y=..."
6. Verify hotkey sent: "Sending: <label> (<description>)"
7. Check host machine received keyboard input
```

**E2E Tests:** Not applicable (embedded firmware)

## Common Patterns

**Hardware Initialization Pattern:**
```cpp
void setup() {
    Serial.begin(115200);
    Serial0.begin(115200);
    Serial0.println("Hotkey Display starting...");

    // Initialize display
    display_init();
    Serial.println("Display initialized");

    // Initialize LVGL
    lvgl_init();
    Serial.println("LVGL initialized");

    // Initialize USB HID
    usb_hid_init();
    Serial.println("USB HID initialized");

    // Build the UI
    create_ui();
    Serial0.println("UI created");
}
```

**Event Callback Pattern:**
```cpp
static void btn_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        const Hotkey *hk = (const Hotkey *)lv_event_get_user_data(e);
        if (hk) {
            send_hotkey(*hk);
            // Update status bar
            if (status_label) {
                lv_label_set_text_fmt(status_label, LV_SYMBOL_OK " Sent: %s (%s)",
                                     hk->label, hk->description);
            }
        }
    }
}
```

**Polling Pattern (Touch Input):**
```cpp
static void touchpad_read_cb(lv_indev_drv_t *indev_drv, lv_indev_data_t *data) {
    uint16_t x, y;
    if (tft.getTouch(&x, &y)) {
        data->state = LV_INDEV_STATE_PR;
        data->point.x = x;
        data->point.y = y;
        Serial0.printf("TOUCH: x=%d y=%d\n", x, y);
    } else {
        data->state = LV_INDEV_STATE_REL;
        if (millis() - touch_debug_timer > 3000) {
            touch_debug_timer = millis();
            Serial0.println("touch: polling (no touch)");
        }
    }
}
```

**USB HID Send Pattern:**
```cpp
void send_hotkey(const Hotkey &hk) {
    Serial.printf("Sending: %s (%s)\n", hk->label, hk->description);

    if (hk.modifiers & MOD_CONSUMER) {
        // Media/consumer control key
        ConsumerControl.press(hk.key);
        delay(50);
        ConsumerControl.release();
    } else {
        // Regular keyboard combo
        send_key_combo(hk.modifiers, hk.key);
    }
}

void send_key_combo(uint8_t modifiers, uint16_t key) {
    if (modifiers & MOD_CTRL)  Keyboard.press(KEY_LEFT_CTRL);
    if (modifiers & MOD_SHIFT) Keyboard.press(KEY_LEFT_SHIFT);
    if (modifiers & MOD_ALT)   Keyboard.press(KEY_LEFT_ALT);
    if (modifiers & MOD_GUI)   Keyboard.press(KEY_LEFT_GUI);

    Keyboard.press((uint8_t)key);
    delay(50);
    Keyboard.releaseAll();
}
```

**Configuration Pattern (LVGL Display Buffer):**
```cpp
#define LVGL_BUF_SIZE (SCREEN_WIDTH * 40)

static lv_color_t *buf1 = nullptr;
static lv_color_t *buf2 = nullptr;

void lvgl_init(void) {
    // Allocate double-buffered draw area in PSRAM
    buf1 = (lv_color_t *)ps_malloc(LVGL_BUF_SIZE * sizeof(lv_color_t));
    buf2 = (lv_color_t *)ps_malloc(LVGL_BUF_SIZE * sizeof(lv_color_t));
    lv_disp_draw_buf_init(&draw_buf, buf1, buf2, LVGL_BUF_SIZE);
}
```

## Run Commands

**No test runner available** - Project uses manual hardware testing

**Build and Deploy:**
```bash
# Build firmware
pio run -e elcrow_7inch

# Upload to ESP32-S3
pio run -e elcrow_7inch -t upload

# Monitor serial output
pio device monitor -b 115200
```

**Manual Testing Checklist:**
- Serial initialization messages confirm hardware setup
- Touch events logged when display is touched
- Hotkey sent messages logged when buttons are pressed
- Status bar updates visual feedback after hotkey send
- Tab navigation switches between pages
- All 36 hotkeys (across 3 pages) are accessible and sendable

---

*Testing analysis: 2026-02-12*
