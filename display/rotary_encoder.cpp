#include "rotary_encoder.h"
#include <Arduino.h>

// ============================================================
// Rotary Encoder I2C Driver (AS5600-compatible)
// ============================================================

static uint16_t last_position = 0;
static uint16_t debounce_threshold = 10;  // Minimum change to register as rotation
static bool last_button_state = false;
static uint32_t button_debounce_timer = 0;
static const uint32_t BUTTON_DEBOUNCE_MS = 20;

void encoder_init() {
    // Wire.begin() should already be called in main.cpp setup()
    // This function is a placeholder for future initialization if needed
    last_position = 0;
    last_button_state = false;
}

int8_t encoder_poll() {
    // Request 2 bytes from encoder device
    Wire.beginTransmission(ENCODER_I2C_ADDR);
    Wire.write(ENCODER_POSITION_REGISTER);
    if (Wire.endTransmission(false) != 0) {
        // I2C error, encoder not responding
        return 0;
    }

    // Read 2 bytes: position MSB and LSB
    if (Wire.requestFrom(ENCODER_I2C_ADDR, 2) != 2) {
        // Not enough bytes read
        return 0;
    }

    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    uint16_t current_position = ((uint16_t)msb << 8) | lsb;

    int8_t rotation_event = 0;

    // Detect rotation: large change in position indicates a page turn
    int16_t delta = (int16_t)current_position - (int16_t)last_position;

    // Account for wrap-around at 0/4096 boundary (14-bit AS5600)
    if (delta > 2048) {
        delta -= 4096;  // Wrapped backward (CCW)
    } else if (delta < -2048) {
        delta += 4096;  // Wrapped forward (CW)
    }

    // Only register if delta exceeds debounce threshold
    if (delta > (int16_t)debounce_threshold) {
        rotation_event = 1;  // Rotated forward (CW) - next page
        last_position = current_position;
    } else if (delta < -(int16_t)debounce_threshold) {
        rotation_event = -1;  // Rotated backward (CCW) - prev page
        last_position = current_position;
    }

    // Button state: typically read from an additional register or GPIO
    // For now, stub implementation assumes button is on a separate I2C device or GPIO
    // This would be filled in with actual hardware protocol
    // bool current_button = read_encoder_button();
    // if (current_button != last_button_state) {
    //     if (debounce timer expired) {
    //         last_button_state = current_button;
    //         return current_button ? 2 : -2;
    //     }
    // }

    return rotation_event;
}

void encoder_set_debounce(uint16_t threshold) {
    debounce_threshold = threshold;
}

uint16_t encoder_get_position() {
    return last_position;
}

bool encoder_get_button() {
    return last_button_state;
}
