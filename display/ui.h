#pragma once
#include "protocol.h"
#include "config.h"

// Build the complete hotkey UI from AppConfig (config required, no hardcoded fallback)
void create_ui(const AppConfig* cfg);

// Rebuild UI after configuration change (re-create pages without reboot)
void rebuild_ui(const AppConfig* cfg);

// Update stats header with new metrics from companion app.
// Accepts raw payload bytes -- auto-detects TLV vs legacy StatsPayload format.
// Shows the header on first call.
void update_stats(const uint8_t *data, uint8_t len);

// Hide stats header (called on timeout)
void hide_stats_header();

// Power state UI transitions
void show_clock_mode();      // Switch to clock screen (called by power state machine)
void show_hotkey_view();     // Switch back to main screen (called on wake)

// Device status update (call from main loop every ~5s or on change)
void update_device_status(int rssi_dbm, bool espnow_linked, uint8_t brightness_level);

// Update clock display (call in clock mode from main loop)
void update_clock_time();

// Enter config mode screen (shows SSID, password, IP, upload URLs)
void show_config_screen();

// Return to main hotkey view from config screen
void hide_config_screen();

// Request deferred UI rebuild (safe to call from any context, executes in loop)
void request_ui_rebuild();

// Show a desktop notification as a toast overlay (auto-dismisses after 5s, tap to dismiss)
void show_notification_toast(const char *app_name, const char *summary, const char *body);

// Access the global config (for config_server to update before rebuild)
AppConfig& get_global_config();
