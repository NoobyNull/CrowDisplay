#pragma once

#include <stdint.h>
#include <Wire.h>

/**
 * Rotary encoder driver for I2C-based encoder (e.g., AS5600, AMS 5500, or I2C expander with encoder signals).
 * Handles rotation detection (page navigation) and button press events.
 *
 * Expected I2C communication:
 * - Device address: 0x36 (configurable)
 * - Read position: 2 bytes (MSB, LSB) returning 16-bit position value
 * - Optional: button state in the same read or separate byte
 */

#define ENCODER_I2C_ADDR 0x36  // Default I2C address (AS5600 or compatible)
#define ENCODER_POSITION_REGISTER 0x0E  // AS5600 angle output register (2 bytes)

/**
 * Initialize rotary encoder I2C driver.
 * Call this once during setup() after Wire.begin().
 */
void encoder_init();

/**
 * Poll the rotary encoder position and button state.
 * Call this periodically (e.g., every 50ms in main loop).
 *
 * Returns:
 *  0: no change
 *  1: rotated forward (CW)
 * -1: rotated backward (CCW)
 *  2: button pressed (rising edge, once per press)
 * -2: button released (falling edge, once per release)
 */
int8_t encoder_poll();

/**
 * Set a custom debounce threshold for rotation detection (in encoder units).
 * Default is 10. Larger values = less sensitive to small jitter.
 */
void encoder_set_debounce(uint16_t threshold);

/**
 * Get the last read raw position value.
 */
uint16_t encoder_get_position();

/**
 * Get button state (true = pressed).
 */
bool encoder_get_button();
