#!/usr/bin/env python3
"""CrowPanel Companion — system tray app.

Runs the companion service (stats streaming, button actions, notifications)
with a system tray icon. Right-click the tray to open the editor, refresh
config, toggle autostart, or quit.

Usage:
    PYTHONPATH=. python companion/crowpanel_tray.py
"""

import logging
import sys

from companion.tray_app import CrowPanelTray


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("CrowPanel Companion Tray starting...")

    app = CrowPanelTray(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
