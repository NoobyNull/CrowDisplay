---
phase: 06-data-driven-display-ui
status: human_needed
verified_by: automated
updated: 2026-02-15
---

# Phase 6 Verification: Data-Driven Display UI

## Must-Have Checks

### 1. Display renders pages and buttons from config
- [x] **PASS** - create_ui_widgets() iterates AppConfig pages/buttons, create_hotkey_button takes ButtonConfig*
- [x] **PASS** - Variable page count from config (for loop over active_profile->pages)
- [x] **PASS** - Each button shows label, color, icon, description from ButtonConfig
- [x] **PASS** - Button press fires correct keystroke via ButtonConfig* event user_data
- [x] **PASS** - No hardcoded page arrays (Hotkey/HotkeyPage/page1_hotkeys all removed)

### 2. Config reload rebuilds UI without reboot
- [x] **PASS** - config_server uploads JSON, saves to SD, updates global config, sets rebuild flag
- [x] **PASS** - loop() checks g_rebuild_pending, calls rebuild_ui(&g_app_config)
- [x] **PASS** - rebuild_ui uses lv_obj_clean(main_screen) for full teardown + recreate

### 3. Repeated reloads do not exhaust LVGL memory
- [x] **PASS** - lv_mem_monitor() logs before/after memory on every rebuild
- [x] **PASS** - lv_obj_clean destroys all children, all widget pointers nulled
- [ ] **HUMAN** - Verify 10 consecutive reloads show stable memory delta on actual hardware

## Compilation Check
- [x] `pio run -e display` builds cleanly (SUCCESS)
- [x] No warnings related to deprecated code paths

## Code Integrity
- [x] No Hotkey struct references in display/ui.cpp
- [x] No HotkeyPage struct references in display/ui.cpp
- [x] No button_config_to_hotkey() calls anywhere
- [x] No hardcoded page arrays (page1_hotkeys, page2_hotkeys, page3_hotkeys)
- [x] static AppConfig g_app_config in main.cpp (program lifetime)
- [x] ButtonConfig* as lv_event_get_user_data in btn_event_cb

## Human Verification Required

The following items require on-device testing:

1. **Hot-reload stability**: Upload a modified config.json via WiFi SoftAP config server. Verify the display shows the updated layout without reboot.

2. **Memory stability across 10 reloads**: Trigger 10 consecutive config reloads and check serial output for lv_mem_monitor delta. Delta should be zero or near-zero (within 100 bytes) after each reload.

3. **Visual correctness**: Verify buttons show correct colors, icons, labels, and descriptions matching the config file content.

## Score

**Automated: 11/12 must-haves verified (92%)**
**Human testing: 1 item remaining (memory stability across 10 reloads)**
