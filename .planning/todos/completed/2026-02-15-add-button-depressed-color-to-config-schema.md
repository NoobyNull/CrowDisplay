---
created: 2026-02-15T22:53:00.000Z
title: Add button depressed color to config schema
area: ui
files:
  - display/config.h:39-57
  - display/config.cpp:364-373
  - display/ui.cpp
  - companion/ui/button_editor.py
  - companion/config_manager.py
---

## Problem

ButtonConfig only has a single `color` field (0xRRGGBB) used as the button background. There is no separate color for the pressed/depressed state. Currently LVGL likely uses a default darkened version of the background color when pressed, but users cannot customize this.

Users want to control what color a button shows when tapped -- e.g. a red "Kill" button could flash white when pressed, or a blue workspace button could turn green to confirm the tap.

## Solution

**Config schema (display/config.h):**
- Add `uint32_t pressed_color` field to ButtonConfig (default 0x000000 or a sentinel like 0xFFFFFFFF meaning "auto-darken")
- Serialize/deserialize in config.cpp JSON helpers

**Device firmware (display/ui.cpp):**
- Apply `pressed_color` via LVGL style `LV_STATE_PRESSED` on each button widget
- If pressed_color is the sentinel/default, use LVGL's default press behavior (darken)

**Editor (companion/ui/button_editor.py):**
- Add a second color picker for "Pressed Color" in the property panel
- Show a checkbox or "Auto" option to use default press darkening

**JSON format:**
- New optional field: `"pressed_color": 1234567` (decimal 0xRRGGBB, same as `color`)
- Backward compatible: if field missing, device uses auto-darken
