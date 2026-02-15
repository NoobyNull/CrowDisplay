---
phase: 07-config-server-softap-http
type: verification
status: human_needed
score: 5/5
updated: 2026-02-15
---

# Phase 7: Config Server (SoftAP + HTTP) -- Verification Report

## Goal
User can wirelessly upload new hotkey configs to the display via a WiFi access point and HTTP server, with validation and seamless ESP-NOW coexistence

## Must-Have Verification

### 1. Config icon triggers SoftAP config mode with SSID/password/IP on screen
- **Status:** PASS (code verified)
- **Evidence:** `LV_SYMBOL_SETTINGS` gear icon in header (ui.cpp:424), `config_server_start()` called on tap (ui.cpp:346), `show_config_screen()` displays SSID "CrowPanel-Config", password "crowconfig", and IP from `WiFi.softAPIP()` (ui.cpp:362-374)

### 2. POST JSON config file, validate, write to SD, rebuild UI without reboot
- **Status:** PASS (code verified)
- **Evidence:** `/api/config/upload` endpoint (config_server.cpp:310), JSON validation via `deserializeJson()` (config_server.cpp:235), atomic write via tmp+rename (config_server.cpp:246,268), `request_ui_rebuild()` triggers deferred rebuild (config_server.cpp:294). HTTP 400 returned on failure with JSON error message (config_server.cpp:316).

### 3. SoftAP auto-stops after 5 minutes of inactivity, or immediately on "Apply and Exit"
- **Status:** PASS (code verified)
- **Evidence:** `INACTIVITY_TIMEOUT_MS` = 5 * 60 * 1000 (config_server.cpp:17), timeout check in `config_server_poll()` (config_server.cpp:429), "Apply & Exit" button calls `config_server_stop()` + `hide_config_screen()` via `config_btn_event_cb` (ui.cpp:349-350)

### 4. Hotkey commands continue over ESP-NOW while config mode is active (WiFi channel pinned)
- **Status:** PASS (code verified)
- **Evidence:** `CONFIG_CHANNEL = 1` (config_server.cpp:16), softAP started on channel 1 (config_server.cpp:359), `esp_wifi_set_channel(1, ...)` called in config_server_start/stop, display/espnow_link.cpp:65, bridge/espnow_link.cpp:62. WiFi mode is AP+STA (config_server.cpp:357) so ESP-NOW remains operational.

### 5. OTA firmware upload available on same HTTP server alongside config upload
- **Status:** PASS (code verified)
- **Evidence:** `/update` endpoint registered on same WebServer (config_server.cpp:387), `handle_ota_upload()` uses `Update.begin/write/end` (config_server.cpp:321-340), `ESP.restart()` on success (config_server.cpp:350). HTML page includes both config and firmware upload forms. ArduinoOTA also active for PlatformIO uploads (config_server.cpp:373-384).

## Build Verification

- Display firmware: **PASS** (SUCCESS, 46.9% RAM, 50.0% Flash)
- Bridge firmware: **PASS** (SUCCESS, 21.1% RAM, 31.1% Flash)

## Human Verification Needed

The following items require hardware testing:

1. **WiFi + ESP-NOW coexistence:** Verify that hotkey button presses still reach the PC (via ESP-NOW) while the SoftAP is active and a client is connected uploading config. Channel 1 pinning is implemented but needs RF testing.

2. **Config upload end-to-end:** Connect to "CrowPanel-Config" WiFi, browse to the device IP, upload a valid config.json, and verify the display rebuilds with the new layout.

3. **OTA firmware upload:** Upload a .bin firmware file via the web UI /update endpoint and verify the device reboots with the new firmware.

4. **Inactivity timeout:** Start config mode, disconnect (or don't connect), wait 5 minutes, and verify the display auto-returns to the main hotkey view.

5. **Apply & Exit button:** Enter config mode, tap "Apply & Exit", and verify SoftAP stops and display returns to main view.

## Score

**5/5 must-haves verified in code.** Hardware testing required for full validation.
