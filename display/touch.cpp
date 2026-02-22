#include "touch.h"

#include <Arduino.h>
#include <Wire.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include "ui.h"
#include "power.h"
#include "config.h"

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
// Swipe gesture detection
// ============================================================
#define SWIPE_MIN_PX     80   // Minimum distance to count as swipe
#define SWIPE_MAX_MS     600  // Maximum duration for a swipe
#define SWIPE_RATIO      1.5f // Primary axis must be this much larger than secondary

static void gesture_check();  // Forward declaration

static bool     swipe_tracking = false;
static bool     swipe_active = false;   // True once finger moved enough — suppress LVGL
static uint16_t swipe_start_x = 0;
static uint16_t swipe_start_y = 0;
static uint32_t swipe_start_ms = 0;
static bool     prev_touch_down = false;

#define SWIPE_SUPPRESS_PX  30  // Start suppressing LVGL after this much movement
#define TAP_CONFIRM_MS     120 // Delay before telling LVGL about press (to distinguish tap vs swipe)

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

    // Check for swipe gestures
    gesture_check();
}

// ============================================================
// Swipe gesture processing -- called from touch_poll()
// ============================================================
static void gesture_check() {
    bool down = touch_down;

    // Touch just started
    if (down && !prev_touch_down) {
        swipe_tracking = true;
        swipe_active = false;
        swipe_start_x = touch_x;
        swipe_start_y = touch_y;
        swipe_start_ms = millis();
    }

    // While touching, check if finger has moved enough to be a swipe
    if (down && swipe_tracking && !swipe_active) {
        int dx = abs((int)touch_x - (int)swipe_start_x);
        int dy = abs((int)touch_y - (int)swipe_start_y);
        if (dx >= SWIPE_SUPPRESS_PX || dy >= SWIPE_SUPPRESS_PX) {
            swipe_active = true;  // Suppress LVGL from here on
        }
    }

    // Touch just released — check for swipe
    if (!down && prev_touch_down && swipe_tracking) {
        swipe_tracking = false;
        uint32_t dt = millis() - swipe_start_ms;

        if (swipe_active && dt <= SWIPE_MAX_MS) {
            int dx = (int)touch_x - (int)swipe_start_x;
            int dy = (int)touch_y - (int)swipe_start_y;
            int abs_dx = abs(dx);
            int abs_dy = abs(dy);

            if (abs_dx > abs_dy && abs_dx >= SWIPE_MIN_PX && abs_dx > abs_dy * SWIPE_RATIO) {
                if (dx > 0) {
                    Serial.println("[gesture] swipe right -> prev page");
                    ui_prev_page();
                } else {
                    Serial.println("[gesture] swipe left -> next page");
                    ui_next_page();
                }
            } else if (abs_dy > abs_dx && abs_dy >= SWIPE_MIN_PX && abs_dy > abs_dx * SWIPE_RATIO) {
                const AppConfig &cfg = get_global_config();
                Serial.printf("[gesture] swipe %s -> mode cycle\n", dy > 0 ? "down" : "up");
                mode_cycle_next(cfg.mode_cycle.enabled_modes);
            }
        }

        swipe_active = false;
    }

    prev_touch_down = down;
}

// ============================================================
// touch_read_cb() -- LVGL input driver callback
// Returns cached touch state, no I2C here.
// ============================================================
void touch_read_cb(lv_indev_drv_t *drv, lv_indev_data_t *data) {
    data->point.x = touch_x;
    data->point.y = touch_y;

    if (swipe_active) {
        // Swipe in progress — hide from LVGL entirely
        data->state = LV_INDEV_STATE_REL;
    } else if (touch_down && swipe_tracking && (millis() - swipe_start_ms < TAP_CONFIRM_MS)) {
        // Touch just started — hold off reporting press until we know it's not a swipe
        data->state = LV_INDEV_STATE_REL;
    } else {
        data->state = touch_down ? LV_INDEV_STATE_PR : LV_INDEV_STATE_REL;
    }
}
