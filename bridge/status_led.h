#pragma once

enum LedState {
    LED_INIT,
    LED_CONNECTED,
    LED_DISCONNECTED,
    LED_CONFIG_MODE,
    LED_SLEEP
};

void status_led_init();
void status_led_set_state(LedState state);
void status_led_flash();   // Brief white flash (100ms)
void status_led_update();  // Call from loop()
