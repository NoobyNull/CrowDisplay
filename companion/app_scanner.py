"""
App Scanner: Discover installed Linux applications from .desktop files.

Scans /usr/share/applications and ~/.local/share/applications for .desktop
entries, extracts name/icon/exec, and resolves icon paths from the active
icon theme for use as button icons on the device.
"""

import configparser
import glob
import os
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AppEntry:
    """Represents an installed application."""
    name: str
    icon_name: str  # freedesktop icon name (e.g., "firefox")
    exec_cmd: str   # Exec line from .desktop
    comment: str = ""
    categories: List[str] = field(default_factory=list)
    desktop_file: str = ""
    icon_path: str = ""  # Resolved filesystem path to icon
    wm_class: str = ""   # StartupWMClass from .desktop file


def _get_icon_theme() -> str:
    """Get the active GTK icon theme name."""
    try:
        result = subprocess.run(
            ["gtk-query-settings", "gtk-icon-theme-name"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "gtk-icon-theme-name" in line:
                # Format: gtk-icon-theme-name: "kora"
                parts = line.split('"')
                if len(parts) >= 2:
                    return parts[1]
    except Exception:
        pass
    return "hicolor"


def _resolve_icon_path(icon_name: str, theme: str) -> str:
    """
    Resolve an icon name to a filesystem path.

    Search order:
    1. If icon_name is already an absolute path, use it
    2. Search active theme directories (48x48, scalable, 64x64, 32x32)
    3. Search hicolor fallback
    4. Search /usr/share/pixmaps
    """
    if not icon_name:
        return ""

    # Already an absolute path
    if os.path.isabs(icon_name):
        if os.path.exists(icon_name):
            return icon_name
        # Try adding common extensions
        for ext in (".png", ".svg", ".xpm"):
            if os.path.exists(icon_name + ext):
                return icon_name + ext
        return ""

    # Search icon theme directories
    icon_dirs = [f"/usr/share/icons/{theme}", "/usr/share/icons/hicolor"]
    # Prefer scalable (SVG) and large sizes for best quality when rasterized
    size_dirs = ["scalable", "256x256", "128x128", "64x64", "48x48", "32x32"]
    extensions = [".png", ".svg", ".xpm"]

    for icon_dir in icon_dirs:
        for size in size_dirs:
            for ext in extensions:
                path = os.path.join(icon_dir, size, "apps", icon_name + ext)
                if os.path.exists(path):
                    return path

    # Search pixmaps
    for ext in extensions:
        path = f"/usr/share/pixmaps/{icon_name}{ext}"
        if os.path.exists(path):
            return path

    # Brute-force search across all theme subdirs
    for icon_dir in icon_dirs:
        for match in glob.glob(os.path.join(icon_dir, "**", "apps", icon_name + ".*"), recursive=True):
            return match

    return ""


def scan_applications() -> List[AppEntry]:
    """
    Scan system for installed applications.

    Returns a sorted list of AppEntry objects with resolved icon paths.
    """
    desktop_dirs = [
        "/usr/share/applications",
        os.path.expanduser("~/.local/share/applications"),
    ]

    theme = _get_icon_theme()
    apps = []
    seen_names = set()

    for app_dir in desktop_dirs:
        if not os.path.isdir(app_dir):
            continue

        for desktop_file in glob.glob(os.path.join(app_dir, "*.desktop")):
            try:
                cp = configparser.ConfigParser(interpolation=None)
                cp.read(desktop_file)

                if not cp.has_section("Desktop Entry"):
                    continue

                entry = cp["Desktop Entry"]

                # Skip non-applications and hidden entries
                if entry.get("Type", "") != "Application":
                    continue
                if entry.get("NoDisplay", "false").lower() == "true":
                    continue
                if entry.get("Hidden", "false").lower() == "true":
                    continue

                name = entry.get("Name", "")
                if not name or name in seen_names:
                    continue
                seen_names.add(name)

                icon_name = entry.get("Icon", "")
                exec_cmd = entry.get("Exec", "")
                comment = entry.get("Comment", "")
                categories = [c.strip() for c in entry.get("Categories", "").split(";") if c.strip()]
                wm_class = entry.get("StartupWMClass", "")

                # Resolve icon to filesystem path
                icon_path = _resolve_icon_path(icon_name, theme)

                apps.append(AppEntry(
                    name=name,
                    icon_name=icon_name,
                    exec_cmd=exec_cmd,
                    comment=comment,
                    categories=categories,
                    desktop_file=desktop_file,
                    icon_path=icon_path,
                    wm_class=wm_class,
                ))

            except Exception:
                continue

    apps.sort(key=lambda a: a.name.lower())
    return apps
