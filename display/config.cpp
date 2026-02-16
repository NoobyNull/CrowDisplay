#include "config.h"
#include "sdcard.h"
#include <ArduinoJson.h>
#include <Arduino.h>
#include <lvgl.h>
#include "protocol.h"

// ============================================================
// Default/Builtin Profiles (hardcoded fallback)
// ============================================================

// Create default configuration from hardcoded hotkeys
AppConfig config_create_defaults() {
    AppConfig cfg;
    cfg.version = CONFIG_VERSION;
    cfg.active_profile_name = "Hyprland";
    cfg.brightness_level = 100;

    // Profile: Hyprland (3 pages, 12 buttons each)
    ProfileConfig hyprland;
    hyprland.name = "Hyprland";

    // ===== Page 1: Window Management =====
    PageConfig page1;
    page1.name = "Window Manager";

    // Button colors (from ui.cpp)
    const uint32_t CLR_BLUE = 0x3498DB;
    const uint32_t CLR_TEAL = 0x1ABC9C;
    const uint32_t CLR_RED = 0xE74C3C;
    const uint32_t CLR_CYAN = 0x00BCD4;
    const uint32_t CLR_INDIGO = 0x3F51B5;

    // Key codes (from ui.cpp)
    const uint8_t KEY_RETURN = 0xB0;
    const uint8_t KEY_LEFT_ARROW = 0xD8;
    const uint8_t KEY_RIGHT_ARROW = 0xD7;
    const uint8_t KEY_UP_ARROW = 0xDA;
    const uint8_t KEY_DOWN_ARROW = 0xD9;
    const uint8_t KEY_PRINT_SCREEN = 0xCE;

    // WS 1..4, Focus L/R/U/D, Kill, Fullscr, Float, WS 5
    ButtonConfig btn;

    // WS 1
    btn.label = "WS 1";
    btn.description = "Super+1";
    btn.color = CLR_BLUE;
    btn.icon = LV_SYMBOL_HOME;
    btn.action_type = ACTION_HOTKEY;
    btn.modifiers = MOD_GUI;
    btn.keycode = '1';
    page1.buttons.push_back(btn);

    // WS 2
    btn.label = "WS 2";
    btn.description = "Super+2";
    btn.keycode = '2';
    page1.buttons.push_back(btn);

    // WS 3
    btn.label = "WS 3";
    btn.description = "Super+3";
    btn.keycode = '3';
    page1.buttons.push_back(btn);

    // WS 4
    btn.label = "WS 4";
    btn.description = "Super+4";
    btn.keycode = '4';
    page1.buttons.push_back(btn);

    // Focus Left
    btn.label = "Focus L";
    btn.description = "Super+Left";
    btn.color = CLR_TEAL;
    btn.icon = LV_SYMBOL_LEFT;
    btn.keycode = KEY_LEFT_ARROW;
    page1.buttons.push_back(btn);

    // Focus Right
    btn.label = "Focus R";
    btn.description = "Super+Right";
    btn.icon = LV_SYMBOL_RIGHT;
    btn.keycode = KEY_RIGHT_ARROW;
    page1.buttons.push_back(btn);

    // Focus Up
    btn.label = "Focus Up";
    btn.description = "Super+Up";
    btn.icon = LV_SYMBOL_UP;
    btn.keycode = KEY_UP_ARROW;
    page1.buttons.push_back(btn);

    // Focus Down
    btn.label = "Focus Dn";
    btn.description = "Super+Down";
    btn.icon = LV_SYMBOL_DOWN;
    btn.keycode = KEY_DOWN_ARROW;
    page1.buttons.push_back(btn);

    // Kill
    btn.label = "Kill";
    btn.description = "Super+Q";
    btn.color = CLR_RED;
    btn.icon = LV_SYMBOL_CLOSE;
    btn.modifiers = MOD_GUI;
    btn.keycode = 'q';
    page1.buttons.push_back(btn);

    // Fullscreen
    btn.label = "Fullscr";
    btn.description = "Super+F";
    btn.color = CLR_CYAN;
    btn.icon = LV_SYMBOL_NEW_LINE;
    btn.keycode = 'f';
    page1.buttons.push_back(btn);

    // Float
    btn.label = "Float";
    btn.description = "Super+Sh+Space";
    btn.color = CLR_INDIGO;
    btn.icon = LV_SYMBOL_SHUFFLE;
    btn.modifiers = MOD_GUI | MOD_SHIFT;
    btn.keycode = ' ';
    page1.buttons.push_back(btn);

    // WS 5
    btn.label = "WS 5";
    btn.description = "Super+5";
    btn.color = CLR_BLUE;
    btn.icon = LV_SYMBOL_HOME;
    btn.modifiers = MOD_GUI;
    btn.keycode = '5';
    page1.buttons.push_back(btn);

    hyprland.pages.push_back(page1);

    // ===== Page 2: System Actions =====
    PageConfig page2;
    page2.name = "System Actions";

    const uint32_t CLR_GREEN = 0x2ECC71;
    const uint32_t CLR_ORANGE = 0xE67E22;
    const uint32_t CLR_LIME = 0x8BC34A;
    const uint32_t CLR_PINK = 0xE91E63;
    const uint32_t CLR_AMBER = 0xFFC107;
    const uint32_t CLR_GREY = 0x7F8C8D;

    // Terminal
    btn.label = "Terminal";
    btn.description = "Super+Enter";
    btn.color = CLR_GREEN;
    btn.icon = LV_SYMBOL_KEYBOARD;
    btn.action_type = ACTION_HOTKEY;
    btn.modifiers = MOD_GUI;
    btn.keycode = KEY_RETURN;
    page2.buttons.push_back(btn);

    // Files
    btn.label = "Files";
    btn.description = "Super+T";
    btn.color = CLR_ORANGE;
    btn.icon = LV_SYMBOL_DIRECTORY;
    btn.keycode = 't';
    page2.buttons.push_back(btn);

    // Launcher
    btn.label = "Launcher";
    btn.description = "Super+D";
    btn.color = CLR_LIME;
    btn.icon = LV_SYMBOL_LIST;
    btn.keycode = 'd';
    page2.buttons.push_back(btn);

    // Browser
    btn.label = "Browser";
    btn.description = "Super+B";
    btn.color = CLR_BLUE;
    btn.icon = LV_SYMBOL_EYE_OPEN;
    btn.keycode = 'b';
    page2.buttons.push_back(btn);

    // Screenshot Select
    btn.label = "ScreenSel";
    btn.description = "Super+Sh+S";
    btn.color = CLR_PINK;
    btn.icon = LV_SYMBOL_IMAGE;
    btn.modifiers = MOD_GUI | MOD_SHIFT;
    btn.keycode = 's';
    page2.buttons.push_back(btn);

    // Screenshot Full
    btn.label = "ScreenFull";
    btn.description = "Print";
    btn.color = CLR_PINK;
    btn.icon = LV_SYMBOL_IMAGE;
    btn.modifiers = MOD_NONE;
    btn.keycode = KEY_PRINT_SCREEN;
    page2.buttons.push_back(btn);

    // Color Picker
    btn.label = "ColorPick";
    btn.description = "Super+Sh+C";
    btn.color = CLR_AMBER;
    btn.icon = LV_SYMBOL_EYE_OPEN;
    btn.modifiers = MOD_GUI | MOD_SHIFT;
    btn.keycode = 'c';
    page2.buttons.push_back(btn);

    // Lock
    btn.label = "Lock";
    btn.description = "Super+L";
    btn.color = CLR_RED;
    btn.icon = LV_SYMBOL_EYE_CLOSE;
    btn.modifiers = MOD_GUI;
    btn.keycode = 'l';
    page2.buttons.push_back(btn);

    // Logout
    btn.label = "Logout";
    btn.description = "Super+Sh+Q";
    btn.color = CLR_RED;
    btn.icon = LV_SYMBOL_WARNING;
    btn.modifiers = MOD_GUI | MOD_SHIFT;
    btn.keycode = 'q';
    page2.buttons.push_back(btn);

    // Notify
    btn.label = "Notify";
    btn.description = "Super+N";
    btn.color = CLR_TEAL;
    btn.icon = LV_SYMBOL_BELL;
    btn.modifiers = MOD_GUI;
    btn.keycode = 'n';
    page2.buttons.push_back(btn);

    // Clipboard
    btn.label = "Clipboard";
    btn.description = "Super+V";
    btn.color = CLR_GREEN;
    btn.icon = LV_SYMBOL_PASTE;
    btn.keycode = 'v';
    page2.buttons.push_back(btn);

    // Settings
    btn.label = "Settings";
    btn.description = "Super+I";
    btn.color = CLR_GREY;
    btn.icon = LV_SYMBOL_SETTINGS;
    btn.keycode = 'i';
    page2.buttons.push_back(btn);

    hyprland.pages.push_back(page2);

    // ===== Page 3: Media Controls =====
    PageConfig page3;
    page3.name = "Media + Extras";

    // Media keys (consumer control codes)
    btn.label = "Play/Pause";
    btn.description = "Media Play/Pause";
    btn.color = 0x9B59B6; // Purple
    btn.icon = LV_SYMBOL_PLAY;
    btn.action_type = ACTION_MEDIA_KEY;
    btn.modifiers = 0;
    btn.keycode = 0;
    btn.consumer_code = 0x00CD;  // Play/Pause
    page3.buttons.push_back(btn);

    btn.label = "Next";
    btn.description = "Media Next";
    btn.icon = LV_SYMBOL_RIGHT;  // Use right arrow for next
    btn.consumer_code = 0x00B5;  // Next track
    page3.buttons.push_back(btn);

    btn.label = "Prev";
    btn.description = "Media Previous";
    btn.icon = LV_SYMBOL_LEFT;  // Use left arrow for previous
    btn.consumer_code = 0x00B6;  // Previous track
    page3.buttons.push_back(btn);

    btn.label = "VolUp";
    btn.description = "Volume Up";
    btn.icon = LV_SYMBOL_PLUS;
    btn.consumer_code = 0x00E9;  // Volume Up
    page3.buttons.push_back(btn);

    btn.label = "VolDn";
    btn.description = "Volume Down";
    btn.icon = LV_SYMBOL_MINUS;
    btn.consumer_code = 0x00EA;  // Volume Down
    page3.buttons.push_back(btn);

    btn.label = "Mute";
    btn.description = "Mute";
    btn.icon = LV_SYMBOL_MUTE;
    btn.consumer_code = 0x00E2;  // Mute
    page3.buttons.push_back(btn);

    // Regular hotkeys for remaining 6 buttons
    btn.action_type = ACTION_HOTKEY;
    btn.consumer_code = 0;

    btn.label = "Redo";
    btn.description = "Ctrl+Sh+Z";
    btn.color = CLR_BLUE;
    btn.icon = LV_SYMBOL_REFRESH;
    btn.modifiers = MOD_CTRL | MOD_SHIFT;
    btn.keycode = 'z';
    page3.buttons.push_back(btn);

    btn.label = "Copy";
    btn.description = "Ctrl+C";
    btn.color = CLR_GREEN;
    btn.icon = LV_SYMBOL_COPY;
    btn.modifiers = MOD_CTRL;
    btn.keycode = 'c';
    page3.buttons.push_back(btn);

    btn.label = "Cut";
    btn.description = "Ctrl+X";
    btn.color = CLR_RED;
    btn.icon = LV_SYMBOL_CUT;
    btn.modifiers = MOD_CTRL;
    btn.keycode = 'x';
    page3.buttons.push_back(btn);

    btn.label = "Paste";
    btn.description = "Ctrl+V";
    btn.color = CLR_ORANGE;
    btn.icon = LV_SYMBOL_PASTE;
    btn.modifiers = MOD_CTRL;
    btn.keycode = 'v';
    page3.buttons.push_back(btn);

    btn.label = "Save";
    btn.description = "Ctrl+S";
    btn.color = CLR_GREEN;
    btn.icon = LV_SYMBOL_SAVE;
    btn.modifiers = MOD_CTRL;
    btn.keycode = 's';
    page3.buttons.push_back(btn);

    btn.label = "Undo";
    btn.description = "Ctrl+Z";
    btn.color = CLR_CYAN;
    btn.icon = LV_SYMBOL_LOOP;
    btn.modifiers = MOD_CTRL;
    btn.keycode = 'z';
    page3.buttons.push_back(btn);

    hyprland.pages.push_back(page3);

    cfg.profiles.push_back(hyprland);

    // Default stats header: matches the original hardcoded 8 stats
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
// JSON Serialization/Deserialization (ArduinoJson v7 API)
// ============================================================

// Helper: Serialize button to JSON object
static void button_to_json(JsonObject obj, const ButtonConfig& btn) {
    obj["label"] = btn.label.c_str();
    obj["description"] = btn.description.c_str();
    obj["color"] = btn.color;
    obj["icon"] = btn.icon.c_str();
    obj["action_type"] = (int)btn.action_type;
    obj["modifiers"] = btn.modifiers;
    obj["keycode"] = btn.keycode;
    obj["consumer_code"] = btn.consumer_code;
    obj["grid_row"] = btn.grid_row;
    obj["grid_col"] = btn.grid_col;
    obj["pressed_color"] = btn.pressed_color;
}

// Helper: Deserialize button from JSON object
static void json_to_button(JsonObject obj, ButtonConfig& btn) {
    if (!obj["label"].isNull()) btn.label = obj["label"].as<const char*>();
    if (!obj["description"].isNull()) btn.description = obj["description"].as<const char*>();
    if (!obj["color"].isNull()) btn.color = obj["color"].as<uint32_t>();
    if (!obj["icon"].isNull()) btn.icon = obj["icon"].as<const char*>();
    if (!obj["action_type"].isNull()) btn.action_type = (ActionType)obj["action_type"].as<int>();
    if (!obj["modifiers"].isNull()) btn.modifiers = obj["modifiers"].as<uint8_t>();
    if (!obj["keycode"].isNull()) btn.keycode = obj["keycode"].as<uint8_t>();
    if (!obj["consumer_code"].isNull()) btn.consumer_code = obj["consumer_code"].as<uint16_t>();

    // Grid positioning (v0.9.1)
    if (!obj["grid_row"].isNull()) btn.grid_row = obj["grid_row"].as<int8_t>();
    if (!obj["grid_col"].isNull()) btn.grid_col = obj["grid_col"].as<int8_t>();
    if (!obj["pressed_color"].isNull()) btn.pressed_color = obj["pressed_color"].as<uint32_t>();

    // Validate grid positioning constraints
    if (btn.grid_row < -1 || btn.grid_row >= GRID_ROWS) {
        Serial.printf("CONFIG: WARNING - grid_row %d out of range [-1,%d], clamping\n",
                      btn.grid_row, GRID_ROWS - 1);
        btn.grid_row = (btn.grid_row < -1) ? -1 : (GRID_ROWS - 1);
    }
    if (btn.grid_col < -1 || btn.grid_col >= GRID_COLS) {
        Serial.printf("CONFIG: WARNING - grid_col %d out of range [-1,%d], clamping\n",
                      btn.grid_col, GRID_COLS - 1);
        btn.grid_col = (btn.grid_col < -1) ? -1 : (GRID_COLS - 1);
    }
    // If one is explicit and the other is auto, force both to auto
    if ((btn.grid_row >= 0) != (btn.grid_col >= 0)) {
        Serial.printf("CONFIG: WARNING - partial grid position (row=%d, col=%d), resetting to auto-flow\n",
                      btn.grid_row, btn.grid_col);
        btn.grid_row = -1;
        btn.grid_col = -1;
    }
}

// Helper: Serialize page to JSON object
static void page_to_json(JsonObject obj, const PageConfig& page) {
    obj["name"] = page.name.c_str();
    JsonArray buttons_array = obj["buttons"].to<JsonArray>();
    for (const auto& btn : page.buttons) {
        JsonObject btn_obj = buttons_array.add<JsonObject>();
        button_to_json(btn_obj, btn);
    }
}

// Helper: Deserialize page from JSON object
static void json_to_page(JsonObject obj, PageConfig& page) {
    if (!obj["name"].isNull()) page.name = obj["name"].as<const char*>();
    page.buttons.clear();
    if (!obj["buttons"].isNull()) {
        JsonArray buttons_array = obj["buttons"].as<JsonArray>();
        int btn_count = 0;
        for (JsonObject btn_obj : buttons_array) {
            if (btn_count >= CONFIG_MAX_BUTTONS) {
                Serial.printf("CONFIG: WARNING - page '%s' has >%d buttons, truncating\n",
                              page.name.c_str(), CONFIG_MAX_BUTTONS);
                break;
            }
            ButtonConfig btn;
            json_to_button(btn_obj, btn);
            page.buttons.push_back(btn);
            btn_count++;
        }
    }
    Serial.printf("CONFIG: Page '%s': %d buttons loaded\n",
                  page.name.c_str(), (int)page.buttons.size());
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
static void json_to_profile(JsonObject obj, ProfileConfig& profile) {
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
            json_to_page(page_obj, page);
            // Skip empty pages
            if (page.buttons.empty()) {
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

    buffer[bytes_read] = '\0';  // Null-terminate JSON string

    // Parse JSON (ArduinoJson v7 auto-sizing JsonDocument)
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, (const char*)buffer);
    free(buffer);  // Done with file buffer

    if (error) {
        Serial.printf("CONFIG: JSON parse failed: %s, using defaults\n", error.c_str());
        return config_create_defaults();
    }

    // Deserialize AppConfig
    AppConfig cfg;

    // Read version field (CFG-06)
    if (!doc["version"].isNull()) {
        cfg.version = doc["version"].as<uint8_t>();
    } else {
        cfg.version = 0;  // No version field in file
    }
    Serial.printf("CONFIG: schema version %d (expected %d)\n", cfg.version, CONFIG_VERSION);
    if (cfg.version > CONFIG_VERSION) {
        Serial.println("CONFIG: WARNING - config was created by a newer version, some fields may be ignored");
    } else if (cfg.version < CONFIG_VERSION) {
        Serial.println("CONFIG: NOTE - older config format, will be upgraded on next save");
    }

    if (!doc["active_profile_name"].isNull()) {
        cfg.active_profile_name = doc["active_profile_name"].as<const char*>();
    }
    if (!doc["brightness_level"].isNull()) {
        cfg.brightness_level = doc["brightness_level"].as<uint8_t>();
    }

    // Parse display mode settings (v0.9.1) -- defaults if missing
    cfg.default_mode = doc["default_mode"] | (uint8_t)0;  // MODE_HOTKEYS
    cfg.slideshow_interval_sec = doc["slideshow_interval_sec"] | (uint16_t)30;
    cfg.clock_analog = doc["clock_analog"] | false;

    // Validate default_mode range
    if (cfg.default_mode > 3) {
        Serial.printf("CONFIG: WARNING - invalid default_mode=%d, using MODE_HOTKEYS\n", cfg.default_mode);
        cfg.default_mode = 0;
    }
    // Validate slideshow interval
    if (cfg.slideshow_interval_sec < 5) cfg.slideshow_interval_sec = 5;
    if (cfg.slideshow_interval_sec > 300) cfg.slideshow_interval_sec = 300;

    cfg.profiles.clear();
    if (!doc["profiles"].isNull()) {
        JsonArray profiles_array = doc["profiles"].as<JsonArray>();
        for (JsonObject profile_obj : profiles_array) {
            ProfileConfig profile;
            json_to_profile(profile_obj, profile);
            cfg.profiles.push_back(profile);
        }
    }

    // Parse stats_header (v0.9.1) -- defaults if missing
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
            // Validate type range
            if (sc.type < 1 || sc.type > STAT_TYPE_MAX) {
                Serial.printf("CONFIG: WARNING - invalid stat type %d, skipping\n", sc.type);
                continue;
            }
            cfg.stats_header.push_back(sc);
            stat_count++;
        }
        Serial.printf("CONFIG: Loaded %d stats_header entries\n", (int)cfg.stats_header.size());
    } else {
        // No stats_header in JSON -- apply defaults (matches original hardcoded 8)
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

    // Validate: ensure active profile exists
    if (cfg.profiles.empty() || !cfg.get_active_profile()) {
        Serial.println("CONFIG: Invalid configuration (no valid active profile), using defaults");
        return config_create_defaults();
    }

    // Validate page count (CFG-03)
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

    // Load summary logging
    int total_buttons = 0;
    for (const auto& page : active->pages) {
        total_buttons += (int)page.buttons.size();
    }
    Serial.printf("CONFIG: Loaded '%s' - %zu pages, %d total buttons, version %d\n",
                  cfg.active_profile_name.c_str(), active->pages.size(),
                  total_buttons, cfg.version);
    return cfg;
}

bool config_save(const AppConfig& config) {
    if (!sdcard_mounted()) {
        Serial.println("CONFIG: SD card not mounted, cannot save");
        return false;
    }

    // Backup existing config.json to config.json.bak (CFG-07)
    if (sdcard_file_exists("/config.json")) {
        // Read existing file into PSRAM buffer
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
        } else {
            Serial.println("CONFIG: WARNING - PSRAM alloc failed for backup, continuing save");
        }
    }

    // Build JSON document (ArduinoJson v7 auto-sizing)
    JsonDocument doc;
    doc["version"] = CONFIG_VERSION;
    doc["active_profile_name"] = config.active_profile_name.c_str();
    doc["brightness_level"] = config.brightness_level;

    // Display mode settings (v0.9.1)
    doc["default_mode"] = config.default_mode;
    doc["slideshow_interval_sec"] = config.slideshow_interval_sec;
    doc["clock_analog"] = config.clock_analog;

    JsonArray profiles_array = doc["profiles"].to<JsonArray>();
    for (const auto& profile : config.profiles) {
        JsonObject profile_obj = profiles_array.add<JsonObject>();
        profile_to_json(profile_obj, profile);
    }

    // Serialize stats_header
    if (!config.stats_header.empty()) {
        JsonArray stats_arr = doc["stats_header"].to<JsonArray>();
        for (const auto& sc : config.stats_header) {
            JsonObject stat_obj = stats_arr.add<JsonObject>();
            stat_obj["type"] = sc.type;
            stat_obj["color"] = sc.color;
            stat_obj["position"] = sc.position;
        }
    }

    // Serialize to string
    String json_str;
    serializeJson(doc, json_str);

    // Atomic write pattern (CFG-08): write to /config.tmp, then rename
    if (!sdcard_write_file("/config.tmp", (const uint8_t*)json_str.c_str(), json_str.length())) {
        Serial.println("CONFIG: Failed to write /config.tmp");
        return false;
    }

    // Remove old config.json before rename (FAT may not support overwrite-rename)
    sdcard_file_remove("/config.json");

    // Rename temp to final
    if (!sdcard_file_rename("/config.tmp", "/config.json")) {
        Serial.println("CONFIG: Failed to rename /config.tmp to /config.json");
        // Attempt recovery: restore from backup
        if (sdcard_file_exists("/config.json.bak")) {
            sdcard_file_rename("/config.json.bak", "/config.json");
            Serial.println("CONFIG: Restored /config.json from backup");
        }
        return false;
    }

    // Verify the written file parses correctly
    uint8_t *verify_buf = (uint8_t *)ps_malloc(64 * 1024);
    if (verify_buf) {
        int verify_bytes = sdcard_read_file("/config.json", verify_buf, (64 * 1024) - 1);
        if (verify_bytes > 0) {
            verify_buf[verify_bytes] = '\0';
            JsonDocument verify_doc;
            DeserializationError verify_err = deserializeJson(verify_doc, (const char*)verify_buf);
            if (verify_err) {
                Serial.printf("CONFIG: WARNING - saved file failed verification: %s\n", verify_err.c_str());
                // Restore from backup
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
