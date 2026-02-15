---
created: 2026-02-15T22:58:00.000Z
title: Forward host OS notifications to display as toast overlays
area: general
files:
  - companion/hotkey_companion.py
  - shared/protocol.h
  - bridge/bridge.ino
  - display/ui.cpp
  - display/ui.h
---

## Problem

Users want to see desktop notifications (Slack messages, Discord pings, email alerts, system events, etc.) appear as toast popups on the CrowPanel display. CachyOS (Arch-based) uses standard freedesktop notifications via D-Bus, with configurable notification sources in the OS settings. The companion app should tap into whichever notifications the user has enabled at the OS level and forward selected ones to the display.

## Solution

**Protocol extension (shared/protocol.h):**
- New message type: `MSG_NOTIFICATION = 0x07`
- Payload: app_name (16 bytes) + summary (32 bytes) + body (64 bytes) + urgency (1 byte)
- Total ~113 bytes fits within ESP-NOW 250-byte limit

**Companion app (companion/hotkey_companion.py or new module):**
- Monitor D-Bus `org.freedesktop.Notifications` interface using `dbus-next` (already a dependency for shutdown detection)
- Intercept `Notify` method calls on the session bus -- this catches all notifications the OS is already configured to show
- Configurable app filter: user selects which app names to forward (e.g. "Slack", "Discord", "Thunderbird") via a config file or the editor app
- Truncate text to fit protocol payload size
- Send as MSG_NOTIFICATION HID output report to bridge

**Bridge (bridge/bridge.ino):**
- Relay MSG_NOTIFICATION over ESP-NOW to display (same pattern as MSG_STATS)

**Display (display/ui.cpp):**
- Toast overlay widget: semi-transparent dark panel at top of screen
- Shows app icon/name + summary text
- Auto-dismiss after 3-5 seconds with fade-out animation
- Queue multiple notifications if they arrive in rapid succession
- LVGL `lv_msgbox` or custom positioned label with `lv_anim`

**Editor app (companion/crowpanel_editor.py or settings panel):**
- "Notifications" tab/section where user checks which app names to forward
- Discovers available app names by monitoring D-Bus for a few seconds or from a common list
- Saves filter list to companion config file

**D-Bus approach:**
- Session bus (not system bus) -- this is where desktop app notifications live
- `org.freedesktop.Notifications` is the standard interface on all freedesktop-compliant DEs
- CachyOS notification settings control what the DE shows -- the companion monitors the same bus and independently selects what to forward to the display
- No conflict with the OS notification daemon -- the companion is a passive listener using `BecomeMonitor` or `AddMatch`
