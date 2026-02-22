#include "status_led.h"
#include <Adafruit_NeoPixel.h>

#define LED_PIN       48
#define LED_BRIGHTNESS 6  // ~25% of previous, very dim

static Adafruit_NeoPixel pixel(1, LED_PIN, NEO_GRB + NEO_KHZ800);
static LedState current_state = LED_INIT;
static bool flash_active = false;
static uint32_t flash_start_ms = 0;
static uint32_t blink_last_ms = 0;
static bool blink_on = true;

static void apply_state_color() {
    switch (current_state) {
        case LED_INIT:
            pixel.setPixelColor(0, pixel.Color(LED_BRIGHTNESS, LED_BRIGHTNESS, 0)); // Yellow
            break;
        case LED_CONNECTED:
            pixel.setPixelColor(0, pixel.Color(0, LED_BRIGHTNESS, 0)); // Green
            break;
        case LED_DISCONNECTED:
            pixel.setPixelColor(0, pixel.Color(LED_BRIGHTNESS, 0, 0)); // Red
            break;
        case LED_CONFIG_MODE:
            // Handled by blink logic in update()
            break;
        case LED_SLEEP:
            pixel.setPixelColor(0, 0); // Off
            break;
    }
    pixel.show();
}

void status_led_init() {
    pixel.begin();
    pixel.setBrightness(255);  // We control brightness via color values
    current_state = LED_INIT;
    apply_state_color();
}

void status_led_set_state(LedState state) {
    if (state == current_state) return;
    current_state = state;
    blink_on = true;
    blink_last_ms = millis();
    if (!flash_active) {
        apply_state_color();
    }
}

void status_led_flash() {
    flash_active = true;
    flash_start_ms = millis();
    pixel.setPixelColor(0, pixel.Color(LED_BRIGHTNESS, LED_BRIGHTNESS, LED_BRIGHTNESS)); // White
    pixel.show();
}

void status_led_update() {
    uint32_t now = millis();

    // Flash overlay: white for 100ms then revert
    if (flash_active) {
        if (now - flash_start_ms >= 100) {
            flash_active = false;
            apply_state_color();
        }
        return;  // Don't run blink logic during flash
    }

    // Blink logic for config mode (~2Hz = 250ms on/off)
    if (current_state == LED_CONFIG_MODE) {
        if (now - blink_last_ms >= 250) {
            blink_last_ms = now;
            blink_on = !blink_on;
            if (blink_on) {
                pixel.setPixelColor(0, pixel.Color(0, 0, LED_BRIGHTNESS)); // Blue
            } else {
                pixel.setPixelColor(0, pixel.Color(0, 0, 0)); // Off
            }
            pixel.show();
        }
    }
}
