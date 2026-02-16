"""
CrowPanel Companion Tray Application

Single PySide6 process with QSystemTrayIcon. Runs the CompanionService in
background threads and provides a right-click tray menu to open the editor,
refresh config, toggle autostart, and quit.
"""

import logging
import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QIcon, QImage, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from companion.config_manager import get_config_manager, DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_PATH
from companion.hotkey_companion import CompanionService

# XDG autostart paths
AUTOSTART_DIR = Path.home() / ".config" / "autostart"
DESKTOP_FILE_NAME = "crowpanel-companion.desktop"
DATA_DIR = Path(__file__).parent / "data"

# Icon files
TRAY_ICON_PATH = DATA_DIR / "crowpanel-tray-64.png"
APP_ICON_PATH = DATA_DIR / "app-icon-256.png"

# Tint colors for bridge state
COLOR_CONNECTED = QColor("#2ECC71")
COLOR_DISCONNECTED = QColor("#E74C3C")


class _ServiceSignals(QObject):
    """Bridge between CompanionService callbacks (background threads) and Qt main thread."""
    bridge_connected = Signal()
    bridge_disconnected = Signal()
    stats_sent = Signal()
    button_pressed = Signal(int, int)


def _tint_icon(path: Path, tint: QColor) -> QIcon:
    """Load a grayscale PNG and tint it with the given color.

    Multiplies each pixel's RGB by the tint color while preserving alpha.
    """
    image = QImage(str(path))
    if image.isNull():
        # Fallback: solid colored square
        px = QPixmap(64, 64)
        px.fill(tint)
        return QIcon(px)

    image = image.convertToFormat(QImage.Format_ARGB32)

    tr, tg, tb = tint.redF(), tint.greenF(), tint.blueF()

    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() == 0:
                continue
            # Use luminance of grayscale pixel as intensity
            lum = pixel.redF()  # grayscale, so R==G==B
            image.setPixelColor(x, y, QColor.fromRgbF(
                lum * tr, lum * tg, lum * tb, pixel.alphaF()
            ))

    return QIcon(QPixmap.fromImage(image))


class CrowPanelTray(QApplication):
    """System tray application for CrowPanel Companion."""

    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        # Set application icon (glossy circle badge)
        if APP_ICON_PATH.is_file():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))

        # Config manager (shared singleton)
        self._config_mgr = get_config_manager()

        # Companion service
        self._service = CompanionService(self._config_mgr)

        # Qt signal bridge for thread-safe UI updates
        self._signals = _ServiceSignals()
        self._signals.bridge_connected.connect(self._on_bridge_connected)
        self._signals.bridge_disconnected.connect(self._on_bridge_disconnected)
        self._signals.stats_sent.connect(self._on_stats_sent)
        self._signals.button_pressed.connect(self._on_button_pressed)

        # Wire service callbacks to emit Qt signals
        self._service.on_bridge_connected = lambda: self._signals.bridge_connected.emit()
        self._service.on_bridge_disconnected = lambda: self._signals.bridge_disconnected.emit()
        self._service.on_stats_sent = lambda: self._signals.stats_sent.emit()
        self._service.on_button_press = lambda p, w: self._signals.button_pressed.emit(p, w)

        # System tray icon — tinted grayscale crow
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_tint_icon(TRAY_ICON_PATH, COLOR_DISCONNECTED))
        self._tray.setToolTip("CrowPanel — Bridge: Disconnected")

        # Tray menu
        self._menu = QMenu()
        self._status_action = self._menu.addAction("Bridge: Disconnected")
        self._status_action.setEnabled(False)
        self._menu.addSeparator()

        edit_action = self._menu.addAction("Edit...")
        edit_action.triggered.connect(self._on_edit)

        refresh_action = self._menu.addAction("Refresh Config")
        refresh_action.triggered.connect(self._on_refresh)

        self._menu.addSeparator()

        self._autostart_action = self._menu.addAction("Autostart")
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(self._is_autostart_enabled())
        self._autostart_action.triggered.connect(self._on_toggle_autostart)

        self._menu.addSeparator()

        quit_action = self._menu.addAction("Quit")
        quit_action.triggered.connect(self._on_quit)

        self._tray.setContextMenu(self._menu)
        self._tray.show()

        # Editor window (created on demand)
        self._editor = None

        # Start companion service
        self._service.start()

    def _on_bridge_connected(self):
        self._tray.setIcon(_tint_icon(TRAY_ICON_PATH, COLOR_CONNECTED))
        self._update_status()

    def _on_bridge_disconnected(self):
        self._tray.setIcon(_tint_icon(TRAY_ICON_PATH, COLOR_DISCONNECTED))
        self._update_status()

    def _on_stats_sent(self):
        self._update_status()

    def _on_button_pressed(self, page_idx, widget_idx):
        logging.debug("Tray: button press page=%d widget=%d", page_idx, widget_idx)

    def _update_status(self):
        text = self._service.status_text
        self._status_action.setText(text)
        self._tray.setToolTip(f"CrowPanel — {text}")

    def _on_edit(self):
        """Open or bring to front the editor window."""
        if self._editor is None:
            from companion.ui.editor_main import EditorMainWindow
            self._editor = EditorMainWindow(self._config_mgr)
            self._editor.setAttribute(Qt.WA_DeleteOnClose, False)
            self._editor._tray_mode = True
            # Set the app icon on the editor window too
            if APP_ICON_PATH.is_file():
                self._editor.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self._editor.show()
        self._editor.raise_()
        self._editor.activateWindow()

    def _on_refresh(self):
        self._service.reload_config()
        if self._editor is not None and self._editor.isVisible():
            self._editor._auto_load_config()

    def _on_toggle_autostart(self, checked):
        desktop_src = DATA_DIR / DESKTOP_FILE_NAME
        desktop_dst = AUTOSTART_DIR / DESKTOP_FILE_NAME

        if checked:
            AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            if desktop_src.is_file():
                shutil.copy2(str(desktop_src), str(desktop_dst))
            else:
                # Generate a minimal desktop file if the template doesn't exist
                tray_script = Path(__file__).parent / "crowpanel_tray.py"
                desktop_dst.write_text(
                    f"[Desktop Entry]\n"
                    f"Type=Application\n"
                    f"Name=CrowPanel Companion\n"
                    f"Exec=python3 {tray_script}\n"
                    f"Icon=crowpanel\n"
                    f"Categories=Utility;System;\n"
                    f"StartupNotify=false\n"
                    f"X-GNOME-Autostart-enabled=true\n"
                )
            logging.info("Autostart enabled: %s", desktop_dst)
        else:
            if desktop_dst.is_file():
                desktop_dst.unlink()
            logging.info("Autostart disabled")

    def _is_autostart_enabled(self):
        return (AUTOSTART_DIR / DESKTOP_FILE_NAME).is_file()

    def _on_quit(self):
        """Clean shutdown."""
        self._service.stop()
        if self._editor is not None:
            self._editor._tray_mode = False
            self._editor.close()
        self._tray.hide()
        self.quit()
