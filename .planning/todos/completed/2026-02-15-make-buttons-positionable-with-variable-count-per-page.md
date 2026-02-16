---
created: 2026-02-15T22:51:42.178Z
title: Make buttons positionable with variable count per page
area: ui
files:
  - display/config.h:39-57
  - display/config.cpp:364-395
  - companion/ui/editor_main.py
  - companion/ui/button_editor.py
  - companion/config_manager.py
---

## Problem

The current config schema and editor enforce a fixed 4x3 (12-slot) button grid per page. Buttons are stored as a flat list and rendered sequentially left-to-right, top-to-bottom. Users cannot:

1. **Control button count** -- every page shows 12 slots regardless of how many buttons are needed. No way to have a page with just 3 or 6 buttons.
2. **Position buttons freely** -- buttons fill the grid sequentially. A user can't place a button at a specific row/col (e.g. put "Kill" in the bottom-right corner with empty slots elsewhere).
3. **Move buttons** -- no drag-and-drop or move-up/move-down to rearrange button positions within a page.

This affects both the device firmware (ButtonConfig struct has no position fields, display/ui.cpp renders sequentially) and the desktop editor (hardcoded 4x3 grid widget).

## Solution

**Config schema changes (display/config.h):**
- Add optional `row` and `col` fields to ButtonConfig (default -1 = auto-place sequentially)
- Or: keep the flat list but interpret index as position (simpler, buttons just fill available slots)
- Remove the hard 12-button assumption; render only the buttons that exist in the list

**Editor changes (companion/):**
- Variable button count: allow adding/removing individual buttons within a page (not just pages)
- Grid shows only populated slots, with empty slots as "+" add buttons
- Drag-and-drop or arrow buttons to reorder within the grid
- Grid dimensions could remain 4x3 max but only filled slots show content

**Device firmware (display/ui.cpp):**
- Render only `page.buttons.size()` buttons, not a fixed 12
- Handle empty grid cells gracefully (skip or show blank)
