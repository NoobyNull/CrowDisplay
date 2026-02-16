#pragma once

#include <stdint.h>
#include <vector>
#include <string>

// ============================================================
// Configuration Schema for Configurable Hotkey Layouts
// ============================================================
//
// Config version: increment when schema changes require migration.
#define CONFIG_VERSION 1

// Maximum pages per profile (validated on load)
#define CONFIG_MAX_PAGES 16

// Maximum buttons per page (4x3 grid = 12)
#define CONFIG_MAX_BUTTONS 12

// Grid dimensions
#define GRID_COLS 4
#define GRID_ROWS 3
//
// This schema defines the JSON structure for hotkey profiles
// that can be stored on SD card and loaded at runtime.
//
// Format: profiles[] contains pages, each page contains buttons
// JSON: { "profiles": [ { "name": "...", "pages": [ { "buttons": [...] } ] } ] }

// ============================================================
// Button Action Types
// ============================================================

enum ActionType : uint8_t {
    ACTION_HOTKEY = 0,        // Keyboard hotkey (modifiers + keycode)
    ACTION_MEDIA_KEY = 1,     // Media control (consumer control code)
};

// ============================================================
// Button Configuration
// ============================================================

struct ButtonConfig {
    // Display properties
    std::string label;        // Short button label (e.g., "WS 1", "Kill")
    std::string description;  // Tooltip description (e.g., "Super+1")
    uint32_t color;           // LVGL color (0xRRGGBB)
    std::string icon;         // LVGL symbol string (e.g., LV_SYMBOL_HOME)

    // Action properties
    ActionType action_type;   // HOTKEY or MEDIA_KEY
    uint8_t modifiers;        // MOD_CTRL | MOD_SHIFT | MOD_ALT | MOD_GUI
    uint8_t keycode;          // ASCII key or special key code (for HOTKEY)
    uint16_t consumer_code;   // USB HID consumer control code (for MEDIA_KEY)

    // Grid positioning (optional, defaults to auto-flow)
    int8_t grid_row;          // -1 = auto-flow (default), 0-2 = explicit row
    int8_t grid_col;          // -1 = auto-flow (default), 0-3 = explicit column
    uint32_t pressed_color;   // 0x000000 = auto-darken (default), else explicit color

    // Constructor with defaults
    ButtonConfig()
        : label(""), description(""), color(0xFFFFFF), icon(""),
          action_type(ACTION_HOTKEY), modifiers(0), keycode(0),
          consumer_code(0), grid_row(-1), grid_col(-1), pressed_color(0x000000) {}
};

// ============================================================
// Page Configuration
// ============================================================

struct PageConfig {
    std::string name;                     // Page name (e.g., "Window Manager")
    std::vector<ButtonConfig> buttons;    // Buttons on this page (up to 12)

    PageConfig() : name(""), buttons() {}
};

// ============================================================
// Stats Header Configuration
// ============================================================

#define CONFIG_MAX_STATS 8

struct StatConfig {
    uint8_t type;      // StatType enum value (1-20)
    uint32_t color;    // Display color (0xRRGGBB)
    uint8_t position;  // Display order (0-based, left-to-right then row wrap)

    StatConfig() : type(0), color(0xFFFFFF), position(0) {}
    StatConfig(uint8_t t, uint32_t c, uint8_t p) : type(t), color(c), position(p) {}
};

// ============================================================
// Profile Configuration
// ============================================================

struct ProfileConfig {
    std::string name;                     // Profile name (e.g., "Hyprland Default")
    std::vector<PageConfig> pages;        // Pages in this profile

    ProfileConfig() : name(""), pages() {}
};

// ============================================================
// Application Configuration
// ============================================================

struct AppConfig {
    uint8_t version;                      // Config schema version (CONFIG_VERSION)
    std::string active_profile_name;      // Currently active profile name
    std::vector<ProfileConfig> profiles;  // All loaded profiles
    uint8_t brightness_level;             // Display brightness (0-100)

    // Display mode settings (v0.9.1)
    uint8_t default_mode;                 // DisplayMode enum value (0=HOTKEYS, 1=CLOCK, 2=PICTURE_FRAME, 3=STANDBY)
    uint16_t slideshow_interval_sec;      // Picture frame slideshow interval in seconds (default 30)
    bool clock_analog;                    // true = analog clock, false = digital clock

    // Stats header configuration (v0.9.1)
    std::vector<StatConfig> stats_header; // User-selected stats (default 8, max CONFIG_MAX_STATS)

    AppConfig() : version(CONFIG_VERSION), active_profile_name(""), profiles(), brightness_level(100),
                  default_mode(0), slideshow_interval_sec(30), clock_analog(false), stats_header() {}

    // Helper: Get currently active profile
    ProfileConfig* get_active_profile() {
        for (auto& p : profiles) {
            if (p.name == active_profile_name) {
                return &p;
            }
        }
        return nullptr;
    }

    const ProfileConfig* get_active_profile() const {
        for (const auto& p : profiles) {
            if (p.name == active_profile_name) {
                return &p;
            }
        }
        return nullptr;
    }

    // Helper: Get profile by name
    ProfileConfig* get_profile(const std::string& name) {
        for (auto& p : profiles) {
            if (p.name == name) {
                return &p;
            }
        }
        return nullptr;
    }
};

// ============================================================
// Configuration I/O Helpers (declared in config.cpp)
// ============================================================

// Load configuration from SD card (/config.json)
// Returns AppConfig with defaults on failure
AppConfig config_load();

// Save configuration to SD card (/config.json)
// Writes JSON atomically: write to /config.tmp, rename to /config.json
bool config_save(const AppConfig& config);

// Create default configuration (hardcoded builtin profiles)
AppConfig config_create_defaults();
