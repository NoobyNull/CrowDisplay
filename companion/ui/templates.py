"""
Page Templates: Pre-built page layouts and smart default config generation.

Each template function returns a list of widget dicts for a pre-built page layout.
Grid layout: 800x480, status bar at (0,0,800,40), usable y=45..440,
page nav at (300,445,200,30).
"""

import os
import logging
from pathlib import Path

from companion.config_manager import (
    WIDGET_HOTKEY_BUTTON,
    WIDGET_STAT_MONITOR,
    WIDGET_STATUS_BAR,
    WIDGET_CLOCK,
    WIDGET_TEXT_LABEL,
    WIDGET_PAGE_NAV,
    ACTION_HOTKEY,
    ACTION_MEDIA_KEY,
    ACTION_LAUNCH_APP,
    ACTION_SHELL_CMD,
    MOD_NONE,
    MOD_CTRL,
    MOD_SHIFT,
    MOD_ALT,
    MOD_GUI,
    make_default_widget,
    get_default_hardware_buttons,
    get_default_encoder,
)
from companion.ui.editor_constants import (
    STAT_DEFAULT_COLORS,
    _GRID_X0,
    _GRID_Y0,
    _CELL_W,
    _CELL_H,
    _GAP,
)

logger = logging.getLogger(__name__)


# ============================================================
# Smart Default Config: Query KDE Favorites + Build Auto Config
# ============================================================

def _get_kde_favorites():
    """Read KDE Plasma favorites from kactivitymanagerd database.

    Returns a list of desktop file basenames (e.g., ['firefox.desktop', 'discord.desktop']).
    """
    import sqlite3
    db_path = Path.home() / ".local/share/kactivitymanagerd/resources/database"
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT targettedResource FROM ResourceLink "
            "WHERE initiatingAgent='org.kde.plasma.favorites.applications'"
        ).fetchall()
        conn.close()
        # Extract desktop file names:
        #   "applications:foo.desktop" -> "foo.desktop"
        #   "org.kde.kontact.desktop" -> "org.kde.kontact.desktop"
        # Skip special entries like "preferred://browser"
        result = []
        for (res,) in rows:
            if not res or "://" in res:
                continue
            if ":" in res:
                res = res.split(":")[-1]
            if res.endswith(".desktop"):
                result.append(res)
        return result
    except Exception as e:
        logger.warning("Failed to read KDE favorites: %s", e)
        return []


_APP_CACHE = None  # Cache scanned apps for reuse


def _get_all_apps():
    """Get all installed apps, using cache if available."""
    global _APP_CACHE
    if _APP_CACHE is None:
        try:
            from companion.app_scanner import scan_applications
            _APP_CACHE = scan_applications()
        except Exception as e:
            logger.warning("Failed to scan applications: %s", e)
            _APP_CACHE = []
    return _APP_CACHE


def _resolve_app_from_desktop(desktop_file):
    """Try to resolve a .desktop file to an app entry.

    Matches by desktop_file basename (e.g., "firefox.desktop" or just "firefox").

    Returns a dict with keys: name, exec_cmd, icon_name, wm_class
    or None if not found.
    """
    all_apps = _get_all_apps()
    # Normalize the lookup: remove .desktop extension if present
    lookup_name = desktop_file.replace(".desktop", "").lower()

    for app in all_apps:
        if not app.desktop_file:
            continue
        # Extract basename without extension from app.desktop_file
        # (app.desktop_file might be full path like "/usr/share/applications/firefox.desktop")
        basename = os.path.basename(app.desktop_file).replace(".desktop", "").lower()
        if basename == lookup_name:
            return {
                "name": app.name,
                "exec_cmd": app.exec_cmd,
                "icon_name": app.icon_name,
                "wm_class": app.wm_class,
            }

    logger.debug("App not found for desktop file: %s", desktop_file)
    return None


def _build_app_launcher_page(apps):
    """Build a 4x3 grid of app launcher buttons from a list of app dicts.

    Each app dict should have: name, exec_cmd, icon_name (optional), wm_class (optional).
    Returns a list of widgets.
    """
    widgets = [_tpl_status_bar()]
    for i, app in enumerate(apps[:12]):  # Limit to 12 (4x3 grid)
        col, row = i % 4, i // 4
        x = _GRID_X0 + col * (_CELL_W + _GAP)
        y = _GRID_Y0 + row * (_CELL_H + _GAP)
        btn = _tpl_btn(
            app.get("name", f"App {i+1}"), x, y, _CELL_W, _CELL_H,
            action_type=ACTION_LAUNCH_APP, icon="\uf015", color=0x3498DB,
            launch_command=app.get("exec_cmd", ""),
        )
        wm_class = app.get("wm_class")
        if wm_class:
            btn["launch_wm_class"] = wm_class
            btn["launch_focus_or_launch"] = True
        icon_name = app.get("icon_name")
        if icon_name:
            btn["icon_source"] = icon_name
            btn["icon_source_type"] = "freedesktop"
        widgets.append(btn)
    widgets.append(_tpl_page_nav())
    return {"name": "Apps", "widgets": widgets}


def _generate_smart_default_config():
    """Generate a smart default config using all templates + KDE favorites.

    Returns a complete config dict with 7 pages:
    1. App Launcher (from KDE favorites)
    2. System Dashboard
    3. Media Controller
    4. Dev Workbench
    5. Productivity
    6. Streaming Deck
    7. Meeting Controls

    Also includes hardware_buttons and encoder defaults.
    """
    # Get KDE favorites and resolve to app entries
    kde_favorites = _get_kde_favorites()
    apps = []
    for desktop_file in kde_favorites:
        app = _resolve_app_from_desktop(desktop_file)
        if app:
            apps.append(app)

    # If we have fewer than 12 apps, pad with placeholder entries
    # (user can customize later)
    while len(apps) < 12:
        apps.append({
            "name": f"App {len(apps) + 1}",
            "exec_cmd": "",
            "icon_name": "",
            "wm_class": "",
        })

    # Build pages -- add page_nav to templates that don't include one
    def _ensure_page_nav(widgets):
        """Append page nav if not already present."""
        for w in widgets:
            if w.get("widget_type") == WIDGET_PAGE_NAV:
                return widgets
        widgets.append(_tpl_page_nav())
        return widgets

    pages = [
        _build_app_launcher_page(apps),
        {"name": "Dashboard", "widgets": _ensure_page_nav(template_system_dashboard())},
        {"name": "Media", "widgets": _ensure_page_nav(template_media_controller())},
        {"name": "Dev", "widgets": _ensure_page_nav(template_dev_workbench())},
        {"name": "Productivity", "widgets": _ensure_page_nav(template_productivity())},
        {"name": "Stream", "widgets": _ensure_page_nav(template_streaming_deck())},
        {"name": "Meeting", "widgets": _ensure_page_nav(template_meeting_controls())},
    ]

    from companion.config_manager import (
        CONFIG_VERSION, get_default_mode_cycle, get_default_display_settings,
        ensure_widget_ids,
    )
    config = {
        "version": CONFIG_VERSION,
        "active_profile_name": "Default",
        "brightness_level": 100,
        "default_mode": 0,
        "slideshow_interval_sec": 30,
        "clock_analog": False,
        "profiles": [{"name": "Default", "pages": pages}],
        "hardware_buttons": get_default_hardware_buttons(),
        "encoder": get_default_encoder(),
        "mode_cycle": get_default_mode_cycle(),
        "display_settings": get_default_display_settings(),
    }
    ensure_widget_ids(config)
    return config


def _tpl_btn(label, x, y, w=None, h=None, *, action_type=ACTION_HOTKEY,
             icon="\uf015", color=0x3498DB, modifiers=MOD_NONE, keycode=0,
             consumer_code=0, launch_command="", shell_command="", url=""):
    """Helper: create a hotkey button widget dict with overrides."""
    b = make_default_widget(WIDGET_HOTKEY_BUTTON, x, y)
    b["label"] = label
    b["icon"] = icon
    b["color"] = color
    b["action_type"] = action_type
    b["modifiers"] = modifiers
    b["keycode"] = keycode
    b["consumer_code"] = consumer_code
    b["launch_command"] = launch_command
    b["shell_command"] = shell_command
    b["url"] = url
    if w is not None:
        b["width"] = w
    if h is not None:
        b["height"] = h
    return b


def _tpl_stat(label, stat_type, x, y, color=None):
    """Helper: create a stat monitor widget dict."""
    s = make_default_widget(WIDGET_STAT_MONITOR, x, y)
    s["label"] = label
    s["stat_type"] = stat_type
    if color is not None:
        s["color"] = color
    else:
        s["color"] = STAT_DEFAULT_COLORS.get(stat_type, 0x3498DB)
    return s


def _tpl_status_bar():
    return make_default_widget(WIDGET_STATUS_BAR, 0, 0)


def _tpl_page_nav():
    return make_default_widget(WIDGET_PAGE_NAV, 300, 445)


def _tpl_text_label(label, x, y, w=200, h=30, font_size=16, color=0xFFFFFF):
    t = make_default_widget(WIDGET_TEXT_LABEL, x, y)
    t["label"] = label
    t["width"] = w
    t["height"] = h
    t["font_size"] = font_size
    t["color"] = color
    return t


def _tpl_clock(x, y):
    c = make_default_widget(WIDGET_CLOCK, x, y)
    return c


def template_app_launcher():
    """4x3 grid of Launch App buttons."""
    widgets = [_tpl_status_bar()]
    for i in range(12):
        col, row = i % 4, i // 4
        x = _GRID_X0 + col * (_CELL_W + _GAP)
        y = _GRID_Y0 + row * (_CELL_H + _GAP)
        widgets.append(_tpl_btn(
            f"App {i + 1}", x, y, _CELL_W, _CELL_H,
            action_type=ACTION_LAUNCH_APP, icon="\uf015", color=0x3498DB,
        ))
    widgets.append(_tpl_page_nav())
    return widgets


def template_system_dashboard():
    """Digital clock + 8 stat monitors + uptime."""
    widgets = [_tpl_status_bar()]
    widgets.append(_tpl_clock(300, 50))
    stats = [
        ("CPU", 0x01), ("RAM", 0x02), ("GPU", 0x03), ("CPU Temp", 0x04),
        ("GPU Temp", 0x05), ("Disk", 0x06), ("Net Up", 0x07), ("Net Down", 0x08),
    ]
    for i, (label, st) in enumerate(stats):
        col, row = i % 4, i // 4
        x = 6 + col * 198
        y = 200 + row * 60
        widgets.append(_tpl_stat(label, st, x, y))
    # Uptime widget
    widgets.append(_tpl_stat("Uptime", 0x0C, 6, 330, color=0x7F8C8D))
    return widgets


def template_media_controller():
    """Now Playing label + media control buttons."""
    widgets = [_tpl_status_bar()]
    widgets.append(_tpl_text_label("Now Playing", 200, 50, 400, 40, font_size=22))
    media_btns = [
        ("Prev", "\uf048", 0xB6),      # Previous Track
        ("Play", "\uf04b", 0xCD),       # Play/Pause
        ("Next", "\uf051", 0xB5),       # Next Track
        ("Vol-", "\uf027", 0xEA),       # Volume Down
        ("Vol+", "\uf028", 0xE9),       # Volume Up
    ]
    for i, (label, icon, cc) in enumerate(media_btns):
        x = 50 + i * 150
        widgets.append(_tpl_btn(
            label, x, 150, 130, 120,
            action_type=ACTION_MEDIA_KEY, icon=icon, color=0x9B59B6,
            consumer_code=cc,
        ))
    # Mute button centered below
    widgets.append(_tpl_btn(
        "Mute", 300, 300, 200, 100,
        action_type=ACTION_MEDIA_KEY, icon="\uf026", color=0xE74C3C,
        consumer_code=0xE2,
    ))
    return widgets


def template_dev_workbench():
    """6 dev hotkey buttons + 4 stat monitors."""
    widgets = [_tpl_status_bar()]
    # Dev shortcuts -- common IDE keybindings (lowercase ASCII = HID keycode)
    dev_btns = [
        ("Build", "\uf013", MOD_CTRL | MOD_SHIFT, ord('b')),   # SETTINGS
        ("Run", "\uf04b", MOD_CTRL | MOD_SHIFT, ord('r')),     # PLAY
        ("Debug", "\uf071", MOD_CTRL | MOD_SHIFT, ord('d')),   # WARNING
        ("Terminal", "\uf11c", MOD_CTRL, ord('`')),             # KEYBOARD
        ("Git", "\uf021", MOD_CTRL | MOD_SHIFT, ord('g')),     # REFRESH
        ("Browser", "\uf1eb", MOD_ALT, 0xC8),                  # WIFI
    ]
    for i, (label, icon, mods, kc) in enumerate(dev_btns):
        col, row = i % 3, i // 3
        x = 6 + col * 264
        y = 50 + row * 130
        widgets.append(_tpl_btn(
            label, x, y, 255, 120,
            icon=icon, color=0x3F51B5, modifiers=mods, keycode=kc,
        ))
    # Stats row at bottom
    dev_stats = [
        ("CPU", 0x01), ("RAM", 0x02), ("GPU Temp", 0x05), ("Load Avg", 0x0F),
    ]
    for i, (label, st) in enumerate(dev_stats):
        x = 6 + i * 198
        y = 320
        widgets.append(_tpl_stat(label, st, x, y))
    return widgets


def template_productivity():
    """8 utility buttons -- KDE apps + shell commands."""
    widgets = [_tpl_status_bar()]
    # (label, icon, action_type, launch_cmd, wm_class, shell_cmd, icon_source, mods, keycode)
    apps = [
        ("Screenshot", "\uf03e", ACTION_LAUNCH_APP, "spectacle", "spectacle", "", "spectacle", MOD_NONE, 0),
        ("Files", "\uf07b", ACTION_LAUNCH_APP, "dolphin", "dolphin", "", "system-file-manager", MOD_NONE, 0),
        ("Calculator", "\uf00b", ACTION_LAUNCH_APP, "kcalc", "kcalc", "", "accessories-calculator", MOD_NONE, 0),
        ("Lock", "\uf00d", ACTION_HOTKEY, "", "", "", "", MOD_GUI, ord('l')),
        ("Browser", "\uf1eb", ACTION_SHELL_CMD, "", "", "xdg-open http://", "internet-web-browser", MOD_NONE, 0),
        ("Email", "\uf0e0", ACTION_SHELL_CMD, "", "", "xdg-open mailto:", "internet-mail", MOD_NONE, 0),
        ("Notes", "\uf304", ACTION_LAUNCH_APP, "kate", "kate", "", "kate", MOD_NONE, 0),
        ("Settings", "\uf013", ACTION_LAUNCH_APP, "systemsettings", "systemsettings", "", "preferences-system", MOD_NONE, 0),
    ]
    for i, (label, icon, at, launch_cmd, wm_class, shell_cmd, icon_src, mods, kc) in enumerate(apps):
        col, row = i % 4, i // 4
        x = _GRID_X0 + col * (_CELL_W + _GAP)
        y = _GRID_Y0 + row * (160 + _GAP)
        btn = _tpl_btn(
            label, x, y, _CELL_W, 150,
            action_type=at, icon=icon, color=0x2ECC71,
            launch_command=launch_cmd, shell_command=shell_cmd,
            modifiers=mods, keycode=kc,
        )
        if wm_class:
            btn["launch_wm_class"] = wm_class
            btn["launch_focus_or_launch"] = True
        if icon_src:
            btn["icon_source"] = icon_src
            btn["icon_source_type"] = "freedesktop"
        widgets.append(btn)
    widgets.append(_tpl_page_nav())
    return widgets


def template_streaming_deck():
    """Streaming control buttons with color coding."""
    widgets = [_tpl_status_bar()]
    widgets.append(_tpl_text_label("STREAM CONTROLS", 200, 50, 400, 35, font_size=20))
    stream_btns = [
        ("Scene 1", "\uf008", 0x3498DB, MOD_NONE, 0),   # VIDEO
        ("Scene 2", "\uf008", 0x3498DB, MOD_NONE, 0),   # VIDEO
        ("Scene 3", "\uf008", 0x3498DB, MOD_NONE, 0),   # VIDEO
        ("Mute Mic", "\uf026", 0xE74C3C, MOD_NONE, 0),  # MUTE
        ("Stream", "\uf008", 0x2ECC71, MOD_NONE, 0),    # VIDEO
        ("Camera", "\uf03e", 0x2ECC71, MOD_NONE, 0),    # IMAGE
    ]
    for i, (label, icon, color, mods, kc) in enumerate(stream_btns):
        col, row = i % 3, i // 3
        x = 50 + col * 245
        y = 110 + row * 160
        widgets.append(_tpl_btn(
            label, x, y, 230, 140,
            icon=icon, color=color, modifiers=mods, keycode=kc,
        ))
    return widgets


def template_meeting_controls():
    """Meeting control buttons for Teams/Zoom."""
    widgets = [_tpl_status_bar()]
    widgets.append(_tpl_text_label("MEETING", 250, 50, 300, 35, font_size=22))
    # Ctrl+Shift+<key> combos that work in Teams & Zoom
    meeting_btns = [
        ("Mute Mic", "\uf026", 0xE67E22, ord('m')),      # MUTE -- Ctrl+Shift+M
        ("Camera", "\uf03e", 0xE67E22, ord('o')),         # IMAGE -- Ctrl+Shift+O
        ("Share", "\uf093", 0x3498DB, ord('e')),           # UPLOAD -- Ctrl+Shift+E
        ("Chat", "\uf0e0", 0x3498DB, ord('c')),            # ENVELOPE -- Ctrl+Shift+C
        ("Hand", "\uf077", 0x3498DB, ord('k')),            # UP -- Ctrl+Shift+K
        ("Leave", "\uf011", 0xE74C3C, ord('h')),           # POWER -- Ctrl+Shift+H
    ]
    for i, (label, icon, color, kc) in enumerate(meeting_btns):
        col, row = i % 3, i // 3
        x = 50 + col * 245
        y = 110 + row * 160
        widgets.append(_tpl_btn(
            label, x, y, 230, 140,
            icon=icon, color=color,
            modifiers=MOD_CTRL | MOD_SHIFT, keycode=kc,
        ))
    return widgets


def template_blank_canvas():
    """Status bar only -- blank canvas."""
    return [_tpl_status_bar()]


# All templates: (menu_label, function)
PAGE_TEMPLATES = [
    ("App Launcher (4x3 grid)", template_app_launcher),
    ("System Dashboard", template_system_dashboard),
    ("Media Controller", template_media_controller),
    ("Dev Workbench", template_dev_workbench),
    ("Productivity", template_productivity),
    ("Streaming Deck", template_streaming_deck),
    ("Meeting Controls", template_meeting_controls),
    ("Blank Canvas", template_blank_canvas),
]
