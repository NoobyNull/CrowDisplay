#pragma once

#include <stdint.h>
#include <vector>
#include <string>

// ============================================================
// Configuration Schema for WYSIWYG Widget Layouts
// ============================================================
//
// Config version: increment when schema changes require migration.
// v1: Grid-based button layout (4x3 grid with spans)
// v2: WYSIWYG absolute pixel positioning with widget types
#define CONFIG_VERSION 2

// Maximum pages per profile (validated on load)
#define CONFIG_MAX_PAGES 16

// Maximum widgets per page
#define CONFIG_MAX_WIDGETS 32

// Display dimensions
#define DISPLAY_WIDTH  800
#define DISPLAY_HEIGHT 480

// Snap grid for editor positioning (pixels)
#define SNAP_GRID 10

// Minimum widget dimensions
#define WIDGET_MIN_W 40
#define WIDGET_MIN_H 30

// Legacy grid dimensions (for v1 migration)
#define GRID_COLS 4
#define GRID_ROWS 3

//
// This schema defines the JSON structure for widget layouts
// that can be stored on SD card and loaded at runtime.
//
// Format: profiles[] contains pages, each page contains widgets
// JSON: { "profiles": [ { "name": "...", "pages": [ { "widgets": [...] } ] } ] }

// ============================================================
// Widget Types
// ============================================================

enum WidgetType : uint8_t {
    WIDGET_HOTKEY_BUTTON = 0,    // Keyboard shortcut trigger with icon/label/color
    WIDGET_STAT_MONITOR  = 1,    // Single system stat (CPU%, temp, etc.)
    WIDGET_STATUS_BAR    = 2,    // Device info: WiFi, battery, time
    WIDGET_CLOCK         = 3,    // Analog or digital clock face
    WIDGET_TEXT_LABEL    = 4,    // Static text with configurable font/color
    WIDGET_SEPARATOR     = 5,    // Horizontal or vertical divider line
    WIDGET_PAGE_NAV      = 6,    // Visual page indicator dots/arrows
};

#define WIDGET_TYPE_MAX 6

// ============================================================
// Button Action Types (used by WIDGET_HOTKEY_BUTTON)
// ============================================================

enum ActionType : uint8_t {
    ACTION_HOTKEY = 0,        // Keyboard hotkey (modifiers + keycode)
    ACTION_MEDIA_KEY = 1,     // Media control (consumer control code)
    ACTION_LAUNCH_APP = 2,    // Launch/focus application (PC-side)
    ACTION_SHELL_CMD = 3,     // Run shell command (PC-side)
    ACTION_OPEN_URL = 4,      // Open URL (PC-side)
    ACTION_DISPLAY_SETTINGS = 5,  // Toggle config AP mode (display-local)
    ACTION_DISPLAY_CLOCK = 6,     // Switch to clock mode (display-local)
    ACTION_DISPLAY_PICTURE = 7,   // Switch to picture frame mode (display-local)
    ACTION_PAGE_NEXT = 8,         // Navigate to next page (display-local)
    ACTION_PAGE_PREV = 9,         // Navigate to previous page (display-local)
    ACTION_PAGE_GOTO = 10,        // Go to specific page (uses keycode as page number)
    ACTION_MODE_CYCLE = 11,       // Cycle through configured display modes
    ACTION_BRIGHTNESS = 12,       // Cycle brightness presets
    ACTION_CONFIG_MODE = 13,      // Enter SoftAP config mode
    ACTION_DDC = 14,              // DDC/CI monitor control (brightness, contrast, input, etc.)
    ACTION_FOCUS_NEXT = 15,       // Focus next button on current page (display-local)
    ACTION_FOCUS_PREV = 16,       // Focus previous button on current page (display-local)
    ACTION_FOCUS_ACTIVATE = 17,   // Activate (press) the currently focused button (display-local)
};

// ============================================================
// Widget Configuration (replaces ButtonConfig)
// ============================================================

struct WidgetConfig {
    // --- Layout (absolute pixel positioning on 800x480 display) ---
    int16_t x;                // X position in pixels (0 = left edge)
    int16_t y;                // Y position in pixels (0 = top edge)
    int16_t width;            // Width in pixels
    int16_t height;           // Height in pixels

    // --- Common properties ---
    WidgetType widget_type;   // Which widget type this is
    std::string label;        // Display label (used by most widget types)
    bool show_label;          // Whether to render label on device
    uint32_t color;           // Primary color (0xRRGGBB)
    uint32_t bg_color;        // Background color (0xRRGGBB, 0 = transparent/default)

    // --- Hotkey Button properties (widget_type == WIDGET_HOTKEY_BUTTON) ---
    std::string description;  // Tooltip description (e.g., "Super+1")
    bool show_description;    // Whether to render description on device
    std::string icon;         // LVGL symbol string (e.g., LV_SYMBOL_HOME)
    std::string icon_path;    // SD card image path (e.g., "/icons/calc.png") — overrides icon symbol
    ActionType action_type;   // HOTKEY or MEDIA_KEY
    uint8_t modifiers;        // MOD_CTRL | MOD_SHIFT | MOD_ALT | MOD_GUI
    uint8_t keycode;          // ASCII key or special key code
    uint16_t consumer_code;   // USB HID consumer control code (for MEDIA_KEY)
    uint32_t pressed_color;   // 0x000000 = auto-darken, else explicit color

    // --- DDC Monitor Control properties (action_type == ACTION_DDC) ---
    uint8_t ddc_vcp_code;     // DDC VCP code (0x10=brightness, 0x12=contrast, etc.)
    uint16_t ddc_value;       // Absolute value (when ddc_adjustment == 0)
    int16_t ddc_adjustment;   // Signed step (+/-), 0 = use absolute value
    uint8_t ddc_display;      // ddcutil --display N (0 = auto-detect)

    // --- Stat Monitor properties (widget_type == WIDGET_STAT_MONITOR) ---
    uint8_t stat_type;        // StatType enum value (1-23)
    uint8_t value_position;   // 0=inline (default), 1=value top/label bottom, 2=label top/value bottom

    // --- Clock properties (widget_type == WIDGET_CLOCK) ---
    bool clock_analog;        // true = analog, false = digital

    // --- Status Bar properties (widget_type == WIDGET_STATUS_BAR) ---
    bool show_wifi;           // Show WiFi icon
    bool show_pc;             // Show USB/PC connection icon
    bool show_settings;       // Show settings gear icon
    bool show_brightness;     // Show brightness icon
    bool show_battery;        // Show battery percentage
    bool show_time;           // Show current time
    uint8_t icon_spacing;     // Spacing between status bar icons in pixels (2-20)

    // --- Text Label properties (widget_type == WIDGET_TEXT_LABEL) ---
    uint8_t font_size;        // Font size (12, 14, 16, 20, 22, 28, 40)
    uint8_t text_align;       // 0=left, 1=center, 2=right

    // --- Separator properties (widget_type == WIDGET_SEPARATOR) ---
    bool separator_vertical;  // true = vertical, false = horizontal
    uint8_t thickness;        // Line thickness in pixels (1-8)

    // Constructor with defaults
    WidgetConfig()
        : x(0), y(0), width(180), height(100),
          widget_type(WIDGET_HOTKEY_BUTTON),
          label(""), show_label(true), color(0xFFFFFF), bg_color(0),
          description(""), show_description(true), icon(""), icon_path(""),
          action_type(ACTION_HOTKEY), modifiers(0), keycode(0),
          consumer_code(0), pressed_color(0x000000),
          ddc_vcp_code(0), ddc_value(0), ddc_adjustment(0), ddc_display(0),
          stat_type(0), value_position(0),
          clock_analog(false),
          show_wifi(true), show_pc(true), show_settings(true), show_brightness(true),
          show_battery(true), show_time(true), icon_spacing(8),
          font_size(16), text_align(1),
          separator_vertical(false), thickness(2) {}
};

// ============================================================
// Page Configuration
// ============================================================

struct PageConfig {
    std::string name;                       // Page name (e.g., "Window Manager")
    std::string bg_image;                   // SD card path for background image (e.g., "/bkgnds/dark.png")
    std::vector<WidgetConfig> widgets;      // Widgets on this page

    PageConfig() : name(""), bg_image(""), widgets() {}
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
// Hardware Button Configuration
// ============================================================

struct HwButtonConfig {
    ActionType action_type;
    std::string label;
    uint8_t keycode;        // For PAGE_GOTO (page number), or HOTKEY keycode
    uint16_t consumer_code; // For MEDIA_KEY
    uint8_t modifiers;      // For HOTKEY modifiers
    uint8_t ddc_vcp_code;   // For ACTION_DDC
    uint16_t ddc_value;
    int16_t ddc_adjustment;
    uint8_t ddc_display;
    HwButtonConfig() : action_type(ACTION_PAGE_NEXT), label(""), keycode(0),
                       consumer_code(0), modifiers(0),
                       ddc_vcp_code(0), ddc_value(0), ddc_adjustment(0), ddc_display(0) {}
};

struct EncoderConfig {
    ActionType push_action;
    std::string push_label;
    uint8_t push_keycode;
    uint16_t push_consumer_code;
    uint8_t push_modifiers;
    uint8_t encoder_mode;    // 0=page_nav, 1=volume, 2=brightness, 3=app_select, 4=mode_cycle, 5=ddc_control
    uint8_t ddc_vcp_code;    // For mode 5: VCP code to adjust
    uint8_t ddc_step;        // For mode 5: unsigned step per click
    uint8_t ddc_display;     // For mode 5: display number (0=auto)
    EncoderConfig() : push_action(ACTION_BRIGHTNESS), push_label("Brightness"),
                      push_keycode(0), push_consumer_code(0), push_modifiers(0),
                      encoder_mode(0), ddc_vcp_code(0x10), ddc_step(10), ddc_display(0) {}
};

struct ModeCycleConfig {
    std::vector<uint8_t> enabled_modes; // DisplayMode values in rotation order
    ModeCycleConfig() : enabled_modes({0, 1, 2, 3}) {} // All modes by default
};

struct DisplaySettings {
    uint16_t dim_timeout_sec;
    uint16_t sleep_timeout_sec;
    bool wake_on_touch;
    bool clock_24h;
    uint32_t clock_color_theme;
    uint16_t slideshow_interval_sec;
    std::string slideshow_transition;   // "fade", "slide", "none"
    DisplaySettings() : dim_timeout_sec(60), sleep_timeout_sec(300),
                        wake_on_touch(true), clock_24h(true),
                        clock_color_theme(0xFFFFFF), slideshow_interval_sec(30),
                        slideshow_transition("fade") {}
};

// ============================================================
// Application Configuration
// ============================================================

struct AppConfig {
    uint8_t version;                      // Config schema version (CONFIG_VERSION)
    std::string active_profile_name;      // Currently active profile name
    std::vector<ProfileConfig> profiles;  // All loaded profiles
    uint8_t brightness_level;             // Display brightness (0-100)

    // Display mode settings
    uint8_t default_mode;                 // DisplayMode enum value (0=HOTKEYS, 1=CLOCK, 2=PICTURE_FRAME, 3=STANDBY)
    uint16_t slideshow_interval_sec;      // Picture frame slideshow interval in seconds (default 30)
    bool clock_analog;                    // true = analog clock, false = digital clock (global fallback)

    // Stats header configuration (for stat monitor widgets without explicit config)
    std::vector<StatConfig> stats_header; // User-selected stats (default 8, max CONFIG_MAX_STATS)

    // Hardware input configuration
    HwButtonConfig hw_buttons[4];
    EncoderConfig encoder;
    ModeCycleConfig mode_cycle;
    DisplaySettings display_settings;

    AppConfig() : version(CONFIG_VERSION), active_profile_name(""), profiles(), brightness_level(100),
                  default_mode(0), slideshow_interval_sec(30), clock_analog(false), stats_header(),
                  hw_buttons(), encoder(), mode_cycle(), display_settings() {}

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
// Handles v1→v2 migration automatically
AppConfig config_load();

// Save configuration to SD card (/config.json)
// Writes JSON atomically: write to /config.tmp, rename to /config.json
bool config_save(const AppConfig& config);

// Create default configuration (hardcoded builtin profiles)
AppConfig config_create_defaults();
