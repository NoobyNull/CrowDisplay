/**
 * @file main.cpp
 * Hotkey Display for Elcrow 7.0" CrowPanel (ESP32-S3)
 * 
 * Displays a grid of customizable hotkey buttons on the touchscreen.
 * When touched, sends the corresponding keyboard shortcut via USB HID.
 * 
 * Features:
 * - 3x4 grid of touch buttons (12 hotkeys per page)
 * - Multiple pages via tab navigation
 * - Visual feedback on press
 * - USB HID keyboard output
 */

#include <Arduino.h>
#include <lvgl.h>
#include "display_driver.h"
#include "usb_hid.h"

// ══════════════════════════════════════════════════════════════
//  HOTKEY DEFINITIONS - Customize your hotkeys here!
// ══════════════════════════════════════════════════════════════

// Color palette (LVGL hex colors)
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

// ── Page 1: General Shortcuts ──
static const Hotkey page1_hotkeys[] = {
    {"Copy",      "Ctrl+C",         MOD_CTRL,             'c', CLR_BLUE,   LV_SYMBOL_COPY},
    {"Paste",     "Ctrl+V",         MOD_CTRL,             'v', CLR_GREEN,  LV_SYMBOL_PASTE},
    {"Cut",       "Ctrl+X",         MOD_CTRL,             'x', CLR_ORANGE, LV_SYMBOL_CUT},
    {"Undo",      "Ctrl+Z",         MOD_CTRL,             'z', CLR_RED,    LV_SYMBOL_LEFT},
    {"Redo",      "Ctrl+Shift+Z",   MOD_CTRL | MOD_SHIFT, 'z', CLR_PURPLE, LV_SYMBOL_RIGHT},
    {"Save",      "Ctrl+S",         MOD_CTRL,             's', CLR_TEAL,   LV_SYMBOL_SAVE},
    {"Select All", "Ctrl+A",        MOD_CTRL,             'a', CLR_PINK,   LV_SYMBOL_LIST},
    {"Find",      "Ctrl+F",         MOD_CTRL,             'f', CLR_YELLOW, LV_SYMBOL_EYE_OPEN},
    {"New",       "Ctrl+N",         MOD_CTRL,             'n', CLR_BLUE,   LV_SYMBOL_FILE},
    {"Print",     "Ctrl+P",         MOD_CTRL,             'p', CLR_GREY,   LV_SYMBOL_CHARGE},
    {"Close",     "Ctrl+W",         MOD_CTRL,             'w', CLR_RED,    LV_SYMBOL_CLOSE},
    {"Refresh",   "Ctrl+R",         MOD_CTRL,             'r', CLR_GREEN,  LV_SYMBOL_REFRESH},
};

// ── Page 2: Window Management ──
static const Hotkey page2_hotkeys[] = {
    {"Desktop",   "Win+D",          MOD_GUI,              'd', CLR_BLUE,   LV_SYMBOL_HOME},
    {"Task View", "Win+Tab",        MOD_GUI,              KEY_TAB, CLR_PURPLE, LV_SYMBOL_LIST},
    {"Lock",      "Win+L",          MOD_GUI,              'l', CLR_RED,    LV_SYMBOL_EYE_CLOSE},
    {"Explorer",  "Win+E",          MOD_GUI,              'e', CLR_ORANGE, LV_SYMBOL_DIRECTORY},
    {"Settings",  "Win+I",          MOD_GUI,              'i', CLR_TEAL,   LV_SYMBOL_SETTINGS},
    {"Snap Left", "Win+Left",       MOD_GUI,              KEY_LEFT_ARROW, CLR_GREEN, LV_SYMBOL_LEFT},
    {"Snap Right","Win+Right",      MOD_GUI,              KEY_RIGHT_ARROW, CLR_GREEN, LV_SYMBOL_RIGHT},
    {"Maximize",  "Win+Up",         MOD_GUI,              KEY_UP_ARROW, CLR_BLUE, LV_SYMBOL_UP},
    {"Minimize",  "Win+Down",       MOD_GUI,              KEY_DOWN_ARROW, CLR_GREY, LV_SYMBOL_DOWN},
    {"Screenshot","Win+Shift+S",    MOD_GUI | MOD_SHIFT,  's', CLR_PINK,   LV_SYMBOL_IMAGE},
    {"Task Mgr",  "Ctrl+Shift+Esc", MOD_CTRL | MOD_SHIFT, KEY_ESC, CLR_RED, LV_SYMBOL_WARNING},
    {"Alt+Tab",   "Alt+Tab",        MOD_ALT,              KEY_TAB, CLR_DARK, LV_SYMBOL_SHUFFLE},
};

// ── Page 3: Media & Dev ──
static const Hotkey page3_hotkeys[] = {
    {"Play/Pause","Media Play",     MOD_CONSUMER,         MEDIA_PLAY_PAUSE, CLR_GREEN,  LV_SYMBOL_PLAY},
    {"Next",      "Media Next",     MOD_CONSUMER,         MEDIA_NEXT,       CLR_BLUE,   LV_SYMBOL_NEXT},
    {"Prev",      "Media Prev",     MOD_CONSUMER,         MEDIA_PREV,       CLR_BLUE,   LV_SYMBOL_PREV},
    {"Vol Up",    "Volume Up",      MOD_CONSUMER,         MEDIA_VOL_UP,     CLR_TEAL,   LV_SYMBOL_VOLUME_MAX},
    {"Vol Down",  "Volume Down",    MOD_CONSUMER,         MEDIA_VOL_DOWN,   CLR_TEAL,   LV_SYMBOL_VOLUME_MID},
    {"Mute",      "Mute",           MOD_CONSUMER,         MEDIA_MUTE,       CLR_RED,    LV_SYMBOL_MUTE},
    {"Terminal",  "Ctrl+`",         MOD_CTRL,             '`', CLR_DARK,   LV_SYMBOL_KEYBOARD},
    {"Comment",   "Ctrl+/",         MOD_CTRL,             '/', CLR_GREY,   LV_SYMBOL_EDIT},
    {"Format",    "Ctrl+Shift+F",   MOD_CTRL | MOD_SHIFT, 'f', CLR_PURPLE, LV_SYMBOL_LOOP},
    {"Debug",     "F5",             MOD_NONE,             KEY_F5, CLR_GREEN, LV_SYMBOL_RIGHT},
    {"Build",     "Ctrl+Shift+B",   MOD_CTRL | MOD_SHIFT, 'b', CLR_ORANGE, LV_SYMBOL_DOWNLOAD},
    {"Palette",   "Ctrl+Shift+P",   MOD_CTRL | MOD_SHIFT, 'p', CLR_PINK,   LV_SYMBOL_KEYBOARD},
};

// Page configuration
struct HotkeyPage {
    const char *name;
    const Hotkey *hotkeys;
    uint8_t count;
};

static const HotkeyPage pages[] = {
    {"General",   page1_hotkeys, sizeof(page1_hotkeys) / sizeof(Hotkey)},
    {"Windows",   page2_hotkeys, sizeof(page2_hotkeys) / sizeof(Hotkey)},
    {"Media/Dev", page3_hotkeys, sizeof(page3_hotkeys) / sizeof(Hotkey)},
};
static const uint8_t NUM_PAGES = sizeof(pages) / sizeof(HotkeyPage);

// ══════════════════════════════════════════════════════════════
//  UI CREATION
// ══════════════════════════════════════════════════════════════

static lv_obj_t *tabview = nullptr;
static lv_obj_t *status_label = nullptr;

// Button event handler
static void btn_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        const Hotkey *hk = (const Hotkey *)lv_event_get_user_data(e);
        if (hk) {
            send_hotkey(*hk);
            // Update status bar
            if (status_label) {
                lv_label_set_text_fmt(status_label, LV_SYMBOL_OK " Sent: %s (%s)", hk->label, hk->description);
            }
        }
    }
}

static lv_obj_t *create_hotkey_button(lv_obj_t *parent, const Hotkey *hk) {
    // Button container
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_set_size(btn, 170, 90);
    lv_obj_add_flag(btn, LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_obj_add_event_cb(btn, btn_event_cb, LV_EVENT_CLICKED, (void *)hk);

    // Style
    lv_obj_set_style_bg_color(btn, lv_color_hex(hk->color), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(btn, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(btn, 12, LV_PART_MAIN);
    lv_obj_set_style_shadow_width(btn, 8, LV_PART_MAIN);
    lv_obj_set_style_shadow_ofs_y(btn, 4, LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(btn, LV_OPA_30, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn, 0, LV_PART_MAIN);

    // Pressed style
    lv_obj_set_style_bg_color(btn, lv_color_darken(lv_color_hex(hk->color), LV_OPA_30), LV_STATE_PRESSED);
    lv_obj_set_style_transform_width(btn, -3, LV_STATE_PRESSED);
    lv_obj_set_style_transform_height(btn, -3, LV_STATE_PRESSED);

    // Layout inside button
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

    // Shortcut sublabel
    lv_obj_t *sub = lv_label_create(btn);
    lv_label_set_text(sub, hk->description);
    lv_obj_set_style_text_font(sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_style_text_color(sub, lv_color_make(200, 200, 200), LV_PART_MAIN);

    return btn;
}

static void create_hotkey_page(lv_obj_t *tab, const HotkeyPage &page) {
    // Grid layout: 4 columns x 3 rows
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

static void create_ui(void) {
    // Dark background
    lv_obj_set_style_bg_color(lv_scr_act(), lv_color_hex(0x0f0f23), LV_PART_MAIN);

    // Title bar
    lv_obj_t *header = lv_obj_create(lv_scr_act());
    lv_obj_set_size(header, SCREEN_WIDTH, 45);
    lv_obj_align(header, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_bg_color(header, lv_color_hex(0x16213e), LV_PART_MAIN);
    lv_obj_set_style_border_width(header, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(header, 0, LV_PART_MAIN);
    lv_obj_clear_flag(header, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *title = lv_label_create(header);
    lv_label_set_text(title, LV_SYMBOL_KEYBOARD "  Hotkey Display");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_set_style_text_color(title, lv_color_hex(0xE0E0E0), LV_PART_MAIN);
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 15, 0);

    // Status label in header
    status_label = lv_label_create(header);
    lv_label_set_text(status_label, LV_SYMBOL_USB " Ready");
    lv_obj_set_style_text_font(status_label, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(status_label, lv_color_hex(0x2ECC71), LV_PART_MAIN);
    lv_obj_align(status_label, LV_ALIGN_RIGHT_MID, -15, 0);

    // Tab view for pages
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

    // Create pages
    for (uint8_t i = 0; i < NUM_PAGES; i++) {
        lv_obj_t *tab = lv_tabview_add_tab(tabview, pages[i].name);
        create_hotkey_page(tab, pages[i]);
    }
}

// ══════════════════════════════════════════════════════════════
//  ARDUINO SETUP & LOOP
// ══════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    Serial0.begin(115200);
    Serial0.println("Hotkey Display starting...");

    // Initialize display
    display_init();
    Serial.println("Display initialized");

    // Initialize LVGL
    lvgl_init();
    Serial.println("LVGL initialized");

    // Initialize USB HID
    usb_hid_init();
    Serial.println("USB HID initialized");

    // Build the UI
    create_ui();
    Serial0.println("UI created");
    Serial0.println("Setup complete - touch should be working!");
}

void loop() {
    lvgl_tick();
    delay(5);
}
