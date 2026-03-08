# Companion Test Suite

Pytest-based test suite for the Elcrow Display Hotkeys companion application.

## Overview

The test suite validates core functionality of the Python companion module:

- **Configuration Management** (`test_config.py`) - JSON serialization, schema validation, action types
- **Keycode Mapping** (`test_keycode_map.py`) - Qt to Arduino HID keycode translation
- **Action Execution** (`test_action_executor.py`) - Action dispatch logic and modifiers

## Running Tests

### Setup

First-time setup requires creating a Python virtual environment with pytest:

```bash
python3 -m venv test_venv
source test_venv/bin/activate
pip install pytest
```

### Run All Tests

```bash
source test_venv/bin/activate
pytest companion/tests/ -v
```

### Run Specific Test File

```bash
pytest companion/tests/test_config.py -v
pytest companion/tests/test_keycode_map.py -v
pytest companion/tests/test_action_executor.py -v
```

### Run Specific Test Class

```bash
pytest companion/tests/test_config.py::TestActionTypeConstants -v
pytest companion/tests/test_keycode_map.py::TestModifierMapping -v
```

### Run Single Test

```bash
pytest companion/tests/test_config.py::TestConfigRoundTrip::test_json_serialization -v
```

## Test Coverage

### test_config.py (21 tests)

Tests for `companion/config_manager.py`:

**TestActionTypeConstants** (3 tests)
- Validates all action type constants are defined and unique
- Checks that action types are integers

**TestDisplayLocalActions** (6 tests)
- Verifies display-local action classification
- Ensures correct action types are marked as local/non-local

**TestConfigSchema** (5 tests)
- Tests basic config structure and schema
- Validates action object layouts for each action type

**TestConfigRoundTrip** (4 tests)
- JSON serialization and deserialization
- Config file I/O
- Multi-page and multi-action type configs

**TestActionTypeValidation** (3 tests)
- Validates uniqueness of action types
- Tests large config with 100+ widgets for integrity

### test_keycode_map.py (37 tests)

Tests for `companion/keycode_map.py`:

**TestModifierMapping** (6 tests)
- Qt modifier flag to device bitmask conversion
- Validates Ctrl, Shift, Alt, GUI modifiers
- Tests modifier isolation (no bit overlap)

**TestSpecialKeyMapping** (9 tests)
- Qt special key to Arduino keycode mapping
- Return, Escape, Backspace, Tab, Insert, Delete, Home, End, PageUp/Down

**TestNavigationKeys** (4 tests)
- Arrow key mapping (Up, Down, Left, Right)

**TestLockKeys** (2 tests)
- CapsLock and NumLock mapping

**TestFunctionKeys** (7 tests)
- F1-F24 key mapping
- Validates continuous ranges (F1-F12, F13-F24)

**TestArduinoKeyNames** (3 tests)
- Reverse lookup Arduino codes to human-readable names
- Validates name strings

**TestKeyMappingConsistency** (4 tests)
- Validates all keycodes are 8-bit values
- Checks modifier isolation
- Tests special key ranges

### test_action_executor.py (40 tests)

Tests for `companion/action_executor.py`:

**TestModifierMapping** (7 tests)
- Modifier bitmask and name conversions
- Ctrl, Shift, Alt, Super modifier names
- Validates modifier values are powers of 2

**TestKeycodeMapping** (9 tests)
- Arduino keycode to key name conversion
- ASCII letters, digits, special keys
- Function keys F1-F12

**TestActionTypeValidation** (3 tests)
- Action type constants and values
- Uniqueness validation

**TestDisplayLocalActions** (8 tests)
- Display-local action filtering
- Verifies correct classification of local vs non-local actions

**TestKeycodeRanges** (3 tests)
- Coverage of ASCII printable range
- Arduino special keys coverage

**TestModifierCombinations** (3 tests)
- Single and combined modifier validation
- MOD_NONE = 0x00 check

## Test Infrastructure

### conftest.py

Pytest configuration and fixtures:
- Module path configuration for companion imports

### pytest.ini

Global pytest configuration:
- Test discovery patterns
- Markers for test categorization
- Output styling

## Key Test Patterns

### Configuration Round-Trip

Tests verify that configs can be serialized to JSON and deserialized without loss:

```python
def test_json_serialization(self):
    config = {"version": 2, "pages": [...]}
    json_str = json.dumps(config)
    reloaded = json.loads(json_str)
    assert reloaded == config
```

### Constant Consistency

Tests verify all constants are unique and valid:

```python
def test_action_type_uniqueness(self):
    types_list = [ACTION_HOTKEY, ACTION_MEDIA_KEY, ...]
    assert len(types_list) == len(set(types_list))
```

### Mapping Validation

Tests verify bidirectional mappings work correctly:

```python
def test_ctrl_modifier(self):
    assert QT_MOD_TO_DEVICE[MockQt.ControlModifier] == 0x01
```

## Mock Objects

**MockQt** - Used in `test_keycode_map.py` to avoid PySide6 dependency:
- Provides Qt constant values for testing
- Allows tests to run in CI environments without X11/display

## Future Test Additions

### Recommended Tests

1. **Protocol parity tests** - Verify C protocol.h matches Python definitions
2. **Configuration migration tests** - V1→V2 upgrade paths
3. **Action executor integration tests** - Actual command execution (with mocks)
4. **WiFi manager tests** - Connection logic and nmcli integration
5. **HID communication tests** - Vendor report parsing and serialization

### Integration Tests

- End-to-end config round-trip through save/load
- Device communication flow simulation
- Multi-page navigation validation
- Action dispatch simulation

## CI Integration

To run tests in CI/CD:

```bash
# Install test dependencies
python3 -m venv test_venv
source test_venv/bin/activate
pip install pytest

# Run tests
pytest companion/tests/ -v --tb=short

# Generate coverage report (optional)
pip install pytest-cov
pytest companion/tests/ --cov=companion --cov-report=term-missing
```

## Debugging Tests

### Verbose Output

```bash
pytest companion/tests/ -vv  # Very verbose
pytest companion/tests/ -s   # Show print statements
```

### Run Single Test with Full Output

```bash
pytest companion/tests/test_config.py::TestConfigRoundTrip::test_json_serialization -vv -s
```

### Run with Python Debugger

```bash
pytest --pdb companion/tests/test_config.py  # Drop to debugger on failure
```

## Test Metrics

- **Total Tests**: 98
- **Pass Rate**: 100%
- **Execution Time**: ~0.03s
- **Coverage Areas**:
  - Configuration schema validation
  - Keycode translation (Qt ↔ Arduino)
  - Action type management
  - Modifier bit manipulation
  - JSON serialization

## Notes

- Tests use `sys.path` manipulation to avoid package installation requirements
- Mock objects allow testing without PySide6/Qt dependencies
- All tests are synchronous (no async/await)
- Tests are isolated and can run in any order
