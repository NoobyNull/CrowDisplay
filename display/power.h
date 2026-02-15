#pragma once
#include <cstdint>

enum PowerState : uint8_t {
    POWER_ACTIVE,   // Full brightness, normal operation
    POWER_DIMMED,   // Reduced brightness, idle timeout
    POWER_CLOCK,    // Minimal brightness, clock mode (PC off)
};

void power_init();              // Set initial state to ACTIVE
void power_update();            // Call from loop() -- checks idle timeout
void power_activity();          // Call on touch or incoming message -- resets idle timer, wakes from DIMMED
void power_shutdown_received(); // Call when MSG_POWER_STATE shutdown received -- enter clock mode
void power_wake_detected();     // Call when any bridge message received in CLOCK_MODE -- return to ACTIVE
PowerState power_get_state();   // Get current power state

// Brightness cycling for user control (3 presets: HIGH/MED/LOW)
void power_cycle_brightness();  // Cycle through brightness presets (only in ACTIVE state)
