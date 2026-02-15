---
status: investigating
trigger: "touch-not-working"
created: 2026-02-12T00:00:00Z
updated: 2026-02-12T02:00:00Z
---

## Current Focus

hypothesis: Touch initialization or polling is silently failing - getTouch() always returns false
test: Add extensive debug logging to verify: 1) tft.begin() return value, 2) touchpad_read_cb being called, 3) getTouch() return values
expecting: Debug output will reveal if touch callback is being called and what getTouch() returns
next_action: Add debug logging to display_driver.cpp and main.cpp, rebuild and check serial output

## Symptoms

expected: Touch input registers - tapping/swiping should trigger UI actions (buttons, sliders, etc.)
actual: Nothing at all - no response to any touch input whatsoever. Display renders fine.
errors: None reported
reproduction: Touch anywhere on the screen - nothing happens
started: Touch WORKED with OEM trial LVGL v8 demo. Hardware confirmed good. Stopped working with current code.

## Eliminated

- hypothesis: Touch RST pin was incorrectly configured as GPIO_NUM_38 instead of -1
  evidence: Changed pin_rst to -1 (matching official reference) and flashed. Touch still does NOT work.
  timestamp: 2026-02-12T01:00:00Z

## Evidence

- timestamp: 2026-02-12T00:01:00Z
  checked: src/display_driver.cpp, src/main.cpp
  found: Touch driver (GT911) IS configured in LGFX class with I2C pins SDA=19, SCL=20, address 0x14. LVGL input device IS registered with touchpad_read_cb callback. Debug logging present in touchpad_read_cb.
  implication: Touch initialization code exists. Need to compare against working OEM example and check for initialization order issues.

- timestamp: 2026-02-12T00:02:00Z
  checked: .pio/libdeps/elcrow_7inch/LovyanGFX/src/lgfx_user/LGFX_Elecrow_ESP32_Display_WZ8048C070.h
  found: Official LovyanGFX reference has pin_rst = -1 (disabled). User's display_driver.cpp has pin_rst = GPIO_NUM_38.
  implication: CRITICAL DIFFERENCE. The GT911 touch controller may not have a dedicated RST pin on this hardware, or it's internally managed. Setting it to GPIO_NUM_38 could be driving that pin incorrectly and preventing touch initialization.

- timestamp: 2026-02-12T00:03:00Z
  checked: .pio/libdeps/elcrow_7inch/LovyanGFX/src/lgfx/v1/touch/Touch_GT911.cpp lines 59-65
  found: When pin_rst >= 0, the GT911 driver actively drives the reset pin (sets output mode, pulls low, delays, pulls high). When pin_rst = -1, this entire sequence is skipped.
  implication: Confirms that setting pin_rst = GPIO_NUM_38 causes the driver to actively control GPIO 38, which is wrong for this hardware. The fix (pin_rst = -1) prevents this incorrect GPIO control.

- timestamp: 2026-02-12T01:01:00Z
  checked: platformio.ini and LVGL header files
  found: Project uses LVGL v8.3.11 (NOT v9 as initially assumed). display_driver.cpp uses correct LVGL v8 API names (LV_INDEV_STATE_PRESSED/RELEASED). State enum names are correct.
  implication: LVGL API version is NOT the issue. The touch callback registration appears correct for v8.

- timestamp: 2026-02-12T01:02:00Z
  checked: Touch_GT911.cpp init() function, lines 69
  found: GT911 touch init calls lgfx::i2c::init(_cfg.i2c_port, _cfg.pin_sda, _cfg.pin_scl) to initialize I2C bus I2C_NUM_1 on pins 19/20. This happens during tft.begin() in display_init().
  implication: The GT911 driver initializes and owns I2C_NUM_1. Any subsequent I2C initialization on the same pins could break the GT911's connection.

- timestamp: 2026-02-12T01:03:00Z
  checked: main.cpp lines 257-265
  found: CRITICAL BUG - After display_init() and lvgl_init(), the code calls Wire.begin(19, 20) for an I2C scan. This re-initializes the Arduino Wire library on the SAME pins (19/20) that GT911 is already using.
  implication: Wire.begin() is re-configuring I2C hardware, likely breaking the GT911's I2C connection. The GT911 was working fine after display_init(), but then Wire.begin() destroys it. This explains why touch doesn't work even though pin_rst is now correct.

## Resolution

root_cause: [investigating - Wire.begin() fix did NOT solve the problem]

fix: [not yet found]

verification: [not yet verified]

files_changed: []
