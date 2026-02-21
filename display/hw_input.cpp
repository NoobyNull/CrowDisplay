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
// PCF8575 I2C GPIO Expander on GPIOD bus (Wire: SDA=IO19, SCL=IO20)
// Shared I2C bus with GT911 touch — must hold i2c mutex for all access
// ============================================================

// GPIOD connector also exposes IO38 as a digital GPIO (e.g. PCF8575 INT)
#define GPIOD_PIN    38

// PCF8575 pin assignments (active LOW) — TBD, using debug output to discover
// Press each button and check serial for "[D] 0x.... P?=0" lines
#define PIN_BTN1     (1 << 0)   // P0 - placeholder
#define PIN_BTN2     (1 << 1)   // P1 - placeholder
#define PIN_BTN3     (1 << 2)   // P2 - placeholder
#define PIN_BTN4     (1 << 3)   // P3 - placeholder
#define PIN_BTN5     (1 << 4)   // P4 - placeholder
#define PIN_BTN6     (1 << 5)   // P5 - placeholder
// No encoder in current hardware

// Debounce timing
#define BUTTON_DEBOUNCE_MS  50
#define REBOOT_HOLD_MS      5000 // Hold all buttons for 5s to force reboot
#define NUM_BUTTONS         6    // 6 hardware buttons

// ============================================================
// State
// ============================================================
static bool pcf_available = false;
static uint8_t pcf_addr = 0;

// Button debounce state
static uint16_t prev_pin_state = 0xFFFF;  // All high = nothing pressed
static uint32_t btn_debounce_time[NUM_BUTTONS] = {0};
static bool btn_prev_pressed[NUM_BUTTONS] = {false};

// All-buttons-held reboot detection
static uint32_t all_btn_hold_start = 0;
static bool all_btn_held = false;

// App-select focus
static int focused_widget_idx = -1;
static lv_obj_t *focus_highlight_obj = nullptr;
static lv_opa_t focus_prev_opa = LV_OPA_TRANSP;  // Restore original opacity on clear

// ============================================================
// I2C helpers (all PCF8575 access must hold i2c mutex)
// ============================================================

static uint32_t pcf_read_ok = 0, pcf_read_fail = 0;
static uint32_t pcf_consec_fail = 0;       // Consecutive failures (for bus recovery)
static const uint32_t BUS_RECOVERY_THRESHOLD = 20;  // Trigger recovery after 20 consecutive fails

static uint16_t pcf8575_read() {
    // Must be called with i2c mutex held
    uint8_t n = Wire.requestFrom(pcf_addr, (uint8_t)2);
    if (Wire.available() < 2) {
        pcf_read_fail++;
        pcf_consec_fail++;

        // I2C bus recovery: reinitialize after sustained failures
        // ESP_ERR_INVALID_STATE leaves the peripheral stuck; Wire.begin() resets it
        if (pcf_consec_fail == BUS_RECOVERY_THRESHOLD) {
            Serial.println("[hw_input] I2C bus stuck, attempting recovery...");
            Wire.end();
            delay(1);
            Wire.begin(19, 20);
            Serial.println("[hw_input] I2C bus reinitialized");
        }

        return 0xFFFF;  // read failed, return all-high (masks the failure)
    }
    uint8_t lo = Wire.read();
    uint8_t hi = Wire.read();
    pcf_read_ok++;
    pcf_consec_fail = 0;  // Reset consecutive fail counter on success
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

    // I2C bus scan for debugging (shared bus: SDA=19, SCL=20)
    Serial.print("[hw_input] I2C scan:");
    for (uint8_t addr = 0x08; addr < 0x78; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            Serial.printf(" 0x%02X", addr);
        }
    }
    Serial.println();

    // Scan for PCF8575 (0x20-0x27)
    for (uint8_t addr = 0x20; addr <= 0x27; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            pcf_addr = addr;
            pcf_available = true;
            Serial.printf("[hw_input] PCF8575 found at 0x%02X\n", addr);
            break;
        }
    }

    i2c_give();

    if (!pcf_available) {
        Serial.println("[hw_input] PCF8575 not found (hardware buttons disabled)");
        return false;
    }

    // Write 0xFFFF to set all pins as inputs (quasi-bidirectional: write 1 = input)
    if (i2c_take(10)) {
        Wire.beginTransmission(pcf_addr);
        Wire.write(0xFF);  // low byte: all inputs
        Wire.write(0xFF);  // high byte: all inputs
        Wire.endTransmission();

        uint16_t pins = pcf8575_read();
        Serial.printf("[hw_input] Initial pin state: 0x%04X\n", pins);
        i2c_give();

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
            const HwButtonConfig &hbc = get_global_config().hw_buttons[hw_btn_idx < NUM_BUTTONS ? hw_btn_idx : 0];
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
        case ACTION_FOCUS_NEXT:
            hw_input_focus_next();
            break;
        case ACTION_FOCUS_PREV:
            hw_input_focus_prev();
            break;
        case ACTION_FOCUS_ACTIVATE:
            hw_input_activate_focus();
            break;
    }
}

// ============================================================
// hw_input_poll()
// ============================================================
void hw_input_poll() {
    static uint32_t poll_heartbeat = 0;
    if (millis() - poll_heartbeat >= 3000) {
        poll_heartbeat = millis();
        Serial.printf("[hw_input] poll: pcf=%d\n", pcf_available);
    }
    if (!pcf_available) return;

    if (!i2c_take(20)) return;  // Wait up to 20ms for I2C mutex
    uint16_t pins = pcf8575_read();
    i2c_give();

    // Filter glitched reads: all-zero is physically impossible (all active-low
    // buttons + encoder pressed simultaneously). Discard and keep previous state.
    if (pins == 0x0000) return;

    // Debug: log ALL pin changes with bit-level diff
    static uint32_t dbg_timer = 0;
    if (pins != prev_pin_state) {
        uint16_t diff = pins ^ prev_pin_state;
        Serial.printf("[D] 0x%04X d=0x%04X", pins, diff);
        for (int b = 0; b < 16; b++) {
            if (diff & (1 << b)) Serial.printf(" P%d=%d", b, (pins >> b) & 1);
        }
        Serial.println();
    } else if (millis() - dbg_timer >= 3000) {
        dbg_timer = millis();
        Serial.printf("[D] idle 0x%04X ok=%lu fail=%lu\n", pins, pcf_read_ok, pcf_read_fail);
    }

    // --- All-buttons held reboot check (first 4) ---
    bool all_four = !(pins & PIN_BTN1) && !(pins & PIN_BTN2) &&
                    !(pins & PIN_BTN3) && !(pins & PIN_BTN4);
    if (all_four) {
        if (!all_btn_held) {
            all_btn_held = true;
            all_btn_hold_start = millis();
            Serial.println("[hw_input] All 4 buttons held — hold 5s to reboot");
        } else if (millis() - all_btn_hold_start >= REBOOT_HOLD_MS) {
            Serial.println("[hw_input] REBOOT triggered by 4-button hold");
            delay(100);
            ESP.restart();
        }
    } else {
        all_btn_held = false;
    }

    if (pins == 0xFFFF && prev_pin_state == 0xFFFF) return; // No change, all high

    uint32_t now = millis();
    const AppConfig &cfg = get_global_config();

    // --- Debounce and dispatch 6 hardware buttons ---
    static const uint16_t btn_masks[NUM_BUTTONS] = {PIN_BTN1, PIN_BTN2, PIN_BTN3, PIN_BTN4, PIN_BTN5, PIN_BTN6};
    for (int i = 0; i < NUM_BUTTONS; i++) {
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

    // TODO: encoder support removed (no encoder in current hardware)
    // Re-add encoder switch + rotation handling if encoder is reconnected

    prev_pin_state = pins;
}

// ============================================================
// App-select focus management
// ============================================================
static void apply_focus_style(lv_obj_t *obj) {
    // Use outline (renders outside object bounds, always visible even if border is clipped)
    lv_obj_set_style_outline_color(obj, lv_color_hex(0x00FF00), LV_PART_MAIN);
    lv_obj_set_style_outline_width(obj, 4, LV_PART_MAIN);
    lv_obj_set_style_outline_opa(obj, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_outline_pad(obj, 3, LV_PART_MAIN);
}

void hw_input_focus_next() {
    int page = ui_get_current_page();
    const AppConfig &cfg = get_global_config();
    const ProfileConfig *profile = cfg.get_active_profile();
    if (!profile || page >= (int)profile->pages.size()) {
        Serial.printf("[focus] no profile or page %d out of range\n", page);
        return;
    }

    const auto &widgets = profile->pages[page].widgets;
    int widget_count = (int)widgets.size();
    if (widget_count <= 0) { Serial.println("[focus] no widgets"); return; }

    // Save current position BEFORE clearing (clear_focus resets focused_widget_idx to -1)
    int start = focused_widget_idx;
    hw_input_clear_focus();
    for (int i = 0; i < widget_count; i++) {
        int idx = (start + 1 + i) % widget_count;
        if (widgets[idx].widget_type == WIDGET_HOTKEY_BUTTON) {
            focused_widget_idx = idx;
            lv_obj_t *obj = ui_get_widget_obj(page, idx);
            if (obj) {
                focus_prev_opa = lv_obj_get_style_bg_opa(obj, LV_PART_MAIN);
                apply_focus_style(obj);
                focus_highlight_obj = obj;
                Serial.printf("[focus] -> widget %d on page %d\n", idx, page);
            } else {
                Serial.printf("[focus] widget %d obj is NULL\n", idx);
            }
            return;
        }
    }
    Serial.println("[focus] no hotkey button found");
}

void hw_input_focus_prev() {
    int page = ui_get_current_page();
    const AppConfig &cfg = get_global_config();
    const ProfileConfig *profile = cfg.get_active_profile();
    if (!profile || page >= (int)profile->pages.size()) return;

    const auto &widgets = profile->pages[page].widgets;
    int widget_count = (int)widgets.size();
    if (widget_count <= 0) return;

    // Save current position BEFORE clearing (clear_focus resets focused_widget_idx to -1)
    int start = focused_widget_idx <= 0 ? widget_count : focused_widget_idx;
    hw_input_clear_focus();
    for (int i = 0; i < widget_count; i++) {
        int idx = (start - 1 - i + widget_count) % widget_count;
        if (widgets[idx].widget_type == WIDGET_HOTKEY_BUTTON) {
            focused_widget_idx = idx;
            lv_obj_t *obj = ui_get_widget_obj(page, idx);
            if (obj) {
                focus_prev_opa = lv_obj_get_style_bg_opa(obj, LV_PART_MAIN);
                apply_focus_style(obj);
                focus_highlight_obj = obj;
                Serial.printf("[focus] <- widget %d on page %d\n", idx, page);
            }
            return;
        }
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
        lv_obj_set_style_bg_opa(focus_highlight_obj, focus_prev_opa, LV_PART_MAIN);
        lv_obj_set_style_outline_width(focus_highlight_obj, 0, LV_PART_MAIN);
        focus_highlight_obj = nullptr;
        focus_prev_opa = LV_OPA_TRANSP;
    }
    focused_widget_idx = -1;
}
