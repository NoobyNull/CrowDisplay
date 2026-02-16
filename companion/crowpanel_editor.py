#!/usr/bin/env python3
"""
CrowPanel Editor: Main PySide6 application entry point

Launches the desktop GUI editor for visual hotkey layout design.
Supports loading/saving JSON configs and WiFi deployment to device.

Usage:
    python crowpanel_editor.py [--device-ip 192.168.4.1]
"""

import sys
import argparse
from PySide6.QtWidgets import QApplication

from companion.config_manager import get_config_manager
from companion.ui.editor_main import EditorMainWindow


def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description="CrowPanel Desktop Editor")
    parser.add_argument(
        "--device-ip",
        default="192.168.4.1",
        help="Device IP address for WiFi deployment (default: 192.168.4.1)",
    )
    args = parser.parse_args()

    # Create Qt application
    app = QApplication(sys.argv)

    # Create config manager (singleton)
    config_manager = get_config_manager()

    # Create main window
    editor = EditorMainWindow(config_manager)
    editor.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
