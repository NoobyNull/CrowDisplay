#include <Arduino.h>
#include <Wire.h>
#include <lvgl.h>
#include "display_hw.h"
#include "touch.h"
#include "protocol.h"

static uint32_t touch_timer = 0;

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== Display Unit Starting ===");

    Wire.begin(19, 20);  // I2C SDA=19, SCL=20

    touch_init();      // Create I2C mutex
    display_init();    // PCA9557 touch reset + LCD init
    gt911_discover();  // Discover GT911 (after PCA9557 reset)
    lvgl_init();       // LVGL buffers + drivers

    // Placeholder: UI will be added in Plan 03
    lv_obj_t *label = lv_label_create(lv_scr_act());
    lv_label_set_text(label, "Display Unit Ready");
    lv_obj_center(label);

    Serial.println("Display setup complete");
}

void loop() {
    if (millis() - touch_timer >= 50) {
        touch_timer = millis();
        touch_poll();
    }
    lvgl_tick();
    delay(5);
}
