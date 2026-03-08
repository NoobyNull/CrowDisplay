"""
Editor Utilities: FontAwesome loading, icon resolution, color conversion helpers.
"""

import os
import logging

from PySide6.QtGui import QColor, QPixmap

logger = logging.getLogger(__name__)

# Load FontAwesome for rendering LVGL symbol icons as actual glyphs
_FA_FONT_FAMILY = None
_FA_FONT_PATHS = [
    "/usr/share/fonts/awesome-terminal-fonts/fontawesome-regular.ttf",
    "/usr/share/fonts/TTF/fontawesome-regular.ttf",
]
def _get_fa_font_family():
    global _FA_FONT_FAMILY
    if _FA_FONT_FAMILY is not None:
        return _FA_FONT_FAMILY
    from PySide6.QtGui import QFontDatabase
    for path in _FA_FONT_PATHS:
        if os.path.exists(path):
            font_id = QFontDatabase.addApplicationFont(path)
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                _FA_FONT_FAMILY = families[0]
                logger.info("Loaded FontAwesome: %s", _FA_FONT_FAMILY)
                return _FA_FONT_FAMILY
    _FA_FONT_FAMILY = ""  # Not found, use fallback
    logger.warning("FontAwesome font not found, icons will show as text names")
    return _FA_FONT_FAMILY


def _resolve_icon_source(widget_dict):
    """Resolve icon_source from widget dict to a filesystem path, or None."""
    icon_source = widget_dict.get("icon_source", "")
    icon_source_type = widget_dict.get("icon_source_type", "")
    if not icon_source or not icon_source_type:
        return None
    if icon_source_type == "file":
        return icon_source if os.path.exists(icon_source) else None
    if icon_source_type == "freedesktop":
        from companion.app_scanner import _resolve_icon_path, _get_icon_theme
        return _resolve_icon_path(icon_source, _get_icon_theme()) or None
    return None


def _load_icon_pixmap(source_path, width, height):
    """Load and rasterize an icon from source_path at the given size. Returns QPixmap or None."""
    if not source_path:
        return None
    try:
        from companion.image_optimizer import optimize_icon
        png_data = optimize_icon(source_path, width, height)
        pixmap = QPixmap()
        pixmap.loadFromData(png_data, "PNG")
        return pixmap if not pixmap.isNull() else None
    except Exception as e:
        logger.warning("Failed to load icon %s: %s", source_path, e)
        return None


def _int_to_qcolor(color_val):
    """Convert 0xRRGGBB int to QColor."""
    return QColor((color_val >> 16) & 0xFF, (color_val >> 8) & 0xFF, color_val & 0xFF)


def _qcolor_to_int(qcolor):
    """Convert QColor to 0xRRGGBB int."""
    return (qcolor.red() << 16) | (qcolor.green() << 8) | qcolor.blue()
