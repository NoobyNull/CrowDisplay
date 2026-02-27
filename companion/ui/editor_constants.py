"""
Editor Constants: Stat type mappings, media keys, widget palette icons, grid layout constants.
"""

from companion.config_manager import (
    WIDGET_HOTKEY_BUTTON,
    WIDGET_STAT_MONITOR,
    WIDGET_STATUS_BAR,
    WIDGET_CLOCK,
    WIDGET_TEXT_LABEL,
    WIDGET_SEPARATOR,
    WIDGET_PAGE_NAV,
)

# Stat type dropdown options: (display_name, type_id)
STAT_TYPE_OPTIONS = [
    ("CPU %", 0x01),
    ("RAM %", 0x02),
    ("GPU %", 0x03),
    ("CPU Temp", 0x04),
    ("GPU Temp", 0x05),
    ("Disk %", 0x06),
    ("Net Up", 0x07),
    ("Net Down", 0x08),
    ("CPU Freq", 0x09),
    ("GPU Freq", 0x0A),
    ("Swap %", 0x0B),
    ("Uptime", 0x0C),
    ("Battery", 0x0D),
    ("Fan RPM", 0x0E),
    ("Load Avg", 0x0F),
    ("Proc Count", 0x10),
    ("VRAM %", 0x11),
    ("GPU Power", 0x12),
    ("Disk Read", 0x13),
    ("Disk Write", 0x14),
    ("Display Uptime", 0x15),
    ("Proc (User)", 0x16),
    ("Proc (System)", 0x17),
]

# Reverse lookup: stat type ID -> display name
STAT_TYPE_NAMES = {tid: name for name, tid in STAT_TYPE_OPTIONS}

# Default stat colors by type ID
STAT_DEFAULT_COLORS = {
    0x01: 0x3498DB, 0x02: 0x2ECC71, 0x03: 0xE67E22, 0x04: 0xE74C3C,
    0x05: 0xF1C40F, 0x06: 0x7F8C8D, 0x07: 0x1ABC9C, 0x08: 0x1ABC9C,
    0x09: 0x3498DB, 0x0A: 0xE67E22, 0x0B: 0x9B59B6, 0x0C: 0x7F8C8D,
    0x0D: 0x2ECC71, 0x0E: 0xE74C3C, 0x0F: 0xE67E22, 0x10: 0x7F8C8D,
    0x11: 0xE67E22, 0x12: 0xE74C3C, 0x13: 0x1ABC9C, 0x14: 0x1ABC9C,
    0x15: 0x7F8C8D, 0x16: 0x3498DB, 0x17: 0xE74C3C,
}

# Stat placeholders for canvas preview (matching display get_stat_placeholder)
STAT_PLACEHOLDERS = {
    0x01: "CPU --%", 0x02: "RAM --%", 0x03: "GPU --%",
    0x04: "CPU --\u00b0C", 0x05: "GPU --\u00b0C", 0x06: "Disk --%",
    0x07: "\u2191 -- KB/s", 0x08: "\u2193 -- KB/s",
    0x09: "CPU -- MHz", 0x0A: "GPU -- MHz", 0x0B: "Swap --%",
    0x0C: "Up --h", 0x0D: "Bat --%", 0x0E: "Fan --",
    0x0F: "Load --", 0x10: "Proc --", 0x11: "VRAM --%",
    0x12: "GPU --W", 0x13: "\u2193 R -- KB/s", 0x14: "\u2191 W -- KB/s",
    0x15: "Disp --h", 0x16: "User --", 0x17: "Sys --",
}

# Value-only placeholders for split-label mode
STAT_VALUE_PLACEHOLDERS = {
    0x01: "--%", 0x02: "--%", 0x03: "--%",
    0x04: "--\u00b0C", 0x05: "--\u00b0C", 0x06: "--%",
    0x07: "-- KB/s", 0x08: "-- KB/s",
    0x09: "-- MHz", 0x0A: "-- MHz", 0x0B: "--%",
    0x0C: "--h", 0x0D: "--%", 0x0E: "--",
    0x0F: "--", 0x10: "--", 0x11: "--%",
    0x12: "--W", 0x13: "-- KB/s", 0x14: "-- KB/s",
    0x15: "--h", 0x16: "--", 0x17: "--",
}

# Stat name labels for split-label mode
STAT_NAME_LABELS = {
    0x01: "CPU", 0x02: "RAM", 0x03: "GPU",
    0x04: "CPU", 0x05: "GPU", 0x06: "Disk",
    0x07: "\u2191", 0x08: "\u2193",
    0x09: "CPU", 0x0A: "GPU", 0x0B: "Swap",
    0x0C: "Up", 0x0D: "Bat", 0x0E: "Fan",
    0x0F: "Load", 0x10: "Proc", 0x11: "VRAM",
    0x12: "GPU", 0x13: "\u2193 R", 0x14: "\u2191 W",
    0x15: "Disp", 0x16: "User", 0x17: "Sys",
}

# Default stats_header (matches device defaults)
DEFAULT_STATS_HEADER = [
    {"type": 0x01, "color": 0x3498DB, "position": 0},
    {"type": 0x02, "color": 0x2ECC71, "position": 1},
    {"type": 0x03, "color": 0xE67E22, "position": 2},
    {"type": 0x04, "color": 0xE74C3C, "position": 3},
    {"type": 0x05, "color": 0xF1C40F, "position": 4},
    {"type": 0x07, "color": 0x1ABC9C, "position": 5},
    {"type": 0x08, "color": 0x1ABC9C, "position": 6},
    {"type": 0x06, "color": 0x7F8C8D, "position": 7},
]

# Media key options: (display_name, consumer_code)
MEDIA_KEY_OPTIONS = [
    ("Play/Pause", 0xCD),
    ("Next Track", 0xB5),
    ("Previous Track", 0xB6),
    ("Stop", 0xB7),
    ("Volume Up", 0xE9),
    ("Volume Down", 0xEA),
    ("Mute", 0xE2),
    ("Browser Home", 0x0223),
    ("Browser Back", 0x0224),
]

# Widget palette icons (Unicode for display in list)
WIDGET_PALETTE_ICONS = {
    WIDGET_HOTKEY_BUTTON: "\u2328",  # keyboard
    WIDGET_STAT_MONITOR: "\u2261",   # bars
    WIDGET_STATUS_BAR: "\u2501",     # horizontal line
    WIDGET_CLOCK: "\u23F0",          # clock
    WIDGET_TEXT_LABEL: "\u0054",     # T
    WIDGET_SEPARATOR: "\u2500",      # line
    WIDGET_PAGE_NAV: "\u2022\u2022\u2022",  # dots
}

# Grid layout constants for template pages
_GRID_X0 = 6
_GRID_Y0 = 50
_CELL_W = 192
_CELL_H = 122
_GAP = 6
