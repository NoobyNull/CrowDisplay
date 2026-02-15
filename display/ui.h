#pragma once
#include "protocol.h"
#include "config.h"

// Build the complete hotkey UI from AppConfig (config required, no hardcoded fallback)
void create_ui(const AppConfig* cfg);

// Rebuild UI after configuration change (re-create pages without reboot)
void rebuild_ui(const AppConfig* cfg);

// Update stats header with new metrics from companion app.
// Shows the header on first call. Pass nullptr to hide (timeout).
void update_stats(const StatsPayload *stats);

// Hide stats header (called on timeout)
void hide_stats_header();

// Power state UI transitions
void show_clock_mode();      // Switch to clock screen (called by power state machine)
void show_hotkey_view();     // Switch back to main screen (called on wake)

// Device status update (call from main loop every ~5s or on change)
void update_device_status(int rssi_dbm, bool espnow_linked, uint8_t brightness_level);

// Update clock display (call in clock mode from main loop)
void update_clock_time();

// Show OTA mode overlay with IP address
void show_ota_screen(const char *ip);

// Hide OTA overlay, return to normal view
void hide_ota_screen();

// Request deferred UI rebuild (safe to call from any context, executes in loop)
void request_ui_rebuild();

// Access the global config (for config_server to update before rebuild)
AppConfig& get_global_config();
