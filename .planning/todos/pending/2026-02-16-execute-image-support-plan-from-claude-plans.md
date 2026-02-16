---
created: 2026-02-16T03:43:35.998Z
title: Execute image support plan from Claude plans
area: ui
files:
  - /home/matthew/.claude/plans/moonlit-orbiting-dahl.md
  - display/config.h
  - display/config.cpp
  - display/ui.cpp
  - display/config_server.cpp
  - display/sdcard.h
  - display/sdcard.cpp
  - companion/image_optimizer.py
  - companion/http_client.py
  - companion/ui/editor_main.py
  - companion/ui/deploy_dialog.py
  - companion/config_manager.py
  - companion/requirements.txt
---

## Problem

The WYSIWYG canvas editor is complete but only supports LVGL symbol icons on hotkey buttons. Users want custom images (PNG, JPG, etc.) as button icons and widget backgrounds. A full plan exists at `/home/matthew/.claude/plans/moonlit-orbiting-dahl.md`.

## Solution

Execute the 6-step plan:
1. Config schema — add `icon_path` field to WidgetConfig
2. Firmware — render images in hotkey buttons via `lv_img_create()` with SD card path
3. Image optimizer module — Pillow-based resize/convert to BMP
4. SD card mkdir + HTTP image upload endpoint (`/api/image/upload`)
5. Editor — image picker in properties panel
6. Deploy pipeline — upload images before config via `HTTPClient.upload_image()`

Key decisions: BMP format (already enabled in LVGL, Pillow writes natively), SD filesystem driver already working (picture frame mode proves it), `icon_path` separate from `icon` symbol field.
