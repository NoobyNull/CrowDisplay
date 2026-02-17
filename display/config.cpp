#include "config.h"
#include "sdcard.h"
#include <ArduinoJson.h>
#include <Arduino.h>
#include <lvgl.h>
#include "protocol.h"

// ============================================================
// Default/Builtin Profiles (hardcoded fallback) — v2 format
// ============================================================

// Helper: create a hotkey button widget at absolute position
static WidgetConfig make_hotkey(int16_t x, int16_t y, int16_t w, int16_t h,
                                 const char* label, const char* desc, uint32_t color,
                                 const char* icon, uint8_t mods, uint8_t key,
                                 ActionType atype = ACTION_HOTKEY, uint16_t cc = 0) {
    WidgetConfig w_cfg;
    w_cfg.widget_type = WIDGET_HOTKEY_BUTTON;
    w_cfg.x = x; w_cfg.y = y; w_cfg.width = w; w_cfg.height = h;
    w_cfg.label = label;
    w_cfg.description = desc;
    w_cfg.color = color;
    w_cfg.icon = icon;
    w_cfg.action_type = atype;
    w_cfg.modifiers = mods;
    w_cfg.keycode = key;
    w_cfg.consumer_code = cc;
    return w_cfg;
}

AppConfig config_create_defaults() {
    AppConfig cfg;
    cfg.version = CONFIG_VERSION;
    cfg.active_profile_name = "Hyprland";
    cfg.brightness_level = 100;

    // Colors
    const uint32_t CLR_BLUE = 0x3498DB;
    const uint32_t CLR_TEAL = 0x1ABC9C;
    const uint32_t CLR_RED = 0xE74C3C;
    const uint32_t CLR_CYAN = 0x00BCD4;
    const uint32_t CLR_INDIGO = 0x3F51B5;
    const uint32_t CLR_GREEN = 0x2ECC71;
    const uint32_t CLR_ORANGE = 0xE67E22;
    const uint32_t CLR_LIME = 0x8BC34A;
    const uint32_t CLR_PINK = 0xE91E63;
    const uint32_t CLR_AMBER = 0xFFC107;
    const uint32_t CLR_GREY = 0x7F8C8D;
    const uint32_t CLR_PURPLE = 0x9B59B6;

    const uint8_t KEY_RETURN = 0xB0;
    const uint8_t KEY_LEFT_ARROW = 0xD8;
    const uint8_t KEY_RIGHT_ARROW = 0xD7;
    const uint8_t KEY_UP_ARROW = 0xDA;
    const uint8_t KEY_DOWN_ARROW = 0xD9;
    const uint8_t KEY_PRINT_SCREEN = 0xCE;

    // Default layout: 4x3 grid with 6px padding, matching old grid
    // Grid cell dimensions: (800 - 5*6) / 4 = 192.5 → 192, (390 - 4*6) / 3 = 122 → 122
    // Starting at y=45 (header area) + 6 padding
    const int16_t GRID_X0 = 6;
    const int16_t GRID_Y0 = 50;
    const int16_t CELL_W = 192;
    const int16_t CELL_H = 122;
    const int16_t GAP = 6;

    auto grid_pos = [&](int col, int row, int16_t& ox, int16_t& oy) {
        ox = GRID_X0 + col * (CELL_W + GAP);
        oy = GRID_Y0 + row * (CELL_H + GAP);
    };

    ProfileConfig hyprland;
    hyprland.name = "Hyprland";

    // ===== Page 1: Window Management =====
    {
        PageConfig page;
        page.name = "Window Manager";

        // Add a status bar at top
        WidgetConfig sb;
        sb.widget_type = WIDGET_STATUS_BAR;
        sb.x = 0; sb.y = 0; sb.width = 800; sb.height = 45;
        sb.label = "Hotkeys";
        sb.color = 0xE0E0E0;
        sb.bg_color = 0x16213e;
        page.widgets.push_back(sb);

        struct { const char* lbl; const char* desc; uint32_t clr; const char* ico; uint8_t mod; uint8_t key; } btns[] = {
            {"WS 1", "Super+1", CLR_BLUE, LV_SYMBOL_HOME, MOD_GUI, '1'},
            {"WS 2", "Super+2", CLR_BLUE, LV_SYMBOL_HOME, MOD_GUI, '2'},
            {"WS 3", "Super+3", CLR_BLUE, LV_SYMBOL_HOME, MOD_GUI, '3'},
            {"WS 4", "Super+4", CLR_BLUE, LV_SYMBOL_HOME, MOD_GUI, '4'},
            {"Focus L", "Super+Left", CLR_TEAL, LV_SYMBOL_LEFT, MOD_GUI, KEY_LEFT_ARROW},
            {"Focus R", "Super+Right", CLR_TEAL, LV_SYMBOL_RIGHT, MOD_GUI, KEY_RIGHT_ARROW},
            {"Focus Up", "Super+Up", CLR_TEAL, LV_SYMBOL_UP, MOD_GUI, KEY_UP_ARROW},
            {"Focus Dn", "Super+Down", CLR_TEAL, LV_SYMBOL_DOWN, MOD_GUI, KEY_DOWN_ARROW},
            {"Kill", "Super+Q", CLR_RED, LV_SYMBOL_CLOSE, MOD_GUI, 'q'},
            {"Fullscr", "Super+F", CLR_CYAN, LV_SYMBOL_NEW_LINE, MOD_GUI, 'f'},
            {"Float", "Super+Sh+Space", CLR_INDIGO, LV_SYMBOL_SHUFFLE, (uint8_t)(MOD_GUI | MOD_SHIFT), ' '},
            {"WS 5", "Super+5", CLR_BLUE, LV_SYMBOL_HOME, MOD_GUI, '5'},
        };

        for (int i = 0; i < 12; i++) {
            int16_t x, y;
            grid_pos(i % 4, i / 4, x, y);
            page.widgets.push_back(make_hotkey(x, y, CELL_W, CELL_H,
                btns[i].lbl, btns[i].desc, btns[i].clr, btns[i].ico,
                btns[i].mod, btns[i].key));
        }

        // Page nav at bottom
        WidgetConfig pn;
        pn.widget_type = WIDGET_PAGE_NAV;
        pn.x = 300; pn.y = 445; pn.width = 200; pn.height = 30;
        pn.color = 0x3498DB;
        page.widgets.push_back(pn);

        hyprland.pages.push_back(page);
    }

    // ===== Page 2: System Actions =====
    {
        PageConfig page;
        page.name = "System Actions";

        WidgetConfig sb;
        sb.widget_type = WIDGET_STATUS_BAR;
        sb.x = 0; sb.y = 0; sb.width = 800; sb.height = 45;
        sb.label = "Hotkeys";
        sb.color = 0xE0E0E0;
        sb.bg_color = 0x16213e;
        page.widgets.push_back(sb);

        struct { const char* lbl; const char* desc; uint32_t clr; const char* ico; uint8_t mod; uint8_t key; } btns[] = {
            {"Terminal", "Super+Enter", CLR_GREEN, LV_SYMBOL_KEYBOARD, MOD_GUI, KEY_RETURN},
            {"Files", "Super+T", CLR_ORANGE, LV_SYMBOL_DIRECTORY, MOD_GUI, 't'},
            {"Launcher", "Super+D", CLR_LIME, LV_SYMBOL_LIST, MOD_GUI, 'd'},
            {"Browser", "Super+B", CLR_BLUE, LV_SYMBOL_EYE_OPEN, MOD_GUI, 'b'},
            {"ScreenSel", "Super+Sh+S", CLR_PINK, LV_SYMBOL_IMAGE, (uint8_t)(MOD_GUI | MOD_SHIFT), 's'},
            {"ScreenFull", "Print", CLR_PINK, LV_SYMBOL_IMAGE, MOD_NONE, KEY_PRINT_SCREEN},
            {"ColorPick", "Super+Sh+C", CLR_AMBER, LV_SYMBOL_EYE_OPEN, (uint8_t)(MOD_GUI | MOD_SHIFT), 'c'},
            {"Lock", "Super+L", CLR_RED, LV_SYMBOL_EYE_CLOSE, MOD_GUI, 'l'},
            {"Logout", "Super+Sh+Q", CLR_RED, LV_SYMBOL_WARNING, (uint8_t)(MOD_GUI | MOD_SHIFT), 'q'},
            {"Notify", "Super+N", CLR_TEAL, LV_SYMBOL_BELL, MOD_GUI, 'n'},
            {"Clipboard", "Super+V", CLR_GREEN, LV_SYMBOL_PASTE, MOD_GUI, 'v'},
            {"Settings", "Super+I", CLR_GREY, LV_SYMBOL_SETTINGS, MOD_GUI, 'i'},
        };

        for (int i = 0; i < 12; i++) {
            int16_t x, y;
            grid_pos(i % 4, i / 4, x, y);
            page.widgets.push_back(make_hotkey(x, y, CELL_W, CELL_H,
                btns[i].lbl, btns[i].desc, btns[i].clr, btns[i].ico,
                btns[i].mod, btns[i].key));
        }

        WidgetConfig pn;
        pn.widget_type = WIDGET_PAGE_NAV;
        pn.x = 300; pn.y = 445; pn.width = 200; pn.height = 30;
        pn.color = 0x3498DB;
        page.widgets.push_back(pn);

        hyprland.pages.push_back(page);
    }

    // ===== Page 3: Media Controls =====
    {
        PageConfig page;
        page.name = "Media + Extras";

        WidgetConfig sb;
        sb.widget_type = WIDGET_STATUS_BAR;
        sb.x = 0; sb.y = 0; sb.width = 800; sb.height = 45;
        sb.label = "Hotkeys";
        sb.color = 0xE0E0E0;
        sb.bg_color = 0x16213e;
        page.widgets.push_back(sb);

        // Media keys (first 6)
        struct { const char* lbl; const char* desc; const char* ico; uint16_t cc; } media[] = {
            {"Play/Pause", "Media Play/Pause", LV_SYMBOL_PLAY, 0x00CD},
            {"Next", "Media Next", LV_SYMBOL_RIGHT, 0x00B5},
            {"Prev", "Media Previous", LV_SYMBOL_LEFT, 0x00B6},
            {"VolUp", "Volume Up", LV_SYMBOL_PLUS, 0x00E9},
            {"VolDn", "Volume Down", LV_SYMBOL_MINUS, 0x00EA},
            {"Mute", "Mute", LV_SYMBOL_MUTE, 0x00E2},
        };

        for (int i = 0; i < 6; i++) {
            int16_t x, y;
            grid_pos(i % 4, i / 4, x, y);
            page.widgets.push_back(make_hotkey(x, y, CELL_W, CELL_H,
                media[i].lbl, media[i].desc, CLR_PURPLE, media[i].ico,
                0, 0, ACTION_MEDIA_KEY, media[i].cc));
        }

        // Hotkeys (last 6)
        struct { const char* lbl; const char* desc; uint32_t clr; const char* ico; uint8_t mod; uint8_t key; } hotkeys[] = {
            {"Redo", "Ctrl+Sh+Z", CLR_BLUE, LV_SYMBOL_REFRESH, (uint8_t)(MOD_CTRL | MOD_SHIFT), 'z'},
            {"Copy", "Ctrl+C", CLR_GREEN, LV_SYMBOL_COPY, MOD_CTRL, 'c'},
            {"Cut", "Ctrl+X", CLR_RED, LV_SYMBOL_CUT, MOD_CTRL, 'x'},
            {"Paste", "Ctrl+V", CLR_ORANGE, LV_SYMBOL_PASTE, MOD_CTRL, 'v'},
            {"Save", "Ctrl+S", CLR_GREEN, LV_SYMBOL_SAVE, MOD_CTRL, 's'},
            {"Undo", "Ctrl+Z", CLR_CYAN, LV_SYMBOL_LOOP, MOD_CTRL, 'z'},
        };

        for (int i = 0; i < 6; i++) {
            int16_t x, y;
            grid_pos((i + 6) % 4, (i + 6) / 4, x, y);
            page.widgets.push_back(make_hotkey(x, y, CELL_W, CELL_H,
                hotkeys[i].lbl, hotkeys[i].desc, hotkeys[i].clr, hotkeys[i].ico,
                hotkeys[i].mod, hotkeys[i].key));
        }

        WidgetConfig pn;
        pn.widget_type = WIDGET_PAGE_NAV;
        pn.x = 300; pn.y = 445; pn.width = 200; pn.height = 30;
        pn.color = 0x3498DB;
        page.widgets.push_back(pn);

        hyprland.pages.push_back(page);
    }

    cfg.profiles.push_back(hyprland);

    // Default stats header
    cfg.stats_header = {
        {STAT_CPU_PERCENT, 0x3498DB, 0},
        {STAT_RAM_PERCENT, 0x2ECC71, 1},
        {STAT_GPU_PERCENT, 0xE67E22, 2},
        {STAT_CPU_TEMP,    0xE74C3C, 3},
        {STAT_GPU_TEMP,    0xF1C40F, 4},
        {STAT_NET_UP,      0x1ABC9C, 5},
        {STAT_NET_DOWN,    0x1ABC9C, 6},
        {STAT_DISK_PERCENT,0x7F8C8D, 7},
    };

    return cfg;
}

// ============================================================
// JSON Serialization/Deserialization (ArduinoJson v7 API) — v2
// ============================================================

// Helper: Serialize widget to JSON object
static void widget_to_json(JsonObject obj, const WidgetConfig& w) {
    obj["widget_type"] = (int)w.widget_type;
    obj["x"] = w.x;
    obj["y"] = w.y;
    obj["width"] = w.width;
    obj["height"] = w.height;
    obj["label"] = w.label.c_str();
    obj["color"] = w.color;
    obj["bg_color"] = w.bg_color;

    switch (w.widget_type) {
        case WIDGET_HOTKEY_BUTTON:
            obj["description"] = w.description.c_str();
            obj["icon"] = w.icon.c_str();
            if (!w.icon_path.empty()) obj["icon_path"] = w.icon_path.c_str();
            obj["action_type"] = (int)w.action_type;
            obj["modifiers"] = w.modifiers;
            obj["keycode"] = w.keycode;
            obj["consumer_code"] = w.consumer_code;
            obj["pressed_color"] = w.pressed_color;
            break;
        case WIDGET_STAT_MONITOR:
            obj["stat_type"] = w.stat_type;
            break;
        case WIDGET_CLOCK:
            obj["clock_analog"] = w.clock_analog;
            break;
        case WIDGET_STATUS_BAR:
            obj["show_wifi"] = w.show_wifi;
            obj["show_pc"] = w.show_pc;
            obj["show_settings"] = w.show_settings;
            obj["show_brightness"] = w.show_brightness;
            obj["show_battery"] = w.show_battery;
            obj["show_time"] = w.show_time;
            break;
        case WIDGET_TEXT_LABEL:
            obj["font_size"] = w.font_size;
            obj["text_align"] = w.text_align;
            break;
        case WIDGET_SEPARATOR:
            obj["separator_vertical"] = w.separator_vertical;
            obj["thickness"] = w.thickness;
            break;
        case WIDGET_PAGE_NAV:
            break;
    }
}

// Helper: Deserialize widget from JSON object
static void json_to_widget(JsonObject obj, WidgetConfig& w) {
    w.widget_type = (WidgetType)(obj["widget_type"] | (int)WIDGET_HOTKEY_BUTTON);
    w.x = obj["x"] | (int16_t)0;
    w.y = obj["y"] | (int16_t)0;
    w.width = obj["width"] | (int16_t)180;
    w.height = obj["height"] | (int16_t)100;

    if (!obj["label"].isNull()) w.label = obj["label"].as<const char*>();
    w.color = obj["color"] | (uint32_t)0xFFFFFF;
    w.bg_color = obj["bg_color"] | (uint32_t)0;

    // Clamp to display bounds
    if (w.x < 0) w.x = 0;
    if (w.y < 0) w.y = 0;
    if (w.x + w.width > DISPLAY_WIDTH) w.width = DISPLAY_WIDTH - w.x;
    if (w.y + w.height > DISPLAY_HEIGHT) w.height = DISPLAY_HEIGHT - w.y;
    if (w.width < WIDGET_MIN_W) w.width = WIDGET_MIN_W;
    if (w.height < WIDGET_MIN_H) w.height = WIDGET_MIN_H;

    // Validate widget type
    if (w.widget_type > WIDGET_TYPE_MAX) {
        Serial.printf("CONFIG: WARNING - widget_type %d invalid, defaulting to HOTKEY_BUTTON\n", w.widget_type);
        w.widget_type = WIDGET_HOTKEY_BUTTON;
    }

    switch (w.widget_type) {
        case WIDGET_HOTKEY_BUTTON:
            if (!obj["description"].isNull()) w.description = obj["description"].as<const char*>();
            if (!obj["icon"].isNull()) w.icon = obj["icon"].as<const char*>();
            if (!obj["icon_path"].isNull()) w.icon_path = obj["icon_path"].as<const char*>();
            w.action_type = (ActionType)(obj["action_type"] | (int)ACTION_HOTKEY);
            w.modifiers = obj["modifiers"] | (uint8_t)0;
            w.keycode = obj["keycode"] | (uint8_t)0;
            w.consumer_code = obj["consumer_code"] | (uint16_t)0;
            w.pressed_color = obj["pressed_color"] | (uint32_t)0;
            break;
        case WIDGET_STAT_MONITOR:
            w.stat_type = obj["stat_type"] | (uint8_t)0;
            if (w.stat_type < 1 || w.stat_type > STAT_TYPE_MAX) {
                Serial.printf("CONFIG: WARNING - stat_type %d invalid\n", w.stat_type);
                w.stat_type = STAT_CPU_PERCENT;
            }
            break;
        case WIDGET_CLOCK:
            w.clock_analog = obj["clock_analog"] | false;
            break;
        case WIDGET_STATUS_BAR:
            w.show_wifi = obj["show_wifi"] | true;
            w.show_pc = obj["show_pc"] | true;
            w.show_settings = obj["show_settings"] | true;
            w.show_brightness = obj["show_brightness"] | true;
            w.show_battery = obj["show_battery"] | true;
            w.show_time = obj["show_time"] | true;
            break;
        case WIDGET_TEXT_LABEL:
            w.font_size = obj["font_size"] | (uint8_t)16;
            w.text_align = obj["text_align"] | (uint8_t)1;
            break;
        case WIDGET_SEPARATOR:
            w.separator_vertical = obj["separator_vertical"] | false;
            w.thickness = obj["thickness"] | (uint8_t)2;
            if (w.thickness < 1) w.thickness = 1;
            if (w.thickness > 8) w.thickness = 8;
            break;
        case WIDGET_PAGE_NAV:
            break;
    }
}

// Helper: Serialize page to JSON object (v2)
static void page_to_json(JsonObject obj, const PageConfig& page) {
    obj["name"] = page.name.c_str();
    JsonArray widgets_array = obj["widgets"].to<JsonArray>();
    for (const auto& w : page.widgets) {
        JsonObject w_obj = widgets_array.add<JsonObject>();
        widget_to_json(w_obj, w);
    }
}

// Helper: Deserialize page from JSON object (v2)
static void json_to_page_v2(JsonObject obj, PageConfig& page) {
    if (!obj["name"].isNull()) page.name = obj["name"].as<const char*>();
    page.widgets.clear();
    if (!obj["widgets"].isNull()) {
        JsonArray widgets_array = obj["widgets"].as<JsonArray>();
        int count = 0;
        for (JsonObject w_obj : widgets_array) {
            if (count >= CONFIG_MAX_WIDGETS) {
                Serial.printf("CONFIG: WARNING - page '%s' has >%d widgets, truncating\n",
                              page.name.c_str(), CONFIG_MAX_WIDGETS);
                break;
            }
            WidgetConfig w;
            json_to_widget(w_obj, w);
            page.widgets.push_back(w);
            count++;
        }
    }
    Serial.printf("CONFIG: Page '%s': %d widgets loaded\n",
                  page.name.c_str(), (int)page.widgets.size());
}

// ============================================================
// V1 Migration: Convert old grid-based buttons to v2 widgets
// ============================================================

static void migrate_v1_page(JsonObject page_obj, PageConfig& page) {
    if (!page_obj["name"].isNull()) page.name = page_obj["name"].as<const char*>();
    page.widgets.clear();

    // Add a default status bar at top
    WidgetConfig sb;
    sb.widget_type = WIDGET_STATUS_BAR;
    sb.x = 0; sb.y = 0; sb.width = DISPLAY_WIDTH; sb.height = 45;
    sb.label = "Hotkeys";
    sb.color = 0xE0E0E0;
    sb.bg_color = 0x16213e;
    page.widgets.push_back(sb);

    // Grid cell dimensions for v1 layout
    const int16_t GRID_X0 = 6;
    const int16_t GRID_Y0 = 50;
    const int16_t CELL_W = 192;
    const int16_t CELL_H = 122;
    const int16_t GAP = 6;

    if (page_obj["buttons"].isNull()) return;

    JsonArray buttons_array = page_obj["buttons"].as<JsonArray>();
    int auto_row = 0, auto_col = 0;
    int btn_count = 0;

    for (JsonObject btn_obj : buttons_array) {
        if (btn_count >= 12) break;

        WidgetConfig w;
        w.widget_type = WIDGET_HOTKEY_BUTTON;

        // Read v1 button fields
        if (!btn_obj["label"].isNull()) w.label = btn_obj["label"].as<const char*>();
        if (!btn_obj["description"].isNull()) w.description = btn_obj["description"].as<const char*>();
        w.color = btn_obj["color"] | (uint32_t)0xFFFFFF;
        if (!btn_obj["icon"].isNull()) w.icon = btn_obj["icon"].as<const char*>();
        w.action_type = (ActionType)(btn_obj["action_type"] | (int)ACTION_HOTKEY);
        w.modifiers = btn_obj["modifiers"] | (uint8_t)0;
        w.keycode = btn_obj["keycode"] | (uint8_t)0;
        w.consumer_code = btn_obj["consumer_code"] | (uint16_t)0;
        w.pressed_color = btn_obj["pressed_color"] | (uint32_t)0;

        // Convert grid position to pixel coordinates
        int8_t grid_row = btn_obj["grid_row"] | (int8_t)-1;
        int8_t grid_col = btn_obj["grid_col"] | (int8_t)-1;
        uint8_t col_span = btn_obj["col_span"] | (uint8_t)1;
        uint8_t row_span = btn_obj["row_span"] | (uint8_t)1;

        int target_row, target_col;
        if (grid_row >= 0 && grid_col >= 0) {
            target_row = grid_row;
            target_col = grid_col;
        } else {
            target_row = auto_row;
            target_col = auto_col;
            col_span = 1;
            row_span = 1;
            auto_col++;
            if (auto_col >= GRID_COLS) {
                auto_col = 0;
                auto_row++;
            }
        }

        // Convert to pixel coordinates
        w.x = GRID_X0 + target_col * (CELL_W + GAP);
        w.y = GRID_Y0 + target_row * (CELL_H + GAP);
        w.width = col_span * CELL_W + (col_span - 1) * GAP;
        w.height = row_span * CELL_H + (row_span - 1) * GAP;

        page.widgets.push_back(w);
        btn_count++;
    }

    // Add page nav at bottom
    WidgetConfig pn;
    pn.widget_type = WIDGET_PAGE_NAV;
    pn.x = 300; pn.y = 445; pn.width = 200; pn.height = 30;
    pn.color = 0x3498DB;
    page.widgets.push_back(pn);

    Serial.printf("CONFIG: Migrated v1 page '%s': %d buttons -> %d widgets\n",
                  page.name.c_str(), btn_count, (int)page.widgets.size());
}

// Helper: Serialize profile to JSON object
static void profile_to_json(JsonObject obj, const ProfileConfig& profile) {
    obj["name"] = profile.name.c_str();
    JsonArray pages_array = obj["pages"].to<JsonArray>();
    for (const auto& page : profile.pages) {
        JsonObject page_obj = pages_array.add<JsonObject>();
        page_to_json(page_obj, page);
    }
}

// Helper: Deserialize profile from JSON object
static void json_to_profile(JsonObject obj, ProfileConfig& profile, uint8_t config_version) {
    if (!obj["name"].isNull()) profile.name = obj["name"].as<const char*>();
    profile.pages.clear();
    if (!obj["pages"].isNull()) {
        JsonArray pages_array = obj["pages"].as<JsonArray>();
        int page_count = 0;
        for (JsonObject page_obj : pages_array) {
            if (page_count >= CONFIG_MAX_PAGES) {
                Serial.printf("CONFIG: WARNING - profile '%s' has >%d pages, truncating\n",
                              profile.name.c_str(), CONFIG_MAX_PAGES);
                break;
            }
            PageConfig page;
            if (config_version < 2) {
                // V1 migration: convert grid buttons to absolute widgets
                migrate_v1_page(page_obj, page);
            } else {
                json_to_page_v2(page_obj, page);
            }
            if (page.widgets.empty()) {
                Serial.printf("CONFIG: WARNING - skipping empty page '%s'\n", page.name.c_str());
                continue;
            }
            profile.pages.push_back(page);
            page_count++;
        }
    }
}

// ============================================================
// Configuration I/O
// ============================================================

AppConfig config_load() {
    // Try to load from SD card
    if (!sdcard_mounted()) {
        Serial.println("CONFIG: SD card not mounted, using defaults");
        return config_create_defaults();
    }

    // PSRAM-allocated buffer for reading file (max 64KB for config)
    uint8_t *buffer = (uint8_t *)ps_malloc(64 * 1024);
    if (!buffer) {
        Serial.println("CONFIG: PSRAM alloc failed for read buffer, using defaults");
        return config_create_defaults();
    }

    int bytes_read = sdcard_read_file("/config.json", buffer, (64 * 1024) - 1);

    if (bytes_read <= 0) {
        Serial.println("CONFIG: /config.json not found, using defaults");
        free(buffer);
        return config_create_defaults();
    }

    buffer[bytes_read] = '\0';

    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, (const char*)buffer);
    free(buffer);

    if (error) {
        Serial.printf("CONFIG: JSON parse failed: %s, using defaults\n", error.c_str());
        return config_create_defaults();
    }

    AppConfig cfg;

    // Read version field
    uint8_t file_version = doc["version"] | (uint8_t)0;
    cfg.version = CONFIG_VERSION;  // Always upgrade to current
    Serial.printf("CONFIG: file schema version %d (current %d)\n", file_version, CONFIG_VERSION);

    if (file_version < 2) {
        Serial.println("CONFIG: Migrating v1 -> v2 (grid -> absolute positioning)");
    }

    if (!doc["active_profile_name"].isNull()) {
        cfg.active_profile_name = doc["active_profile_name"].as<const char*>();
    }
    if (!doc["brightness_level"].isNull()) {
        cfg.brightness_level = doc["brightness_level"].as<uint8_t>();
    }

    // Parse display mode settings
    cfg.default_mode = doc["default_mode"] | (uint8_t)0;
    cfg.slideshow_interval_sec = doc["slideshow_interval_sec"] | (uint16_t)30;
    cfg.clock_analog = doc["clock_analog"] | false;

    if (cfg.default_mode > 3) {
        Serial.printf("CONFIG: WARNING - invalid default_mode=%d, using MODE_HOTKEYS\n", cfg.default_mode);
        cfg.default_mode = 0;
    }
    if (cfg.slideshow_interval_sec < 5) cfg.slideshow_interval_sec = 5;
    if (cfg.slideshow_interval_sec > 300) cfg.slideshow_interval_sec = 300;

    cfg.profiles.clear();
    if (!doc["profiles"].isNull()) {
        JsonArray profiles_array = doc["profiles"].as<JsonArray>();
        for (JsonObject profile_obj : profiles_array) {
            ProfileConfig profile;
            json_to_profile(profile_obj, profile, file_version);
            cfg.profiles.push_back(profile);
        }
    }

    // Parse stats_header
    if (!doc["stats_header"].isNull()) {
        cfg.stats_header.clear();
        JsonArray stats_arr = doc["stats_header"].as<JsonArray>();
        int stat_count = 0;
        for (JsonObject stat_obj : stats_arr) {
            if (stat_count >= CONFIG_MAX_STATS) break;
            StatConfig sc;
            sc.type = stat_obj["type"] | (uint8_t)0;
            sc.color = stat_obj["color"] | (uint32_t)0xFFFFFF;
            sc.position = stat_obj["position"] | (uint8_t)0;
            if (sc.type < 1 || sc.type > STAT_TYPE_MAX) {
                Serial.printf("CONFIG: WARNING - invalid stat type %d, skipping\n", sc.type);
                continue;
            }
            cfg.stats_header.push_back(sc);
            stat_count++;
        }
        Serial.printf("CONFIG: Loaded %d stats_header entries\n", (int)cfg.stats_header.size());
    } else {
        cfg.stats_header = {
            {STAT_CPU_PERCENT, 0x3498DB, 0},
            {STAT_RAM_PERCENT, 0x2ECC71, 1},
            {STAT_GPU_PERCENT, 0xE67E22, 2},
            {STAT_CPU_TEMP,    0xE74C3C, 3},
            {STAT_GPU_TEMP,    0xF1C40F, 4},
            {STAT_NET_UP,      0x1ABC9C, 5},
            {STAT_NET_DOWN,    0x1ABC9C, 6},
            {STAT_DISK_PERCENT,0x7F8C8D, 7},
        };
        Serial.println("CONFIG: No stats_header in JSON, using 8 defaults");
    }

    // Hardware buttons (optional, defaults if missing)
    JsonArray hw_btns = doc["hardware_buttons"];
    if (!hw_btns.isNull()) {
        for (int i = 0; i < 4 && i < (int)hw_btns.size(); i++) {
            JsonObject btn = hw_btns[i];
            cfg.hw_buttons[i].action_type = (ActionType)(btn["action_type"] | 8); // PAGE_NEXT default
            cfg.hw_buttons[i].label = btn["label"] | "";
            cfg.hw_buttons[i].keycode = btn["keycode"] | 0;
            cfg.hw_buttons[i].consumer_code = btn["consumer_code"] | 0;
            cfg.hw_buttons[i].modifiers = btn["modifiers"] | 0;
        }
    }

    // Encoder (optional)
    JsonObject enc = doc["encoder"];
    if (!enc.isNull()) {
        cfg.encoder.push_action = (ActionType)(enc["push_action"] | 12); // BRIGHTNESS default
        cfg.encoder.push_label = enc["push_label"] | "Brightness";
        cfg.encoder.push_keycode = enc["push_keycode"] | 0;
        cfg.encoder.push_consumer_code = enc["push_consumer_code"] | 0;
        cfg.encoder.push_modifiers = enc["push_modifiers"] | 0;
        cfg.encoder.encoder_mode = enc["encoder_mode"] | 0; // page_nav default
    }

    // Mode cycle (optional)
    JsonArray modes = doc["mode_cycle"];
    if (!modes.isNull()) {
        cfg.mode_cycle.enabled_modes.clear();
        for (JsonVariant m : modes) {
            cfg.mode_cycle.enabled_modes.push_back(m.as<uint8_t>());
        }
    }

    // Display settings (optional)
    JsonObject ds = doc["display_settings"];
    if (!ds.isNull()) {
        cfg.display_settings.dim_timeout_sec = ds["dim_timeout_sec"] | 60;
        cfg.display_settings.sleep_timeout_sec = ds["sleep_timeout_sec"] | 300;
        cfg.display_settings.wake_on_touch = ds["wake_on_touch"] | true;
        cfg.display_settings.clock_24h = ds["clock_24h"] | true;
        cfg.display_settings.clock_color_theme = ds["clock_color_theme"] | (uint32_t)0xFFFFFF;
        cfg.display_settings.slideshow_interval_sec = ds["slideshow_interval_sec"] | 30;
        cfg.display_settings.slideshow_transition = ds["slideshow_transition"] | "fade";
    }

    // Validate
    if (cfg.profiles.empty() || !cfg.get_active_profile()) {
        Serial.println("CONFIG: Invalid configuration (no valid active profile), using defaults");
        return config_create_defaults();
    }

    ProfileConfig *active = cfg.get_active_profile();
    if (active->pages.empty()) {
        Serial.println("CONFIG: Active profile has 0 pages, using defaults");
        return config_create_defaults();
    }
    if ((int)active->pages.size() > CONFIG_MAX_PAGES) {
        Serial.printf("CONFIG: WARNING - active profile has %zu pages (max %d), truncating\n",
                      active->pages.size(), CONFIG_MAX_PAGES);
        active->pages.resize(CONFIG_MAX_PAGES);
    }

    // If migrated from v1, save upgraded config
    if (file_version < 2) {
        Serial.println("CONFIG: Saving migrated v2 config...");
        config_save(cfg);
    }

    int total_widgets = 0;
    for (const auto& page : active->pages) {
        total_widgets += (int)page.widgets.size();
    }
    Serial.printf("CONFIG: Loaded '%s' - %zu pages, %d total widgets, version %d\n",
                  cfg.active_profile_name.c_str(), active->pages.size(),
                  total_widgets, cfg.version);
    return cfg;
}

bool config_save(const AppConfig& config) {
    if (!sdcard_mounted()) {
        Serial.println("CONFIG: SD card not mounted, cannot save");
        return false;
    }

    // Backup existing config.json
    if (sdcard_file_exists("/config.json")) {
        uint8_t *backup_buf = (uint8_t *)ps_malloc(64 * 1024);
        if (backup_buf) {
            int backup_bytes = sdcard_read_file("/config.json", backup_buf, (64 * 1024) - 1);
            if (backup_bytes > 0) {
                if (sdcard_write_file("/config.json.bak", backup_buf, backup_bytes)) {
                    Serial.println("CONFIG: backed up /config.json to /config.json.bak");
                } else {
                    Serial.println("CONFIG: WARNING - backup to /config.json.bak failed, continuing save");
                }
            }
            free(backup_buf);
        }
    }

    // Build JSON document
    JsonDocument doc;
    doc["version"] = CONFIG_VERSION;
    doc["active_profile_name"] = config.active_profile_name.c_str();
    doc["brightness_level"] = config.brightness_level;

    doc["default_mode"] = config.default_mode;
    doc["slideshow_interval_sec"] = config.slideshow_interval_sec;
    doc["clock_analog"] = config.clock_analog;

    JsonArray profiles_array = doc["profiles"].to<JsonArray>();
    for (const auto& profile : config.profiles) {
        JsonObject profile_obj = profiles_array.add<JsonObject>();
        profile_to_json(profile_obj, profile);
    }

    if (!config.stats_header.empty()) {
        JsonArray stats_arr = doc["stats_header"].to<JsonArray>();
        for (const auto& sc : config.stats_header) {
            JsonObject stat_obj = stats_arr.add<JsonObject>();
            stat_obj["type"] = sc.type;
            stat_obj["color"] = sc.color;
            stat_obj["position"] = sc.position;
        }
    }

    // Hardware buttons
    JsonArray hw_btns = doc["hardware_buttons"].to<JsonArray>();
    for (int i = 0; i < 4; i++) {
        JsonObject btn = hw_btns.add<JsonObject>();
        btn["action_type"] = (uint8_t)config.hw_buttons[i].action_type;
        btn["label"] = config.hw_buttons[i].label;
        btn["keycode"] = config.hw_buttons[i].keycode;
        btn["consumer_code"] = config.hw_buttons[i].consumer_code;
        btn["modifiers"] = config.hw_buttons[i].modifiers;
    }

    // Encoder
    JsonObject enc = doc["encoder"].to<JsonObject>();
    enc["push_action"] = (uint8_t)config.encoder.push_action;
    enc["push_label"] = config.encoder.push_label;
    enc["push_keycode"] = config.encoder.push_keycode;
    enc["push_consumer_code"] = config.encoder.push_consumer_code;
    enc["push_modifiers"] = config.encoder.push_modifiers;
    enc["encoder_mode"] = config.encoder.encoder_mode;

    // Mode cycle
    JsonArray modes = doc["mode_cycle"].to<JsonArray>();
    for (uint8_t m : config.mode_cycle.enabled_modes) {
        modes.add(m);
    }

    // Display settings
    JsonObject ds = doc["display_settings"].to<JsonObject>();
    ds["dim_timeout_sec"] = config.display_settings.dim_timeout_sec;
    ds["sleep_timeout_sec"] = config.display_settings.sleep_timeout_sec;
    ds["wake_on_touch"] = config.display_settings.wake_on_touch;
    ds["clock_24h"] = config.display_settings.clock_24h;
    ds["clock_color_theme"] = config.display_settings.clock_color_theme;
    ds["slideshow_interval_sec"] = config.display_settings.slideshow_interval_sec;
    ds["slideshow_transition"] = config.display_settings.slideshow_transition;

    String json_str;
    serializeJson(doc, json_str);

    // Atomic write
    if (!sdcard_write_file("/config.tmp", (const uint8_t*)json_str.c_str(), json_str.length())) {
        Serial.println("CONFIG: Failed to write /config.tmp");
        return false;
    }

    sdcard_file_remove("/config.json");

    if (!sdcard_file_rename("/config.tmp", "/config.json")) {
        Serial.println("CONFIG: Failed to rename /config.tmp to /config.json");
        if (sdcard_file_exists("/config.json.bak")) {
            sdcard_file_rename("/config.json.bak", "/config.json");
            Serial.println("CONFIG: Restored /config.json from backup");
        }
        return false;
    }

    // Verify
    uint8_t *verify_buf = (uint8_t *)ps_malloc(64 * 1024);
    if (verify_buf) {
        int verify_bytes = sdcard_read_file("/config.json", verify_buf, (64 * 1024) - 1);
        if (verify_bytes > 0) {
            verify_buf[verify_bytes] = '\0';
            JsonDocument verify_doc;
            DeserializationError verify_err = deserializeJson(verify_doc, (const char*)verify_buf);
            if (verify_err) {
                Serial.printf("CONFIG: WARNING - saved file failed verification: %s\n", verify_err.c_str());
                if (sdcard_file_exists("/config.json.bak")) {
                    sdcard_file_remove("/config.json");
                    sdcard_file_rename("/config.json.bak", "/config.json");
                    Serial.println("CONFIG: Restored /config.json from backup after verification failure");
                }
                free(verify_buf);
                return false;
            }
        }
        free(verify_buf);
    }

    Serial.printf("CONFIG: Saved configuration (%zu bytes)\n", json_str.length());
    return true;
}
