#pragma once
#include "protocol.h"

void create_ui();  // Build the complete hotkey UI

// Update stats header with new metrics from companion app.
// Shows the header on first call. Pass nullptr to hide (timeout).
void update_stats(const StatsPayload *stats);

// Hide stats header (called on timeout)
void hide_stats_header();
