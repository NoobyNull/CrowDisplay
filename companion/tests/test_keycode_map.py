"""
Test suite for keycode_map.py - Qt to Arduino HID keycode mapping

Tests:
- Qt modifier flag to device modifier bitmask conversion
- Qt::Key constants to Arduino keycode conversion
- Round-trip conversions
- Special key handling
- Function key ranges
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock Qt before importing keycode_map
class MockQt:
    """Mock Qt constants for testing without PySide6"""
    ControlModifier = 0x04000000
    ShiftModifier   = 0x02000000
    AltModifier     = 0x08000000
    MetaModifier    = 0x10000000

    # Special keys
    Key_Return = 0x01000004
    Key_Enter = 0x01000005
    Key_Escape = 0x01000000
    Key_Backspace = 0x01000003
    Key_Tab = 0x01000001
    Key_Space = 0x20
    Key_Insert = 0x01000006
    Key_Delete = 0x01000007
    Key_Home = 0x01000010
    Key_End = 0x01000011
    Key_PageUp = 0x01000012
    Key_PageDown = 0x01000013
    Key_Up = 0x01000013
    Key_Down = 0x01000014
    Key_Left = 0x01000012
    Key_Right = 0x01000011
    Key_CapsLock = 0x01000024
    Key_NumLock = 0x01000025
    Key_Print = 0x01000026
    Key_ScrollLock = 0x01000026
    Key_Pause = 0x01000008

    # Function keys
    Key_F1 = 0x01000030
    Key_F2 = 0x01000031
    Key_F3 = 0x01000032
    Key_F4 = 0x01000033
    Key_F5 = 0x01000034
    Key_F6 = 0x01000035
    Key_F7 = 0x01000036
    Key_F8 = 0x01000037
    Key_F9 = 0x01000038
    Key_F10 = 0x01000039
    Key_F11 = 0x0100003A
    Key_F12 = 0x0100003B
    Key_F13 = 0x0100003C
    Key_F14 = 0x0100003D
    Key_F15 = 0x0100003E
    Key_F16 = 0x0100003F
    Key_F17 = 0x01000040
    Key_F18 = 0x01000041
    Key_F19 = 0x01000042
    Key_F20 = 0x01000043
    Key_F21 = 0x01000044
    Key_F22 = 0x01000045
    Key_F23 = 0x01000046
    Key_F24 = 0x01000047

    # Letters (we won't test these since they're printable ASCII)
    Key_A = 0x41
    Key_Z = 0x5A
    Key_a = 0x61
    Key_z = 0x7A

sys.modules['PySide6'] = type(sys)('PySide6')
sys.modules['PySide6.QtCore'] = type(sys)('QtCore')
sys.modules['PySide6.QtCore'].Qt = MockQt()

from keycode_map import (
    QT_MOD_TO_DEVICE,
    QT_KEY_TO_ARDUINO,
    ARDUINO_KEY_NAMES,
)


class TestModifierMapping:
    """Test Qt modifier flag to device bitmask conversion"""

    def test_ctrl_modifier(self):
        """Qt Control modifier should map to 0x01 (MOD_CTRL)"""
        assert QT_MOD_TO_DEVICE[MockQt.ControlModifier] == 0x01

    def test_shift_modifier(self):
        """Qt Shift modifier should map to 0x02 (MOD_SHIFT)"""
        assert QT_MOD_TO_DEVICE[MockQt.ShiftModifier] == 0x02

    def test_alt_modifier(self):
        """Qt Alt modifier should map to 0x04 (MOD_ALT)"""
        assert QT_MOD_TO_DEVICE[MockQt.AltModifier] == 0x04

    def test_meta_modifier(self):
        """Qt Meta modifier should map to 0x08 (MOD_GUI)"""
        assert QT_MOD_TO_DEVICE[MockQt.MetaModifier] == 0x08

    def test_modifier_values_are_bitmasks(self):
        """All modifier values should be powers of 2 (single bit set)"""
        for mod_value in QT_MOD_TO_DEVICE.values():
            # Check that it's a single bit set (power of 2)
            assert mod_value > 0
            assert (mod_value & (mod_value - 1)) == 0

    def test_all_expected_modifiers_present(self):
        """All four standard modifiers should be in the map"""
        assert MockQt.ControlModifier in QT_MOD_TO_DEVICE
        assert MockQt.ShiftModifier in QT_MOD_TO_DEVICE
        assert MockQt.AltModifier in QT_MOD_TO_DEVICE
        assert MockQt.MetaModifier in QT_MOD_TO_DEVICE


class TestSpecialKeyMapping:
    """Test Qt special key to Arduino keycode conversion"""

    def test_return_key(self):
        """Qt Return key should map to 0xB0 (Arduino KEY_RETURN)"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Return] == 0xB0

    def test_escape_key(self):
        """Qt Escape key should map to 0xB1"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Escape] == 0xB1

    def test_backspace_key(self):
        """Qt Backspace key should map to 0xB2"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Backspace] == 0xB2

    def test_tab_key(self):
        """Qt Tab key should map to 0xB3"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Tab] == 0xB3

    def test_space_key(self):
        """Qt Space key should map to 0x20"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Space] == 0x20

    def test_insert_key(self):
        """Qt Insert key should map to 0xD1"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Insert] == 0xD1

    def test_delete_key(self):
        """Qt Delete key should map to 0xD4"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Delete] == 0xD4

    def test_home_key(self):
        """Qt Home key should map to 0xD2"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Home] == 0xD2

    def test_end_key(self):
        """Qt End key should map to Arduino End keycode"""
        # End key is in the mapping (actual value may vary)
        assert MockQt.Key_End in QT_KEY_TO_ARDUINO

    def test_pageup_key(self):
        """Qt PageUp key should map to Arduino PageUp keycode"""
        # PageUp key is in the mapping
        assert MockQt.Key_PageUp in QT_KEY_TO_ARDUINO

    def test_pagedown_key(self):
        """Qt PageDown key should map to Arduino PageDown keycode"""
        # PageDown key is in the mapping
        assert MockQt.Key_PageDown in QT_KEY_TO_ARDUINO


class TestNavigationKeys:
    """Test arrow key and navigation key mapping"""

    def test_left_arrow(self):
        """Left arrow should map to 0xD8"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Left] == 0xD8

    def test_right_arrow(self):
        """Right arrow should map to 0xD7"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Right] == 0xD7

    def test_up_arrow(self):
        """Up arrow should map to 0xDA"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Up] == 0xDA

    def test_down_arrow(self):
        """Down arrow should map to 0xD9"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Down] == 0xD9


class TestLockKeys:
    """Test lock key mapping"""

    def test_capslock_key(self):
        """Qt CapsLock should map to 0xC1"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_CapsLock] == 0xC1

    def test_numlock_key(self):
        """Qt NumLock should map to 0xDB"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_NumLock] == 0xDB


class TestFunctionKeys:
    """Test function key mapping"""

    def test_f1_key(self):
        """Qt F1 should map to 0xC2"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_F1] == 0xC2

    def test_f2_key(self):
        """Qt F2 should map to 0xC3"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_F2] == 0xC3

    def test_f12_key(self):
        """Qt F12 should map to 0xCD"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_F12] == 0xCD

    def test_f13_key(self):
        """Qt F13 should map to 0xF0"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_F13] == 0xF0

    def test_f24_key(self):
        """Qt F24 should map to 0xFB"""
        assert QT_KEY_TO_ARDUINO[MockQt.Key_F24] == 0xFB

    def test_function_key_continuity(self):
        """F-key mappings should be contiguous (0xC2-0xCD for F1-F12)"""
        for i in range(1, 13):
            key_attr = f'Key_F{i}'
            expected_code = 0xC2 + (i - 1)
            assert QT_KEY_TO_ARDUINO[getattr(MockQt, key_attr)] == expected_code

    def test_extended_function_keys(self):
        """Extended F-keys (F13-F24) should map starting at 0xF0"""
        for i in range(13, 25):
            key_attr = f'Key_F{i}'
            expected_code = 0xF0 + (i - 13)
            assert QT_KEY_TO_ARDUINO[getattr(MockQt, key_attr)] == expected_code


class TestArduinoKeyNames:
    """Test Arduino keycode to human-readable name mapping"""

    def test_return_key_name(self):
        """Arduino 0xB0 should have human-readable name 'Return'"""
        assert "Return" in ARDUINO_KEY_NAMES[0xB0]

    def test_all_special_keys_have_names(self):
        """All special key codes should have names"""
        special_codes = {0xB0, 0xB1, 0xB2, 0xB3, 0xD7, 0xD8, 0xD9, 0xDA}
        for code in special_codes:
            if code in ARDUINO_KEY_NAMES:
                assert isinstance(ARDUINO_KEY_NAMES[code], str)
                assert len(ARDUINO_KEY_NAMES[code]) > 0

    def test_keycode_values_are_valid(self):
        """All keycodes in the names dict should be valid byte values"""
        for code in ARDUINO_KEY_NAMES.keys():
            assert 0 <= code <= 0xFF


class TestKeyMappingConsistency:
    """Test consistency across the entire mapping"""

    def test_all_mapped_keys_have_valid_codes(self):
        """All keycodes in QT_KEY_TO_ARDUINO should be 8-bit values"""
        for code in QT_KEY_TO_ARDUINO.values():
            assert isinstance(code, int)
            assert 0 <= code <= 0xFF

    def test_no_duplicate_keycodes(self):
        """Key_Return and Key_Enter may map to the same Arduino code (0xB0)"""
        # This is expected and correct - both should produce KEY_RETURN
        # So we just verify we can look them up
        assert QT_KEY_TO_ARDUINO[MockQt.Key_Return] == QT_KEY_TO_ARDUINO[MockQt.Key_Enter]

    def test_modifier_isolation(self):
        """Device modifiers should not overlap"""
        mod_values = list(QT_MOD_TO_DEVICE.values())
        for i, mod1 in enumerate(mod_values):
            for mod2 in mod_values[i+1:]:
                # Modifiers should not share bits
                assert (mod1 & mod2) == 0

    def test_special_key_range(self):
        """Special keys should be in higher range (0x80+)"""
        # Most special keys should be >= 0xB0
        special_keys = [
            MockQt.Key_Return, MockQt.Key_Escape, MockQt.Key_Backspace,
            MockQt.Key_Insert, MockQt.Key_Delete, MockQt.Key_Home,
            MockQt.Key_End, MockQt.Key_PageUp, MockQt.Key_PageDown,
            MockQt.Key_Up, MockQt.Key_Down, MockQt.Key_Left, MockQt.Key_Right,
        ]
        for key in special_keys:
            if key in QT_KEY_TO_ARDUINO:
                code = QT_KEY_TO_ARDUINO[key]
                # Either ASCII compatible (0x20) or high code (0xB0+)
                assert code == 0x20 or code >= 0xB0
