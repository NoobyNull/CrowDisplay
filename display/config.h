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

// Maximum buttons per page (validated on load)
#define CONFIG_MAX_BUTTONS 16
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

    // Constructor with defaults
    ButtonConfig()
        : label(""), description(""), color(0xFFFFFF), icon(""),
          action_type(ACTION_HOTKEY), modifiers(0), keycode(0),
          consumer_code(0) {}
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

    AppConfig() : version(CONFIG_VERSION), active_profile_name(""), profiles(), brightness_level(100) {}

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
