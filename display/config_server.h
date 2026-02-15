#pragma once

#include <stdint.h>
#include <stdbool.h>

// ============================================================
// Configuration Server - Unified SoftAP HTTP Interface
// ============================================================
//
// Provides a WiFi SoftAP ("CrowPanel-Config") with HTTP endpoints:
//   - Config upload: POST /api/config/upload (JSON config files)
//   - OTA firmware:  POST /update (binary firmware files)
//   - ArduinoOTA:    PlatformIO upload-port support
//
// Usage:
//   config_server_start()  - Start SoftAP + web server + ArduinoOTA
//   config_server_poll()   - Call from main loop (handles HTTP + OTA + timeout)
//   config_server_stop()   - Stop SoftAP + web server + ArduinoOTA
//
// Architecture:
//   - SoftAP operates on channel 1 (pinned for ESP-NOW coexistence)
//   - 5-minute inactivity timeout auto-stops SoftAP
//   - Validates JSON before writing to SD card
//   - Atomically writes: upload -> tmp file -> validate -> rename -> rebuild UI
//   - Upload errors return HTTP 400 with descriptive JSON error

// Start configuration server: bring up SoftAP + HTTP endpoints + ArduinoOTA
// Returns true if SoftAP started successfully
bool config_server_start();

// Stop configuration server: tear down SoftAP, web server, and ArduinoOTA
void config_server_stop();

// Must be called from loop() while config server is active
// Handles HTTP clients, ArduinoOTA, and inactivity timeout
void config_server_poll();

// Is config server currently active?
bool config_server_active();

// Check if server timed out due to inactivity (returns true once, then clears)
bool config_server_timed_out();

// Callback: called when new config is successfully validated and applied
// (fired AFTER rebuild_ui() completes)
typedef void (*on_config_updated_callback_t)();
void config_server_set_callback(on_config_updated_callback_t cb);
