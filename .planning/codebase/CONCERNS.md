# Codebase Concerns

**Analysis Date:** 2026-02-12

## Memory Management Issues

**PSRAM Buffer Allocation Without Validation:**
- Issue: `lvgl_init()` allocates LVGL draw buffers via `ps_malloc()` without checking for allocation failure
- Files: `src/display_driver.cpp` (lines 175-176)
- Impact: If PSRAM allocation fails (exhausted memory), `buf1` and `buf2` remain nullptr, but code proceeds to initialize LVGL. This causes undefined behavior when LVGL attempts to write to draw buffers
- Fix approach: Add null pointer checks after `ps_malloc()` calls. Return error status or halt initialization if allocation fails

**Static Pointer Initialization:**
- Issue: Multiple global/static pointers initialized as nullptr without runtime validation before use
- Files: `src/main.cpp` (lines 103-104: `tabview`, `status_label`), `src/display_driver.cpp` (lines 125-126: `buf1`, `buf2`)
- Impact: Dereference of uninitialized pointers in event handlers (`btn_event_cb` at line 114 checks `status_label` but doesn't validate `tabview`)
- Fix approach: Implement initialization guards in event handlers. Add assertions or runtime checks before any pointer dereference

## Timing and Synchronization Concerns

**Hard-Coded Delays for USB Enumeration:**
- Issue: 500ms blocking delay in `usb_hid_init()` (line 15) assumes USB enumeration time
- Files: `src/usb_hid.cpp` (line 15)
- Impact: May cause startup lag; delay time is platform-dependent and not guaranteed to be sufficient for all USB host conditions
- Fix approach: Implement USB enumeration readiness checking instead of fixed delay. Use USB library's connection state APIs if available

**Fixed Delays in HID Key Transmission:**
- Issue: 50ms fixed delays between key press/release in `send_key_combo()` and consumer control send
- Files: `src/usb_hid.cpp` (lines 28, 38)
- Impact: Introduces unnecessary latency in hotkey response. Assumes this delay is required but no comments explain why
- Fix approach: Verify minimum required delay with USB HID spec. Consider making configurable or removing if not strictly necessary

**High-Frequency LVGL Polling with Fixed 5ms Delay:**
- Issue: `loop()` calls `lvgl_tick()` every 5ms unconditionally
- Files: `src/main.cpp` (lines 269-270)
- Impact: Creates tight loop consuming CPU resources. May cause power inefficiency on battery-powered devices
- Fix approach: Use interrupt-driven approach or OS-level task scheduling instead of delay-based polling

**Debug I2C Scan on Every Startup:**
- Issue: Full I2C bus scan (127 addresses) runs on every boot
- Files: `src/main.cpp` (lines 257-264)
- Impact: Adds 1-2 second startup delay even when I2C discovery not needed. Unnecessary blocking operation
- Fix approach: Conditional compile with build flag. Move to diagnostic function called only on demand

## Touch Input Reliability

**Debug Logging Flooding Serial Output:**
- Issue: `touchpad_read_cb()` logs every no-touch event every 3 seconds, plus all touch events
- Files: `src/display_driver.cpp` (lines 151, 157)
- Impact: Serial output can become unreadable; may impact performance if Serial0 buffer backs up. No way to disable debug logging at runtime
- Fix approach: Add DEBUG flag or logging level control. Use internal logging buffer instead of Serial. Make diagnostics opt-in via configuration

**No Touch Input Validation:**
- Issue: Touch coordinates returned by `tft.getTouch()` are used directly without range checking
- Files: `src/display_driver.cpp` (line 147-150)
- Impact: Malformed touch data or edge cases (out-of-bounds coordinates) could cause LVGL event processing issues
- Fix approach: Add bounds checking (0-799 x, 0-479 y). Filter noise/spurious reads

## UI Event Handling Gaps

**Null Pointer Risk in Status Label Update:**
- Issue: `btn_event_cb()` checks if `hk` exists but unconditionally assumes `status_label` is valid when non-null
- Files: `src/main.cpp` (lines 114-116)
- Impact: If `status_label` was deleted or invalidated elsewhere in code, writing to it causes crash
- Fix approach: Validate `status_label` validity before use. Consider using LVGL ref counting or safer handle pattern

**No Bounds Checking on Hotkey Index:**
- Issue: Button event handler casts void pointer directly to Hotkey without validating
- Files: `src/main.cpp` (line 110)
- Impact: If event user_data is corrupted or mismatched, accessing Hotkey struct members causes undefined behavior
- Fix approach: Add validation function to verify Hotkey structure integrity (check bounds, expected values)

**Missing Button Press/Release Visual Feedback Reliability:**
- Issue: Button press animations depend on LVGL state management without error handling
- Files: `src/main.cpp` (lines 138-140)
- Impact: If LVGL state becomes corrupted, visual feedback may not display. User left unsure if button press registered
- Fix approach: Implement additional visual feedback (color change, sound) that doesn't depend on LVGL state alone

## Keyboard/HID Output Issues

**No Verification of Hotkey Delivery:**
- Issue: `send_hotkey()` sends via USB HID but never checks if transmission succeeded
- Files: `src/usb_hid.cpp` (lines 32-44)
- Impact: Key press may fail silently (USB disconnected, busy). User sees status message "Sent" but key never reached host
- Fix approach: Implement ACK/handshake mechanism if ESP32 HID library supports it. Return status code from `send_hotkey()`

**Incomplete Modifier Key Handling:**
- Issue: `send_key_combo()` only handles standard modifiers (Ctrl, Shift, Alt, GUI); no error if unknown modifier flag set
- Files: `src/usb_hid.cpp` (lines 19-30)
- Impact: If MOD_* bitmask is malformed, unhandled modifiers silently ignored
- Fix approach: Add assertion or validation that modifier bitmask is valid. Document supported modifiers

**Media Key Implementation Fragile:**
- Issue: Consumer control keys use raw hex values (0xCD, 0xB5, etc.) without library constant validation
- Files: `src/usb_hid.h` (lines 24-30), `src/main.cpp` (lines 71-76)
- Impact: Hex values may not match actual USB HID consumer control codes. Media keys may not work on all hosts
- Fix approach: Cross-reference against USB HID consumer page specification. Use library constants if available. Test on multiple OS hosts

## Display Driver Fragility

**Hard-Coded GPIO Pin Configuration:**
- Issue: All 22 GPIO pins for RGB parallel display are hard-coded with no abstraction
- Files: `src/display_driver.cpp` (lines 47-72)
- Impact: Impossible to reuse driver for similar boards with different pin layouts. One mistake in pin config breaks display. No in-code documentation of pin mapping rationale
- Fix approach: Extract pin configuration to header file with board-specific blocks. Add pin mapping documentation

**No Validation of Display Timing Parameters:**
- Issue: RGB panel timing parameters (hsync_front_porch, vsync_pulse_width, etc.) are hard-coded numbers
- Files: `src/display_driver.cpp` (lines 76-86)
- Impact: Incorrect values cause display artifacts or signal integrity issues. No way to debug timing without recompiling
- Fix approach: Add validation that timing sums match datasheet specs. Document each timing parameter source

**Display Initialization Without Error Checking:**
- Issue: `display_init()` and `lvgl_init()` have no return values or error status
- Files: `src/display_driver.cpp` (lines 163-168, 171-194)
- Impact: If LovyanGFX initialization fails silently, code continues with invalid display state. No diagnostics
- Fix approach: Return bool/int status from initialization functions. Check and log errors in setup()

**Touch Controller I2C Address Hard-Coded:**
- Issue: GT911 touch I2C address (0x14) is hard-coded with no fallback
- Files: `src/display_driver.cpp` (line 113)
- Impact: If device has alternate address (0x5D), touch won't work and no diagnostic error reported
- Fix approach: Probe I2C address before configuring. Support address configuration via define

## LVGL Configuration Risk

**Memory Budget Extremely Tight:**
- Issue: `LV_MEM_SIZE` set to 96KB (line 17 of lv_conf.h) with complex UI (tabs, buttons, labels)
- Files: `src/lv_conf.h` (line 17)
- Impact: LVGL may fragment heap or fail to allocate objects during runtime. No warning when approaching limit
- Fix approach: Profile actual memory usage. Increase to 192KB or use PSRAM for LVGL memory pool

**Shadow Cache Disabled but Complex Shadows Used:**
- Issue: `LV_SHADOW_CACHE_SIZE` set to 0 (disabled) but button shadows enabled (8px width)
- Files: `src/lv_conf.h` (line 30), `src/main.cpp` (line 132)
- Impact: Shadow rendering may be slow/inefficient since no cache. Impact on frame rate unknown
- Fix approach: Enable shadow cache (set to 1 or 2) to test performance impact

**Assertion Checks May Hide Bugs:**
- Issue: `LV_USE_ASSERT_NULL` enabled; null pointer crashes during development only
- Files: `src/lv_conf.h` (line 44)
- Impact: Production builds may have assertions disabled, hiding null pointer bugs
- Fix approach: Log assertion failures instead of crashing. Implement safe null checks regardless of assert status

## Scaling and Page Management

**Fixed 3-Page Layout Not Scalable:**
- Issue: Hard-coded 12 hotkeys per page in 3x4 grid; adding more pages requires code changes
- Files: `src/main.cpp` (lines 92-97, 224-227)
- Impact: New hotkeys/pages require recompilation. No data-driven hotkey configuration
- Fix approach: Consider SPIFFS/NVS-based hotkey configuration file. Allow pages to scale to N hotkeys with dynamic grid

**No Validation of Hotkey Array Size:**
- Issue: `sizeof()` trick for array length assumes hotkey arrays are static (works now but fragile)
- Files: `src/main.cpp` (lines 93-95)
- Impact: If hotkey arrays moved to external data structure, size calculation breaks silently
- Fix approach: Add explicit count field or validation function to ensure array length matches count in struct

## Development and Testing

**Debug Serial Output Not Configurable:**
- Issue: Multiple Serial/Serial0 print statements throughout code; no way to disable for production
- Files: `src/main.cpp` (lines 237, 241, 245, 253), `src/usb_hid.cpp` (line 16, 33), `src/display_driver.cpp` (lines 151, 157)
- Impact: Serial logging consumes power and bandwidth. No log level control
- Fix approach: Implement DEBUG_LEVEL macro or logging abstraction. Make configurable at compile time

**No Unit Tests:**
- Issue: No test framework or test files present
- Files: N/A - codebase lacks test structure
- Impact: Hotkey sending, event handling, display rendering are not tested. Regression bugs impossible to catch
- Fix approach: Add unit tests for hotkey structs, key combo generation. Mock LVGL for event handler tests

**No Error Recovery Mechanism:**
- Issue: Initialization assumes all steps succeed; no recovery or fallback if display/USB init fails
- Files: `src/main.cpp` (lines 234-265)
- Impact: If hardware fails partway through boot, device enters undefined state with no indication of problem
- Fix approach: Implement step-by-step health check. Display error on screen if possible. Reboot on critical failure

## Technical Debt Summary

**High Priority:**
1. PSRAM allocation validation in `lvgl_init()` - potential crash
2. USB enumeration verification instead of fixed delay
3. Touch coordinate bounds checking
4. HID delivery verification - silent failures possible

**Medium Priority:**
1. Remove/conditionally compile I2C diagnostic scan
2. Make debug logging configurable
3. Validate hotkey pointers in event handlers
4. Extract GPIO configuration to board definitions

**Low Priority:**
1. Touch debug logging frequency reduction
2. LVGL memory budget review and optimization
3. Consider data-driven hotkey configuration
4. Add comprehensive unit tests

---

*Concerns audit: 2026-02-12*
