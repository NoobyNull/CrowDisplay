---
created: 2026-02-15T23:03:00.000Z
title: Add display modes - standby, macro pad, picture frame, clock
area: ui
files:
  - display/power.h:4-7
  - display/power.cpp
  - display/ui.cpp:300-340
  - display/ui.h
  - display/main.cpp
  - display/config.h
  - companion/ui/editor_main.py
---

## Problem

The display currently has 3 implicit states: ACTIVE (hotkey grid + stats), DIMMED (same UI, lower brightness), and CLOCK (simple clock on PC shutdown). These are power states, not user-selectable display modes.

Users want 4 distinct display modes they can switch between:

1. **Standby** -- screen off or minimal (replaces DIMMED, saves power when not in use)
2. **Macro/Button Pad** -- the current hotkey grid UI (existing ACTIVE mode)
3. **Digital Picture Frame** -- slideshow of images from SD card (new)
4. **Clock** -- enhanced clock with both analog and digital faces (expand existing CLOCK_MODE)

## Solution

**Display mode enum (display/power.h or new display_mode.h):**
```
enum DisplayMode : uint8_t {
    MODE_STANDBY = 0,       // Screen off / very dim, wake on touch
    MODE_MACRO_PAD = 1,     // Hotkey button grid (current ACTIVE)
    MODE_PICTURE_FRAME = 2, // SD card image slideshow
    MODE_CLOCK = 3,         // Analog + digital clock face
};
```

Separate display mode from power state -- power state (ACTIVE/DIMMED/CLOCK) controls brightness/sleep, display mode controls what's shown.

**Standby mode:**
- Screen off or backlight at minimum
- Wake on touch → return to previous mode
- Optional: show time very dimly (OLED-style burn-in safe, but this is LCD so less concern)

**Macro/Button Pad mode:**
- Current hotkey grid UI, no changes needed
- This is the default active mode

**Digital Picture Frame mode:**
- Read BMP/JPG images from SD card folder (e.g. /photos/)
- LVGL `lv_img` widget scaled to 800x480
- Configurable slideshow interval (5s, 10s, 30s, 60s)
- Transition animation (fade, slide)
- Touch to pause/skip, swipe to go back
- Show clock overlay in corner (optional)
- Note: LVGL can decode PNG/BMP natively; JPG needs a decoder or pre-conversion

**Clock mode (enhanced):**
- **Digital clock:** large time display with date, day of week (expand current simple clock)
- **Analog clock:** rendered with LVGL line/arc drawing -- hour/minute/second hands on a circular face
- User selectable: analog, digital, or both side-by-side
- Weather widget placeholder for future expansion
- Configurable 12h/24h format

**Mode switching:**
- Swipe gesture from edge or dedicated UI element (e.g. long-press, swipe down from top)
- Physical button if available, or a "mode" button in the stats header
- Config option for default mode on boot
- Mode persists across dimming (DIMMED is brightness, not a mode)

**Config schema (display/config.h):**
```
struct DisplayModeConfig {
    uint8_t default_mode;           // MODE_MACRO_PAD default
    uint8_t clock_style;            // 0=digital, 1=analog, 2=both
    bool clock_24h;                 // true=24h, false=12h
    uint16_t slideshow_interval_s;  // seconds between photos
    std::string photos_path;        // SD card folder for pictures
};
```

**Editor (companion/ui/editor_main.py):**
- "Display Modes" settings section
- Default mode selector
- Clock style picker (digital/analog/both, 12h/24h)
- Slideshow interval setting
- Photos folder path

**Power state integration:**
- ACTIVE + MODE_MACRO_PAD = current behavior
- ACTIVE + MODE_CLOCK = enhanced clock
- ACTIVE + MODE_PICTURE_FRAME = slideshow
- DIMMED + any mode = lower brightness, same content
- MODE_STANDBY = screen off regardless of power state
- PC shutdown signal → MODE_CLOCK (or MODE_STANDBY per config)
