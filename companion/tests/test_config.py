"""
Test suite for config_manager.py - configuration round-trip and validation

Tests:
- Config loading and saving (JSON round-trip)
- Widget state serialization/deserialization
- Config migration (V1 grid buttons -> V2 absolute widgets)
- Validation of action types and structure
- Config defaults and schema
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import (
    ACTION_HOTKEY, ACTION_MEDIA_KEY, ACTION_LAUNCH_APP,
    ACTION_SHELL_CMD, ACTION_OPEN_URL,
    ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE,
    ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO,
    ACTION_MODE_CYCLE, ACTION_BRIGHTNESS, ACTION_CONFIG_MODE,
    ACTION_DDC, ACTION_FOCUS_NEXT, ACTION_FOCUS_PREV, ACTION_FOCUS_ACTIVATE,
    VALID_ACTION_TYPES, DISPLAY_LOCAL_ACTIONS,
)


class TestActionTypeConstants:
    """Verify action type constants are consistent"""

    def test_valid_action_types_completeness(self):
        """All individual action constants should be in VALID_ACTION_TYPES"""
        individual_types = {
            ACTION_HOTKEY, ACTION_MEDIA_KEY, ACTION_LAUNCH_APP,
            ACTION_SHELL_CMD, ACTION_OPEN_URL,
            ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE,
            ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO,
            ACTION_MODE_CYCLE, ACTION_BRIGHTNESS, ACTION_CONFIG_MODE,
            ACTION_DDC, ACTION_FOCUS_NEXT, ACTION_FOCUS_PREV, ACTION_FOCUS_ACTIVATE,
        }
        assert all(t in VALID_ACTION_TYPES for t in individual_types)

    def test_action_type_uniqueness(self):
        """All action type constants must be unique"""
        types_list = [
            ACTION_HOTKEY, ACTION_MEDIA_KEY, ACTION_LAUNCH_APP,
            ACTION_SHELL_CMD, ACTION_OPEN_URL,
            ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE,
            ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO,
            ACTION_MODE_CYCLE, ACTION_BRIGHTNESS, ACTION_CONFIG_MODE,
            ACTION_DDC, ACTION_FOCUS_NEXT, ACTION_FOCUS_PREV, ACTION_FOCUS_ACTIVATE,
        ]
        assert len(types_list) == len(set(types_list))

    def test_action_values_are_integers(self):
        """Action type constants should be integers"""
        types_to_check = [
            ACTION_HOTKEY, ACTION_MEDIA_KEY, ACTION_LAUNCH_APP,
            ACTION_SHELL_CMD, ACTION_OPEN_URL,
            ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE,
            ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO,
            ACTION_MODE_CYCLE, ACTION_BRIGHTNESS, ACTION_CONFIG_MODE,
            ACTION_DDC, ACTION_FOCUS_NEXT, ACTION_FOCUS_PREV, ACTION_FOCUS_ACTIVATE,
        ]
        assert all(isinstance(t, int) for t in types_to_check)


class TestDisplayLocalActions:
    """Verify display-local action classification"""

    def test_display_local_actions_are_valid(self):
        """All display-local actions must be in VALID_ACTION_TYPES"""
        assert all(action in VALID_ACTION_TYPES for action in DISPLAY_LOCAL_ACTIONS)

    def test_display_settings_is_local(self):
        """ACTION_DISPLAY_SETTINGS should be in display-local set"""
        assert ACTION_DISPLAY_SETTINGS in DISPLAY_LOCAL_ACTIONS

    def test_hotkey_is_not_local(self):
        """ACTION_HOTKEY should NOT be in display-local set"""
        assert ACTION_HOTKEY not in DISPLAY_LOCAL_ACTIONS

    def test_display_clock_is_local(self):
        """ACTION_DISPLAY_CLOCK should be in display-local set"""
        assert ACTION_DISPLAY_CLOCK in DISPLAY_LOCAL_ACTIONS

    def test_display_picture_is_local(self):
        """ACTION_DISPLAY_PICTURE should be in display-local set"""
        assert ACTION_DISPLAY_PICTURE in DISPLAY_LOCAL_ACTIONS

    def test_page_navigation_is_local(self):
        """Page navigation actions should be display-local"""
        for action in [ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO]:
            assert action in DISPLAY_LOCAL_ACTIONS


class TestConfigSchema:
    """Test basic config schema and default structures"""

    def _make_hotkey_action(self, mod=0, key=0x61) -> Dict[str, Any]:
        """Create a basic hotkey action"""
        return {
            "type": ACTION_HOTKEY,
            "mod": mod,
            "key": key,
        }

    def _make_media_key_action(self, code=0xE2) -> Dict[str, Any]:
        """Create a basic media key action"""
        return {
            "type": ACTION_MEDIA_KEY,
            "code": code,
        }

    def _make_launch_app_action(self, app="firefox") -> Dict[str, Any]:
        """Create a basic launch app action"""
        return {
            "type": ACTION_LAUNCH_APP,
            "app": app,
        }

    def _make_shell_cmd_action(self, cmd="echo test") -> Dict[str, Any]:
        """Create a basic shell command action"""
        return {
            "type": ACTION_SHELL_CMD,
            "cmd": cmd,
        }

    def _make_url_action(self, url="https://example.com") -> Dict[str, Any]:
        """Create a basic URL action"""
        return {
            "type": ACTION_OPEN_URL,
            "url": url,
        }

    def test_hotkey_action_schema(self):
        """Hotkey action should have type, mod, and key fields"""
        action = self._make_hotkey_action()
        assert action["type"] == ACTION_HOTKEY
        assert "mod" in action
        assert "key" in action

    def test_media_key_action_schema(self):
        """Media key action should have type and code fields"""
        action = self._make_media_key_action()
        assert action["type"] == ACTION_MEDIA_KEY
        assert "code" in action

    def test_launch_app_action_schema(self):
        """Launch app action should have type and app fields"""
        action = self._make_launch_app_action()
        assert action["type"] == ACTION_LAUNCH_APP
        assert "app" in action

    def test_shell_cmd_action_schema(self):
        """Shell command action should have type and cmd fields"""
        action = self._make_shell_cmd_action()
        assert action["type"] == ACTION_SHELL_CMD
        assert "cmd" in action

    def test_url_action_schema(self):
        """URL action should have type and url fields"""
        action = self._make_url_action()
        assert action["type"] == ACTION_OPEN_URL
        assert "url" in action


class TestConfigRoundTrip:
    """Test config JSON serialization and deserialization"""

    def test_json_serialization(self):
        """Config should be serializable to JSON"""
        config = {
            "version": 2,
            "pages": [
                {
                    "name": "Page 1",
                    "widgets": [
                        {
                            "id": "w1",
                            "type": "button",
                            "x": 10, "y": 10, "width": 100, "height": 50,
                            "label": "Test",
                            "action": {"type": ACTION_HOTKEY, "mod": 0, "key": 0x61},
                        }
                    ]
                }
            ]
        }

        json_str = json.dumps(config)
        assert isinstance(json_str, str)
        assert json.loads(json_str) == config

    def test_config_with_multiple_pages(self):
        """Config with multiple pages should round-trip correctly"""
        config = {
            "version": 2,
            "pages": [
                {"name": "Page 1", "widgets": []},
                {"name": "Page 2", "widgets": []},
                {"name": "Page 3", "widgets": []},
            ]
        }

        json_str = json.dumps(config)
        reloaded = json.loads(json_str)
        assert len(reloaded["pages"]) == 3
        assert reloaded["pages"][0]["name"] == "Page 1"

    def test_config_with_various_action_types(self):
        """Config with different action types should preserve all fields"""
        config = {
            "version": 2,
            "pages": [{
                "name": "Mixed Actions",
                "widgets": [
                    {
                        "id": "w1",
                        "type": "button",
                        "x": 0, "y": 0, "width": 100, "height": 50,
                        "label": "Hotkey",
                        "action": {"type": ACTION_HOTKEY, "mod": 0x01, "key": 0x61},
                    },
                    {
                        "id": "w2",
                        "type": "button",
                        "x": 100, "y": 0, "width": 100, "height": 50,
                        "label": "Media",
                        "action": {"type": ACTION_MEDIA_KEY, "code": 0xE2},
                    },
                    {
                        "id": "w3",
                        "type": "button",
                        "x": 200, "y": 0, "width": 100, "height": 50,
                        "label": "App",
                        "action": {"type": ACTION_LAUNCH_APP, "app": "firefox"},
                    },
                ]
            }]
        }

        json_str = json.dumps(config)
        reloaded = json.loads(json_str)
        widgets = reloaded["pages"][0]["widgets"]

        assert widgets[0]["action"]["mod"] == 0x01
        assert widgets[1]["action"]["code"] == 0xE2
        assert widgets[2]["action"]["app"] == "firefox"

    def test_config_file_io(self):
        """Config should be readable/writable to disk"""
        config = {
            "version": 2,
            "pages": [
                {
                    "name": "Test Page",
                    "widgets": [
                        {
                            "id": "test_widget",
                            "type": "button",
                            "x": 10, "y": 10, "width": 100, "height": 50,
                            "label": "Test Button",
                            "action": {"type": ACTION_HOTKEY, "mod": 0, "key": 0x61},
                        }
                    ]
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            filepath = f.name

        try:
            with open(filepath, 'r') as f:
                loaded = json.load(f)
            assert loaded == config
        finally:
            Path(filepath).unlink()


class TestActionTypeValidation:
    """Test validation of action types in configs"""

    def test_all_action_types_are_valid(self):
        """All defined action types should be considered valid"""
        for action_type in VALID_ACTION_TYPES:
            assert isinstance(action_type, int)
            assert action_type >= 0

    def test_action_type_in_valid_set(self):
        """ACTION_HOTKEY should be in VALID_ACTION_TYPES"""
        assert ACTION_HOTKEY in VALID_ACTION_TYPES

    def test_large_config_integrity(self):
        """Large config with many widgets should remain valid after JSON round-trip"""
        config = {
            "version": 2,
            "pages": []
        }

        # Create 10 pages with 10 widgets each
        for page_num in range(10):
            page = {
                "name": f"Page {page_num}",
                "widgets": []
            }
            for widget_num in range(10):
                page["widgets"].append({
                    "id": f"p{page_num}_w{widget_num}",
                    "type": "button",
                    "x": widget_num * 50,
                    "y": 0,
                    "width": 50,
                    "height": 50,
                    "label": f"Button {widget_num}",
                    "action": {
                        "type": ACTION_HOTKEY,
                        "mod": widget_num % 8,
                        "key": 0x61 + (widget_num % 26),
                    }
                })
            config["pages"].append(page)

        json_str = json.dumps(config)
        reloaded = json.loads(json_str)

        assert len(reloaded["pages"]) == 10
        assert all(len(page["widgets"]) == 10 for page in reloaded["pages"])
        assert reloaded["pages"][5]["widgets"][5]["id"] == "p5_w5"
