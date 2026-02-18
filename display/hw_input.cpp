#include "hw_input.h"
#include <Arduino.h>
#include <Wire.h>
#include "touch.h"     // i2c_take/i2c_give
#include "config.h"
#include "protocol.h"
#include "ui.h"
#include "power.h"
#include "espnow_link.h"
#include "config_server.h"

// ============================================================
// TCA9548A I2C Mux + PCF8575 Addresses
// ============================================================
#define TCA9548A_ADDR   0x77
#define PCF8575_MUX_CH  0      // Channel 0 on mux

// PCF8575 pin assignments (active LOW)
#define PIN_ENC_SW   (1 << 0)   // P0 - Encoder push button
#define PIN_BTN1     (1 << 1)   // P1 - Hardware button 1
#define PIN_BTN2     (1 << 2)   // P2 - Hardware button 2
#define PIN_BTN3     (1 << 3)   // P3 - Hardware button 3
#define PIN_BTN4     (1 << 4)   // P4 - Hardware button 4
#define PIN_ENC_DT   (1 << 10)  // P10 - Encoder DT (data)
#define PIN_ENC_CLK  (1 << 11)  // P11 - Encoder CLK (clock)

// Debounce timing
#define BUTTON_DEBOUNCE_MS  50
#define ENCODER_ROT_MIN_MS  80  // Minimum interval between rotation events

// ============================================================
// State
// ============================================================
static bool pcf_available = false;
static uint8_t pcf_addr = 0;

// Button debounce state
static uint16_t prev_pin_state = 0xFFFF;  // All high = nothing pressed
static uint32_t btn_debounce_time[5] = {0}; // 4 buttons + encoder switch
static bool btn_prev_pressed[5] = {false};

// Encoder quadrature state
static uint8_t enc_prev_state = 0;
static uint32_t enc_last_rotation_ms = 0;

// App-select focus
static int focused_widget_idx = -1;
static lv_obj_t *focus_highlight_obj = nullptr;

// ============================================================
// I2C helpers (all PCF8575 access must hold i2c mutex)
// ============================================================

static bool tca_select_channel(uint8_t ch) {
    Wire.beginTransmission(TCA9548A_ADDR);
    Wire.write(1 << ch);
    return Wire.endTransmission() == 0;
}

static void tca_deselect() {
    Wire.beginTransmission(TCA9548A_ADDR);
    Wire.write(0);
    Wire.endTransmission();
}

static uint16_t pcf8575_read() {
    // Must be called with i2c mutex held and mux channel selected
    Wire.requestFrom(pcf_addr, (uint8_t)2);
    if (Wire.available() < 2) return 0xFFFF;
    uint8_t lo = Wire.read();
    uint8_t hi = Wire.read();
    return (hi << 8) | lo;
}

// ============================================================
// hw_input_init()
// ============================================================
bool hw_input_init() {
    if (!i2c_take(50)) {
        Serial.println("[hw_input] I2C mutex timeout at init");
        return false;
    }

    // I2C bus scan for debugging
    Serial.print("[hw_input] I2C scan:");
    for (uint8_t addr = 0x08; addr < 0x78; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            Serial.printf(" 0x%02X", addr);
        }
    }
    Serial.println();

    // Select mux channel
    if (!tca_select_channel(PCF8575_MUX_CH)) {
        Serial.println("[hw_input] TCA9548A not found at 0x70");
        tca_deselect();
        i2c_give();
        return false;
    }

    // Scan for PCF8575 at 0x20-0x27
    for (uint8_t addr = 0x20; addr <= 0x27; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            pcf_addr = addr;
            pcf_available = true;
            Serial.printf("[hw_input] PCF8575 found at 0x%02X on mux channel %d\n", addr, PCF8575_MUX_CH);
            break;
        }
    }

    tca_deselect();
    i2c_give();

    if (!pcf_available) {
        Serial.println("[hw_input] PCF8575 not found (hardware buttons disabled)");
        return false;
    }

    // Initialize encoder quadrature state
    if (i2c_take(10)) {
        tca_select_channel(PCF8575_MUX_CH);
        uint16_t pins = pcf8575_read();
        tca_deselect();
        i2c_give();

        uint8_t clk = (pins & PIN_ENC_CLK) ? 1 : 0;
        uint8_t dt  = (pins & PIN_ENC_DT)  ? 1 : 0;
        enc_prev_state = (clk << 1) | dt;
        prev_pin_state = pins;
    }

    return true;
}

bool hw_input_available() {
    return pcf_available;
}

// ============================================================
// Action dispatch (shared by buttons and encoder push)
// ============================================================
static void dispatch_action(ActionType action, uint8_t keycode, uint16_t consumer_code,
                            uint8_t modifiers, uint8_t hw_btn_idx) {
    power_activity();

    switch (action) {
        case ACTION_HOTKEY:
            send_hotkey_to_bridge(modifiers, keycode);
            break;
        case ACTION_MEDIA_KEY:
            send_media_key_to_bridge(consumer_code);
            break;
        case ACTION_LAUNCH_APP:
        case ACTION_SHELL_CMD:
        case ACTION_OPEN_URL:
            // Send as button press for companion to handle
            // Use page 0xFF and hw_btn_idx as widget to signal hardware button
            send_button_press_to_bridge(0xFF, hw_btn_idx);
            break;
        case ACTION_DISPLAY_SETTINGS:
        case ACTION_CONFIG_MODE:
            if (!config_server_active()) {
                config_server_start();
                show_config_screen();
            } else {
                config_server_stop();
                hide_config_screen();
            }
            break;
        case ACTION_DISPLAY_CLOCK:
            display_set_mode(MODE_CLOCK);
            break;
        case ACTION_DISPLAY_PICTURE:
            display_set_mode(MODE_PICTURE_FRAME);
            break;
        case ACTION_PAGE_NEXT:
            ui_next_page();
            break;
        case ACTION_PAGE_PREV:
            ui_prev_page();
            break;
        case ACTION_PAGE_GOTO:
            ui_goto_page(keycode);
            break;
        case ACTION_MODE_CYCLE:
            mode_cycle_next(get_global_config().mode_cycle.enabled_modes);
            break;
        case ACTION_BRIGHTNESS:
            power_cycle_brightness();
            break;
        case ACTION_DDC: {
            const HwButtonConfig &hbc = get_global_config().hw_buttons[hw_btn_idx < 4 ? hw_btn_idx : 0];
            DdcCmdMsg ddc;
            ddc.vcp_code = hbc.ddc_vcp_code;
            ddc.value = hbc.ddc_value;
            ddc.adjustment = hbc.ddc_adjustment;
            ddc.display_num = hbc.ddc_display;
            espnow_send(MSG_DDC_CMD, (const uint8_t *)&ddc, sizeof(ddc));
            Serial.printf("[hw_input] DDC cmd: vcp=0x%02X val=%d adj=%d disp=%d\n",
                          ddc.vcp_code, ddc.value, ddc.adjustment, ddc.display_num);
            break;
        }
    }
}

// ============================================================
// Encoder rotation dispatch
// ============================================================
static void dispatch_encoder_rotation(int8_t direction) {
    power_activity();
    const AppConfig &cfg = get_global_config();
    uint8_t mode = cfg.encoder.encoder_mode;

    switch (mode) {
        case 0: // page_nav
            if (direction > 0) ui_next_page();
            else ui_prev_page();
            break;
        case 1: // volume
            if (direction > 0) send_media_key_to_bridge(0x00E9); // Vol+
            else send_media_key_to_bridge(0x00EA);               // Vol-
            break;
        case 2: // brightness
            power_cycle_brightness();
            break;
        case 3: // app_select
            if (direction > 0) hw_input_focus_next();
            else hw_input_focus_prev();
            break;
        case 4: // mode_cycle
            if (direction > 0)
                mode_cycle_next(cfg.mode_cycle.enabled_modes);
            else
                mode_cycle_next(cfg.mode_cycle.enabled_modes); // same direction, just cycle
            break;
        case 5: { // ddc_control
            DdcCmdMsg ddc;
            ddc.vcp_code = cfg.encoder.ddc_vcp_code;
            ddc.value = 0;
            ddc.adjustment = (direction > 0) ? (int16_t)cfg.encoder.ddc_step : -(int16_t)cfg.encoder.ddc_step;
            ddc.display_num = cfg.encoder.ddc_display;
            espnow_send(MSG_DDC_CMD, (const uint8_t *)&ddc, sizeof(ddc));
            Serial.printf("[hw_input] Encoder DDC: vcp=0x%02X adj=%d\n", ddc.vcp_code, ddc.adjustment);
            break;
        }
    }
}

// ============================================================
// Quadrature decoder
// ============================================================
// Gray code transition table: returns +1 (CW), -1 (CCW), 0 (invalid/no change)
static const int8_t QUAD_TABLE[16] = {
    0, -1,  1,  0,
    1,  0,  0, -1,
   -1,  0,  0,  1,
    0,  1, -1,  0
};

static int8_t decode_encoder(uint16_t pins) {
    uint8_t clk = (pins & PIN_ENC_CLK) ? 1 : 0;
    uint8_t dt  = (pins & PIN_ENC_DT)  ? 1 : 0;
    uint8_t new_state = (clk << 1) | dt;

    if (new_state == enc_prev_state) return 0;

    uint8_t idx = (enc_prev_state << 2) | new_state;
    enc_prev_state = new_state;

    int8_t dir = QUAD_TABLE[idx];

    // Enforce minimum interval between rotation events
    if (dir != 0) {
        uint32_t now = millis();
        if (now - enc_last_rotation_ms < ENCODER_ROT_MIN_MS) {
            return 0; // Too fast, ignore
        }
        enc_last_rotation_ms = now;
    }

    return dir;
}

// ============================================================
// hw_input_poll()
// ============================================================
void hw_input_poll() {
    if (!pcf_available) return;

    if (!i2c_take(5)) return;  // Don't block if touch is using I2C

    tca_select_channel(PCF8575_MUX_CH);
    uint16_t pins = pcf8575_read();
    tca_deselect();
    i2c_give();

    // Debug: log raw pin state every 2 seconds
    static uint32_t dbg_timer = 0;
    if (millis() - dbg_timer >= 2000) {
        dbg_timer = millis();
        Serial.printf("[hw_input] raw pins=0x%04X\n", pins);
    }

    if (pins == 0xFFFF && prev_pin_state == 0xFFFF) return; // No change, all high

    uint32_t now = millis();
    const AppConfig &cfg = get_global_config();

    // --- Debounce and dispatch 4 hardware buttons ---
    static const uint16_t btn_masks[4] = {PIN_BTN1, PIN_BTN2, PIN_BTN3, PIN_BTN4};
    for (int i = 0; i < 4; i++) {
        bool pressed = !(pins & btn_masks[i]); // Active LOW
        if (pressed != btn_prev_pressed[i]) {
            if (now - btn_debounce_time[i] >= BUTTON_DEBOUNCE_MS) {
                btn_debounce_time[i] = now;
                btn_prev_pressed[i] = pressed;
                if (pressed) {
                    // Press edge - dispatch action
                    const HwButtonConfig &bc = cfg.hw_buttons[i];
                    Serial.printf("[hw_input] Button %d pressed (action=%d)\n", i + 1, bc.action_type);
                    dispatch_action(bc.action_type, bc.keycode, bc.consumer_code,
                                    bc.modifiers, i);
                }
            }
        }
    }

    // --- Debounce encoder switch ---
    {
        bool pressed = !(pins & PIN_ENC_SW);
        if (pressed != btn_prev_pressed[4]) {
            if (now - btn_debounce_time[4] >= BUTTON_DEBOUNCE_MS) {
                btn_debounce_time[4] = now;
                btn_prev_pressed[4] = pressed;
                if (pressed) {
                    // In app-select mode, push fires focused widget
                    if (cfg.encoder.encoder_mode == 3 && focused_widget_idx >= 0) {
                        hw_input_activate_focus();
                    } else {
                        // Normal push action
                        Serial.printf("[hw_input] Encoder push (action=%d)\n", cfg.encoder.push_action);
                        dispatch_action(cfg.encoder.push_action, cfg.encoder.push_keycode,
                                        cfg.encoder.push_consumer_code, cfg.encoder.push_modifiers, 0xFF);
                    }
                }
            }
        }
    }

    // --- Quadrature encoder rotation ---
    int8_t rot = decode_encoder(pins);
    if (rot != 0) {
        Serial.printf("[hw_input] Encoder rotation: %s\n", rot > 0 ? "CW" : "CCW");
        dispatch_encoder_rotation(rot);
    }

    prev_pin_state = pins;
}

// ============================================================
// App-select focus management
// ============================================================
void hw_input_focus_next() {
    int page = ui_get_current_page();
    int count = ui_get_page_count();
    if (count <= 0) return;

    // Get widget count for current page from config
    const AppConfig &cfg = get_global_config();
    const ProfileConfig *profile = cfg.get_active_profile();
    if (!profile || page >= (int)profile->pages.size()) return;

    int widget_count = (int)profile->pages[page].widgets.size();
    if (widget_count <= 0) return;

    // Clear previous highlight
    hw_input_clear_focus();

    // Advance focus
    focused_widget_idx = (focused_widget_idx + 1) % widget_count;

    // Apply visual highlight (gold border)
    lv_obj_t *obj = ui_get_widget_obj(page, focused_widget_idx);
    if (obj) {
        lv_obj_set_style_border_color(obj, lv_color_hex(0xFFD700), LV_PART_MAIN);
        lv_obj_set_style_border_width(obj, 3, LV_PART_MAIN);
        focus_highlight_obj = obj;
    }
}

void hw_input_focus_prev() {
    int page = ui_get_current_page();
    const AppConfig &cfg = get_global_config();
    const ProfileConfig *profile = cfg.get_active_profile();
    if (!profile || page >= (int)profile->pages.size()) return;

    int widget_count = (int)profile->pages[page].widgets.size();
    if (widget_count <= 0) return;

    hw_input_clear_focus();

    focused_widget_idx = focused_widget_idx <= 0 ? widget_count - 1 : focused_widget_idx - 1;

    lv_obj_t *obj = ui_get_widget_obj(page, focused_widget_idx);
    if (obj) {
        lv_obj_set_style_border_color(obj, lv_color_hex(0xFFD700), LV_PART_MAIN);
        lv_obj_set_style_border_width(obj, 3, LV_PART_MAIN);
        focus_highlight_obj = obj;
    }
}

void hw_input_activate_focus() {
    if (focused_widget_idx < 0) return;

    int page = ui_get_current_page();
    const AppConfig &cfg = get_global_config();
    const ProfileConfig *profile = cfg.get_active_profile();
    if (!profile || page >= (int)profile->pages.size()) return;

    const std::vector<WidgetConfig> &widgets = profile->pages[page].widgets;
    if (focused_widget_idx >= (int)widgets.size()) return;

    const WidgetConfig &w = widgets[focused_widget_idx];
    if (w.widget_type == WIDGET_HOTKEY_BUTTON) {
        Serial.printf("[hw_input] Activating focused widget %d (action=%d)\n",
                      focused_widget_idx, w.action_type);
        dispatch_action(w.action_type, w.keycode, w.consumer_code, w.modifiers, focused_widget_idx);
    }
}

void hw_input_clear_focus() {
    if (focus_highlight_obj) {
        lv_obj_set_style_border_width(focus_highlight_obj, 0, LV_PART_MAIN);
        focus_highlight_obj = nullptr;
    }
    focused_widget_idx = -1;
}
