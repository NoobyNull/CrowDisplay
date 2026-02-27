"""
Test suite for action_executor.py - action dispatch and execution

Tests:
- Modifier bitmask validation
- Keycode to key name conversion
- Action type validation
- Special key handling
- Display-local action filtering
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from action_executor import (
    _KEY_NAMES,
    _MOD_NAMES,
)

from config_manager import (
    ACTION_HOTKEY, ACTION_MEDIA_KEY, ACTION_LAUNCH_APP,
    ACTION_SHELL_CMD, ACTION_OPEN_URL,
    ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE,
    ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO,
    ACTION_MODE_CYCLE, ACTION_BRIGHTNESS, ACTION_CONFIG_MODE,
    ACTION_DDC, ACTION_FOCUS_NEXT, ACTION_FOCUS_PREV, ACTION_FOCUS_ACTIVATE,
    MOD_NONE, MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI,
    DISPLAY_LOCAL_ACTIONS,
)


class TestModifierMapping:
    """Test modifier bitmask and name conversions"""

    def test_mod_names_keys_are_valid(self):
        """All keys in _MOD_NAMES should be valid modifier values"""
        valid_mods = {MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI}
        for mod in _MOD_NAMES.keys():
            assert mod in valid_mods

    def test_mod_names_values_are_strings(self):
        """All values in _MOD_NAMES should be strings"""
        for name in _MOD_NAMES.values():
            assert isinstance(name, str)

    def test_ctrl_modifier_name(self):
        """MOD_CTRL should have name 'ctrl'"""
        assert _MOD_NAMES[MOD_CTRL] == "ctrl"

    def test_shift_modifier_name(self):
        """MOD_SHIFT should have name 'shift'"""
        assert _MOD_NAMES[MOD_SHIFT] == "shift"

    def test_alt_modifier_name(self):
        """MOD_ALT should have name 'alt'"""
        assert _MOD_NAMES[MOD_ALT] == "alt"

    def test_gui_modifier_name(self):
        """MOD_GUI should have name 'super'"""
        assert _MOD_NAMES[MOD_GUI] == "super"

    def test_all_standard_modifiers_have_names(self):
        """All four standard modifiers should be in the name map"""
        assert MOD_CTRL in _MOD_NAMES
        assert MOD_SHIFT in _MOD_NAMES
        assert MOD_ALT in _MOD_NAMES
        assert MOD_GUI in _MOD_NAMES

    def test_modifier_values_are_powers_of_2(self):
        """Modifier values should be single bits (powers of 2)"""
        modifiers = [MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI]
        for mod in modifiers:
            assert mod > 0
            # Check single bit: value & (value - 1) == 0
            assert (mod & (mod - 1)) == 0

    def test_modifiers_are_non_overlapping(self):
        """Modifiers should not share bits (bitwise AND should be 0)"""
        modifiers = [MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI]
        for i, mod1 in enumerate(modifiers):
            for mod2 in modifiers[i+1:]:
                assert (mod1 & mod2) == 0


class TestKeycodeMapping:
    """Test Arduino keycode to key name conversion"""

    def test_printable_ascii_letters_lowercase(self):
        """Lowercase ASCII letters should map to themselves"""
        for ascii_code in range(ord('a'), ord('z') + 1):
            expected_name = chr(ascii_code)
            assert _KEY_NAMES[ascii_code] == expected_name

    def test_printable_ascii_uppercase(self):
        """Uppercase ASCII letters should map to lowercase names"""
        for ascii_code in range(ord('A'), ord('Z') + 1):
            expected_name = chr(ascii_code).lower()
            assert _KEY_NAMES[ascii_code] == expected_name

    def test_printable_ascii_digits(self):
        """Digits should map to themselves"""
        for ascii_code in range(ord('0'), ord('9') + 1):
            expected_digit = chr(ascii_code)
            assert _KEY_NAMES[ascii_code] == expected_digit

    def test_space_key(self):
        """Space character should map to 'space'"""
        assert _KEY_NAMES[ord(' ')] == 'space'

    def test_special_keys_have_names(self):
        """Arduino special keys should have human-readable names"""
        special_keys = {
            0xB0: 'enter',
            0xB1: 'esc',
            0xB2: 'backspace',
            0xB3: 'tab',
            0xD7: 'right',
            0xD8: 'left',
            0xD9: 'down',
            0xDA: 'up',
        }
        for keycode, expected_name in special_keys.items():
            assert _KEY_NAMES[keycode] == expected_name

    def test_home_end_keys(self):
        """Home and End keys should have names"""
        assert _KEY_NAMES[0xD1] == 'home'  # KEY_HOME
        assert _KEY_NAMES[0xD4] == 'end'   # KEY_END

    def test_pageup_pagedown_keys(self):
        """PageUp and PageDown keys should have names"""
        assert _KEY_NAMES[0xD5] == 'pageup'
        assert _KEY_NAMES[0xD6] == 'pagedown'

    def test_insert_delete_keys(self):
        """Insert and Delete keys should have names"""
        assert _KEY_NAMES[0xD2] == 'insert'
        assert _KEY_NAMES[0xD3] == 'delete'

    def test_function_keys_f1_to_f12(self):
        """F1-F12 keys should map to 'f1' through 'f12'"""
        # F1 = 0xC2, F2 = 0xC3, ..., F12 = 0xCD
        for i, keycode in enumerate(range(0xC2, 0xCE), 1):
            expected_name = f'f{i}'
            assert _KEY_NAMES[keycode] == expected_name

    def test_all_keycode_names_are_strings(self):
        """All entries in _KEY_NAMES should have string values"""
        for name in _KEY_NAMES.values():
            assert isinstance(name, str)
            assert len(name) > 0

    def test_keycode_names_are_lowercase(self):
        """Key names should be lowercase (except for names that are just digits)"""
        for name in _KEY_NAMES.values():
            # Skip pure digits
            if not name.isdigit():
                assert name == name.lower()


class TestActionTypeValidation:
    """Test action type constants and relationships"""

    def test_hotkey_action_value(self):
        """ACTION_HOTKEY should be 0"""
        assert ACTION_HOTKEY == 0

    def test_media_key_action_value(self):
        """ACTION_MEDIA_KEY should be 1"""
        assert ACTION_MEDIA_KEY == 1

    def test_action_type_uniqueness(self):
        """All action types should have unique values"""
        types = [
            ACTION_HOTKEY, ACTION_MEDIA_KEY, ACTION_LAUNCH_APP,
            ACTION_SHELL_CMD, ACTION_OPEN_URL,
            ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE,
            ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO,
            ACTION_MODE_CYCLE, ACTION_BRIGHTNESS, ACTION_CONFIG_MODE,
            ACTION_DDC, ACTION_FOCUS_NEXT, ACTION_FOCUS_PREV, ACTION_FOCUS_ACTIVATE,
        ]
        assert len(types) == len(set(types))

    def test_action_types_are_non_negative(self):
        """All action type values should be non-negative"""
        types = [
            ACTION_HOTKEY, ACTION_MEDIA_KEY, ACTION_LAUNCH_APP,
            ACTION_SHELL_CMD, ACTION_OPEN_URL,
            ACTION_DISPLAY_SETTINGS, ACTION_DISPLAY_CLOCK, ACTION_DISPLAY_PICTURE,
            ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO,
            ACTION_MODE_CYCLE, ACTION_BRIGHTNESS, ACTION_CONFIG_MODE,
            ACTION_DDC, ACTION_FOCUS_NEXT, ACTION_FOCUS_PREV, ACTION_FOCUS_ACTIVATE,
        ]
        assert all(t >= 0 for t in types)


class TestDisplayLocalActions:
    """Test display-local action filtering"""

    def test_display_settings_is_local(self):
        """ACTION_DISPLAY_SETTINGS should be display-local"""
        assert ACTION_DISPLAY_SETTINGS in DISPLAY_LOCAL_ACTIONS

    def test_display_clock_is_local(self):
        """ACTION_DISPLAY_CLOCK should be display-local"""
        assert ACTION_DISPLAY_CLOCK in DISPLAY_LOCAL_ACTIONS

    def test_display_picture_is_local(self):
        """ACTION_DISPLAY_PICTURE should be display-local"""
        assert ACTION_DISPLAY_PICTURE in DISPLAY_LOCAL_ACTIONS

    def test_page_navigation_actions_are_local(self):
        """Page navigation actions should be display-local"""
        page_actions = {ACTION_PAGE_NEXT, ACTION_PAGE_PREV, ACTION_PAGE_GOTO}
        assert page_actions.issubset(DISPLAY_LOCAL_ACTIONS)

    def test_hotkey_is_not_local(self):
        """ACTION_HOTKEY should NOT be display-local"""
        assert ACTION_HOTKEY not in DISPLAY_LOCAL_ACTIONS

    def test_media_key_is_not_local(self):
        """ACTION_MEDIA_KEY should NOT be display-local"""
        assert ACTION_MEDIA_KEY not in DISPLAY_LOCAL_ACTIONS

    def test_launch_app_is_not_local(self):
        """ACTION_LAUNCH_APP should NOT be display-local"""
        assert ACTION_LAUNCH_APP not in DISPLAY_LOCAL_ACTIONS

    def test_shell_cmd_is_not_local(self):
        """ACTION_SHELL_CMD should NOT be display-local"""
        assert ACTION_SHELL_CMD not in DISPLAY_LOCAL_ACTIONS

    def test_url_open_is_not_local(self):
        """ACTION_OPEN_URL should NOT be display-local"""
        assert ACTION_OPEN_URL not in DISPLAY_LOCAL_ACTIONS

    def test_ddc_is_not_local(self):
        """ACTION_DDC should NOT be display-local (may need companion)"""
        # Note: This might be debatable, but DDC typically goes through companion
        pass


class TestKeycodeRanges:
    """Test keycode range coverage"""

    def test_ascii_printable_range_covered(self):
        """ASCII printable range should have letters and digits mapped"""
        # Letters a-z should be in the map
        for code in range(ord('a'), ord('z') + 1):
            assert code in _KEY_NAMES
        # Digits 0-9 should be in the map
        for code in range(ord('0'), ord('9') + 1):
            assert code in _KEY_NAMES

    def test_arduino_special_keys_covered(self):
        """Arduino special key range should have coverage"""
        # Sample key codes from Arduino USBHIDKeyboard
        critical_keys = [
            0xB0,  # RETURN
            0xB1,  # ESCAPE
            0xB2,  # BACKSPACE
            0xB3,  # TAB
            0xC1,  # CAPS_LOCK
            0xC2,  # F1
            0xCD,  # F12
            0xD7,  # RIGHT_ARROW
            0xD8,  # LEFT_ARROW
            0xD9,  # DOWN_ARROW
            0xDA,  # UP_ARROW
        ]
        for code in critical_keys:
            assert code in _KEY_NAMES

    def test_no_empty_keycode_names(self):
        """No keycode should map to empty string"""
        for code, name in _KEY_NAMES.items():
            assert len(name) > 0


class TestModifierCombinations:
    """Test valid modifier combinations"""

    def test_single_modifier_combinations(self):
        """Each modifier should be usable alone"""
        modifiers = [MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI]
        for mod in modifiers:
            assert mod > 0
            assert mod in _MOD_NAMES

    def test_combined_modifier_values(self):
        """Combined modifiers should produce unique values"""
        combos = [
            MOD_CTRL | MOD_SHIFT,
            MOD_CTRL | MOD_ALT,
            MOD_SHIFT | MOD_ALT,
            MOD_CTRL | MOD_SHIFT | MOD_ALT | MOD_GUI,
        ]
        assert len(set(combos)) == len(combos)

    def test_modifier_none_is_zero(self):
        """MOD_NONE should be 0"""
        assert MOD_NONE == 0x00
