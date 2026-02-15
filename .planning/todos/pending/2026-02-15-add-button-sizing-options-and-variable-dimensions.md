---
created: 2026-02-15T22:55:00.000Z
title: Add button sizing options and variable dimensions
area: ui
files:
  - display/config.h:39-57
  - display/config.cpp:364-373
  - display/ui.cpp
  - companion/ui/editor_main.py
  - companion/ui/button_editor.py
  - companion/config_manager.py
---

## Problem

All buttons are currently the same size -- each occupies exactly one cell in the 4x3 grid. Users want buttons of different sizes to create more expressive layouts:

- **1x1** -- standard single cell (current default)
- **2x1** -- wide button spanning 2 columns (good for labels like "Play/Pause" or important actions)
- **1x2** -- tall button spanning 2 rows
- **2x2** -- large button spanning 2x2 cells (good for primary actions like "Kill" or "Lock")

This is listed as ADV-01 in the future requirements: "Variable button sizes (1x1, 2x1, 1x2, 2x2 grid units)".

## Solution

**Config schema (display/config.h):**
- Add `uint8_t col_span` and `uint8_t row_span` fields to ButtonConfig (default 1, 1)
- Combined with the grid position todo, each button would have: row, col, col_span, row_span
- Validate that spans don't overflow grid boundaries or overlap other buttons

**Device firmware (display/ui.cpp):**
- Use LVGL `lv_obj_set_grid_cell()` with span parameters, or manually calculate button position and size based on grid cell dimensions
- Skip grid cells occupied by multi-span buttons when laying out subsequent buttons

**Editor (companion/ui/button_editor.py):**
- Add "Size" dropdown or spinboxes: col_span (1-4), row_span (1-3)
- Grid preview shows buttons at their actual span size

**Editor grid (companion/ui/editor_main.py):**
- Render multi-cell buttons spanning across grid positions
- Prevent overlapping placements (validate on size change)

**JSON format:**
- New optional fields: `"col_span": 2, "row_span": 1` (default both 1)
- Backward compatible: missing fields default to 1x1
