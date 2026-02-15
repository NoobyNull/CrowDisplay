/**
 * @file display_driver.cpp
 * Display and LVGL initialization for Elcrow 7.0" CrowPanel
 * Uses LovyanGFX for RGB parallel panel + GT911 touch
 *
 * LGFX configuration based on official:
 *   lgfx_user/LGFX_Elecrow_ESP32_Display_WZ8048C070.h
 */

#include "display_driver.h"

#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include <lgfx/v1/platforms/esp32s3/Panel_RGB.hpp>
#include <lgfx/v1/platforms/esp32s3/Bus_RGB.hpp>
#include <driver/i2c.h>
#include <Wire.h>
#include <PCA9557.h>
#include <lvgl.h>

// ══════════════════════════════════════════════════════════════
//  LovyanGFX Display Class for CrowPanel 7.0" (WZ8048C070)
// ══════════════════════════════════════════════════════════════

class LGFX : public lgfx::LGFX_Device {
public:
    lgfx::Bus_RGB     _bus_instance;
    lgfx::Panel_RGB   _panel_instance;
    lgfx::Light_PWM   _light_instance;
    lgfx::Touch_GT911 _touch_instance;

    LGFX(void) {
        {
            auto cfg = _panel_instance.config();
            cfg.memory_width  = SCREEN_WIDTH;
            cfg.memory_height = SCREEN_HEIGHT;
            cfg.panel_width   = SCREEN_WIDTH;
            cfg.panel_height  = SCREEN_HEIGHT;
            cfg.offset_x = 0;
            cfg.offset_y = 0;
            _panel_instance.config(cfg);
        }

        {
            auto cfg = _bus_instance.config();
            cfg.panel = &_panel_instance;

            // Blue (B0-B4)
            cfg.pin_d0  = GPIO_NUM_15;
            cfg.pin_d1  = GPIO_NUM_7;
            cfg.pin_d2  = GPIO_NUM_6;
            cfg.pin_d3  = GPIO_NUM_5;
            cfg.pin_d4  = GPIO_NUM_4;

            // Green (G0-G5)
            cfg.pin_d5  = GPIO_NUM_9;
            cfg.pin_d6  = GPIO_NUM_46;
            cfg.pin_d7  = GPIO_NUM_3;
            cfg.pin_d8  = GPIO_NUM_8;
            cfg.pin_d9  = GPIO_NUM_16;
            cfg.pin_d10 = GPIO_NUM_1;

            // Red (R0-R4)
            cfg.pin_d11 = GPIO_NUM_14;
            cfg.pin_d12 = GPIO_NUM_21;
            cfg.pin_d13 = GPIO_NUM_47;
            cfg.pin_d14 = GPIO_NUM_48;
            cfg.pin_d15 = GPIO_NUM_45;

            // Sync
            cfg.pin_henable = GPIO_NUM_41;
            cfg.pin_vsync   = GPIO_NUM_40;
            cfg.pin_hsync   = GPIO_NUM_39;
            cfg.pin_pclk    = GPIO_NUM_0;
            cfg.freq_write  = 12000000;

            // Timing
            cfg.hsync_polarity    = 0;
            cfg.hsync_front_porch = 40;
            cfg.hsync_pulse_width = 48;
            cfg.hsync_back_porch  = 40;
            cfg.vsync_polarity    = 0;
            cfg.vsync_front_porch = 1;
            cfg.vsync_pulse_width = 31;
            cfg.vsync_back_porch  = 13;
            cfg.pclk_active_neg   = 1;
            cfg.de_idle_high      = 0;
            cfg.pclk_idle_high    = 0;

            _bus_instance.config(cfg);
        }
        _panel_instance.setBus(&_bus_instance);

        {
            auto cfg = _light_instance.config();
            cfg.pin_bl = GPIO_NUM_2;
            _light_instance.config(cfg);
        }
        _panel_instance.light(&_light_instance);

        {
            auto cfg = _touch_instance.config();
            cfg.x_min       = 0;
            cfg.x_max       = 799;
            cfg.y_min       = 0;
            cfg.y_max       = 479;
            cfg.pin_int     = -1;
            cfg.pin_rst     = -1;
            cfg.bus_shared  = false;
            cfg.offset_rotation = 0;
            cfg.i2c_port    = I2C_NUM_1;
            cfg.pin_sda     = GPIO_NUM_19;
            cfg.pin_scl     = GPIO_NUM_20;
            cfg.freq        = 400000;
            cfg.i2c_addr    = 0x14;
            _touch_instance.config(cfg);
            _panel_instance.setTouch(&_touch_instance);
        }
        setPanel(&_panel_instance);
    }
};

static LGFX tft;

// LVGL draw buffers (allocated in PSRAM)
static lv_disp_draw_buf_t draw_buf;
static lv_color_t *buf1 = nullptr;
static lv_color_t *buf2 = nullptr;
#define LVGL_BUF_SIZE (SCREEN_WIDTH * 40)

// ── LVGL Display Flush Callback ──
static void disp_flush_cb(lv_disp_drv_t *disp_drv, const lv_area_t *area, lv_color_t *color_p) {
    uint32_t w = (area->x2 - area->x1 + 1);
    uint32_t h = (area->y2 - area->y1 + 1);

    tft.startWrite();
    tft.setAddrWindow(area->x1, area->y1, w, h);
    tft.writePixels((lgfx::rgb565_t *)&color_p->full, w * h);
    tft.endWrite();

    lv_disp_flush_ready(disp_drv);
}

// ── LVGL Touch Read Callback ──
static uint32_t touch_debug_timer = 0;

static void touchpad_read_cb(lv_indev_drv_t *indev_drv, lv_indev_data_t *data) {
    uint16_t x, y;
    if (tft.getTouch(&x, &y)) {
        data->state = LV_INDEV_STATE_PR;
        data->point.x = x;
        data->point.y = y;
        Serial0.printf("TOUCH: x=%d y=%d\n", x, y);
    } else {
        data->state = LV_INDEV_STATE_REL;
        // Print "no touch" once every 3 seconds so we know the callback runs
        if (millis() - touch_debug_timer > 3000) {
            touch_debug_timer = millis();
            Serial0.println("touch: polling (no touch)");
        }
    }
}

// ── Initialize Display Hardware ──
void display_init(void) {
    // GPIO 38 must be driven LOW on CrowPanel v3.0
    pinMode(38, OUTPUT);
    digitalWrite(38, LOW);

    // PCA9557 I/O expander controls touch reset/enable lines
    // Must be initialized BEFORE display/touch begin
    Wire.begin(19, 20);
    PCA9557 ioExpander(0x18, &Wire);
    ioExpander.pinMode(0, OUTPUT);
    ioExpander.pinMode(1, OUTPUT);
    ioExpander.digitalWrite(0, LOW);
    ioExpander.digitalWrite(1, LOW);
    delay(20);
    ioExpander.digitalWrite(0, HIGH);
    delay(100);
    ioExpander.pinMode(1, INPUT);

    tft.begin();
    tft.setRotation(0);
    tft.setBrightness(200);
    tft.fillScreen(TFT_BLACK);
}

// ── Initialize LVGL ──
void lvgl_init(void) {
    lv_init();

    // Allocate double-buffered draw area in PSRAM
    buf1 = (lv_color_t *)ps_malloc(LVGL_BUF_SIZE * sizeof(lv_color_t));
    buf2 = (lv_color_t *)ps_malloc(LVGL_BUF_SIZE * sizeof(lv_color_t));
    lv_disp_draw_buf_init(&draw_buf, buf1, buf2, LVGL_BUF_SIZE);

    // Display driver
    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = SCREEN_WIDTH;
    disp_drv.ver_res = SCREEN_HEIGHT;
    disp_drv.flush_cb = disp_flush_cb;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);

    // Touch input driver
    static lv_indev_drv_t indev_drv;
    lv_indev_drv_init(&indev_drv);
    indev_drv.type = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = touchpad_read_cb;
    lv_indev_drv_register(&indev_drv);
}

// ── Call in loop() to drive LVGL ──
void lvgl_tick(void) {
    lv_timer_handler();
}
