#include "power.h"
#include "display_hw.h"

#include <Arduino.h>

// ============================================================
// Constants
// ============================================================
static constexpr uint32_t IDLE_TIMEOUT_MS   = 60000;  // 60 seconds

static constexpr uint8_t BRIGHTNESS_ACTIVE  = 200;
static constexpr uint8_t BRIGHTNESS_DIMMED  = 64;
static constexpr uint8_t BRIGHTNESS_CLOCK   = 16;

// User-selectable brightness presets (cycled in ACTIVE state)
static const uint8_t BRIGHTNESS_PRESETS[] = {255, 180, 100};
static constexpr uint8_t NUM_PRESETS = sizeof(BRIGHTNESS_PRESETS) / sizeof(BRIGHTNESS_PRESETS[0]);

// ============================================================
// State
// ============================================================
static PowerState current_state     = POWER_ACTIVE;
static uint32_t   last_activity_ms  = 0;
static uint8_t    preset_index      = 0;   // Current user brightness preset
static uint8_t    user_brightness   = BRIGHTNESS_ACTIVE;  // Tracks user-chosen brightness for wake restore

// ============================================================
// power_init()
// ============================================================
void power_init() {
    current_state    = POWER_ACTIVE;
    last_activity_ms = millis();
    user_brightness  = BRIGHTNESS_ACTIVE;
    set_backlight(BRIGHTNESS_ACTIVE);
}

// ============================================================
// power_update() -- call from loop(), checks idle timeout
// ============================================================
void power_update() {
    if (current_state == POWER_ACTIVE) {
        if (millis() - last_activity_ms > IDLE_TIMEOUT_MS) {
            current_state = POWER_DIMMED;
            set_backlight(BRIGHTNESS_DIMMED);
            Serial.println("[power] ACTIVE -> DIMMED (idle timeout)");
        }
    }
    // No automatic transitions from DIMMED or CLOCK
}

// ============================================================
// power_activity() -- touch or incoming message resets idle
// ============================================================
void power_activity() {
    last_activity_ms = millis();

    if (current_state == POWER_DIMMED) {
        current_state = POWER_ACTIVE;
        set_backlight(user_brightness);
        Serial.println("[power] DIMMED -> ACTIVE (activity)");
    }
    // In CLOCK mode, only power_wake_detected() can transition out
}

// ============================================================
// power_shutdown_received() -- PC going to sleep/shutdown
// ============================================================
void power_shutdown_received() {
    current_state = POWER_CLOCK;
    set_backlight(BRIGHTNESS_CLOCK);
    Serial.println("[power] -> CLOCK_MODE (PC shutdown)");
}

// ============================================================
// power_wake_detected() -- bridge message in CLOCK mode
// ============================================================
void power_wake_detected() {
    if (current_state == POWER_CLOCK) {
        current_state    = POWER_ACTIVE;
        last_activity_ms = millis();
        set_backlight(BRIGHTNESS_ACTIVE);
        Serial.println("[power] CLOCK_MODE -> ACTIVE (wake)");
    }
}

// ============================================================
// power_get_state()
// ============================================================
PowerState power_get_state() {
    return current_state;
}

// ============================================================
// power_cycle_brightness() -- cycle user presets (ACTIVE only)
// ============================================================
void power_cycle_brightness() {
    if (current_state != POWER_ACTIVE) return;

    preset_index = (preset_index + 1) % NUM_PRESETS;
    user_brightness = BRIGHTNESS_PRESETS[preset_index];
    set_backlight(user_brightness);
    last_activity_ms = millis();

    Serial.printf("[power] Brightness preset %d: %d\n", preset_index, user_brightness);
}
