#include <lvgl.h>
#include <Arduino.h>
#include <ctime>
#include "protocol.h"
#include "config.h"
#include "display_hw.h"
#include "espnow_link.h"
#include "power.h"
#include "ota.h"
#include <WiFi.h>

// ============================================================
//  Key codes matching USB HID usage table (Arduino USBHIDKeyboard)
// ============================================================
#define KEY_RETURN      0xB0
#define KEY_LEFT_ARROW  0xD8
#define KEY_RIGHT_ARROW 0xD7
#define KEY_UP_ARROW    0xDA
#define KEY_DOWN_ARROW  0xD9
#define KEY_PRINT_SCREEN 0xCE

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
#define CLR_DPURPLE 0x7B1FA2
#define CLR_MAGENTA 0xAD1457

// ============================================================
//  Hotkey Data Structures
// ============================================================

struct Hotkey {
    const char *label;
    const char *description;
    uint8_t modifiers;
    uint8_t keycode;
    uint32_t color;
    const char *icon;
    bool is_media;
    uint16_t consumer_code;
};

// Helper: Convert ButtonConfig to Hotkey for rendering
// (store label/description in static buffer - only valid for single call)
static Hotkey button_config_to_hotkey(const ButtonConfig& btn) {
    Hotkey hk;
    hk.label = btn.label.c_str();
    hk.description = btn.description.c_str();
    hk.modifiers = btn.modifiers;
    hk.keycode = btn.keycode;
    hk.color = btn.color;
    hk.icon = btn.icon.c_str();
    hk.is_media = (btn.action_type == ACTION_MEDIA_KEY);
    hk.consumer_code = btn.consumer_code;
    return hk;
}

struct HotkeyPage {
    const char *name;
    const Hotkey *hotkeys;
    uint8_t count;
};

// ============================================================
//  Page 1: Hyprland Window Management (12 keys)
// ============================================================
static const Hotkey page1_hotkeys[] = {
    {"WS 1",       "Super+1",          MOD_GUI,               '1',             CLR_BLUE,   LV_SYMBOL_HOME,     false, 0},
    {"WS 2",       "Super+2",          MOD_GUI,               '2',             CLR_BLUE,   LV_SYMBOL_HOME,     false, 0},
    {"WS 3",       "Super+3",          MOD_GUI,               '3',             CLR_BLUE,   LV_SYMBOL_HOME,     false, 0},
    {"WS 4",       "Super+4",          MOD_GUI,               '4',             CLR_BLUE,   LV_SYMBOL_HOME,     false, 0},
    {"Focus L",    "Super+Left",       MOD_GUI,               KEY_LEFT_ARROW,  CLR_TEAL,   LV_SYMBOL_LEFT,     false, 0},
    {"Focus R",    "Super+Right",      MOD_GUI,               KEY_RIGHT_ARROW, CLR_TEAL,   LV_SYMBOL_RIGHT,    false, 0},
    {"Focus Up",   "Super+Up",         MOD_GUI,               KEY_UP_ARROW,    CLR_TEAL,   LV_SYMBOL_UP,       false, 0},
    {"Focus Dn",   "Super+Down",       MOD_GUI,               KEY_DOWN_ARROW,  CLR_TEAL,   LV_SYMBOL_DOWN,     false, 0},
    {"Kill",       "Super+Q",          MOD_GUI,               'q',             CLR_RED,    LV_SYMBOL_CLOSE,    false, 0},
    {"Fullscr",    "Super+F",          MOD_GUI,               'f',             CLR_CYAN,   LV_SYMBOL_NEW_LINE, false, 0},
    {"Float",      "Super+Sh+Space",   MOD_GUI | MOD_SHIFT,   ' ',             CLR_INDIGO, LV_SYMBOL_SHUFFLE,  false, 0},
    {"WS 5",       "Super+5",          MOD_GUI,               '5',             CLR_BLUE,   LV_SYMBOL_HOME,     false, 0},
};

// ============================================================
//  Page 2: Hyprland System Actions (12 keys)
// ============================================================
static const Hotkey page2_hotkeys[] = {
    {"Terminal",   "Super+Enter",      MOD_GUI,               KEY_RETURN,      CLR_GREEN,  LV_SYMBOL_KEYBOARD, false, 0},
    {"Files",      "Super+T",          MOD_GUI,               't',             CLR_ORANGE, LV_SYMBOL_DIRECTORY,false, 0},
    {"Launcher",   "Super+D",          MOD_GUI,               'd',             CLR_LIME,   LV_SYMBOL_LIST,     false, 0},
    {"Browser",    "Super+B",          MOD_GUI,               'b',             CLR_BLUE,   LV_SYMBOL_EYE_OPEN, false, 0},
    {"ScreenSel",  "Super+Sh+S",       MOD_GUI | MOD_SHIFT,   's',             CLR_PINK,   LV_SYMBOL_IMAGE,    false, 0},
    {"ScreenFull", "Print",            MOD_NONE,              KEY_PRINT_SCREEN,CLR_PINK,   LV_SYMBOL_IMAGE,    false, 0},
    {"ColorPick",  "Super+Sh+C",       MOD_GUI | MOD_SHIFT,   'c',             CLR_AMBER,  LV_SYMBOL_EYE_OPEN, false, 0},
    {"Lock",       "Super+L",          MOD_GUI,               'l',             CLR_RED,    LV_SYMBOL_EYE_CLOSE,false, 0},
    {"Logout",     "Super+Sh+Q",       MOD_GUI | MOD_SHIFT,   'q',             CLR_RED,    LV_SYMBOL_WARNING,  false, 0},
    {"Notify",     "Super+N",          MOD_GUI,               'n',             CLR_TEAL,   LV_SYMBOL_BELL,     false, 0},
    {"Clipboard",  "Super+V",          MOD_GUI,               'v',             CLR_GREEN,  LV_SYMBOL_PASTE,    false, 0},
    {"Settings",   "Super+I",          MOD_GUI,               'i',             CLR_GREY,   LV_SYMBOL_SETTINGS, false, 0},
};

// ============================================================
//  Page 3: Media + Extras (12 keys)
//  First 6: media keys (is_media=true, consumer control codes)
//  Last 6: keyboard shortcuts
// ============================================================
static const Hotkey page3_hotkeys[] = {
    // Media keys (consumer control)
    {"Play",       "Play/Pause",       MOD_NONE, 0, CLR_DPURPLE, LV_SYMBOL_PLAY,    true, 0x00CD},
    {"Next",       "Next Track",       MOD_NONE, 0, CLR_DPURPLE, LV_SYMBOL_NEXT,    true, 0x00B5},
    {"Prev",       "Prev Track",       MOD_NONE, 0, CLR_DPURPLE, LV_SYMBOL_PREV,    true, 0x00B4},
    {"Vol Up",     "Volume Up",        MOD_NONE, 0, CLR_MAGENTA, LV_SYMBOL_VOLUME_MAX,  true, 0x00E9},
    {"Vol Down",   "Volume Down",      MOD_NONE, 0, CLR_MAGENTA, LV_SYMBOL_VOLUME_MID,  true, 0x00EA},
    {"Mute",       "Mute",             MOD_NONE, 0, CLR_MAGENTA, LV_SYMBOL_MUTE,    true, 0x00E2},
    // Extra keyboard shortcuts
    {"WS 6",       "Super+6",          MOD_GUI,               '6',  CLR_BLUE,   LV_SYMBOL_HOME,     false, 0},
    {"WS 7",       "Super+7",          MOD_GUI,               '7',  CLR_BLUE,   LV_SYMBOL_HOME,     false, 0},
    {"WS 8",       "Super+8",          MOD_GUI,               '8',  CLR_BLUE,   LV_SYMBOL_HOME,     false, 0},
    {"Move L",     "Super+Ctrl+H",     MOD_GUI | MOD_CTRL,    'h',  CLR_CYAN,   LV_SYMBOL_LEFT,     false, 0},
    {"Move R",     "Super+Ctrl+L",     MOD_GUI | MOD_CTRL,    'l',  CLR_CYAN,   LV_SYMBOL_RIGHT,    false, 0},
    {"Resize",     "Super+R",          MOD_GUI,               'r',  CLR_ORANGE, LV_SYMBOL_LOOP,     false, 0},
};

// Page configuration
static const HotkeyPage pages[] = {
    {"Windows", page1_hotkeys, sizeof(page1_hotkeys) / sizeof(Hotkey)},
    {"System",  page2_hotkeys, sizeof(page2_hotkeys) / sizeof(Hotkey)},
    {"Media",   page3_hotkeys, sizeof(page3_hotkeys) / sizeof(Hotkey)},
};
static const uint8_t NUM_PAGES = sizeof(pages) / sizeof(HotkeyPage);

// ============================================================
//  UI State
// ============================================================
static lv_obj_t *tabview = nullptr;
static lv_obj_t *status_label = nullptr;
static lv_obj_t *stats_header = nullptr;
static bool stats_visible = false;

// Device status header labels
static lv_obj_t *rssi_label = nullptr;
static lv_obj_t *bright_btn = nullptr;

// Global config reference (set by create_ui)
static const AppConfig *g_active_config = nullptr;

// Clock mode screen
static lv_obj_t *main_screen = nullptr;
static lv_obj_t *clock_screen = nullptr;
static lv_obj_t *clock_time_label = nullptr;
static lv_obj_t *clock_rssi_label = nullptr;

// OTA screen
static lv_obj_t *ota_screen = nullptr;
static lv_obj_t *ota_ip_label = nullptr;

// Stats header labels (row 1: cpu%, ram%, gpu%, cpu_temp, gpu_temp; row 2: net_up, net_down, disk%)
static lv_obj_t *stat_labels[8] = {};

// Forward declarations
void update_clock_time();
void show_ota_screen(const char *ip);
void hide_ota_screen();

// ============================================================
//  Brightness Button Callback
// ============================================================
static void brightness_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        power_cycle_brightness();
    }
}

// ============================================================
//  Button Event Handler
// ============================================================
static void btn_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        const Hotkey *hk = (const Hotkey *)lv_event_get_user_data(e);
        if (hk) {
            if (hk->is_media) {
                send_media_key_to_bridge(hk->consumer_code);
            } else {
                send_hotkey_to_bridge(hk->modifiers, hk->keycode);
            }

            // Update status bar
            if (status_label) {
                lv_label_set_text_fmt(status_label, LV_SYMBOL_OK " Sent: %s (%s)", hk->label, hk->description);
            }

            Serial.printf("Hotkey: %s (%s) mod=0x%02X key=0x%02X media=%d\n",
                          hk->label, hk->description, hk->modifiers, hk->keycode, hk->is_media);
        }
    }
}

// ============================================================
//  Button Creation
// ============================================================
static lv_obj_t *create_hotkey_button(lv_obj_t *parent, const Hotkey *hk) {
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_set_size(btn, 170, 90);
    lv_obj_add_flag(btn, LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_obj_add_event_cb(btn, btn_event_cb, LV_EVENT_CLICKED, (void *)hk);

    // Normal style
    lv_obj_set_style_bg_color(btn, lv_color_hex(hk->color), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(btn, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(btn, 12, LV_PART_MAIN);
    lv_obj_set_style_shadow_width(btn, 8, LV_PART_MAIN);
    lv_obj_set_style_shadow_ofs_y(btn, 4, LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(btn, LV_OPA_30, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn, 0, LV_PART_MAIN);

    // Pressed style: darken + shrink for visual feedback (DISP-03)
    lv_obj_set_style_bg_color(btn, lv_color_darken(lv_color_hex(hk->color), LV_OPA_30), LV_STATE_PRESSED);
    lv_obj_set_style_transform_width(btn, -3, LV_STATE_PRESSED);
    lv_obj_set_style_transform_height(btn, -3, LV_STATE_PRESSED);

    // Column flex layout: icon -> label -> description
    lv_obj_set_flex_flow(btn, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(btn, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_all(btn, 8, LV_PART_MAIN);

    // Icon
    if (hk->icon) {
        lv_obj_t *icon = lv_label_create(btn);
        lv_label_set_text(icon, hk->icon);
        lv_obj_set_style_text_font(icon, &lv_font_montserrat_22, LV_PART_MAIN);
        lv_obj_set_style_text_color(icon, lv_color_white(), LV_PART_MAIN);
    }

    // Label
    lv_obj_t *label = lv_label_create(btn);
    lv_label_set_text(label, hk->label);
    lv_obj_set_style_text_font(label, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_style_text_color(label, lv_color_white(), LV_PART_MAIN);

    // Description sublabel
    lv_obj_t *sub = lv_label_create(btn);
    lv_label_set_text(sub, hk->description);
    lv_obj_set_style_text_font(sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_style_text_color(sub, lv_color_make(200, 200, 200), LV_PART_MAIN);

    return btn;
}

// ============================================================
//  Page Creation
// ============================================================
static void create_hotkey_page(lv_obj_t *tab, const HotkeyPage &page) {
    // Grid layout: 4 columns x 3 rows with wrap
    lv_obj_set_flex_flow(tab, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(tab, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_SPACE_EVENLY);
    lv_obj_set_style_pad_all(tab, 10, LV_PART_MAIN);
    lv_obj_set_style_pad_row(tab, 10, LV_PART_MAIN);
    lv_obj_set_style_pad_column(tab, 10, LV_PART_MAIN);
    lv_obj_set_style_bg_color(tab, lv_color_hex(0x1a1a2e), LV_PART_MAIN);

    for (uint8_t i = 0; i < page.count; i++) {
        create_hotkey_button(tab, &page.hotkeys[i]);
    }
}

// ============================================================
//  Stats Header: helper to create a stat label with color
// ============================================================
static lv_obj_t *create_stat_label(lv_obj_t *parent, const char *text, uint32_t color) {
    lv_obj_t *lbl = lv_label_create(parent);
    lv_label_set_text(lbl, text);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl, lv_color_hex(color), LV_PART_MAIN);
    return lbl;
}

// ============================================================
//  Stats Header: create the two-row header container
// ============================================================
static void create_stats_header() {
    stats_header = lv_obj_create(lv_scr_act());
    lv_obj_set_size(stats_header, SCREEN_WIDTH, 90);
    lv_obj_align(stats_header, LV_ALIGN_TOP_MID, 0, 45);
    lv_obj_set_style_bg_color(stats_header, lv_color_hex(0x0d1b2a), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(stats_header, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_width(stats_header, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(stats_header, 0, LV_PART_MAIN);
    lv_obj_clear_flag(stats_header, LV_OBJ_FLAG_SCROLLABLE);

    // Start hidden
    lv_obj_add_flag(stats_header, LV_OBJ_FLAG_HIDDEN);

    // Row 1 container (top 45px): CPU%, RAM%, GPU%, CPU temp, GPU temp
    lv_obj_t *row1 = lv_obj_create(stats_header);
    lv_obj_set_size(row1, SCREEN_WIDTH - 20, 40);
    lv_obj_align(row1, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_bg_opa(row1, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(row1, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(row1, 0, LV_PART_MAIN);
    lv_obj_clear_flag(row1, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(row1, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(row1, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    // Colors: CPU blue, RAM green, GPU orange, CPU temp red, GPU temp yellow
    stat_labels[0] = create_stat_label(row1, "CPU --%",  0x3498DB);  // cpu_percent
    stat_labels[1] = create_stat_label(row1, "RAM --%",  0x2ECC71);  // ram_percent
    stat_labels[2] = create_stat_label(row1, "GPU --%",  0xE67E22);  // gpu_percent
    stat_labels[3] = create_stat_label(row1, "CPU --\xC2\xB0""C", 0xE74C3C);  // cpu_temp
    stat_labels[4] = create_stat_label(row1, "GPU --\xC2\xB0""C", 0xF1C40F);  // gpu_temp

    // Row 2 container (bottom 45px): Net up, Net down, Disk%
    lv_obj_t *row2 = lv_obj_create(stats_header);
    lv_obj_set_size(row2, SCREEN_WIDTH - 20, 40);
    lv_obj_align(row2, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_opa(row2, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(row2, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(row2, 0, LV_PART_MAIN);
    lv_obj_clear_flag(row2, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(row2, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(row2, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    // Colors: network teal, disk grey
    stat_labels[5] = create_stat_label(row2, LV_SYMBOL_UPLOAD " -- KB/s",   0x1ABC9C);  // net_up
    stat_labels[6] = create_stat_label(row2, LV_SYMBOL_DOWNLOAD " -- KB/s", 0x1ABC9C);  // net_down
    stat_labels[7] = create_stat_label(row2, "Disk --%",                     0x7F8C8D);  // disk_percent
}

// ============================================================
//  Public: update_stats() -- Update stats header with new data
// ============================================================
void update_stats(const StatsPayload *stats) {
    if (!stats_header || !stats) return;

    // Show header if hidden
    if (!stats_visible) {
        lv_obj_clear_flag(stats_header, LV_OBJ_FLAG_HIDDEN);
        stats_visible = true;
        // Resize tabview to make room for stats header
        lv_obj_set_size(tabview, SCREEN_WIDTH, SCREEN_HEIGHT - 45 - 90);
        lv_obj_align(tabview, LV_ALIGN_BOTTOM_MID, 0, 0);
    }

    // Helper lambda for unavailable values
    auto fmt_pct = [](lv_obj_t *lbl, const char *prefix, uint8_t val) {
        if (val == 0xFF)
            lv_label_set_text_fmt(lbl, "%s N/A", prefix);
        else
            lv_label_set_text_fmt(lbl, "%s %d%%", prefix, val);
    };

    auto fmt_temp = [](lv_obj_t *lbl, const char *prefix, uint8_t val) {
        if (val == 0xFF)
            lv_label_set_text_fmt(lbl, "%s N/A", prefix);
        else
            lv_label_set_text_fmt(lbl, "%s %d\xC2\xB0""C", prefix, val);
    };

    // Row 1
    fmt_pct(stat_labels[0], "CPU", stats->cpu_percent);
    fmt_pct(stat_labels[1], "RAM", stats->ram_percent);
    fmt_pct(stat_labels[2], "GPU", stats->gpu_percent);
    fmt_temp(stat_labels[3], "CPU", stats->cpu_temp);
    fmt_temp(stat_labels[4], "GPU", stats->gpu_temp);

    // Row 2 - network
    if (stats->net_up_kbps >= 1024)
        lv_label_set_text_fmt(stat_labels[5], LV_SYMBOL_UPLOAD " %.1f MB/s", stats->net_up_kbps / 1024.0f);
    else
        lv_label_set_text_fmt(stat_labels[5], LV_SYMBOL_UPLOAD " %d KB/s", stats->net_up_kbps);

    if (stats->net_down_kbps >= 1024)
        lv_label_set_text_fmt(stat_labels[6], LV_SYMBOL_DOWNLOAD " %.1f MB/s", stats->net_down_kbps / 1024.0f);
    else
        lv_label_set_text_fmt(stat_labels[6], LV_SYMBOL_DOWNLOAD " %d KB/s", stats->net_down_kbps);

    fmt_pct(stat_labels[7], "Disk", stats->disk_percent);
}

// ============================================================
//  Public: hide_stats_header() -- Hide stats header on timeout
// ============================================================
void hide_stats_header() {
    if (!stats_header || !stats_visible) return;

    lv_obj_add_flag(stats_header, LV_OBJ_FLAG_HIDDEN);
    stats_visible = false;

    // Restore tabview to full size
    lv_obj_set_size(tabview, SCREEN_WIDTH, SCREEN_HEIGHT - 45);
    lv_obj_align(tabview, LV_ALIGN_BOTTOM_MID, 0, 0);
}

// ============================================================
//  Public: update_device_status() -- Update header indicators
// ============================================================
void update_device_status(int rssi_dbm, bool espnow_linked, uint8_t brightness_level) {
    // WiFi signal icon -- color reflects signal strength
    if (rssi_label) {
        if (rssi_dbm == 0 || !espnow_linked) {
            lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
        } else if (rssi_dbm > -50) {
            lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_GREEN), LV_PART_MAIN);
        } else if (rssi_dbm > -70) {
            lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_YELLOW), LV_PART_MAIN);
        } else {
            lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_RED), LV_PART_MAIN);
        }
    }

    (void)brightness_level;
}

// ============================================================
//  Public: show_clock_mode() -- Switch to clock screen
// ============================================================
void show_clock_mode() {
    if (clock_screen) {
        update_clock_time();
        lv_scr_load(clock_screen);
    }
}

// ============================================================
//  Public: show_hotkey_view() -- Switch back to main screen
// ============================================================
void show_hotkey_view() {
    if (main_screen) {
        lv_scr_load(main_screen);
    }
}

// ============================================================
//  Public: update_clock_time() -- Refresh clock display
// ============================================================
void update_clock_time() {
    if (!clock_time_label || !clock_rssi_label) return;

    time_t now = time(nullptr);
    struct tm *tm = localtime(&now);
    lv_label_set_text_fmt(clock_time_label, "%02d:%02d", tm->tm_hour, tm->tm_min);

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
//  OTA Button Callback
// ============================================================
static void ota_btn_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        if (!ota_active()) {
            if (ota_start()) {
                show_ota_screen(WiFi.softAPIP().toString().c_str());
            }
        } else {
            ota_stop();
            hide_ota_screen();
        }
    }
}

// ============================================================
//  Public: show_ota_screen() -- Show OTA mode overlay
// ============================================================
void show_ota_screen(const char *ip) {
    if (!ota_screen) return;
    if (ota_ip_label) {
        lv_label_set_text_fmt(ota_ip_label,
            "Connect to WiFi: CrowPanel-OTA\nPassword: crowpanel\n\n"
            "Web upload: http://%s\n"
            "PlatformIO: pio run -t upload --upload-port %s\n\n"
            "Tap " LV_SYMBOL_WIFI " to exit OTA mode", ip, ip);
    }
    lv_scr_load(ota_screen);
}

// ============================================================
//  Public: hide_ota_screen() -- Return to main view
// ============================================================
void hide_ota_screen() {
    if (main_screen) {
        lv_scr_load(main_screen);
    }
}

// ============================================================
//  Public: create_ui() -- Build the complete hotkey tabview UI
// ============================================================
void create_ui(const AppConfig* cfg) {
    // Use provided config, or fall back to hardcoded defaults
    if (cfg) {
        g_active_config = cfg;
    } else {
        // Will use hardcoded pages[] array below
        g_active_config = nullptr;
    }
    // Save reference to the main screen before adding widgets
    main_screen = lv_scr_act();

    // Dark background
    lv_obj_set_style_bg_color(lv_scr_act(), lv_color_hex(0x0f0f23), LV_PART_MAIN);

    // Header bar (45px)
    lv_obj_t *header = lv_obj_create(lv_scr_act());
    lv_obj_set_size(header, SCREEN_WIDTH, 45);
    lv_obj_align(header, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_bg_color(header, lv_color_hex(0x16213e), LV_PART_MAIN);
    lv_obj_set_style_border_width(header, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(header, 0, LV_PART_MAIN);
    lv_obj_clear_flag(header, LV_OBJ_FLAG_SCROLLABLE);

    // Title on the left
    lv_obj_t *title = lv_label_create(header);
    lv_label_set_text(title, LV_SYMBOL_KEYBOARD "  Hotkeys");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_set_style_text_color(title, lv_color_hex(0xE0E0E0), LV_PART_MAIN);
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 15, 0);

    // Status label (center-ish)
    status_label = lv_label_create(header);
    lv_label_set_text(status_label, LV_SYMBOL_USB " Ready");
    lv_obj_set_style_text_font(status_label, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(status_label, lv_color_hex(0x2ECC71), LV_PART_MAIN);
    lv_obj_align(status_label, LV_ALIGN_CENTER, 0, 0);

    // Device status indicators on the right side of header
    // Battery label
    rssi_label = lv_label_create(header);
    lv_label_set_text(rssi_label, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_font(rssi_label, &lv_font_montserrat_18, LV_PART_MAIN);
    lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
    lv_obj_align(rssi_label, LV_ALIGN_RIGHT_MID, -15, 0);

    // OTA button (tappable)
    lv_obj_t *ota_btn = lv_label_create(header);
    lv_label_set_text(ota_btn, LV_SYMBOL_DOWNLOAD);
    lv_obj_set_style_text_font(ota_btn, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_style_text_color(ota_btn, lv_color_hex(CLR_CYAN), LV_PART_MAIN);
    lv_obj_align(ota_btn, LV_ALIGN_RIGHT_MID, -55, 0);
    lv_obj_add_flag(ota_btn, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(ota_btn, ota_btn_event_cb, LV_EVENT_CLICKED, nullptr);

    // Brightness button (tappable)
    bright_btn = lv_label_create(header);
    lv_label_set_text(bright_btn, LV_SYMBOL_IMAGE);
    lv_obj_set_style_text_font(bright_btn, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_style_text_color(bright_btn, lv_color_hex(CLR_YELLOW), LV_PART_MAIN);
    lv_obj_align(bright_btn, LV_ALIGN_RIGHT_MID, -95, 0);
    lv_obj_add_flag(bright_btn, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(bright_btn, brightness_event_cb, LV_EVENT_CLICKED, nullptr);

    // --- Clock mode screen (created but not loaded) ---
    clock_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(clock_screen, lv_color_hex(0x0f0f23), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(clock_screen, LV_OPA_COVER, LV_PART_MAIN);

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

    // --- OTA screen (created but not loaded) ---
    ota_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(ota_screen, lv_color_hex(0x0d1b2a), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(ota_screen, LV_OPA_COVER, LV_PART_MAIN);

    lv_obj_t *ota_title = lv_label_create(ota_screen);
    lv_label_set_text(ota_title, LV_SYMBOL_DOWNLOAD "  OTA Update Mode");
    lv_obj_set_style_text_font(ota_title, &lv_font_montserrat_28, LV_PART_MAIN);
    lv_obj_set_style_text_color(ota_title, lv_color_hex(CLR_CYAN), LV_PART_MAIN);
    lv_obj_align(ota_title, LV_ALIGN_TOP_MID, 0, 40);

    ota_ip_label = lv_label_create(ota_screen);
    lv_label_set_text(ota_ip_label, "Starting...");
    lv_obj_set_style_text_font(ota_ip_label, &lv_font_montserrat_18, LV_PART_MAIN);
    lv_obj_set_style_text_color(ota_ip_label, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_text_align(ota_ip_label, LV_TEXT_ALIGN_CENTER, LV_PART_MAIN);
    lv_obj_align(ota_ip_label, LV_ALIGN_CENTER, 0, 0);

    // Exit button on OTA screen
    lv_obj_t *ota_exit = lv_btn_create(ota_screen);
    lv_obj_set_size(ota_exit, 200, 50);
    lv_obj_align(ota_exit, LV_ALIGN_BOTTOM_MID, 0, -40);
    lv_obj_set_style_bg_color(ota_exit, lv_color_hex(CLR_RED), LV_PART_MAIN);
    lv_obj_add_event_cb(ota_exit, ota_btn_event_cb, LV_EVENT_CLICKED, nullptr);
    lv_obj_t *exit_lbl = lv_label_create(ota_exit);
    lv_label_set_text(exit_lbl, "Exit OTA Mode");
    lv_obj_center(exit_lbl);

    // Stats header (hidden by default, shown on first MSG_STATS)
    create_stats_header();

    // Tabview with bottom tabs (45px tab bar)
    // Initially full height (no stats header visible)
    tabview = lv_tabview_create(lv_scr_act(), LV_DIR_BOTTOM, 45);
    lv_obj_set_size(tabview, SCREEN_WIDTH, SCREEN_HEIGHT - 45);
    lv_obj_align(tabview, LV_ALIGN_BOTTOM_MID, 0, 0);

    // Style the tab buttons
    lv_obj_t *tab_btns = lv_tabview_get_tab_btns(tabview);
    lv_obj_set_style_bg_color(tab_btns, lv_color_hex(0x16213e), LV_PART_MAIN);
    lv_obj_set_style_text_color(tab_btns, lv_color_hex(0xBBBBBB), LV_PART_MAIN);
    lv_obj_set_style_text_color(tab_btns, lv_color_hex(0x3498DB), LV_PART_ITEMS | LV_STATE_CHECKED);
    lv_obj_set_style_border_color(tab_btns, lv_color_hex(0x3498DB), LV_PART_ITEMS | LV_STATE_CHECKED);
    lv_obj_set_style_text_font(tab_btns, &lv_font_montserrat_16, LV_PART_MAIN);

    // Create pages from config or hardcoded defaults
    if (g_active_config && !g_active_config->profiles.empty()) {
        // Use AppConfig: create pages from active profile
        const ProfileConfig* active_profile = g_active_config->get_active_profile();
        if (active_profile) {
            for (size_t i = 0; i < active_profile->pages.size(); i++) {
                const PageConfig& page = active_profile->pages[i];
                lv_obj_t *tab = lv_tabview_add_tab(tabview, page.name.c_str());

                // Create buttons from config
                lv_obj_set_flex_flow(tab, LV_FLEX_FLOW_ROW_WRAP);
                lv_obj_set_flex_align(tab, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_SPACE_EVENLY);
                lv_obj_set_style_pad_all(tab, 10, LV_PART_MAIN);
                lv_obj_set_style_pad_row(tab, 10, LV_PART_MAIN);
                lv_obj_set_style_pad_column(tab, 10, LV_PART_MAIN);
                lv_obj_set_style_bg_color(tab, lv_color_hex(0x1a1a2e), LV_PART_MAIN);

                for (const auto& btn_cfg : page.buttons) {
                    // Create temporary Hotkey from ButtonConfig for rendering
                    Hotkey hk = button_config_to_hotkey(btn_cfg);
                    create_hotkey_button(tab, &hk);
                }
            }
            Serial.printf("UI created from config: %zu page(s)\n", active_profile->pages.size());
        } else {
            Serial.println("UI: Active profile not found, falling back to hardcoded defaults");
            // Fall through to hardcoded pages below
            g_active_config = nullptr;
        }
    }

    // Create pages from hardcoded defaults (if no config)
    if (!g_active_config) {
        for (uint8_t i = 0; i < NUM_PAGES; i++) {
            lv_obj_t *tab = lv_tabview_add_tab(tabview, pages[i].name);
            create_hotkey_page(tab, pages[i]);
        }
        Serial.println("UI created: 3 pages, 36 buttons (hardcoded defaults)");
    }

    Serial.println("UI initialized: stats header, device status, clock screen ready");
}

// ============================================================
//  Public: rebuild_ui() -- Recreate UI from new AppConfig
// ============================================================
void rebuild_ui(const AppConfig* cfg) {
    if (!cfg) {
        Serial.println("rebuild_ui: Config is nullptr, ignoring");
        return;
    }

    if (!tabview) {
        Serial.println("rebuild_ui: Tabview not initialized");
        return;
    }

    // Delete and recreate tabview (LVGL 8.3 has no lv_tabview_remove_tab)
    lv_obj_del(tabview);
    tabview = lv_tabview_create(lv_scr_act(), LV_DIR_BOTTOM, 45);
    lv_obj_set_size(tabview, 800, 480 - 45);
    lv_obj_align(tabview, LV_ALIGN_BOTTOM_MID, 0, 0);

    // Update active config
    g_active_config = cfg;

    // Recreate pages
    const ProfileConfig* active_profile = cfg->get_active_profile();
    if (active_profile) {
        for (size_t i = 0; i < active_profile->pages.size(); i++) {
            const PageConfig& page = active_profile->pages[i];
            lv_obj_t *tab = lv_tabview_add_tab(tabview, page.name.c_str());

            // Create buttons from config
            lv_obj_set_flex_flow(tab, LV_FLEX_FLOW_ROW_WRAP);
            lv_obj_set_flex_align(tab, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_SPACE_EVENLY);
            lv_obj_set_style_pad_all(tab, 10, LV_PART_MAIN);
            lv_obj_set_style_pad_row(tab, 10, LV_PART_MAIN);
            lv_obj_set_style_pad_column(tab, 10, LV_PART_MAIN);
            lv_obj_set_style_bg_color(tab, lv_color_hex(0x1a1a2e), LV_PART_MAIN);

            for (const auto& btn_cfg : page.buttons) {
                Hotkey hk = button_config_to_hotkey(btn_cfg);
                create_hotkey_button(tab, &hk);
            }
        }
        Serial.printf("UI rebuilt: %zu page(s) from config\n", active_profile->pages.size());
    } else {
        Serial.println("rebuild_ui: Active profile not found");
    }
}
