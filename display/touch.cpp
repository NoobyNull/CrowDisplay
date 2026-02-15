#include "touch.h"

#include <Arduino.h>
#include <Wire.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

// ============================================================
// I2C Mutex -- protects all Wire operations
// ============================================================
static SemaphoreHandle_t i2c_mutex = NULL;

bool i2c_take(uint32_t timeout_ms) {
    return xSemaphoreTake(i2c_mutex, pdMS_TO_TICKS(timeout_ms)) == pdTRUE;
}

void i2c_give() {
    xSemaphoreGive(i2c_mutex);
}

// ============================================================
// GT911 Touch -- direct I2C via Wire
// ============================================================
static uint8_t gt911_addr = 0;

static volatile bool     touch_down = false;
static volatile uint16_t touch_x = 0;
static volatile uint16_t touch_y = 0;

static uint32_t touch_err_timer = 0;  // Rate-limit error logging

// ============================================================
// touch_init() -- create mutex only (GT911 not yet reset)
// ============================================================
void touch_init() {
    i2c_mutex = xSemaphoreCreateMutex();
    configASSERT(i2c_mutex != NULL);
    Serial.println("I2C mutex created");
}

// ============================================================
// gt911_discover() -- probe for GT911 at 0x5D and 0x14
// Call AFTER display_init() since PCA9557 resets the GT911.
// ============================================================
void gt911_discover() {
    uint8_t addrs[] = {0x5D, 0x14};
    for (int attempt = 0; attempt < 10; attempt++) {
        for (int i = 0; i < 2; i++) {
            if (!i2c_take(50)) continue;
            Wire.beginTransmission(addrs[i]);
            uint8_t err = Wire.endTransmission();
            i2c_give();

            if (err == 0) {
                gt911_addr = addrs[i];
                Serial.printf("GT911 found at 0x%02X (attempt %d)\n", gt911_addr, attempt);
                return;
            }
        }
        delay(100);
    }
    Serial.println("GT911 not found!");
}

// ============================================================
// touch_poll() -- read GT911 with full mutex protection
// ============================================================
void touch_poll() {
    if (gt911_addr == 0) return;

    // Acquire mutex for the entire GT911 transaction
    if (!i2c_take(10)) return;  // Skip this cycle if bus is busy

    // Read status register (0x814E)
    Wire.beginTransmission(gt911_addr);
    Wire.write(0x81);
    Wire.write(0x4E);
    int err = Wire.endTransmission();
    if (err != 0) {
        i2c_give();
        if (millis() - touch_err_timer > 2000) {
            touch_err_timer = millis();
            Serial.printf("GT911 i2c err: %d\n", err);
        }
        touch_down = false;
        return;
    }

    delay(1);
    Wire.requestFrom(gt911_addr, (uint8_t)1);
    if (!Wire.available()) {
        i2c_give();
        touch_down = false;
        return;
    }

    uint8_t status = Wire.read();
    uint8_t touches = status & 0x0F;

    if ((status & 0x80) && touches > 0) {
        // Read touch point 0 data (0x8150)
        Wire.beginTransmission(gt911_addr);
        Wire.write(0x81);
        Wire.write(0x50);
        Wire.endTransmission();
        delay(1);
        Wire.requestFrom(gt911_addr, (uint8_t)4);
        if (Wire.available() >= 4) {
            touch_x = Wire.read() | (Wire.read() << 8);
            touch_y = Wire.read() | (Wire.read() << 8);
            touch_down = true;
        }
    } else {
        touch_down = false;
    }

    // Clear status register
    Wire.beginTransmission(gt911_addr);
    Wire.write(0x81);
    Wire.write(0x4E);
    Wire.write(0x00);
    Wire.endTransmission();

    i2c_give();
}

// ============================================================
// touch_read_cb() -- LVGL input driver callback
// Returns cached touch state, no I2C here.
// ============================================================
void touch_read_cb(lv_indev_drv_t *drv, lv_indev_data_t *data) {
    data->point.x = touch_x;
    data->point.y = touch_y;
    data->state   = touch_down ? LV_INDEV_STATE_PR : LV_INDEV_STATE_REL;
}
