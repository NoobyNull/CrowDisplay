#pragma once
#include "protocol.h"

void create_ui();  // Build the complete hotkey UI

// Update stats header with new metrics from companion app.
// Shows the header on first call. Pass nullptr to hide (timeout).
void update_stats(const StatsPayload *stats);

// Hide stats header (called on timeout)
void hide_stats_header();

// Power state UI transitions
void show_clock_mode();      // Switch to clock screen (called by power state machine)
void show_hotkey_view();     // Switch back to main screen (called on wake)

// Device status update (call from main loop every ~5s or on change)
void update_device_status(uint8_t battery_pct, bool espnow_linked, uint8_t brightness_level);

// Update clock display (call in clock mode from main loop)
void update_clock_time();
