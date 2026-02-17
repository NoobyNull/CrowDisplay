#pragma once
#include <cstdint>
#include <vector>

enum PowerState : uint8_t {
    POWER_ACTIVE,   // Full brightness, normal operation
    POWER_DIMMED,   // Reduced brightness, idle timeout
    POWER_CLOCK,    // Minimal brightness, clock mode (PC off)
};

// Display modes -- orthogonal to PowerState
// PowerState controls brightness, DisplayMode controls what is shown
enum DisplayMode : uint8_t {
    MODE_HOTKEYS       = 0,  // Main hotkey UI (default)
    MODE_CLOCK         = 1,  // Clock display (analog or digital)
    MODE_PICTURE_FRAME = 2,  // Image slideshow from SD card
    MODE_STANDBY       = 3,  // Minimal standby UI (time + stats)
};

void power_init();              // Set initial state to ACTIVE
void power_update();            // Call from loop() -- checks idle timeout
void power_activity();          // Call on touch or incoming message -- resets idle timer, wakes from DIMMED
void power_shutdown_received(); // Call when MSG_POWER_STATE shutdown received -- enter clock mode
void power_wake_detected();     // Call when any bridge message received in CLOCK_MODE -- return to ACTIVE
PowerState power_get_state();   // Get current power state

// Brightness cycling for user control (3 presets: HIGH/MED/LOW)
void power_cycle_brightness();  // Cycle through brightness presets (only in ACTIVE state)

// Display mode switching (orthogonal to power state)
void display_set_mode(DisplayMode mode);   // Switch to new display mode
DisplayMode display_get_mode();            // Get current display mode

// Mode cycling through user-configured enabled modes list
void mode_cycle_next(const std::vector<uint8_t>& enabled_modes);
