---
created: 2026-02-17T00:40:40.333Z
title: Add physical buttons rotary encoder and display function settings
area: companion
files:
  - display/main.cpp
  - display/ui.cpp
  - companion/hotkey_companion.py
  - companion/crowpanel_editor.py
---

## Problem

The CrowPanel has physical buttons and a rotary encoder on the hardware that are not yet mapped to any functionality. Additionally, the display supports built-in functions like clock mode and picture slideshow mode, but there is no way to configure these function settings (e.g., slideshow interval, clock style) from the companion app editor.

Need to:
1. Map physical buttons on the display hardware to actions (e.g., page navigation, brightness, mode switching)
2. Map rotary encoder to scrollable actions (e.g., volume, brightness, page cycling)
3. Add settings UI in the companion editor for display-local functions:
   - Clock mode settings (style, color, 12/24h)
   - Slideshow settings (interval, transition, folder path)
   - Other display functions that don't require PC interaction

## Solution

Phase 11 (Hardware Buttons + System Actions) already exists in the roadmap for physical button mapping. This todo extends it to include:
- GPIO interrupt handlers for physical buttons on the CrowPanel
- Rotary encoder driver (likely using ESP32 PCNT or polling)
- Companion editor panel for "Display Functions" settings section
- Config schema additions for clock/slideshow/function preferences
- Bidirectional sync of function settings via ESP-NOW or HTTP upload
