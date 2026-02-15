#include <Arduino.h>
#include <Wire.h>
#include <lvgl.h>
#include "display_hw.h"
#include "touch.h"
#include "ui.h"
#include "espnow_link.h"

static uint32_t touch_timer = 0;

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== Display Unit Starting ===");

    Wire.begin(19, 20);  // I2C SDA=19, SCL=20

    touch_init();      // Create I2C mutex
    display_init();    // PCA9557 touch reset + LCD init
    gt911_discover();  // Discover GT911 (after PCA9557 reset)
    lvgl_init();       // LVGL buffers + drivers

    espnow_link_init();  // ESP-NOW to bridge

    create_ui();       // Build hotkey tabview UI

    Serial.println("Display setup complete");
}

void loop() {
    // Poll touch at ~20Hz
    if (millis() - touch_timer >= 50) {
        touch_timer = millis();
        touch_poll();
    }

    // Drive LVGL
    lvgl_tick();

    // Check for ACK from bridge (non-blocking)
    uint8_t ack_status;
    if (espnow_poll_ack(ack_status)) {
        Serial.printf("ACK: status=%d\n", ack_status);
        // Future: update UI status indicator
    }

    delay(5);
}
