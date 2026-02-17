#pragma once
#include <stdint.h>

// Initialize PCF8575 hardware input: scan TCA9548A channel 0 for PCF8575 at 0x20-0x27
// Returns true if PCF8575 found, false if not (hardware buttons disabled gracefully)
bool hw_input_init();

// Poll hardware buttons and encoder. Call every 50ms from loop().
// Reads PCF8575 via I2C mux, debounces buttons, decodes encoder quadrature.
// Dispatches configured actions for button presses and encoder events.
void hw_input_poll();

// Check if PCF8575 was detected at init
bool hw_input_available();

// Focus management for app-select encoder mode
void hw_input_focus_next();    // Highlight next widget on current page
void hw_input_focus_prev();    // Highlight previous widget
void hw_input_activate_focus(); // Fire the focused widget's action
void hw_input_clear_focus();   // Remove focus highlight (call on page change)
