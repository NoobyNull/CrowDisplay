#include <lvgl.h>
#include <Arduino.h>
#include <ctime>
#include <cmath>
#include <vector>
#include <SD.h>
#include "protocol.h"
#include "config.h"
#include "display_hw.h"
#include "espnow_link.h"
#include "power.h"
#include "config_server.h"
#include "ui.h"
#include <WiFi.h>

// ============================================================
//  Color Palette
// ============================================================
#define CLR_RED     0xE74C3C
#define CLR_BLUE    0x3498DB
#define CLR_GREEN   0x2ECC71
#define CLR_ORANGE  0xE67E22
#define CLR_PURPLE  0x9B59B6
#define CLR_TEAL    0x1ABC9C
#define CLR_PINK    0xE91E63
#define CLR_YELLOW  0xF1C40F
#define CLR_GREY    0x7F8C8D
#define CLR_DARK    0x2C3E50
#define CLR_CYAN    0x00BCD4
#define CLR_INDIGO  0x3F51B5
#define CLR_LIME    0x8BC34A
#define CLR_AMBER   0xFFC107

// ============================================================
//  UI State
// ============================================================
static const AppConfig *g_active_config = nullptr;

// Page management (replaces tabview)
static std::vector<lv_obj_t *> page_containers;
static std::vector<std::vector<lv_obj_t *>> page_widget_objs;  // [page][widget] -> LVGL obj
static int current_page = 0;

// Main screen
static lv_obj_t *main_screen = nullptr;

// Clock mode screen
static lv_obj_t *clock_screen = nullptr;
static lv_obj_t *clock_time_label = nullptr;
static lv_obj_t *clock_rssi_label = nullptr;

// Config mode screen
static lv_obj_t *config_screen = nullptr;
static lv_obj_t *config_info_label = nullptr;

// Clock screen stats labels
static lv_obj_t *clock_stats_label = nullptr;

// Analog clock widgets
static lv_obj_t *analog_clock_face = nullptr;
static lv_obj_t *analog_hour_hand = nullptr;
static lv_obj_t *analog_min_hand = nullptr;
static lv_point_t hour_points[2];
static lv_point_t min_points[2];

// Picture frame mode state
static lv_obj_t *picture_frame_screen = nullptr;
static lv_obj_t *slideshow_img = nullptr;
static lv_obj_t *slideshow_fallback_label = nullptr;
static std::vector<String> slideshow_files;
static size_t slideshow_index = 0;
static lv_timer_t *slideshow_timer = nullptr;

// Standby mode state
static lv_obj_t *standby_screen = nullptr;
static lv_obj_t *standby_time_label = nullptr;
static lv_obj_t *standby_stats_label = nullptr;

// LVGL SD card filesystem driver state
static bool sd_fs_registered = false;

// Stat monitor tracking: widget pointer + stat type for live updates
struct StatWidgetRef {
    lv_obj_t *label;         // Value label (or combined label when inline)
    lv_obj_t *name_label;    // Separate name label (when value_position != 0), or nullptr
    uint8_t stat_type;
    uint8_t value_position;  // 0=inline, 1=value top, 2=value bottom
};
static std::vector<StatWidgetRef> stat_widget_refs;

// Status bar widget references for live updates
struct StatusBarRef {
    lv_obj_t *rssi_label;
    lv_obj_t *pc_label;
    lv_obj_t *time_label;
};
static std::vector<StatusBarRef> status_bar_refs;

// Page nav widget references
static std::vector<lv_obj_t *> page_nav_refs;

// Clock widget labels on pages (for periodic time updates)
static std::vector<lv_obj_t *> clock_widget_labels;

// Analog clock widgets on pages (for periodic hand updates)
struct AnalogClockRef {
    lv_obj_t *face;       // Arc object for the clock face
    lv_obj_t *hour_hand;  // Line object for hour hand
    lv_obj_t *min_hand;   // Line object for minute hand
};
static std::vector<AnalogClockRef> analog_clock_widgets;

// Forward declarations
void update_clock_time();
void show_config_screen();
void hide_config_screen();
static void init_picture_frame_mode();
static void cleanup_picture_frame_mode();
static void init_standby_mode();
static void load_next_slideshow_image();
static void slideshow_timer_cb(lv_timer_t *timer);
static void lvgl_register_sd_driver();
static void update_page_nav_indicators();

// ============================================================
//  Stat helpers
// ============================================================
static const char *get_stat_name(uint8_t type) {
    switch (type) {
        case STAT_CPU_PERCENT:    return "CPU";
        case STAT_RAM_PERCENT:    return "RAM";
        case STAT_GPU_PERCENT:    return "GPU";
        case STAT_CPU_TEMP:       return "CPU";
        case STAT_GPU_TEMP:       return "GPU";
        case STAT_DISK_PERCENT:   return "Disk";
        case STAT_NET_UP:         return LV_SYMBOL_UPLOAD;
        case STAT_NET_DOWN:       return LV_SYMBOL_DOWNLOAD;
        case STAT_CPU_FREQ:       return "CPU";
        case STAT_GPU_FREQ:       return "GPU";
        case STAT_SWAP_PERCENT:   return "Swap";
        case STAT_UPTIME_HOURS:   return "Up";
        case STAT_BATTERY_PCT:    return "Bat";
        case STAT_FAN_RPM:        return "Fan";
        case STAT_LOAD_AVG:       return "Load";
        case STAT_PROC_COUNT:     return "Proc";
        case STAT_GPU_MEM_PCT:    return "VRAM";
        case STAT_GPU_POWER_W:    return "GPU";
        case STAT_DISK_READ_KBS:  return LV_SYMBOL_DOWNLOAD " R";
        case STAT_DISK_WRITE_KBS: return LV_SYMBOL_UPLOAD " W";
        case STAT_DISPLAY_UPTIME: return "Disp";
        case STAT_PROC_USER:      return "User";
        case STAT_PROC_SYSTEM:    return "Sys";
        default:                  return "?";
    }
}

static void format_stat_value(lv_obj_t *lbl, uint8_t type, uint16_t value) {
    const char *name = get_stat_name(type);
    switch (type) {
        case STAT_CPU_PERCENT: case STAT_RAM_PERCENT: case STAT_GPU_PERCENT:
        case STAT_DISK_PERCENT: case STAT_SWAP_PERCENT: case STAT_BATTERY_PCT:
        case STAT_GPU_MEM_PCT:
            if ((value & 0xFF) == 0xFF) lv_label_set_text_fmt(lbl, "%s N/A", name);
            else lv_label_set_text_fmt(lbl, "%s %d%%", name, value & 0xFF);
            break;
        case STAT_CPU_TEMP: case STAT_GPU_TEMP:
            if ((value & 0xFF) == 0xFF) lv_label_set_text_fmt(lbl, "%s N/A", name);
            else lv_label_set_text_fmt(lbl, "%s %d\xC2\xB0""C", name, value & 0xFF);
            break;
        case STAT_NET_UP: case STAT_NET_DOWN:
            if (value >= 1024) lv_label_set_text_fmt(lbl, "%s %.1f MB/s", name, value / 1024.0f);
            else lv_label_set_text_fmt(lbl, "%s %d KB/s", name, value);
            break;
        case STAT_CPU_FREQ: case STAT_GPU_FREQ:
            lv_label_set_text_fmt(lbl, "%s %d MHz", name, value); break;
        case STAT_UPTIME_HOURS: case STAT_DISPLAY_UPTIME:
            lv_label_set_text_fmt(lbl, "%s %dh", name, value); break;
        case STAT_FAN_RPM: case STAT_PROC_COUNT:
        case STAT_PROC_USER: case STAT_PROC_SYSTEM:
            lv_label_set_text_fmt(lbl, "%s %d", name, value); break;
        case STAT_LOAD_AVG:
            lv_label_set_text_fmt(lbl, "%s %.2f", name, value / 100.0f); break;
        case STAT_GPU_POWER_W:
            lv_label_set_text_fmt(lbl, "%s %dW", name, value); break;
        case STAT_DISK_READ_KBS: case STAT_DISK_WRITE_KBS:
            if (value >= 1024) lv_label_set_text_fmt(lbl, "%s %.1f MB/s", name, value / 1024.0f);
            else lv_label_set_text_fmt(lbl, "%s %d KB/s", name, value);
            break;
        default:
            lv_label_set_text_fmt(lbl, "? %d", value); break;
    }
}

static const char *get_stat_placeholder(uint8_t type) {
    switch (type) {
        case STAT_CPU_PERCENT:    return "CPU --%";
        case STAT_RAM_PERCENT:    return "RAM --%";
        case STAT_GPU_PERCENT:    return "GPU --%";
        case STAT_CPU_TEMP:       return "CPU --\xC2\xB0""C";
        case STAT_GPU_TEMP:       return "GPU --\xC2\xB0""C";
        case STAT_DISK_PERCENT:   return "Disk --%";
        case STAT_NET_UP:         return LV_SYMBOL_UPLOAD " -- KB/s";
        case STAT_NET_DOWN:       return LV_SYMBOL_DOWNLOAD " -- KB/s";
        case STAT_CPU_FREQ:       return "CPU -- MHz";
        case STAT_GPU_FREQ:       return "GPU -- MHz";
        case STAT_SWAP_PERCENT:   return "Swap --%";
        case STAT_UPTIME_HOURS:   return "Up --h";
        case STAT_BATTERY_PCT:    return "Bat --%";
        case STAT_FAN_RPM:        return "Fan --";
        case STAT_LOAD_AVG:       return "Load --";
        case STAT_PROC_COUNT:     return "Proc --";
        case STAT_GPU_MEM_PCT:    return "VRAM --%";
        case STAT_GPU_POWER_W:    return "GPU --W";
        case STAT_DISK_READ_KBS:  return LV_SYMBOL_DOWNLOAD " R -- KB/s";
        case STAT_DISK_WRITE_KBS: return LV_SYMBOL_UPLOAD " W -- KB/s";
        case STAT_DISPLAY_UPTIME: return "Disp --h";
        case STAT_PROC_USER:      return "User --";
        case STAT_PROC_SYSTEM:    return "Sys --";
        default:                  return "---";
    }
}

// ============================================================
//  Widget Renderers — one per widget type
// ============================================================

// --- Button Event Data (identity-based: page + widget index + action data) ---
struct ButtonEventData {
    uint8_t page_idx;
    uint8_t widget_idx;
    uint8_t action_type;
    uint8_t keycode;       // For PAGE_GOTO target page, or HOTKEY keycode
    uint8_t modifiers;     // For ACTION_HOTKEY modifier mask
    uint16_t consumer_code; // For ACTION_MEDIA_KEY consumer control code
    uint8_t ddc_vcp_code;  // For ACTION_DDC
    uint16_t ddc_value;
    int16_t ddc_adjustment;
    uint8_t ddc_display;
};
static ButtonEventData btn_event_data[CONFIG_MAX_WIDGETS * CONFIG_MAX_PAGES];
static int btn_event_count = 0;

// --- Hotkey Button ---
static void btn_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        const ButtonEventData *bed = (const ButtonEventData *)lv_event_get_user_data(e);
        if (!bed) return;

        // Display-local actions are handled here without sending to bridge
        switch (bed->action_type) {
            case ACTION_DISPLAY_SETTINGS:
                Serial.println("Button: toggle config AP mode");
                if (!config_server_active()) {
                    if (config_server_start()) show_config_screen();
                } else {
                    config_server_stop();
                    hide_config_screen();
                }
                return;
            case ACTION_DISPLAY_CLOCK:
                Serial.println("Button: switch to clock mode");
                display_set_mode(MODE_CLOCK);
                return;
            case ACTION_DISPLAY_PICTURE:
                Serial.println("Button: switch to picture frame mode");
                display_set_mode(MODE_PICTURE_FRAME);
                return;
            case ACTION_PAGE_NEXT:
                Serial.println("Button: next page");
                ui_next_page();
                return;
            case ACTION_PAGE_PREV:
                Serial.println("Button: prev page");
                ui_prev_page();
                return;
            case ACTION_PAGE_GOTO:
                Serial.printf("Button: goto page %d\n", bed->keycode);
                ui_goto_page(bed->keycode);
                return;
            case ACTION_MODE_CYCLE:
                Serial.println("Button: mode cycle");
                mode_cycle_next(get_global_config().mode_cycle.enabled_modes);
                return;
            case ACTION_BRIGHTNESS:
                Serial.println("Button: brightness cycle");
                power_cycle_brightness();
                return;
            case ACTION_CONFIG_MODE:
                Serial.println("Button: enter config mode");
                if (!config_server_active()) {
                    if (config_server_start()) show_config_screen();
                } else {
                    config_server_stop();
                    hide_config_screen();
                }
                return;
            default:
                break;
        }

        // Route based on action type:
        // - HID actions (hotkey, media key) go directly through bridge USB HID
        // - Companion actions (launch app, shell cmd, open URL) go via button identity
        switch (bed->action_type) {
            case ACTION_HOTKEY:
                send_hotkey_to_bridge(bed->modifiers, bed->keycode);
                Serial.printf("Hotkey: mod=0x%02X key=0x%02X\n", bed->modifiers, bed->keycode);
                break;
            case ACTION_MEDIA_KEY:
                send_media_key_to_bridge(bed->consumer_code);
                Serial.printf("Media key: 0x%04X\n", bed->consumer_code);
                break;
            case ACTION_DDC: {
                DdcCmdMsg ddc;
                ddc.vcp_code = bed->ddc_vcp_code;
                ddc.value = bed->ddc_value;
                ddc.adjustment = bed->ddc_adjustment;
                ddc.display_num = bed->ddc_display;
                espnow_send(MSG_DDC_CMD, (const uint8_t *)&ddc, sizeof(ddc));
                Serial.printf("DDC cmd: vcp=0x%02X val=%d adj=%d disp=%d\n",
                              ddc.vcp_code, ddc.value, ddc.adjustment, ddc.display_num);
                break;
            }
            default:
                // Companion-handled actions: send button identity for lookup
                send_button_press_to_bridge(bed->page_idx, bed->widget_idx);
                Serial.printf("Button press: page=%d widget=%d action=%d\n",
                              bed->page_idx, bed->widget_idx, bed->action_type);
                break;
        }
    }
}

static void render_hotkey_button(lv_obj_t *parent, const WidgetConfig *cfg, uint8_t page_idx, uint8_t widget_idx) {
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_set_pos(btn, cfg->x, cfg->y);
    lv_obj_set_size(btn, cfg->width, cfg->height);
    // Store button identity + action data in static pool for event callback
    ButtonEventData *bed = nullptr;
    if (btn_event_count < CONFIG_MAX_WIDGETS * CONFIG_MAX_PAGES) {
        btn_event_data[btn_event_count] = {
            page_idx, widget_idx, (uint8_t)cfg->action_type,
            cfg->keycode, cfg->modifiers, cfg->consumer_code,
            cfg->ddc_vcp_code, cfg->ddc_value, cfg->ddc_adjustment, cfg->ddc_display
        };
        bed = &btn_event_data[btn_event_count++];
    }
    lv_obj_add_event_cb(btn, btn_event_cb, LV_EVENT_CLICKED, (void *)bed);

    // Normal style: bg_color controls button fill (0 = transparent)
    if (cfg->bg_color) {
        lv_obj_set_style_bg_color(btn, lv_color_hex(cfg->bg_color), LV_PART_MAIN);
        lv_obj_set_style_bg_opa(btn, LV_OPA_COVER, LV_PART_MAIN);
        lv_obj_set_style_shadow_width(btn, 8, LV_PART_MAIN);
        lv_obj_set_style_shadow_ofs_y(btn, 4, LV_PART_MAIN);
        lv_obj_set_style_shadow_opa(btn, LV_OPA_30, LV_PART_MAIN);
    } else {
        lv_obj_set_style_bg_opa(btn, LV_OPA_TRANSP, LV_PART_MAIN);
        lv_obj_set_style_shadow_width(btn, 0, LV_PART_MAIN);
    }
    lv_obj_set_style_radius(btn, 12, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn, 0, LV_PART_MAIN);

    // Pressed style
    lv_color_t pressed_clr;
    if (cfg->pressed_color == 0x000000) {
        lv_color_t base = cfg->bg_color ? lv_color_hex(cfg->bg_color) : lv_color_hex(0x333333);
        pressed_clr = lv_color_darken(base, LV_OPA_30);
    } else {
        pressed_clr = lv_color_hex(cfg->pressed_color);
    }
    lv_obj_set_style_bg_color(btn, pressed_clr, LV_STATE_PRESSED);
    lv_obj_set_style_bg_opa(btn, LV_OPA_COVER, LV_STATE_PRESSED);
    lv_obj_set_style_transform_width(btn, -3, LV_STATE_PRESSED);
    lv_obj_set_style_transform_height(btn, -3, LV_STATE_PRESSED);

    // Column flex layout
    lv_obj_set_flex_flow(btn, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(btn, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_all(btn, 8, LV_PART_MAIN);

    // Determine if label/description will be shown (affects icon sizing)
    bool has_label = cfg->show_label && !cfg->label.empty();
    bool has_desc = cfg->show_description && !cfg->description.empty();
    bool icon_only = !has_label && !has_desc;

    // Icon: image from SD card takes priority over symbol
    bool icon_rendered = false;
    if (!cfg->icon_path.empty()) {
        std::string img_src = "S:" + cfg->icon_path;
        // Verify image file exists before creating widget
        if (SD.exists(cfg->icon_path.c_str())) {
            lv_obj_t *img = lv_img_create(btn);
            lv_img_set_src(img, img_src.c_str());
            // Display at 1:1 — companion already resized to exact pixel size
            icon_rendered = true;
        } else {
            Serial.printf("[ui] icon_path '%s' not found on SD, falling back to symbol\n", cfg->icon_path.c_str());
        }
    }
    if (!icon_rendered && !cfg->icon.empty()) {
        lv_obj_t *icon = lv_label_create(btn);
        lv_label_set_text(icon, cfg->icon.c_str());
        // Adaptive icon font size based on widget dimensions and whether text is shown
        lv_coord_t icon_area = icon_only ? (cfg->width < cfg->height ? cfg->width : cfg->height)
                                         : (cfg->height / 3);
        const lv_font_t *icon_font;
        if (icon_area >= 120)      icon_font = &lv_font_montserrat_40;
        else if (icon_area >= 80)  icon_font = &lv_font_montserrat_28;
        else if (icon_area >= 50)  icon_font = &lv_font_montserrat_22;
        else if (icon_area >= 40)  icon_font = &lv_font_montserrat_20;
        else                       icon_font = &lv_font_montserrat_16;
        lv_obj_set_style_text_font(icon, icon_font, LV_PART_MAIN);
        lv_obj_set_style_text_color(icon, lv_color_hex(cfg->color), LV_PART_MAIN);
    }

    // Label
    if (cfg->show_label && !cfg->label.empty()) {
        lv_obj_t *label = lv_label_create(btn);
        lv_label_set_text(label, cfg->label.c_str());
        lv_obj_set_style_text_font(label, &lv_font_montserrat_16, LV_PART_MAIN);
        lv_obj_set_style_text_color(label, lv_color_hex(cfg->color), LV_PART_MAIN);
    }

    // Description
    if (cfg->show_description && !cfg->description.empty()) {
        lv_obj_t *sub = lv_label_create(btn);
        lv_label_set_text(sub, cfg->description.c_str());
        lv_obj_set_style_text_font(sub, &lv_font_montserrat_12, LV_PART_MAIN);
        lv_obj_set_style_text_color(sub, lv_color_hex(cfg->color), LV_PART_MAIN);
    }
}

// Format just the value part (no name prefix) for split-label mode
static void format_stat_value_only(lv_obj_t *lbl, uint8_t type, uint16_t value) {
    switch (type) {
        case STAT_CPU_PERCENT: case STAT_RAM_PERCENT: case STAT_GPU_PERCENT:
        case STAT_DISK_PERCENT: case STAT_SWAP_PERCENT: case STAT_BATTERY_PCT:
        case STAT_GPU_MEM_PCT:
            if ((value & 0xFF) == 0xFF) lv_label_set_text(lbl, "N/A");
            else lv_label_set_text_fmt(lbl, "%d%%", value & 0xFF);
            break;
        case STAT_CPU_TEMP: case STAT_GPU_TEMP:
            if ((value & 0xFF) == 0xFF) lv_label_set_text(lbl, "N/A");
            else lv_label_set_text_fmt(lbl, "%d\xC2\xB0""C", value & 0xFF);
            break;
        case STAT_NET_UP: case STAT_NET_DOWN:
        case STAT_DISK_READ_KBS: case STAT_DISK_WRITE_KBS:
            if (value >= 1024) lv_label_set_text_fmt(lbl, "%.1f MB/s", value / 1024.0f);
            else lv_label_set_text_fmt(lbl, "%d KB/s", value);
            break;
        case STAT_CPU_FREQ: case STAT_GPU_FREQ:
            lv_label_set_text_fmt(lbl, "%d MHz", value); break;
        case STAT_UPTIME_HOURS: case STAT_DISPLAY_UPTIME:
            lv_label_set_text_fmt(lbl, "%dh", value); break;
        case STAT_FAN_RPM: case STAT_PROC_COUNT:
        case STAT_PROC_USER: case STAT_PROC_SYSTEM:
            lv_label_set_text_fmt(lbl, "%d", value); break;
        case STAT_LOAD_AVG:
            lv_label_set_text_fmt(lbl, "%.2f", value / 100.0f); break;
        case STAT_GPU_POWER_W:
            lv_label_set_text_fmt(lbl, "%dW", value); break;
        default:
            lv_label_set_text_fmt(lbl, "%d", value); break;
    }
}

static const char *get_stat_value_placeholder(uint8_t type) {
    switch (type) {
        case STAT_CPU_PERCENT: case STAT_RAM_PERCENT: case STAT_GPU_PERCENT:
        case STAT_DISK_PERCENT: case STAT_SWAP_PERCENT: case STAT_BATTERY_PCT:
        case STAT_GPU_MEM_PCT: return "--%";
        case STAT_CPU_TEMP: case STAT_GPU_TEMP: return "--\xC2\xB0""C";
        case STAT_NET_UP: case STAT_NET_DOWN:
        case STAT_DISK_READ_KBS: case STAT_DISK_WRITE_KBS: return "-- KB/s";
        case STAT_CPU_FREQ: case STAT_GPU_FREQ: return "-- MHz";
        case STAT_UPTIME_HOURS: case STAT_DISPLAY_UPTIME: return "--h";
        case STAT_FAN_RPM: case STAT_PROC_COUNT:
        case STAT_PROC_USER: case STAT_PROC_SYSTEM: return "--";
        case STAT_LOAD_AVG: return "--";
        case STAT_GPU_POWER_W: return "--W";
        default: return "--";
    }
}

// --- Stat Monitor ---
static void render_stat_monitor(lv_obj_t *parent, const WidgetConfig *cfg) {
    lv_obj_t *container = lv_obj_create(parent);
    lv_obj_set_pos(container, cfg->x, cfg->y);
    lv_obj_set_size(container, cfg->width, cfg->height);
    lv_obj_set_style_bg_color(container, cfg->bg_color ? lv_color_hex(cfg->bg_color) : lv_color_hex(0x0d1b2a), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(container, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_width(container, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(container, 6, LV_PART_MAIN);
    lv_obj_clear_flag(container, LV_OBJ_FLAG_SCROLLABLE);

    if (cfg->value_position == 0) {
        // Inline mode: single centered label with "Name Value"
        lv_obj_t *lbl = lv_label_create(container);
        lv_label_set_text(lbl, get_stat_placeholder(cfg->stat_type));
        lv_obj_set_style_text_font(lbl, &lv_font_montserrat_14, LV_PART_MAIN);
        lv_obj_set_style_text_color(lbl, lv_color_hex(cfg->color), LV_PART_MAIN);
        lv_obj_center(lbl);
        stat_widget_refs.push_back({lbl, nullptr, cfg->stat_type, 0});
    } else {
        // Split mode: two labels stacked vertically
        lv_obj_set_flex_flow(container, LV_FLEX_FLOW_COLUMN);
        lv_obj_set_flex_align(container, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
        lv_obj_set_style_pad_all(container, 2, LV_PART_MAIN);

        lv_obj_t *top_lbl = lv_label_create(container);
        lv_obj_t *bot_lbl = lv_label_create(container);

        lv_obj_t *value_lbl, *name_lbl;
        if (cfg->value_position == 1) {
            // Value on top, name on bottom
            value_lbl = top_lbl;
            name_lbl = bot_lbl;
        } else {
            // Name on top, value on bottom
            name_lbl = top_lbl;
            value_lbl = bot_lbl;
        }

        lv_label_set_text(name_lbl, get_stat_name(cfg->stat_type));
        lv_obj_set_style_text_font(name_lbl, &lv_font_montserrat_12, LV_PART_MAIN);
        lv_obj_set_style_text_color(name_lbl, lv_color_hex(cfg->color), LV_PART_MAIN);

        lv_label_set_text(value_lbl, get_stat_value_placeholder(cfg->stat_type));
        lv_obj_set_style_text_font(value_lbl, &lv_font_montserrat_16, LV_PART_MAIN);
        lv_obj_set_style_text_color(value_lbl, lv_color_hex(cfg->color), LV_PART_MAIN);

        stat_widget_refs.push_back({value_lbl, name_lbl, cfg->stat_type, cfg->value_position});
    }

    // Display uptime: initialize with current millis-based hours
    if (cfg->stat_type == STAT_DISPLAY_UPTIME) {
        uint16_t hours = (uint16_t)(millis() / 3600000UL);
        if (cfg->value_position == 0) {
            auto &ref = stat_widget_refs.back();
            lv_label_set_text_fmt(ref.label, "Disp %dh", hours);
        } else {
            auto &ref = stat_widget_refs.back();
            lv_label_set_text_fmt(ref.label, "%dh", hours);
        }
    }
}

// --- Status Bar ---
static void config_btn_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        if (!config_server_active()) {
            if (config_server_start()) show_config_screen();
        } else {
            config_server_stop();
            hide_config_screen();
        }
    }
}

static void brightness_event_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) power_cycle_brightness();
}

static void brightness_long_press_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_LONG_PRESSED) {
        DisplayMode current = display_get_mode();
        DisplayMode next = (DisplayMode)((current + 1) % 4);
        display_set_mode(next);
    }
}

static void render_status_bar(lv_obj_t *parent, const WidgetConfig *cfg) {
    lv_obj_t *bar = lv_obj_create(parent);
    lv_obj_set_pos(bar, cfg->x, cfg->y);
    lv_obj_set_size(bar, cfg->width, cfg->height);
    lv_obj_set_style_bg_color(bar, cfg->bg_color ? lv_color_hex(cfg->bg_color) : lv_color_hex(0x16213e), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_width(bar, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(bar, 0, LV_PART_MAIN);
    lv_obj_clear_flag(bar, LV_OBJ_FLAG_SCROLLABLE);

    // Title
    lv_obj_t *title = lv_label_create(bar);
    lv_label_set_text_fmt(title, LV_SYMBOL_KEYBOARD "  %s", cfg->label.c_str());
    lv_obj_set_style_text_font(title, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_set_style_text_color(title, lv_color_hex(cfg->color), LV_PART_MAIN);
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 15, 0);

    // Dynamic right-to-left icon packing
    StatusBarRef ref = {};
    int x_offset = -10;  // start 10px from right edge
    const int ICON_GAP = cfg->icon_spacing;
    const int ICON_W = 22;

    // WiFi indicator
    if (cfg->show_wifi) {
        ref.rssi_label = lv_label_create(bar);
        lv_label_set_text(ref.rssi_label, LV_SYMBOL_WIFI);
        lv_obj_set_style_text_font(ref.rssi_label, &lv_font_montserrat_18, LV_PART_MAIN);
        lv_obj_set_style_text_color(ref.rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
        lv_obj_align(ref.rssi_label, LV_ALIGN_RIGHT_MID, x_offset, 0);
        x_offset -= (ICON_W + ICON_GAP);
    }

    // PC connection indicator (USB icon)
    if (cfg->show_pc) {
        ref.pc_label = lv_label_create(bar);
        lv_label_set_text(ref.pc_label, LV_SYMBOL_USB);
        lv_obj_set_style_text_font(ref.pc_label, &lv_font_montserrat_18, LV_PART_MAIN);
        lv_obj_set_style_text_color(ref.pc_label, lv_color_hex(CLR_RED), LV_PART_MAIN);
        lv_obj_align(ref.pc_label, LV_ALIGN_RIGHT_MID, x_offset, 0);
        x_offset -= (ICON_W + ICON_GAP);
    }

    // Config/settings button
    if (cfg->show_settings) {
        lv_obj_t *cfg_btn = lv_label_create(bar);
        lv_label_set_text(cfg_btn, LV_SYMBOL_SETTINGS);
        lv_obj_set_style_text_font(cfg_btn, &lv_font_montserrat_16, LV_PART_MAIN);
        lv_obj_set_style_text_color(cfg_btn, lv_color_hex(CLR_TEAL), LV_PART_MAIN);
        lv_obj_align(cfg_btn, LV_ALIGN_RIGHT_MID, x_offset, 0);
        lv_obj_add_flag(cfg_btn, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_event_cb(cfg_btn, config_btn_event_cb, LV_EVENT_CLICKED, nullptr);
        x_offset -= (ICON_W + ICON_GAP);
    }

    // Brightness button
    if (cfg->show_brightness) {
        lv_obj_t *bright = lv_label_create(bar);
        lv_label_set_text(bright, LV_SYMBOL_IMAGE);
        lv_obj_set_style_text_font(bright, &lv_font_montserrat_16, LV_PART_MAIN);
        lv_obj_set_style_text_color(bright, lv_color_hex(CLR_YELLOW), LV_PART_MAIN);
        lv_obj_align(bright, LV_ALIGN_RIGHT_MID, x_offset, 0);
        lv_obj_add_flag(bright, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_event_cb(bright, brightness_event_cb, LV_EVENT_CLICKED, nullptr);
        lv_obj_add_event_cb(bright, brightness_long_press_cb, LV_EVENT_LONG_PRESSED, nullptr);
        x_offset -= (ICON_W + ICON_GAP);
    }

    // Time label (if enabled)
    if (cfg->show_time) {
        ref.time_label = lv_label_create(bar);
        lv_label_set_text(ref.time_label, "");
        lv_obj_set_style_text_font(ref.time_label, &lv_font_montserrat_14, LV_PART_MAIN);
        lv_obj_set_style_text_color(ref.time_label, lv_color_hex(0x2ECC71), LV_PART_MAIN);
        lv_obj_align(ref.time_label, LV_ALIGN_CENTER, 0, 0);
    }

    status_bar_refs.push_back(ref);
}

// --- Clock Widget ---
static void render_clock(lv_obj_t *parent, const WidgetConfig *cfg) {
    lv_obj_t *container = lv_obj_create(parent);
    lv_obj_set_pos(container, cfg->x, cfg->y);
    lv_obj_set_size(container, cfg->width, cfg->height);
    lv_obj_set_style_bg_color(container, cfg->bg_color ? lv_color_hex(cfg->bg_color) : lv_color_hex(0x0f0f23), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(container, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_width(container, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(container, 8, LV_PART_MAIN);
    lv_obj_clear_flag(container, LV_OBJ_FLAG_SCROLLABLE);

    if (cfg->clock_analog) {
        // Analog clock face
        lv_obj_t *face = lv_arc_create(container);
        int sz = (cfg->width < cfg->height) ? cfg->width - 20 : cfg->height - 20;
        lv_obj_set_size(face, sz, sz);
        lv_obj_center(face);
        lv_arc_set_bg_angles(face, 0, 360);
        lv_arc_set_value(face, 0);
        lv_obj_remove_style(face, NULL, LV_PART_KNOB);
        lv_obj_remove_style(face, NULL, LV_PART_INDICATOR);
        lv_obj_set_style_arc_width(face, 3, LV_PART_MAIN);
        lv_obj_set_style_arc_color(face, lv_color_hex(0x888888), LV_PART_MAIN);

        // Create hour and minute hands
        int cx = cfg->x + cfg->width / 2;
        int cy = cfg->y + cfg->height / 2;
        int hand_radius = sz / 2;

        lv_point_t hour_pts[2] = {{(lv_coord_t)cx, (lv_coord_t)cy}, {(lv_coord_t)cx, (lv_coord_t)(cy - hand_radius / 2)}};
        lv_obj_t *hour_hand = lv_line_create(container);
        lv_line_set_points(hour_hand, hour_pts, 2);
        lv_obj_set_style_line_width(hour_hand, 4, LV_PART_MAIN);
        lv_obj_set_style_line_color(hour_hand, lv_color_white(), LV_PART_MAIN);
        lv_obj_set_style_line_rounded(hour_hand, true, LV_PART_MAIN);

        lv_point_t min_pts[2] = {{(lv_coord_t)cx, (lv_coord_t)cy}, {(lv_coord_t)cx, (lv_coord_t)(cy - hand_radius)}};
        lv_obj_t *min_hand = lv_line_create(container);
        lv_line_set_points(min_hand, min_pts, 2);
        lv_obj_set_style_line_width(min_hand, 2, LV_PART_MAIN);
        lv_obj_set_style_line_color(min_hand, lv_color_white(), LV_PART_MAIN);
        lv_obj_set_style_line_rounded(min_hand, true, LV_PART_MAIN);

        // Track for periodic updates
        analog_clock_widgets.push_back({face, hour_hand, min_hand});
    } else {
        // Digital clock
        lv_obj_t *lbl = lv_label_create(container);
        lv_obj_set_style_text_font(lbl, &lv_font_montserrat_40, LV_PART_MAIN);
        lv_obj_set_style_text_color(lbl, lv_color_hex(cfg->color), LV_PART_MAIN);
        lv_obj_center(lbl);

        // Set initial time and track for periodic updates
        time_t now = time(nullptr);
        struct tm *tm_info = localtime(&now);
        bool use_24h = g_active_config ? g_active_config->display_settings.clock_24h : true;
        if (tm_info && now > 1000000000) {
            if (use_24h) {
                lv_label_set_text_fmt(lbl, "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
            } else {
                int hour12 = tm_info->tm_hour % 12;
                if (hour12 == 0) hour12 = 12;
                lv_label_set_text_fmt(lbl, "%d:%02d%s", hour12, tm_info->tm_min,
                                      tm_info->tm_hour >= 12 ? "p" : "a");
            }
        } else {
            lv_label_set_text(lbl, "--:--");
        }
        clock_widget_labels.push_back(lbl);
    }
}

// --- Text Label ---
static void render_text_label(lv_obj_t *parent, const WidgetConfig *cfg) {
    lv_obj_t *container = lv_obj_create(parent);
    lv_obj_set_pos(container, cfg->x, cfg->y);
    lv_obj_set_size(container, cfg->width, cfg->height);
    lv_obj_set_style_bg_opa(container, cfg->bg_color ? LV_OPA_COVER : LV_OPA_TRANSP, LV_PART_MAIN);
    if (cfg->bg_color) lv_obj_set_style_bg_color(container, lv_color_hex(cfg->bg_color), LV_PART_MAIN);
    lv_obj_set_style_border_width(container, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(container, 0, LV_PART_MAIN);
    lv_obj_clear_flag(container, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl = lv_label_create(container);
    lv_label_set_text(lbl, cfg->label.c_str());

    // Select font size
    const lv_font_t *font = &lv_font_montserrat_16;
    if (cfg->font_size >= 40) font = &lv_font_montserrat_40;
    else if (cfg->font_size >= 28) font = &lv_font_montserrat_28;
    else if (cfg->font_size >= 22) font = &lv_font_montserrat_22;
    else if (cfg->font_size >= 20) font = &lv_font_montserrat_20;
    else if (cfg->font_size >= 16) font = &lv_font_montserrat_16;
    else if (cfg->font_size >= 14) font = &lv_font_montserrat_14;
    else font = &lv_font_montserrat_12;

    lv_obj_set_style_text_font(lbl, font, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl, lv_color_hex(cfg->color), LV_PART_MAIN);

    // Alignment
    if (cfg->text_align == 0) lv_obj_align(lbl, LV_ALIGN_LEFT_MID, 4, 0);
    else if (cfg->text_align == 2) lv_obj_align(lbl, LV_ALIGN_RIGHT_MID, -4, 0);
    else lv_obj_center(lbl);
}

// --- Separator ---
static void render_separator(lv_obj_t *parent, const WidgetConfig *cfg) {
    lv_obj_t *line = lv_obj_create(parent);
    lv_obj_set_pos(line, cfg->x, cfg->y);
    if (cfg->separator_vertical) {
        lv_obj_set_size(line, cfg->thickness, cfg->height);
    } else {
        lv_obj_set_size(line, cfg->width, cfg->thickness);
    }
    lv_obj_set_style_bg_color(line, lv_color_hex(cfg->color), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(line, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_width(line, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(line, 1, LV_PART_MAIN);
    lv_obj_clear_flag(line, LV_OBJ_FLAG_SCROLLABLE);
}

// --- Page Nav ---
static void render_page_nav(lv_obj_t *parent, const WidgetConfig *cfg) {
    lv_obj_t *container = lv_obj_create(parent);
    lv_obj_set_pos(container, cfg->x, cfg->y);
    lv_obj_set_size(container, cfg->width, cfg->height);
    lv_obj_set_style_bg_opa(container, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(container, 0, LV_PART_MAIN);
    lv_obj_clear_flag(container, LV_OBJ_FLAG_SCROLLABLE);

    // Create dot indicators
    lv_obj_set_flex_flow(container, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(container, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(container, 8, LV_PART_MAIN);

    page_nav_refs.push_back(container);
}

static void update_page_nav_indicators() {
    int total_pages = (int)page_containers.size();
    for (auto *container : page_nav_refs) {
        if (!container) continue;
        lv_obj_clean(container);
        for (int i = 0; i < total_pages; i++) {
            lv_obj_t *dot = lv_obj_create(container);
            lv_obj_set_size(dot, 10, 10);
            lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);
            lv_obj_set_style_border_width(dot, 0, LV_PART_MAIN);
            lv_obj_clear_flag(dot, LV_OBJ_FLAG_SCROLLABLE);
            if (i == current_page) {
                lv_obj_set_style_bg_color(dot, lv_color_hex(CLR_BLUE), LV_PART_MAIN);
                lv_obj_set_style_bg_opa(dot, LV_OPA_COVER, LV_PART_MAIN);
            } else {
                lv_obj_set_style_bg_color(dot, lv_color_hex(CLR_GREY), LV_PART_MAIN);
                lv_obj_set_style_bg_opa(dot, LV_OPA_50, LV_PART_MAIN);
            }
        }
    }
}

// ============================================================
//  Widget Dispatcher
// ============================================================
static lv_obj_t* render_widget(lv_obj_t *parent, const WidgetConfig *cfg, uint8_t page_idx, uint8_t widget_idx) {
    int before = (int)lv_obj_get_child_cnt(parent);
    switch (cfg->widget_type) {
        case WIDGET_HOTKEY_BUTTON: render_hotkey_button(parent, cfg, page_idx, widget_idx); break;
        case WIDGET_STAT_MONITOR:  render_stat_monitor(parent, cfg);  break;
        case WIDGET_STATUS_BAR:    render_status_bar(parent, cfg);    break;
        case WIDGET_CLOCK:         render_clock(parent, cfg);         break;
        case WIDGET_TEXT_LABEL:    render_text_label(parent, cfg);    break;
        case WIDGET_SEPARATOR:     render_separator(parent, cfg);     break;
        case WIDGET_PAGE_NAV:      render_page_nav(parent, cfg);      break;
        default:
            Serial.printf("[ui] Unknown widget type %d, skipping\n", cfg->widget_type);
            break;
    }
    int after = (int)lv_obj_get_child_cnt(parent);
    return (after > before) ? lv_obj_get_child(parent, before) : nullptr;
}

// ============================================================
//  Page Management
// ============================================================
static void show_page(int index) {
    if (index < 0 || index >= (int)page_containers.size()) return;

    // Hide all pages
    for (auto *p : page_containers) {
        lv_obj_add_flag(p, LV_OBJ_FLAG_HIDDEN);
    }

    // Show target page
    lv_obj_clear_flag(page_containers[index], LV_OBJ_FLAG_HIDDEN);
    current_page = index;

    update_page_nav_indicators();
    Serial.printf("[ui] Showing page %d/%zu\n", index + 1, page_containers.size());
}

void ui_next_page() {
    if (current_page < (int)page_containers.size() - 1) {
        show_page(current_page + 1);
    }
}

void ui_prev_page() {
    if (current_page > 0) {
        show_page(current_page - 1);
    }
}

void ui_goto_page(int page_index) {
    if (page_index >= 0 && page_index < (int)page_containers.size()) {
        show_page(page_index);
    }
}

int ui_get_current_page() { return current_page; }
int ui_get_page_count() { return (int)page_containers.size(); }

lv_obj_t* ui_get_widget_obj(int page_idx, int widget_idx) {
    if (page_idx < 0 || page_idx >= (int)page_widget_objs.size()) return nullptr;
    if (widget_idx < 0 || widget_idx >= (int)page_widget_objs[page_idx].size()) return nullptr;
    return page_widget_objs[page_idx][widget_idx];
}

// ============================================================
//  Create all pages from config
// ============================================================
static void create_pages(lv_obj_t *screen, const AppConfig *cfg) {
    // Clear tracking arrays
    stat_widget_refs.clear();
    status_bar_refs.clear();
    page_nav_refs.clear();
    clock_widget_labels.clear();
    analog_clock_widgets.clear();
    page_containers.clear();
    page_widget_objs.clear();
    btn_event_count = 0;

    const ProfileConfig *active = cfg->get_active_profile();
    if (!active) {
        Serial.println("[ui] No active profile");
        return;
    }

    for (size_t pi = 0; pi < active->pages.size(); pi++) {
        const PageConfig &page = active->pages[pi];

        // Create a full-screen container for this page
        lv_obj_t *container = lv_obj_create(screen);
        lv_obj_set_size(container, DISPLAY_WIDTH, DISPLAY_HEIGHT);
        lv_obj_set_pos(container, 0, 0);
        // Default layout is none (absolute positioning) in LVGL v8
        lv_obj_set_style_bg_color(container, lv_color_hex(0x0D1117), LV_PART_MAIN);
        lv_obj_set_style_bg_opa(container, LV_OPA_COVER, LV_PART_MAIN);
        lv_obj_set_style_border_width(container, 0, LV_PART_MAIN);
        lv_obj_set_style_radius(container, 0, LV_PART_MAIN);
        lv_obj_set_style_pad_all(container, 0, LV_PART_MAIN);
        lv_obj_clear_flag(container, LV_OBJ_FLAG_SCROLLABLE);

        // Background image from SD card (rendered behind all widgets)
        if (!page.bg_image.empty() && SD.exists(page.bg_image.c_str())) {
            std::string bg_src = "S:" + page.bg_image;
            lv_obj_t *bg = lv_img_create(container);
            lv_img_set_src(bg, bg_src.c_str());
            // SJPG is pre-rendered at 800x480 by companion; if the source
            // image is a different size, scale to cover the full screen.
            lv_img_header_t header;
            if (lv_img_decoder_get_info(bg_src.c_str(), &header) == LV_RES_OK
                && header.w > 0 && header.h > 0
                && (header.w != DISPLAY_WIDTH || header.h != DISPLAY_HEIGHT)) {
                uint16_t zoom_w = (uint16_t)((uint32_t)DISPLAY_WIDTH * 256 / header.w);
                uint16_t zoom_h = (uint16_t)((uint32_t)DISPLAY_HEIGHT * 256 / header.h);
                uint16_t zoom = (zoom_w > zoom_h) ? zoom_w : zoom_h;  // cover (not contain)
                lv_img_set_zoom(bg, zoom);
            }
            lv_obj_center(bg);
            lv_obj_clear_flag(bg, LV_OBJ_FLAG_CLICKABLE);
        }

        // Render all widgets and track their LVGL objects
        std::vector<lv_obj_t *> widget_objs;
        for (size_t wi = 0; wi < page.widgets.size(); wi++) {
            lv_obj_t *obj = render_widget(container, &page.widgets[wi], (uint8_t)pi, (uint8_t)wi);
            widget_objs.push_back(obj);
        }

        // Hide all pages except the first
        if (pi > 0) {
            lv_obj_add_flag(container, LV_OBJ_FLAG_HIDDEN);
        }

        page_containers.push_back(container);
        page_widget_objs.push_back(std::move(widget_objs));
    }

    current_page = 0;
    update_page_nav_indicators();

    Serial.printf("[ui] Created %zu pages\n", page_containers.size());
}

// ============================================================
//  Public: update_stats()
// ============================================================
// Cached stat values for clock/standby screens
static uint16_t cached_cpu = 0xFFFF, cached_ram = 0xFFFF, cached_gpu = 0xFFFF;

static void update_clock_stats_label() {
    if (!clock_stats_label) return;
    auto pct = [](uint16_t v) -> String { return v == 0xFFFF ? "--%" : String(v) + "%"; };
    String line = "CPU " + pct(cached_cpu) + " | RAM " + pct(cached_ram) + " | GPU " + pct(cached_gpu);
    lv_label_set_text(clock_stats_label, line.c_str());

    // Also update standby if it exists
    if (standby_stats_label) {
        lv_label_set_text(standby_stats_label, line.c_str());
    }
}

static void update_stat_widget(uint8_t type, uint16_t value) {
    // Cache key stats for clock/standby screens
    if (type == STAT_CPU_PERCENT) cached_cpu = value;
    else if (type == STAT_RAM_PERCENT) cached_ram = value;
    else if (type == STAT_GPU_PERCENT) cached_gpu = value;

    for (auto &ref : stat_widget_refs) {
        if (ref.stat_type == type && ref.label) {
            if (ref.value_position == 0) {
                format_stat_value(ref.label, type, value);
            } else {
                format_stat_value_only(ref.label, type, value);
            }
        }
    }
}

static void update_stats_legacy(const StatsPayload *stats) {
    update_stat_widget(STAT_CPU_PERCENT, stats->cpu_percent);
    update_stat_widget(STAT_RAM_PERCENT, stats->ram_percent);
    update_stat_widget(STAT_GPU_PERCENT, stats->gpu_percent);
    update_stat_widget(STAT_CPU_TEMP, stats->cpu_temp);
    update_stat_widget(STAT_GPU_TEMP, stats->gpu_temp);
    update_stat_widget(STAT_DISK_PERCENT, stats->disk_percent);
    update_stat_widget(STAT_NET_UP, stats->net_up_kbps);
    update_stat_widget(STAT_NET_DOWN, stats->net_down_kbps);
}

void update_stats(const uint8_t *data, uint8_t len) {
    if (!data || len == 0) return;

    if (len >= sizeof(StatsPayload) && data[0] > STAT_TYPE_MAX) {
        update_stats_legacy((const StatsPayload *)data);
    } else {
        tlv_decode_stats(data, len, update_stat_widget);
    }

    update_clock_stats_label();
}

// ============================================================
//  Public: update_device_status()
// ============================================================
void update_device_status(int rssi_dbm, bool espnow_linked, uint8_t brightness_level, bool stats_active) {
    for (auto &ref : status_bar_refs) {
        if (ref.rssi_label) {
            if (rssi_dbm == 0 || !espnow_linked) {
                lv_obj_set_style_text_color(ref.rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
            } else if (rssi_dbm > -50) {
                lv_obj_set_style_text_color(ref.rssi_label, lv_color_hex(CLR_GREEN), LV_PART_MAIN);
            } else if (rssi_dbm > -70) {
                lv_obj_set_style_text_color(ref.rssi_label, lv_color_hex(CLR_YELLOW), LV_PART_MAIN);
            } else {
                lv_obj_set_style_text_color(ref.rssi_label, lv_color_hex(CLR_RED), LV_PART_MAIN);
            }
        }
        if (ref.pc_label) {
            lv_obj_set_style_text_color(ref.pc_label,
                lv_color_hex(stats_active ? CLR_GREEN : CLR_RED), LV_PART_MAIN);
        }
        if (ref.time_label) {
            time_t now = time(nullptr);
            struct tm *tm_info = localtime(&now);
            if (tm_info && now > 1000000000) { // Only show if time has been synced (post-2001)
                bool use_24h = g_active_config ? g_active_config->display_settings.clock_24h : true;
                if (use_24h) {
                    lv_label_set_text_fmt(ref.time_label, "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
                } else {
                    int hour12 = tm_info->tm_hour % 12;
                    if (hour12 == 0) hour12 = 12;
                    lv_label_set_text_fmt(ref.time_label, "%d:%02d%s", hour12, tm_info->tm_min,
                                          tm_info->tm_hour >= 12 ? "p" : "a");
                }
            }
        }
    }
    (void)brightness_level;
}

// ============================================================
//  Notification Toast
// ============================================================
static lv_obj_t *active_toast = nullptr;

static void toast_anim_opa_cb(void *obj, int32_t v) {
    lv_obj_set_style_opa((lv_obj_t *)obj, (lv_opa_t)v, LV_PART_MAIN);
}

void show_notification_toast(const char *app_name, const char *summary, const char *body) {
    if (active_toast) {
        lv_anim_del(active_toast, nullptr);
        lv_obj_del(active_toast);
        active_toast = nullptr;
    }

    lv_obj_t *toast = lv_obj_create(lv_scr_act());
    lv_obj_set_size(toast, 600, 120);
    lv_obj_align(toast, LV_ALIGN_TOP_RIGHT, -20, 50);
    lv_obj_set_style_bg_color(toast, lv_color_hex(0x1a1a2e), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(toast, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_color(toast, lv_color_hex(CLR_BLUE), LV_PART_MAIN);
    lv_obj_set_style_border_width(toast, 2, LV_PART_MAIN);
    lv_obj_set_style_radius(toast, 12, LV_PART_MAIN);
    lv_obj_set_style_shadow_width(toast, 0, LV_PART_MAIN);
    lv_obj_clear_flag(toast, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *app_lbl = lv_label_create(toast);
    lv_label_set_text(app_lbl, app_name);
    lv_obj_set_style_text_font(app_lbl, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(app_lbl, lv_color_hex(CLR_BLUE), LV_PART_MAIN);
    lv_obj_align(app_lbl, LV_ALIGN_TOP_LEFT, 12, 8);

    lv_obj_t *sum_lbl = lv_label_create(toast);
    lv_label_set_text(sum_lbl, summary);
    lv_obj_set_style_text_font(sum_lbl, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_style_text_color(sum_lbl, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_width(sum_lbl, 560);
    lv_label_set_long_mode(sum_lbl, LV_LABEL_LONG_DOT);
    lv_obj_align(sum_lbl, LV_ALIGN_TOP_LEFT, 12, 28);

    if (body && strlen(body) > 0) {
        lv_obj_t *body_lbl = lv_label_create(toast);
        lv_label_set_text(body_lbl, body);
        lv_label_set_long_mode(body_lbl, LV_LABEL_LONG_DOT);
        lv_obj_set_width(body_lbl, 560);
        lv_obj_set_style_text_font(body_lbl, &lv_font_montserrat_12, LV_PART_MAIN);
        lv_obj_set_style_text_color(body_lbl, lv_color_hex(0xBBBBBB), LV_PART_MAIN);
        lv_obj_align(body_lbl, LV_ALIGN_TOP_LEFT, 12, 52);
    }

    lv_obj_add_flag(toast, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(toast, [](lv_event_t *e) {
        lv_obj_t *obj = lv_event_get_target(e);
        lv_anim_del(obj, nullptr);
        lv_obj_del(obj);
        active_toast = nullptr;
    }, LV_EVENT_CLICKED, nullptr);

    // Auto-dismiss after 5 seconds (no opacity animation — avoids alpha blending)
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, toast);
    lv_anim_set_values(&a, 0, 1);
    lv_anim_set_exec_cb(&a, nullptr);
    lv_anim_set_time(&a, 1);
    lv_anim_set_delay(&a, 5000);
    lv_anim_set_ready_cb(&a, [](lv_anim_t *anim) {
        lv_obj_del((lv_obj_t *)anim->var);
        active_toast = nullptr;
    });
    lv_anim_start(&a);
    active_toast = toast;
}

// ============================================================
//  Clock Mode Screen
// ============================================================
void show_clock_mode() {
    if (clock_screen) {
        update_clock_time();
        lv_scr_load(clock_screen);
    }
}

void show_hotkey_view() {
    if (main_screen) lv_scr_load(main_screen);
}

void update_clock_time() {
    if (!clock_time_label || !clock_rssi_label) return;

    time_t now = time(nullptr);
    struct tm *tm_info = localtime(&now);
    if (!tm_info) return;
    // Don't update display until time has been synced from companion
    if (now < 1000000000) return;

    bool use_analog = g_active_config ? g_active_config->clock_analog : false;

    if (use_analog && analog_clock_face) {
        lv_obj_add_flag(clock_time_label, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(analog_clock_face, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(analog_hour_hand, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(analog_min_hand, LV_OBJ_FLAG_HIDDEN);

        float hour_angle = (tm_info->tm_hour % 12) * 30.0f + tm_info->tm_min * 0.5f;
        float min_angle = tm_info->tm_min * 6.0f;
        int cx = SCREEN_WIDTH / 2;
        int cy = SCREEN_HEIGHT / 2;
        float hour_rad = (hour_angle - 90.0f) * M_PI / 180.0f;
        float min_rad = (min_angle - 90.0f) * M_PI / 180.0f;

        hour_points[0] = {(lv_coord_t)cx, (lv_coord_t)cy};
        hour_points[1] = {(lv_coord_t)(cx + 80 * cosf(hour_rad)), (lv_coord_t)(cy + 80 * sinf(hour_rad))};
        lv_line_set_points(analog_hour_hand, hour_points, 2);

        min_points[0] = {(lv_coord_t)cx, (lv_coord_t)cy};
        min_points[1] = {(lv_coord_t)(cx + 120 * cosf(min_rad)), (lv_coord_t)(cy + 120 * sinf(min_rad))};
        lv_line_set_points(analog_min_hand, min_points, 2);
    } else {
        lv_obj_clear_flag(clock_time_label, LV_OBJ_FLAG_HIDDEN);
        lv_label_set_text_fmt(clock_time_label, "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
        if (analog_clock_face) lv_obj_add_flag(analog_clock_face, LV_OBJ_FLAG_HIDDEN);
        if (analog_hour_hand) lv_obj_add_flag(analog_hour_hand, LV_OBJ_FLAG_HIDDEN);
        if (analog_min_hand) lv_obj_add_flag(analog_min_hand, LV_OBJ_FLAG_HIDDEN);
    }

    int rssi = espnow_get_rssi();
    if (rssi != 0 && rssi > -50)
        lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_GREEN), LV_PART_MAIN);
    else if (rssi != 0 && rssi > -70)
        lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_YELLOW), LV_PART_MAIN);
    else if (rssi != 0)
        lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_RED), LV_PART_MAIN);
    else
        lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
}

// ============================================================
//  Page Clock Widget Updates
// ============================================================
void update_page_clocks() {
    time_t now = time(nullptr);
    struct tm *tm_info = localtime(&now);
    if (!tm_info || now <= 1000000000) return;

    // Update digital clock labels
    bool use_24h = g_active_config ? g_active_config->display_settings.clock_24h : true;
    for (lv_obj_t *lbl : clock_widget_labels) {
        if (!lbl) continue;
        if (use_24h) {
            lv_label_set_text_fmt(lbl, "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
        } else {
            int hour12 = tm_info->tm_hour % 12;
            if (hour12 == 0) hour12 = 12;
            lv_label_set_text_fmt(lbl, "%d:%02d%s", hour12, tm_info->tm_min,
                                  tm_info->tm_hour >= 12 ? "p" : "a");
        }
    }

    // Update analog clock hands
    for (const auto &ref : analog_clock_widgets) {
        if (!ref.face || !ref.hour_hand || !ref.min_hand) continue;

        float hour_angle = (tm_info->tm_hour % 12) * 30.0f + tm_info->tm_min * 0.5f;
        float min_angle = tm_info->tm_min * 6.0f;

        // Get the center of the widget from its parent
        lv_obj_t *parent = lv_obj_get_parent(ref.face);
        if (!parent) continue;

        lv_area_t area;
        lv_obj_get_coords(parent, &area);
        int cx = area.x1 + (area.x2 - area.x1) / 2;
        int cy = area.y1 + (area.y2 - area.y1) / 2;

        float hour_rad = (hour_angle - 90.0f) * M_PI / 180.0f;
        float min_rad = (min_angle - 90.0f) * M_PI / 180.0f;

        lv_point_t hour_pts[2];
        hour_pts[0] = {(lv_coord_t)cx, (lv_coord_t)cy};
        hour_pts[1] = {(lv_coord_t)(cx + 40 * cosf(hour_rad)), (lv_coord_t)(cy + 40 * sinf(hour_rad))};
        lv_line_set_points(ref.hour_hand, hour_pts, 2);

        lv_point_t min_pts[2];
        min_pts[0] = {(lv_coord_t)cx, (lv_coord_t)cy};
        min_pts[1] = {(lv_coord_t)(cx + 60 * cosf(min_rad)), (lv_coord_t)(cy + 60 * sinf(min_rad))};
        lv_line_set_points(ref.min_hand, min_pts, 2);
    }
}

// ============================================================
//  Display Uptime Self-Update
// ============================================================
void update_display_uptime() {
    uint16_t hours = (uint16_t)(millis() / 3600000UL);
    for (auto &ref : stat_widget_refs) {
        if (ref.stat_type == STAT_DISPLAY_UPTIME && ref.label) {
            if (ref.value_position == 0) {
                lv_label_set_text_fmt(ref.label, "Disp %dh", hours);
            } else {
                lv_label_set_text_fmt(ref.label, "%dh", hours);
            }
        }
    }
}

// ============================================================
//  Config Screen
// ============================================================
void show_config_screen() {
    if (!config_screen) return;
    if (config_info_label) {
        IPAddress ip = WiFi.softAPIP();
        lv_label_set_text_fmt(config_info_label,
            "Connect to WiFi:\n"
            "  SSID: CrowPanel-Config\n"
            "  Password: crowconfig\n\n"
            "Config upload:\n"
            "  http://%s\n\n"
            "OTA firmware upload:\n"
            "  http://%s/update\n\n"
            "PlatformIO:\n"
            "  pio run -t upload --upload-port %s",
            ip.toString().c_str(), ip.toString().c_str(), ip.toString().c_str());
    }
    lv_scr_load(config_screen);
}

void hide_config_screen() {
    if (main_screen) lv_scr_load(main_screen);
}

// ============================================================
//  SD Card Filesystem Driver
// ============================================================
static void lvgl_register_sd_driver() {
    if (sd_fs_registered) return;
    static lv_fs_drv_t drv;
    lv_fs_drv_init(&drv);
    drv.letter = 'S';
    drv.open_cb = [](lv_fs_drv_t *, const char *path, lv_fs_mode_t) -> void* {
        File *file = new File();
        *file = SD.open(path, FILE_READ);
        if (!*file) { delete file; return nullptr; }
        return file;
    };
    drv.close_cb = [](lv_fs_drv_t *, void *file_p) -> lv_fs_res_t {
        File *file = (File*)file_p; file->close(); delete file; return LV_FS_RES_OK;
    };
    drv.read_cb = [](lv_fs_drv_t *, void *file_p, void *buf, uint32_t btr, uint32_t *br) -> lv_fs_res_t {
        File *file = (File*)file_p; *br = file->read((uint8_t*)buf, btr); return LV_FS_RES_OK;
    };
    drv.seek_cb = [](lv_fs_drv_t *, void *file_p, uint32_t pos, lv_fs_whence_t whence) -> lv_fs_res_t {
        File *file = (File*)file_p;
        if (whence == LV_FS_SEEK_SET) file->seek(pos);
        else if (whence == LV_FS_SEEK_CUR) file->seek(file->position() + pos);
        else if (whence == LV_FS_SEEK_END) file->seek(file->size() - pos);
        return LV_FS_RES_OK;
    };
    drv.tell_cb = [](lv_fs_drv_t *, void *file_p, uint32_t *pos_p) -> lv_fs_res_t {
        File *file = (File*)file_p; *pos_p = file->position(); return LV_FS_RES_OK;
    };
    lv_fs_drv_register(&drv);
    sd_fs_registered = true;
}

// ============================================================
//  Picture Frame Mode
// ============================================================
static void load_next_slideshow_image() {
    if (slideshow_files.empty() || !slideshow_img) return;
    String path = "S:" + slideshow_files[slideshow_index];
    lv_img_set_src(slideshow_img, path.c_str());
    slideshow_index = (slideshow_index + 1) % slideshow_files.size();
}

static void slideshow_timer_cb(lv_timer_t *timer) { (void)timer; load_next_slideshow_image(); }

static void init_picture_frame_mode() {
    lvgl_register_sd_driver();
    if (!picture_frame_screen) {
        picture_frame_screen = lv_obj_create(NULL);
        lv_obj_set_style_bg_color(picture_frame_screen, lv_color_black(), LV_PART_MAIN);
        lv_obj_set_style_bg_opa(picture_frame_screen, LV_OPA_COVER, LV_PART_MAIN);
    } else {
        lv_obj_clean(picture_frame_screen);
    }
    slideshow_img = nullptr; slideshow_fallback_label = nullptr;
    slideshow_files.clear();

    File dir = SD.open("/pictures");
    if (dir && dir.isDirectory()) {
        File entry;
        while ((entry = dir.openNextFile())) {
            if (!entry.isDirectory()) {
                String name = String(entry.name()); String lower = name; lower.toLowerCase();
                if (lower.endsWith(".jpg") || lower.endsWith(".jpeg") || lower.endsWith(".sjpg")) {
                    slideshow_files.push_back(name.startsWith("/") ? name : "/pictures/" + name);
                }
            }
            entry.close();
        }
        dir.close();
    }

    if (slideshow_files.empty()) {
        slideshow_fallback_label = lv_label_create(picture_frame_screen);
        lv_label_set_text(slideshow_fallback_label, "No images in /pictures\n\nUpload images via companion app");
        lv_obj_center(slideshow_fallback_label);
        lv_obj_set_style_text_color(slideshow_fallback_label, lv_color_white(), LV_PART_MAIN);
        lv_obj_set_style_text_font(slideshow_fallback_label, &lv_font_montserrat_20, LV_PART_MAIN);
        lv_obj_set_style_text_align(slideshow_fallback_label, LV_TEXT_ALIGN_CENTER, LV_PART_MAIN);
        return;
    }

    slideshow_img = lv_img_create(picture_frame_screen);
    lv_obj_set_size(slideshow_img, SCREEN_WIDTH, SCREEN_HEIGHT);
    lv_obj_align(slideshow_img, LV_ALIGN_CENTER, 0, 0);
    slideshow_index = 0;
    load_next_slideshow_image();
    uint32_t interval_ms = g_active_config ? g_active_config->slideshow_interval_sec * 1000 : 30000;
    if (interval_ms < 5000) interval_ms = 5000;
    slideshow_timer = lv_timer_create(slideshow_timer_cb, interval_ms, nullptr);
}

static void cleanup_picture_frame_mode() {
    if (slideshow_timer) { lv_timer_del(slideshow_timer); slideshow_timer = nullptr; }
}

// ============================================================
//  Standby Mode
// ============================================================
static void init_standby_mode() {
    if (!standby_screen) {
        standby_screen = lv_obj_create(NULL);
        lv_obj_set_style_bg_color(standby_screen, lv_color_hex(0x0f0f23), LV_PART_MAIN);
        lv_obj_set_style_bg_opa(standby_screen, LV_OPA_COVER, LV_PART_MAIN);
        standby_time_label = lv_label_create(standby_screen);
        lv_label_set_text(standby_time_label, "00:00");
        lv_obj_set_style_text_font(standby_time_label, &lv_font_montserrat_40, LV_PART_MAIN);
        lv_obj_set_style_text_color(standby_time_label, lv_color_white(), LV_PART_MAIN);
        lv_obj_align(standby_time_label, LV_ALIGN_CENTER, 0, -50);
        standby_stats_label = lv_label_create(standby_screen);
        lv_label_set_text(standby_stats_label, "CPU --% | RAM --% | GPU --%");
        lv_obj_set_style_text_font(standby_stats_label, &lv_font_montserrat_16, LV_PART_MAIN);
        lv_obj_set_style_text_color(standby_stats_label, lv_color_hex(0x888888), LV_PART_MAIN);
        lv_obj_align(standby_stats_label, LV_ALIGN_CENTER, 0, 20);
    }
    time_t now = time(nullptr);
    struct tm *tm_info = localtime(&now);
    if (standby_time_label && tm_info && now > 1000000000)
        lv_label_set_text_fmt(standby_time_label, "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
}

void update_standby_time() {
    if (!standby_time_label) return;
    time_t now = time(nullptr);
    struct tm *tm_info = localtime(&now);
    if (tm_info && now > 1000000000)
        lv_label_set_text_fmt(standby_time_label, "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
}

void update_standby_stats(const StatsPayload *stats) {
    if (!standby_stats_label || !stats) return;
    auto pct_str = [](uint8_t val) -> String { return val == 0xFF ? "N/A" : String(val) + "%"; };
    String line = "CPU " + pct_str(stats->cpu_percent) + " | RAM " + pct_str(stats->ram_percent) +
                  " | GPU " + pct_str(stats->gpu_percent);
    lv_label_set_text(standby_stats_label, line.c_str());
}

// ============================================================
//  Analog Clock Widgets (on clock_screen)
// ============================================================
static void create_analog_clock_widgets(lv_obj_t *parent) {
    analog_clock_face = lv_arc_create(parent);
    lv_obj_set_size(analog_clock_face, 300, 300);
    lv_obj_center(analog_clock_face);
    lv_arc_set_bg_angles(analog_clock_face, 0, 360);
    lv_arc_set_value(analog_clock_face, 0);
    lv_obj_remove_style(analog_clock_face, NULL, LV_PART_KNOB);
    lv_obj_remove_style(analog_clock_face, NULL, LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(analog_clock_face, 4, LV_PART_MAIN);
    lv_obj_set_style_arc_color(analog_clock_face, lv_color_hex(0x888888), LV_PART_MAIN);

    hour_points[0] = {(lv_coord_t)(SCREEN_WIDTH / 2), (lv_coord_t)(SCREEN_HEIGHT / 2)};
    hour_points[1] = {(lv_coord_t)(SCREEN_WIDTH / 2), (lv_coord_t)(SCREEN_HEIGHT / 2 - 80)};
    analog_hour_hand = lv_line_create(parent);
    lv_line_set_points(analog_hour_hand, hour_points, 2);
    lv_obj_set_style_line_width(analog_hour_hand, 6, LV_PART_MAIN);
    lv_obj_set_style_line_color(analog_hour_hand, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_line_rounded(analog_hour_hand, true, LV_PART_MAIN);

    min_points[0] = {(lv_coord_t)(SCREEN_WIDTH / 2), (lv_coord_t)(SCREEN_HEIGHT / 2)};
    min_points[1] = {(lv_coord_t)(SCREEN_WIDTH / 2), (lv_coord_t)(SCREEN_HEIGHT / 2 - 120)};
    analog_min_hand = lv_line_create(parent);
    lv_line_set_points(analog_min_hand, min_points, 2);
    lv_obj_set_style_line_width(analog_min_hand, 4, LV_PART_MAIN);
    lv_obj_set_style_line_color(analog_min_hand, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_line_rounded(analog_min_hand, true, LV_PART_MAIN);

    lv_obj_add_flag(analog_clock_face, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(analog_hour_hand, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(analog_min_hand, LV_OBJ_FLAG_HIDDEN);
}

// ============================================================
//  Mode Transition
// ============================================================
void ui_transition_mode(DisplayMode from, DisplayMode to) {
    switch (from) {
        case MODE_HOTKEYS: break;
        case MODE_CLOCK: break;
        case MODE_PICTURE_FRAME: cleanup_picture_frame_mode(); break;
        case MODE_STANDBY: break;
    }
    switch (to) {
        case MODE_HOTKEYS: show_hotkey_view(); break;
        case MODE_CLOCK: show_clock_mode(); break;
        case MODE_PICTURE_FRAME:
            init_picture_frame_mode();
            if (picture_frame_screen) lv_scr_load(picture_frame_screen);
            break;
        case MODE_STANDBY:
            init_standby_mode();
            if (standby_screen) lv_scr_load(standby_screen);
            break;
    }
}

// ============================================================
//  Public: create_ui()
// ============================================================
void create_ui(const AppConfig* cfg) {
    if (!cfg) { Serial.println("create_ui: nullptr config"); return; }
    g_active_config = cfg;

    // Register SD card filesystem driver for LVGL image loading
    lvgl_register_sd_driver();

    main_screen = lv_scr_act();
    lv_obj_set_style_bg_color(main_screen, lv_color_hex(0x0D1117), LV_PART_MAIN);

    // Clock screen (tap anywhere to wake back to hotkey view)
    clock_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(clock_screen, lv_color_hex(0x0f0f23), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(clock_screen, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_add_flag(clock_screen, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(clock_screen, [](lv_event_t *) {
        power_wake_detected();
        show_hotkey_view();
    }, LV_EVENT_CLICKED, nullptr);
    clock_time_label = lv_label_create(clock_screen);
    lv_label_set_text(clock_time_label, "00:00");
    lv_obj_set_style_text_font(clock_time_label, &lv_font_montserrat_40, LV_PART_MAIN);
    lv_obj_set_style_text_color(clock_time_label, lv_color_white(), LV_PART_MAIN);
    lv_obj_align(clock_time_label, LV_ALIGN_CENTER, 0, -30);
    clock_rssi_label = lv_label_create(clock_screen);
    lv_label_set_text(clock_rssi_label, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_font(clock_rssi_label, &lv_font_montserrat_28, LV_PART_MAIN);
    lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
    lv_obj_align(clock_rssi_label, LV_ALIGN_CENTER, 0, 30);

    // Stats line (CPU / RAM / GPU)
    clock_stats_label = lv_label_create(clock_screen);
    lv_label_set_text(clock_stats_label, "CPU --% | RAM --% | GPU --%");
    lv_obj_set_style_text_font(clock_stats_label, &lv_font_montserrat_18, LV_PART_MAIN);
    lv_obj_set_style_text_color(clock_stats_label, lv_color_hex(0x888888), LV_PART_MAIN);
    lv_obj_align(clock_stats_label, LV_ALIGN_CENTER, 0, 80);

    create_analog_clock_widgets(clock_screen);

    // Config screen
    config_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(config_screen, lv_color_hex(0x0d1b2a), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(config_screen, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_t *cfg_title = lv_label_create(config_screen);
    lv_label_set_text(cfg_title, LV_SYMBOL_SETTINGS "  Config Upload Mode");
    lv_obj_set_style_text_font(cfg_title, &lv_font_montserrat_28, LV_PART_MAIN);
    lv_obj_set_style_text_color(cfg_title, lv_color_hex(CLR_TEAL), LV_PART_MAIN);
    lv_obj_align(cfg_title, LV_ALIGN_TOP_MID, 0, 40);
    config_info_label = lv_label_create(config_screen);
    lv_label_set_text(config_info_label, "Starting...");
    lv_obj_set_style_text_font(config_info_label, &lv_font_montserrat_18, LV_PART_MAIN);
    lv_obj_set_style_text_color(config_info_label, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_text_align(config_info_label, LV_TEXT_ALIGN_LEFT, LV_PART_MAIN);
    lv_obj_align(config_info_label, LV_ALIGN_CENTER, 0, 10);
    lv_obj_t *cfg_exit = lv_btn_create(config_screen);
    lv_obj_set_size(cfg_exit, 250, 50);
    lv_obj_align(cfg_exit, LV_ALIGN_BOTTOM_MID, 0, -40);
    lv_obj_set_style_bg_color(cfg_exit, lv_color_hex(CLR_GREEN), LV_PART_MAIN);
    lv_obj_add_event_cb(cfg_exit, config_btn_event_cb, LV_EVENT_CLICKED, nullptr);
    lv_obj_t *exit_lbl = lv_label_create(cfg_exit);
    lv_label_set_text(exit_lbl, "Apply & Exit");
    lv_obj_center(exit_lbl);

    // Create widget pages
    create_pages(main_screen, cfg);

    Serial.printf("UI initialized: %zu page(s), WYSIWYG mode\n",
                  cfg->get_active_profile() ? cfg->get_active_profile()->pages.size() : 0);
}

// ============================================================
//  Public: rebuild_ui()
// ============================================================
void rebuild_ui(const AppConfig* cfg) {
    if (!cfg || !main_screen) { Serial.println("rebuild_ui: invalid args"); return; }

    lv_mem_monitor_t mon_pre;
    lv_mem_monitor(&mon_pre);

    // Destroy all page containers
    for (auto *p : page_containers) {
        lv_obj_del(p);
    }
    page_containers.clear();
    page_widget_objs.clear();
    stat_widget_refs.clear();
    status_bar_refs.clear();
    page_nav_refs.clear();
    clock_widget_labels.clear();
    analog_clock_widgets.clear();

    g_active_config = cfg;

    // Recreate pages
    create_pages(main_screen, cfg);

    lv_mem_monitor_t mon_post;
    lv_mem_monitor(&mon_post);
    uint32_t used_pre = mon_pre.total_size - mon_pre.free_size;
    uint32_t used_post = mon_post.total_size - mon_post.free_size;
    Serial.printf("UI rebuild: LVGL mem used=%u->%u (delta=%d), free=%u\n",
                  used_pre, used_post, (int32_t)(used_post - used_pre), mon_post.free_size);
}
