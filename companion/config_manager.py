"""
Config Manager: In-memory configuration state with JSON I/O

Holds the AppConfig dict (profile hierarchy) and provides:
- JSON load/save to disk
- Config navigation and updates
- Validation before deploy
- Qt signal emission on config changes
- V1→V2 migration (grid buttons → absolute widgets)
"""

import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional


# Action type constants (must match device/protocol.h)
ACTION_HOTKEY = 0
ACTION_MEDIA_KEY = 1
ACTION_LAUNCH_APP = 2    # Launch/focus application
ACTION_SHELL_CMD = 3     # Run shell command (fire and forget)
ACTION_OPEN_URL = 4      # Open URL in default browser
ACTION_DISPLAY_SETTINGS = 5  # Toggle config AP mode (display-local)
ACTION_DISPLAY_CLOCK = 6     # Switch to clock mode (display-local)
ACTION_DISPLAY_PICTURE = 7   # Switch to picture frame mode (display-local)
ACTION_PAGE_NEXT = 8         # Navigate to next page (display-local)
ACTION_PAGE_PREV = 9         # Navigate to previous page (display-local)
ACTION_PAGE_GOTO = 10        # Go to specific page N (display-local)
ACTION_MODE_CYCLE = 11       # Cycle through configured display modes (display-local)
ACTION_BRIGHTNESS = 12       # Cycle brightness presets (display-local)
ACTION_CONFIG_MODE = 13      # Enter SoftAP config mode (display-local)
ACTION_DDC = 14              # DDC/CI monitor control

VALID_ACTION_TYPES = (
    ACTION_HOTKEY, ACTION_MEDIA_KEY, ACTION_LAUNCH_APP, ACTION_SHELL_CMD, ACTION_OPEN_URL,
    ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE,
    ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO,
    ACTION_MODE_CYCLE, ACTION_BRIGHTNESS, ACTION_CONFIG_MODE,
    ACTION_DDC,
)

# Display-local actions that the companion should NOT try to execute
DISPLAY_LOCAL_ACTIONS = {
    ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE,
    ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO,
    ACTION_MODE_CYCLE, ACTION_BRIGHTNESS, ACTION_CONFIG_MODE,
}

# Human-readable names for action type dropdowns
ACTION_TYPE_NAMES = {
    ACTION_HOTKEY: "Keyboard Shortcut",
    ACTION_MEDIA_KEY: "Media Key",
    ACTION_LAUNCH_APP: "Launch App",
    ACTION_SHELL_CMD: "Shell Command",
    ACTION_OPEN_URL: "Open URL",
    ACTION_DISPLAY_SETTINGS: "Config Mode",
    ACTION_DISPLAY_CLOCK: "Clock Mode",
    ACTION_DISPLAY_PICTURE: "Picture Frame",
    ACTION_PAGE_NEXT: "Next Page",
    ACTION_PAGE_PREV: "Previous Page",
    ACTION_PAGE_GOTO: "Go to Page",
    ACTION_MODE_CYCLE: "Cycle Mode",
    ACTION_BRIGHTNESS: "Brightness",
    ACTION_CONFIG_MODE: "Config Mode (SoftAP)",
    ACTION_DDC: "DDC Monitor Control",
}

# Encoder rotation mode names
ENCODER_MODE_NAMES = {
    0: "Page Navigation",
    1: "Volume Control",
    2: "Brightness",
    3: "App Select",
    4: "Mode Cycle",
    5: "DDC Control",
}

# DDC/CI VCP code constants
DDC_VCP_BRIGHTNESS = 0x10
DDC_VCP_CONTRAST = 0x12
DDC_VCP_INPUT_SOURCE = 0x60
DDC_VCP_VOLUME = 0x62
DDC_VCP_AUDIO_MUTE = 0x8D
DDC_VCP_POWER_MODE = 0xD6

# Human-readable names for DDC VCP codes (for editor combo box)
DDC_VCP_NAMES = {
    DDC_VCP_BRIGHTNESS: "Brightness (0x10)",
    DDC_VCP_CONTRAST: "Contrast (0x12)",
    DDC_VCP_INPUT_SOURCE: "Input Source (0x60)",
    DDC_VCP_VOLUME: "Volume (0x62)",
    DDC_VCP_AUDIO_MUTE: "Audio Mute (0x8D)",
    DDC_VCP_POWER_MODE: "Power Mode (0xD6)",
}

# DDC input source values (common MCCS values)
DDC_INPUT_SOURCES = {
    "DP1": 0x0F,
    "DP2": 0x10,
    "HDMI1": 0x11,
    "HDMI2": 0x12,
}

# Widget type constants (must match display/config.h WidgetType enum)
WIDGET_HOTKEY_BUTTON = 0
WIDGET_STAT_MONITOR = 1
WIDGET_STATUS_BAR = 2
WIDGET_CLOCK = 3
WIDGET_TEXT_LABEL = 4
WIDGET_SEPARATOR = 5
WIDGET_PAGE_NAV = 6

WIDGET_TYPE_MAX = 6

WIDGET_TYPE_NAMES = {
    WIDGET_HOTKEY_BUTTON: "Hotkey Button",
    WIDGET_STAT_MONITOR: "Stat Monitor",
    WIDGET_STATUS_BAR: "Status Bar",
    WIDGET_CLOCK: "Clock",
    WIDGET_TEXT_LABEL: "Text Label",
    WIDGET_SEPARATOR: "Separator",
    WIDGET_PAGE_NAV: "Page Nav",
}

# Default widget sizes
WIDGET_DEFAULT_SIZES = {
    WIDGET_HOTKEY_BUTTON: (180, 100),
    WIDGET_STAT_MONITOR: (120, 50),
    WIDGET_STATUS_BAR: (800, 40),
    WIDGET_CLOCK: (200, 200),
    WIDGET_TEXT_LABEL: (160, 40),
    WIDGET_SEPARATOR: (200, 4),
    WIDGET_PAGE_NAV: (200, 30),
}

# Modifier constants (must match shared/protocol.h)
MOD_NONE = 0x00
MOD_CTRL = 0x01
MOD_SHIFT = 0x02
MOD_ALT = 0x04
MOD_GUI = 0x08

# Config constraints
CONFIG_VERSION = 2
CONFIG_MAX_PAGES = 16
CONFIG_MAX_WIDGETS = 32
CONFIG_MAX_STATS = 8

# Display dimensions
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
SNAP_GRID = 10
WIDGET_MIN_W = 40
WIDGET_MIN_H = 30

# Default config paths
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "crowpanel"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_ICONS_DIR = DEFAULT_CONFIG_DIR / "icons"  # Legacy, kept for migration

# Stat type range (must match shared/protocol.h StatType enum)
STAT_TYPE_MIN = 1
STAT_TYPE_MAX = 23  # 0x17

# Legacy grid dimensions (for v1 migration)
GRID_COLS = 4
GRID_ROWS = 3

# Default colors (hex RGB)
DEFAULT_COLORS = {
    "BLUE": 0x3498DB,
    "TEAL": 0x1ABC9C,
    "RED": 0xE74C3C,
    "CYAN": 0x00BCD4,
    "INDIGO": 0x3F51B5,
    "GREEN": 0x2ECC71,
    "ORANGE": 0xE67E22,
    "PURPLE": 0x9B59B6,
    "GREY": 0x95A5A6,
    "DARK_GREY": 0x34495E,
}


def get_default_hardware_buttons():
    """Default hardware button configuration (4 buttons)."""
    return [
        {"action_type": ACTION_PAGE_NEXT, "label": "Next Page", "keycode": 0, "consumer_code": 0, "modifiers": 0,
         "ddc_vcp_code": 0, "ddc_value": 0, "ddc_adjustment": 0, "ddc_display": 0},
        {"action_type": ACTION_PAGE_PREV, "label": "Prev Page", "keycode": 0, "consumer_code": 0, "modifiers": 0,
         "ddc_vcp_code": 0, "ddc_value": 0, "ddc_adjustment": 0, "ddc_display": 0},
        {"action_type": ACTION_MODE_CYCLE, "label": "Mode", "keycode": 0, "consumer_code": 0, "modifiers": 0,
         "ddc_vcp_code": 0, "ddc_value": 0, "ddc_adjustment": 0, "ddc_display": 0},
        {"action_type": ACTION_CONFIG_MODE, "label": "Config", "keycode": 0, "consumer_code": 0, "modifiers": 0,
         "ddc_vcp_code": 0, "ddc_value": 0, "ddc_adjustment": 0, "ddc_display": 0},
    ]


def get_default_encoder():
    """Default rotary encoder configuration."""
    return {
        "push_action": ACTION_BRIGHTNESS, "push_label": "Brightness",
        "push_keycode": 0, "push_consumer_code": 0, "push_modifiers": 0,
        "encoder_mode": 0,
        "ddc_vcp_code": DDC_VCP_BRIGHTNESS, "ddc_step": 10, "ddc_display": 0,
    }


def get_default_mode_cycle():
    """Default mode cycle order (all modes enabled)."""
    return [0, 1, 2, 3]


def get_default_display_settings():
    """Default display settings."""
    return {
        "dim_timeout_sec": 60, "sleep_timeout_sec": 300,
        "wake_on_touch": True, "clock_24h": True,
        "clock_color_theme": 0xFFFFFF, "slideshow_interval_sec": 30,
        "slideshow_transition": "fade",
    }


def make_default_widget(widget_type: int, x: int = 0, y: int = 0) -> Dict[str, Any]:
    """Create a default widget dict of the given type at position (x, y)."""
    w, h = WIDGET_DEFAULT_SIZES.get(widget_type, (180, 100))
    widget = {
        "widget_type": widget_type,
        "widget_id": str(uuid.uuid4()),
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "label": "",
        "color": 0xFFFFFF,
        "bg_color": 0,
    }

    if widget_type == WIDGET_HOTKEY_BUTTON:
        widget.update({
            "label": "Button",
            "description": "",
            "icon": "\uf015",
            "icon_source": "",
            "icon_source_type": "",
            "color": DEFAULT_COLORS["BLUE"],
            "action_type": ACTION_HOTKEY,
            "modifiers": MOD_NONE,
            "keycode": 0,
            "consumer_code": 0,
            "pressed_color": 0,
            "launch_command": "",
            "launch_wm_class": "",
            "launch_focus_or_launch": True,
            "shell_command": "",
            "url": "",
            "ddc_vcp_code": 0,
            "ddc_value": 0,
            "ddc_adjustment": 0,
            "ddc_display": 0,
        })
    elif widget_type == WIDGET_STAT_MONITOR:
        widget.update({
            "label": "CPU",
            "stat_type": 0x01,
            "color": DEFAULT_COLORS["BLUE"],
            "value_position": 0,
        })
    elif widget_type == WIDGET_STATUS_BAR:
        widget.update({
            "label": "Hotkeys",
            "color": 0xE0E0E0,
            "bg_color": 0x16213e,
            "show_wifi": True,
            "show_pc": True,
            "show_settings": True,
            "show_brightness": True,
            "show_time": True,
            "icon_spacing": 8,
        })
    elif widget_type == WIDGET_CLOCK:
        widget.update({
            "clock_analog": False,
            "color": 0xFFFFFF,
        })
    elif widget_type == WIDGET_TEXT_LABEL:
        widget.update({
            "label": "Label",
            "font_size": 16,
            "text_align": 1,
            "color": 0xFFFFFF,
        })
    elif widget_type == WIDGET_SEPARATOR:
        widget.update({
            "separator_vertical": False,
            "thickness": 2,
            "color": 0x555555,
        })
    elif widget_type == WIDGET_PAGE_NAV:
        widget.update({
            "color": DEFAULT_COLORS["BLUE"],
        })

    return widget


def _migrate_v1_page(v1_page: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a v1 grid-based page to v2 absolute-positioned widgets."""
    v2_page = {"name": v1_page.get("name", "Page"), "widgets": []}

    # Add default status bar
    v2_page["widgets"].append(make_default_widget(WIDGET_STATUS_BAR, 0, 0))

    # Grid cell dimensions for v1 layout
    GRID_X0 = 6
    GRID_Y0 = 50
    CELL_W = 192
    CELL_H = 122
    GAP = 6

    auto_row, auto_col = 0, 0
    for btn in v1_page.get("buttons", []):
        grid_row = btn.get("grid_row", -1)
        grid_col = btn.get("grid_col", -1)
        col_span = btn.get("col_span", 1)
        row_span = btn.get("row_span", 1)

        if grid_row >= 0 and grid_col >= 0:
            target_row, target_col = grid_row, grid_col
        else:
            target_row, target_col = auto_row, auto_col
            col_span = 1
            row_span = 1
            auto_col += 1
            if auto_col >= GRID_COLS:
                auto_col = 0
                auto_row += 1

        x = GRID_X0 + target_col * (CELL_W + GAP)
        y = GRID_Y0 + target_row * (CELL_H + GAP)
        w = col_span * CELL_W + (col_span - 1) * GAP
        h = row_span * CELL_H + (row_span - 1) * GAP

        widget = {
            "widget_type": WIDGET_HOTKEY_BUTTON,
            "x": x, "y": y, "width": w, "height": h,
            "label": btn.get("label", ""),
            "description": btn.get("description", ""),
            "color": btn.get("color", 0xFFFFFF),
            "bg_color": 0,
            "icon": btn.get("icon", ""),
            "action_type": btn.get("action_type", ACTION_HOTKEY),
            "modifiers": btn.get("modifiers", 0),
            "keycode": btn.get("keycode", 0),
            "consumer_code": btn.get("consumer_code", 0),
            "pressed_color": btn.get("pressed_color", 0),
            "launch_command": btn.get("launch_command", ""),
            "launch_wm_class": btn.get("launch_wm_class", ""),
            "launch_focus_or_launch": btn.get("launch_focus_or_launch", True),
            "shell_command": btn.get("shell_command", ""),
            "url": btn.get("url", ""),
        }
        v2_page["widgets"].append(widget)

    # Add page nav
    v2_page["widgets"].append(make_default_widget(WIDGET_PAGE_NAV, 300, 445))

    return v2_page


def _migrate_v1_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate entire v1 config to v2."""
    config["version"] = CONFIG_VERSION
    for profile in config.get("profiles", []):
        new_pages = []
        for page in profile.get("pages", []):
            if "buttons" in page:
                new_pages.append(_migrate_v1_page(page))
            elif "widgets" in page:
                new_pages.append(page)  # Already v2
            else:
                new_pages.append({"name": page.get("name", "Page"), "widgets": []})
        profile["pages"] = new_pages
    return config


def ensure_widget_ids(config: Dict[str, Any]) -> None:
    """Backfill widget_id on any widget that lacks one (backward compat for old configs)."""
    for profile in config.get("profiles", []):
        for page in profile.get("pages", []):
            for widget in page.get("widgets", []):
                if "widget_id" not in widget:
                    widget["widget_id"] = str(uuid.uuid4())


class ConfigManager:
    """Manages in-memory AppConfig with JSON I/O and validation"""

    def __init__(self):
        self.config = {}
        self.config_changed_callback = None
        self.new_config()

    def new_config(self) -> None:
        """Create empty 3-page default config with v2 widgets"""
        GRID_X0 = 6
        GRID_Y0 = 50
        CELL_W = 192
        CELL_H = 122
        GAP = 6

        def make_page(name: str, color: int, start_idx: int) -> Dict[str, Any]:
            page = {"name": name, "widgets": []}
            # Status bar
            page["widgets"].append(make_default_widget(WIDGET_STATUS_BAR, 0, 0))
            # 12 buttons in 4x3 grid
            for i in range(12):
                col = i % 4
                row = i // 4
                x = GRID_X0 + col * (CELL_W + GAP)
                y = GRID_Y0 + row * (CELL_H + GAP)
                w = make_default_widget(WIDGET_HOTKEY_BUTTON, x, y)
                w["width"] = CELL_W
                w["height"] = CELL_H
                w["label"] = f"Button {start_idx + i}"
                w["color"] = color
                page["widgets"].append(w)
            # Page nav
            page["widgets"].append(make_default_widget(WIDGET_PAGE_NAV, 300, 445))
            return page

        self.config = {
            "version": CONFIG_VERSION,
            "active_profile_name": "Default",
            "brightness_level": 100,
            "default_mode": 0,
            "slideshow_interval_sec": 30,
            "clock_analog": False,
            "profiles": [
                {
                    "name": "Default",
                    "pages": [
                        make_page("Page 1", DEFAULT_COLORS["BLUE"], 1),
                        make_page("Page 2", DEFAULT_COLORS["TEAL"], 13),
                        make_page("Page 3", DEFAULT_COLORS["RED"], 25),
                    ],
                }
            ],
            "hardware_buttons": get_default_hardware_buttons(),
            "encoder": get_default_encoder(),
            "mode_cycle": get_default_mode_cycle(),
            "display_settings": get_default_display_settings(),
        }
        ensure_widget_ids(self.config)
        self._emit_changed()

    def load_json_file(self, path: str) -> bool:
        """Load config from JSON file. Handles v1→v2 migration. Returns True on success."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False

            # Migrate v1 configs
            version = data.get("version", 0)
            if version < 2:
                data = _migrate_v1_config(data)

            self.config = data
            # Ensure hardware config sections exist with defaults
            if "hardware_buttons" not in self.config:
                self.config["hardware_buttons"] = get_default_hardware_buttons()
            if "encoder" not in self.config:
                self.config["encoder"] = get_default_encoder()
            if "mode_cycle" not in self.config:
                self.config["mode_cycle"] = get_default_mode_cycle()
            if "display_settings" not in self.config:
                self.config["display_settings"] = get_default_display_settings()
            ensure_widget_ids(self.config)
            self._emit_changed()
            return True
        except (json.JSONDecodeError, FileNotFoundError, IOError):
            return False

    def save_json_file(self, path: str) -> bool:
        """Save config to JSON file. Returns True on success."""
        try:
            with open(path, "w") as f:
                json.dump(self.config, f, indent=2)
            return True
        except IOError:
            return False

    def get_active_profile(self) -> Optional[Dict[str, Any]]:
        """Get currently active profile dict"""
        active_name = self.config.get("active_profile_name", "")
        for profile in self.config.get("profiles", []):
            if profile.get("name") == active_name:
                return profile
        return None

    def get_page(self, index: int) -> Optional[Dict[str, Any]]:
        """Get page dict by index (within active profile)"""
        profile = self.get_active_profile()
        if profile is None:
            return None
        pages = profile.get("pages", [])
        if 0 <= index < len(pages):
            return pages[index]
        return None

    def get_widget(self, page_idx: int, widget_idx: int) -> Optional[Dict[str, Any]]:
        """Get widget dict by page and widget index"""
        page = self.get_page(page_idx)
        if page is None:
            return None
        widgets = page.get("widgets", [])
        if 0 <= widget_idx < len(widgets):
            return widgets[widget_idx]
        return None

    def set_widget(
        self, page_idx: int, widget_idx: int, widget_dict: Dict[str, Any]
    ) -> bool:
        """Update widget at page_idx, widget_idx. Returns True on success."""
        page = self.get_page(page_idx)
        if page is None:
            return False
        widgets = page.get("widgets", [])
        if not (0 <= widget_idx < len(widgets)):
            return False
        widgets[widget_idx] = widget_dict
        self._emit_changed()
        return True

    def add_widget(self, page_idx: int, widget_dict: Dict[str, Any]) -> int:
        """Add a new widget to a page. Returns the widget index, or -1 on failure."""
        page = self.get_page(page_idx)
        if page is None:
            return -1
        widgets = page.get("widgets", [])
        if len(widgets) >= CONFIG_MAX_WIDGETS:
            return -1
        widgets.append(widget_dict)
        self._emit_changed()
        return len(widgets) - 1

    def remove_widget(self, page_idx: int, widget_idx: int) -> bool:
        """Remove widget by index. Returns True on success."""
        page = self.get_page(page_idx)
        if page is None:
            return False
        widgets = page.get("widgets", [])
        if not (0 <= widget_idx < len(widgets)):
            return False
        widgets.pop(widget_idx)
        self._emit_changed()
        return True

    def get_widget_count(self, page_idx: int) -> int:
        """Get number of widgets on a page"""
        page = self.get_page(page_idx)
        if page is None:
            return 0
        return len(page.get("widgets", []))

    def add_page(self, name: str) -> bool:
        """Add new page to active profile"""
        profile = self.get_active_profile()
        if profile is None:
            return False

        pages = profile.get("pages", [])
        if len(pages) >= CONFIG_MAX_PAGES:
            return False

        new_page = {
            "name": name,
            "widgets": [
                make_default_widget(WIDGET_STATUS_BAR, 0, 0),
                make_default_widget(WIDGET_PAGE_NAV, 300, 445),
            ],
        }
        pages.append(new_page)
        self._emit_changed()
        return True

    def remove_page(self, index: int) -> bool:
        """Remove page by index (but keep at least 1 page)"""
        profile = self.get_active_profile()
        if profile is None:
            return False

        pages = profile.get("pages", [])
        if len(pages) <= 1:
            return False
        if not (0 <= index < len(pages)):
            return False

        pages.pop(index)
        self._emit_changed()
        return True

    def rename_page(self, index: int, new_name: str) -> bool:
        """Rename page by index"""
        page = self.get_page(index)
        if page is None:
            return False
        page["name"] = new_name
        self._emit_changed()
        return True

    def reorder_page(self, old_index: int, new_index: int) -> bool:
        """Move a page from old_index to new_index within active profile."""
        profile = self.get_active_profile()
        if profile is None:
            return False
        pages = profile.get("pages", [])
        if not (0 <= old_index < len(pages)) or not (0 <= new_index < len(pages)):
            return False
        pages.insert(new_index, pages.pop(old_index))
        self._emit_changed()
        return True

    def get_page_count(self) -> int:
        """Get number of pages in active profile"""
        profile = self.get_active_profile()
        if profile is None:
            return 0
        return len(profile.get("pages", []))

    def to_json(self) -> str:
        """Serialize config dict to JSON string"""
        return json.dumps(self.config, indent=2)

    def validate(self) -> tuple[bool, str]:
        """Validate config structure. Returns (is_valid, error_message)."""
        # Check version
        if self.config.get("version") != CONFIG_VERSION:
            return False, f"Config version mismatch (got {self.config.get('version')}, expected {CONFIG_VERSION})"

        # Check display mode settings
        default_mode = self.config.get("default_mode", 0)
        if not isinstance(default_mode, int) or default_mode < 0 or default_mode > 3:
            return False, f"Invalid default_mode: {default_mode} (must be 0-3)"

        slideshow_interval = self.config.get("slideshow_interval_sec", 30)
        if not isinstance(slideshow_interval, int) or slideshow_interval < 5 or slideshow_interval > 300:
            return False, f"Invalid slideshow_interval_sec: {slideshow_interval} (must be 5-300)"

        clock_analog = self.config.get("clock_analog", False)
        if not isinstance(clock_analog, bool):
            return False, "clock_analog must be a boolean"

        # Check notification settings (optional)
        notifications_enabled = self.config.get("notifications_enabled", False)
        if not isinstance(notifications_enabled, bool):
            return False, "notifications_enabled must be a boolean"

        notification_filter = self.config.get("notification_filter", [])
        if not isinstance(notification_filter, list):
            return False, "notification_filter must be an array"
        for i, app in enumerate(notification_filter):
            if not isinstance(app, str):
                return False, f"notification_filter[{i}]: must be a string"

        # Check profiles
        profiles = self.config.get("profiles", [])
        if not profiles:
            return False, "No profiles defined"

        active_name = self.config.get("active_profile_name")
        active_profile = None
        for profile in profiles:
            if profile.get("name") == active_name:
                active_profile = profile
                break

        if active_profile is None:
            return False, f"Active profile '{active_name}' not found"

        # Check pages
        pages = active_profile.get("pages", [])
        if not pages:
            return False, "No pages in active profile"

        if len(pages) > CONFIG_MAX_PAGES:
            return False, f"Too many pages (max {CONFIG_MAX_PAGES})"

        # Check widgets
        for pi, page in enumerate(pages):
            widgets = page.get("widgets", [])
            if len(widgets) > CONFIG_MAX_WIDGETS:
                return False, f"Page {pi} has too many widgets (max {CONFIG_MAX_WIDGETS})"

            for wi, widget in enumerate(widgets):
                # Validate widget type
                wtype = widget.get("widget_type", 0)
                if not isinstance(wtype, int) or wtype < 0 or wtype > WIDGET_TYPE_MAX:
                    return False, f"Page {pi} widget {wi}: invalid widget_type {wtype}"

                # Validate position/size
                x = widget.get("x", 0)
                y = widget.get("y", 0)
                w = widget.get("width", 0)
                h = widget.get("height", 0)
                if not isinstance(x, int) or not isinstance(y, int):
                    return False, f"Page {pi} widget {wi}: x/y must be integers"
                if not isinstance(w, int) or not isinstance(h, int):
                    return False, f"Page {pi} widget {wi}: width/height must be integers"
                if x < 0 or y < 0:
                    return False, f"Page {pi} widget {wi}: position ({x},{y}) out of bounds"
                if w < WIDGET_MIN_W or h < WIDGET_MIN_H:
                    return False, f"Page {pi} widget {wi}: size {w}x{h} below minimum {WIDGET_MIN_W}x{WIDGET_MIN_H}"
                if x + w > DISPLAY_WIDTH or y + h > DISPLAY_HEIGHT:
                    return False, f"Page {pi} widget {wi}: extends beyond display ({x}+{w}x{y}+{h})"

                # Validate type-specific fields
                if wtype == WIDGET_HOTKEY_BUTTON:
                    if not isinstance(widget.get("label", ""), str):
                        return False, f"Page {pi} widget {wi}: invalid label"
                    if not isinstance(widget.get("color", 0), int):
                        return False, f"Page {pi} widget {wi}: invalid color"
                    at = widget.get("action_type", ACTION_HOTKEY)
                    if at not in VALID_ACTION_TYPES:
                        return False, f"Page {pi} widget {wi}: invalid action_type"
                    icon_source = widget.get("icon_source", "")
                    if icon_source and not isinstance(icon_source, str):
                        return False, f"Page {pi} widget {wi}: icon_source must be a string"
                    icon_source_type = widget.get("icon_source_type", "")
                    if icon_source_type and icon_source_type not in ("freedesktop", "file"):
                        return False, f"Page {pi} widget {wi}: icon_source_type must be 'freedesktop' or 'file'"

                elif wtype == WIDGET_STAT_MONITOR:
                    st = widget.get("stat_type", 0)
                    if not isinstance(st, int) or st < STAT_TYPE_MIN or st > STAT_TYPE_MAX:
                        return False, f"Page {pi} widget {wi}: stat_type {st} out of range"

        # Validate stats_header
        stats_header = self.config.get("stats_header", [])
        if not isinstance(stats_header, list):
            return False, "stats_header must be an array"
        if len(stats_header) > CONFIG_MAX_STATS:
            return False, f"stats_header has {len(stats_header)} entries (max {CONFIG_MAX_STATS})"

        seen_positions = set()
        for si, stat in enumerate(stats_header):
            if not isinstance(stat, dict):
                return False, f"stats_header[{si}]: must be an object"

            stat_type = stat.get("type")
            if not isinstance(stat_type, int) or stat_type < STAT_TYPE_MIN or stat_type > STAT_TYPE_MAX:
                return False, f"stats_header[{si}]: type {stat_type} out of range"

            color = stat.get("color", 0xFFFFFF)
            if not isinstance(color, int) or color < 0 or color > 0xFFFFFF:
                return False, f"stats_header[{si}]: color out of range"

            position = stat.get("position", si)
            if not isinstance(position, int) or position < 0 or position >= CONFIG_MAX_STATS:
                return False, f"stats_header[{si}]: position {position} out of range"

            if position in seen_positions:
                return False, f"stats_header[{si}]: duplicate position {position}"
            seen_positions.add(position)

        return True, ""

    # Backward compatibility aliases
    def get_button(self, page_idx: int, button_idx: int) -> Optional[Dict[str, Any]]:
        """Alias for get_widget (backward compat)"""
        return self.get_widget(page_idx, button_idx)

    def set_button(
        self, page_idx: int, button_idx: int, button_dict: Dict[str, Any]
    ) -> bool:
        """Alias for set_widget (backward compat)"""
        return self.set_widget(page_idx, button_idx, button_dict)

    def _emit_changed(self) -> None:
        """Emit callback if registered"""
        if self.config_changed_callback:
            self.config_changed_callback()


# Singleton instance
_manager = None


def get_config_manager() -> ConfigManager:
    """Get or create singleton ConfigManager instance"""
    global _manager
    if _manager is None:
        _manager = ConfigManager()
    return _manager
