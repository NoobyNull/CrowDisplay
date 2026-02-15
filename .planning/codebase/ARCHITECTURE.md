# Architecture

**Analysis Date:** 2026-02-12

## Pattern Overview

**Overall:** Embedded GUI application with layered abstraction between hardware drivers and user interface logic.

**Key Characteristics:**
- **Hardware Abstraction Layer:** Display and USB HID interfaces isolated from business logic
- **Composition-Based Hotkey System:** Immutable hotkey definitions composed into pages, with event-driven button callbacks
- **Single-Threaded Event Loop:** Arduino main loop drives LVGL tick, which processes touch events and UI updates
- **Two-Way Communication:** Touchscreen input drives USB HID output with visual UI feedback

## Layers

**Hardware Abstraction (Display):**
- Purpose: Encapsulate all low-level display hardware and LVGL integration details
- Location: `src/display_driver.cpp`, `src/display_driver.h`
- Contains: LovyanGFX RGB panel driver, touch input callbacks, LVGL buffer management and callbacks
- Depends on: LovyanGFX, LVGL core, ESP32 GPIO/I2C hardware
- Used by: `src/main.cpp` for initialization; LVGL internally for rendering

**Hardware Abstraction (USB HID):**
- Purpose: Encapsulate USB keyboard and consumer control (media key) transmission
- Location: `src/usb_hid.cpp`, `src/usb_hid.h`
- Contains: USB HID initialization, keyboard/modifier key sending, media control sending
- Depends on: Arduino USBHIDKeyboard, USBHIDConsumerControl libraries, ESP32-S3 native USB
- Used by: `src/main.cpp` button event handler

**UI/Configuration Layer:**
- Purpose: Define and render hotkey buttons with visual styling and event handling
- Location: `src/main.cpp` (lines 21-182 for data, 184-228 for UI creation)
- Contains: Hotkey definitions (3 pages x 12 keys), LVGL UI tree creation (header, tabview, buttons)
- Depends on: Display driver, USB HID, LVGL
- Used by: Arduino setup/loop for initialization and ongoing event processing

**Application Entry Point:**
- Purpose: Orchestrate startup sequence and main event loop
- Location: `src/main.cpp` (lines 234-272)
- Contains: `setup()` initializes display → LVGL → USB HID → builds UI; `loop()` drives LVGL tick every 5ms

## Data Flow

**Initialization Sequence:**

1. `setup()` begins serial debugging
2. `display_init()` configures LovyanGFX RGB panel and touch controller (GT911 on I2C)
3. `lvgl_init()` allocates PSRAM draw buffers, registers display/touch drivers with LVGL
4. `usb_hid_init()` initializes ESP32-S3 native USB keyboard and consumer control, begins enumeration
5. `create_ui()` builds LVGL object tree: header bar → tabview → 3 tabs with 4x3 button grid per tab
6. I2C scan logs detected devices to serial for debugging

**Touch → USB Flow:**

1. User touches screen → GT911 detects touch coordinates
2. LVGL `touchpad_read_cb()` polls GT911 via I2C, updates LVGL input state
3. LVGL hit-tests touch against button objects, triggers `btn_event_cb()` with LV_EVENT_CLICKED
4. Callback extracts associated Hotkey struct pointer from event user data
5. `send_hotkey(Hotkey)` routes to either:
   - `send_key_combo()` for regular keyboard (applies MOD_CTRL/MOD_SHIFT/MOD_ALT/MOD_GUI, presses key)
   - `ConsumerControl.press/release()` for media keys (when MOD_CONSUMER flag set)
6. Status label in header updates with visual feedback ("Sent: Copy (Ctrl+C)")

**State Management:**

- **Immutable Hotkey Definitions:** Static const arrays `page1_hotkeys`, `page2_hotkeys`, `page3_hotkeys` never modified
- **UI State:** Entirely managed by LVGL object tree in PSRAM; no manual state variables
- **USB State:** USB HID object statics `Keyboard`, `ConsumerControl` maintain session state
- **Display State:** LVGL draw buffer pointers `buf1`, `buf2` allocate once, reused across frames
- **Current Page:** LVGL tabview widget tracks selected tab; user switches via tab button

## Key Abstractions

**Hotkey Definition Struct:**
- Purpose: Encapsulate all data needed to display a button and send its keystroke
- Examples: `page1_hotkeys[0]` = `{"Copy", "Ctrl+C", MOD_CTRL, 'c', CLR_BLUE, LV_SYMBOL_COPY}`
- Pattern: Data-only struct; passed by const reference to UI and HID functions; zero runtime modification

**Display Driver Module:**
- Purpose: Hide LGFX class, buffer management, LVGL configuration behind simple interface
- Pattern: Singleton LGFX instance `tft` with static scope in display_driver.cpp; accessed only via public functions (`display_init()`, `lvgl_init()`, `lvgl_tick()`)

**USB HID Module:**
- Purpose: Translate generic Hotkey structs to platform-specific keyboard/consumer APIs
- Pattern: Wraps ESP32-S3 native USBHIDKeyboard/USBHIDConsumerControl; modifier flags (MOD_CTRL, etc.) are platform-agnostic bitmasks

**HotkeyPage Configuration:**
- Purpose: Package a set of hotkeys with metadata (name, count) for multi-page UI
- Pattern: Struct array `pages[]` used by setup loop to create tabs dynamically; enables adding pages without modifying UI tree code

## Entry Points

**Arduino Entry Point:**
- Location: `src/main.cpp` lines 234-266 (`setup()`)
- Triggers: System reset or power-on
- Responsibilities: Initialize display hardware → LVGL library → USB HID stack → build UI tree; log I2C devices

**Event Loop Entry Point:**
- Location: `src/main.cpp` lines 268-271 (`loop()`)
- Triggers: Called repeatedly by Arduino scheduler (~every millisecond in Arduino)
- Responsibilities: Call `lvgl_tick()` every 5ms via 5ms delay; LVGL handles touch polling, UI redraws, callback dispatching

**Touch Input Callback:**
- Location: `src/display_driver.cpp` lines 145-160 (`touchpad_read_cb()`)
- Triggers: Called by LVGL at `LV_INDEV_DEF_READ_PERIOD` (30ms, set in `lv_conf.h`)
- Responsibilities: Poll GT911 touch IC via `tft.getTouch()`, update LVGL input device state with (x, y) and press/release; log touches to serial for debugging

**Button Click Callback:**
- Location: `src/main.cpp` lines 107-119 (`btn_event_cb()`)
- Triggers: LVGL processes touch hit-test, identifies button, fires LV_EVENT_CLICKED
- Responsibilities: Extract Hotkey pointer from event, call `send_hotkey()`, update status label

**Display Flush Callback:**
- Location: `src/display_driver.cpp` lines 130-140 (`disp_flush_cb()`)
- Triggers: LVGL scheduler when region needs redraw
- Responsibilities: Transfer LVGL framebuffer region to RGB panel via LGFX startWrite/setAddrWindow/writePixels; signal LVGL flush complete

## Error Handling

**Strategy:** Fail-open with serial logging; no exceptions or graceful shutdown.

**Patterns:**
- **USB Not Ready:** If USB enumeration incomplete before first button press, keystroke sends to uninitialized device (no error thrown). Status bar still updates.
- **Touch Polling Fails:** `tft.getTouch()` returns false, LVGL sets LV_INDEV_STATE_REL. No retries or fallback.
- **PSRAM Allocation:** If `ps_malloc()` for LVGL buffers fails, null pointer returned; LVGL asserts on subsequent use (see `LV_USE_ASSERT_NULL` in `lv_conf.h`)
- **GPIO/I2C Config:** Set statically in LGFX class constructor; no runtime validation

## Cross-Cutting Concerns

**Logging:** Serial prints on USB CDC (ARDUINO_USB_CDC_ON_BOOT=1 build flag). All module inits log success messages; touch/button sends log to Serial; I2C scan logs addresses found.

**Validation:** Display dimensions (SCREEN_WIDTH=800, SCREEN_HEIGHT=480) hardcoded. Touch min/max bounds hardcoded in LGFX config. No runtime bounds checking on button grid layout.

**Pin Management:** All GPIO pins and I2C addresses hardcoded in display_driver.cpp LGFX class and lv_conf.h. No abstraction for hardware variants.

**Timing:** Fixed 5ms main loop delay in Arduino loop. LVGL configured for 16ms display refresh period (LV_DISP_DEF_REFR_PERIOD). Touch polling every 30ms (LV_INDEV_DEF_READ_PERIOD). Key press held 50ms before release (send_key_combo/send_hotkey).

---

*Architecture analysis: 2026-02-12*
