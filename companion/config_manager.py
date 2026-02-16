"""
Config Manager: In-memory configuration state with JSON I/O

Holds the AppConfig dict (profile hierarchy) and provides:
- JSON load/save to disk
- Config navigation and updates
- Validation before deploy
- Qt signal emission on config changes
"""

import json
from typing import Dict, List, Any, Optional


# Action type constants (must match device/protocol.h)
ACTION_HOTKEY = 0
ACTION_MEDIA_KEY = 1

# Modifier constants (must match shared/protocol.h)
MOD_NONE = 0x00
MOD_CTRL = 0x01
MOD_SHIFT = 0x02
MOD_ALT = 0x04
MOD_GUI = 0x08

# Config constraints
CONFIG_VERSION = 1
CONFIG_MAX_PAGES = 16
CONFIG_MAX_BUTTONS = 12  # 4x3 grid capacity

# Grid dimensions
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


class ConfigManager:
    """Manages in-memory AppConfig with JSON I/O and validation"""

    def __init__(self):
        self.config = {}
        self.config_changed_callback = None
        self.new_config()

    def new_config(self) -> None:
        """Create empty 3-page default config"""
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
                        {
                            "name": "Page 1",
                            "buttons": [
                                {
                                    "label": f"Button {i+1}",
                                    "description": "",
                                    "color": DEFAULT_COLORS["BLUE"],
                                    "icon": "\uf015",
                                    "action_type": ACTION_HOTKEY,
                                    "modifiers": MOD_NONE,
                                    "keycode": 0,
                                    "consumer_code": 0,
                                    "grid_row": -1,
                                    "grid_col": -1,
                                    "pressed_color": 0,
                                }
                                for i in range(12)  # 4x3 grid
                            ],
                        },
                        {
                            "name": "Page 2",
                            "buttons": [
                                {
                                    "label": f"B{i+13}",
                                    "description": "",
                                    "color": DEFAULT_COLORS["TEAL"],
                                    "icon": "\uf015",
                                    "action_type": ACTION_HOTKEY,
                                    "modifiers": MOD_NONE,
                                    "keycode": 0,
                                    "consumer_code": 0,
                                    "grid_row": -1,
                                    "grid_col": -1,
                                    "pressed_color": 0,
                                }
                                for i in range(12)
                            ],
                        },
                        {
                            "name": "Page 3",
                            "buttons": [
                                {
                                    "label": f"B{i+25}",
                                    "description": "",
                                    "color": DEFAULT_COLORS["RED"],
                                    "icon": "\uf015",
                                    "action_type": ACTION_HOTKEY,
                                    "modifiers": MOD_NONE,
                                    "keycode": 0,
                                    "consumer_code": 0,
                                    "grid_row": -1,
                                    "grid_col": -1,
                                    "pressed_color": 0,
                                }
                                for i in range(12)
                            ],
                        },
                    ],
                }
            ],
        }
        self._emit_changed()

    def load_json_file(self, path: str) -> bool:
        """Load config from JSON file. Returns True on success."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False
            self.config = data
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

    def get_button(self, page_idx: int, button_idx: int) -> Optional[Dict[str, Any]]:
        """Get button dict by page and button index"""
        page = self.get_page(page_idx)
        if page is None:
            return None
        buttons = page.get("buttons", [])
        if 0 <= button_idx < len(buttons):
            return buttons[button_idx]
        return None

    def set_button(
        self, page_idx: int, button_idx: int, button_dict: Dict[str, Any]
    ) -> bool:
        """Update button at page_idx, button_idx. Returns True on success."""
        page = self.get_page(page_idx)
        if page is None:
            return False
        buttons = page.get("buttons", [])
        if not (0 <= button_idx < len(buttons)):
            return False
        buttons[button_idx] = button_dict
        self._emit_changed()
        return True

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
            "buttons": [
                {
                    "label": "",
                    "description": "",
                    "color": DEFAULT_COLORS["BLUE"],
                    "icon": "\uf015",
                    "action_type": ACTION_HOTKEY,
                    "modifiers": MOD_NONE,
                    "keycode": 0,
                    "consumer_code": 0,
                    "grid_row": -1,
                    "grid_col": -1,
                    "pressed_color": 0,
                }
                for _ in range(12)
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
            return False  # Keep at least 1 page
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
        """Move a page from old_index to new_index within active profile.

        Returns False if either index is out of range.
        """
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
        """
        Validate config structure.
        Returns (is_valid, error_message)
        """
        # Check version
        if self.config.get("version") != CONFIG_VERSION:
            return False, "Config version mismatch"

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

        # Check profiles
        profiles = self.config.get("profiles", [])
        if not profiles:
            return False, "No profiles defined"

        # Check active profile exists
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

        # Check buttons
        for pi, page in enumerate(pages):
            buttons = page.get("buttons", [])
            if not buttons:
                return False, f"Page {pi} has no buttons"

            if len(buttons) > CONFIG_MAX_BUTTONS:
                return False, f"Page {pi} has too many buttons"

            for bi, button in enumerate(buttons):
                if not isinstance(button.get("label"), str):
                    return False, f"Page {pi} button {bi}: invalid label"
                if not isinstance(button.get("color"), int):
                    return False, f"Page {pi} button {bi}: invalid color"
                if button.get("action_type") not in (ACTION_HOTKEY, ACTION_MEDIA_KEY):
                    return False, f"Page {pi} button {bi}: invalid action_type"

                # Validate grid positioning (v0.9.1)
                grid_row = button.get("grid_row", -1)
                grid_col = button.get("grid_col", -1)
                if not isinstance(grid_row, int) or grid_row < -1 or grid_row >= GRID_ROWS:
                    return False, f"Page {pi} button {bi}: grid_row {grid_row} out of range [-1, {GRID_ROWS - 1}]"
                if not isinstance(grid_col, int) or grid_col < -1 or grid_col >= GRID_COLS:
                    return False, f"Page {pi} button {bi}: grid_col {grid_col} out of range [-1, {GRID_COLS - 1}]"
                # Partial positioning check: both must be set together
                if (grid_row >= 0) != (grid_col >= 0):
                    return False, f"Page {pi} button {bi}: partial grid position (row={grid_row}, col={grid_col}); set both or neither"

                # Validate pressed_color
                pressed_color = button.get("pressed_color", 0)
                if isinstance(pressed_color, int) and (pressed_color < 0 or pressed_color > 0xFFFFFF):
                    return False, f"Page {pi} button {bi}: pressed_color out of range [0, 0xFFFFFF]"

        return True, ""

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
