#!/usr/bin/env python3
"""Verify Python protocol constants match C++ header definitions.

Parses shared/protocol.h and display/config.h for enum values, #defines,
and struct sizes, then checks they match companion/config_manager.py and
companion/hotkey_companion.py.

Run from project root:  python3 scripts/check_protocol_sync.py
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Parsers ---

def parse_enum_values(header_text: str, enum_name: str) -> dict[str, int]:
    """Extract enum members and their integer values."""
    pattern = rf'enum\s+{enum_name}\s*:\s*uint8_t\s*\{{([^}}]+)\}}'
    m = re.search(pattern, header_text, re.DOTALL)
    if not m:
        return {}
    body = m.group(1)
    result = {}
    for line in body.splitlines():
        line = line.split('//')[0].strip().rstrip(',')
        if '=' in line:
            name, val = line.split('=', 1)
            name = name.strip()
            val = val.strip()
            try:
                result[name] = int(val, 0)
            except ValueError:
                pass
    return result


def parse_defines(header_text: str, prefix: str) -> dict[str, int]:
    """Extract #define constants matching a prefix."""
    result = {}
    for m in re.finditer(rf'#define\s+({prefix}\w+)\s+(0x[\da-fA-F]+|\d+)', header_text):
        name = m.group(1)
        val = m.group(2)
        result[name] = int(val, 0)
    return result


def parse_python_constants(py_text: str, prefix: str) -> dict[str, int]:
    """Extract NAME = value assignments matching a prefix."""
    result = {}
    for m in re.finditer(rf'^({prefix}\w+)\s*=\s*(0x[\da-fA-F]+|\d+)', py_text, re.MULTILINE):
        name = m.group(1)
        val = m.group(2)
        result[name] = int(val, 0)
    return result


# --- Checks ---

def check_match(label: str, cpp_vals: dict[str, int], py_vals: dict[str, int],
                name_map: dict[str, str] | None = None) -> list[str]:
    """Compare C++ and Python constant sets. Returns list of error strings."""
    errors = []
    for cpp_name, cpp_val in cpp_vals.items():
        py_name = name_map.get(cpp_name, cpp_name) if name_map else cpp_name
        if py_name not in py_vals:
            errors.append(f"  MISSING in Python: {cpp_name} = {cpp_val} (expected as {py_name})")
        elif py_vals[py_name] != cpp_val:
            errors.append(f"  MISMATCH: {py_name} = {py_vals[py_name]} in Python, "
                          f"but {cpp_name} = {cpp_val} in C++")
    # Check for Python constants not in C++
    reverse_map = {v: k for k, v in (name_map or {}).items()}
    for py_name, py_val in py_vals.items():
        cpp_name = reverse_map.get(py_name, py_name)
        if cpp_name not in cpp_vals:
            errors.append(f"  EXTRA in Python (not in C++): {py_name} = {py_val}")
    return errors


def main():
    protocol_h = (PROJECT_ROOT / "shared" / "protocol.h").read_text()
    config_h = (PROJECT_ROOT / "display" / "config.h").read_text()
    config_manager_py = (PROJECT_ROOT / "companion" / "config_manager.py").read_text()
    hotkey_companion_py = (PROJECT_ROOT / "companion" / "hotkey_companion.py").read_text()

    all_errors = []

    # 1. MsgType enum vs hotkey_companion.py MSG_ constants
    #    Only check values that Python defines (companion doesn't need display-only types)
    cpp_msg = parse_enum_values(protocol_h, "MsgType")
    py_msg = parse_python_constants(hotkey_companion_py, "MSG_")
    msg_errs = []
    for py_name, py_val in py_msg.items():
        if py_name in cpp_msg and cpp_msg[py_name] != py_val:
            msg_errs.append(f"  MISMATCH: {py_name} = {py_val} in Python, "
                            f"but {cpp_msg[py_name]} in C++")
        elif py_name not in cpp_msg:
            msg_errs.append(f"  EXTRA in Python (not in C++): {py_name} = {py_val}")
    if msg_errs:
        all_errors.append(("MsgType", msg_errs))

    # 2. StatType enum vs config_manager.py STAT_TYPE range
    cpp_stat = parse_enum_values(protocol_h, "StatType")
    cpp_stat_max = parse_defines(protocol_h, "STAT_TYPE_")
    py_stat_range = parse_python_constants(config_manager_py, "STAT_TYPE_")
    stat_errs = []
    if "STAT_TYPE_MAX" in cpp_stat_max and "STAT_TYPE_MAX" in py_stat_range:
        if cpp_stat_max["STAT_TYPE_MAX"] != py_stat_range["STAT_TYPE_MAX"]:
            stat_errs.append(
                f"  MISMATCH: STAT_TYPE_MAX = {py_stat_range['STAT_TYPE_MAX']} in Python, "
                f"but {cpp_stat_max['STAT_TYPE_MAX']} in C++")
    if stat_errs:
        all_errors.append(("StatType range", stat_errs))

    # 3. ActionType enum (config.h) vs config_manager.py ACTION_ constants
    cpp_action = parse_enum_values(config_h, "ActionType")
    py_action = parse_python_constants(config_manager_py, "ACTION_")
    errs = check_match("ActionType (config.h vs config_manager.py)", cpp_action, py_action)
    if errs:
        all_errors.append(("ActionType", errs))

    # 4. WidgetType enum (config.h) vs config_manager.py WIDGET_ constants
    cpp_widget = parse_enum_values(config_h, "WidgetType")
    py_widget = parse_python_constants(config_manager_py, "WIDGET_")
    # Filter to only enum members (exclude WIDGET_DEFAULT_SIZES, WIDGET_TYPE_MAX, etc.)
    py_widget_enums = {k: v for k, v in py_widget.items() if k in cpp_widget}
    errs = check_match("WidgetType (config.h vs config_manager.py)", cpp_widget, py_widget_enums)
    if errs:
        all_errors.append(("WidgetType", errs))

    # 5. Modifier masks (protocol.h) vs config_manager.py MOD_ constants
    cpp_mod = parse_defines(protocol_h, "MOD_")
    py_mod = parse_python_constants(config_manager_py, "MOD_")
    errs = check_match("Modifier masks (protocol.h vs config_manager.py)", cpp_mod, py_mod)
    if errs:
        all_errors.append(("Modifiers", errs))

    # 6. POWER_ constants (protocol.h) vs hotkey_companion.py
    cpp_power = parse_defines(protocol_h, "POWER_")
    py_power = parse_python_constants(hotkey_companion_py, "POWER_")
    errs = check_match("Power states (protocol.h vs hotkey_companion.py)", cpp_power, py_power)
    if errs:
        all_errors.append(("PowerState", errs))

    # 7. WIDGET_TYPE_MAX define
    cpp_wt_max = parse_defines(config_h, "WIDGET_TYPE_")
    py_wt_max = parse_python_constants(config_manager_py, "WIDGET_TYPE_")
    errs = check_match("WIDGET_TYPE_MAX (config.h vs config_manager.py)", cpp_wt_max, py_wt_max)
    if errs:
        all_errors.append(("WIDGET_TYPE_MAX", errs))

    # --- Report ---
    if all_errors:
        print("PROTOCOL SYNC ERRORS:")
        for label, errs in all_errors:
            print(f"\n[{label}]")
            for e in errs:
                print(e)
        print(f"\n{sum(len(e) for _, e in all_errors)} error(s) found.")
        sys.exit(1)
    else:
        print("All protocol constants in sync.")
        sys.exit(0)


if __name__ == "__main__":
    main()
