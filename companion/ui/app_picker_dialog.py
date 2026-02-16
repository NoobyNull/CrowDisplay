"""
App Picker Dialog: Browse installed applications and select one for a button.

Shows a searchable list of installed apps with icons. On selection, returns
the app's name, icon path, and exec command for populating a hotkey button.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap

from companion.app_scanner import AppEntry, scan_applications


class AppPickerDialog(QDialog):
    """Dialog for browsing and selecting an installed application."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Application")
        self.setMinimumSize(500, 600)
        self.setModal(True)

        self._apps = []
        self._selected_app = None

        layout = QVBoxLayout(self)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search applications...")
        self.search_input.textChanged.connect(self._on_search)
        self.search_input.setStyleSheet(
            "padding: 8px; font-size: 14px; background: #1a1a2e; "
            "color: #e0e0e0; border: 1px solid #444; border-radius: 4px;"
        )
        layout.addWidget(self.search_input)

        # App count label
        self.count_label = QLabel("Scanning applications...")
        self.count_label.setStyleSheet("color: #888; font-size: 11px; padding: 2px;")
        layout.addWidget(self.count_label)

        # App list
        self.app_list = QListWidget()
        self.app_list.setIconSize(QSize(32, 32))
        self.app_list.setStyleSheet(
            "QListWidget { background: #161b22; border: 1px solid #333; }"
            "QListWidget::item { padding: 6px 4px; color: #e0e0e0; }"
            "QListWidget::item:selected { background: #1f6feb; }"
            "QListWidget::item:hover { background: #21262d; }"
        )
        self.app_list.itemDoubleClicked.connect(self._on_double_click)
        self.app_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.app_list)

        # Info label for selected app
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #aaa; font-size: 11px; padding: 4px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        self.ok_button = button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setText("Select")
        self.ok_button.setEnabled(False)
        layout.addWidget(button_box)

        # Load apps
        self._load_apps()
        self.search_input.setFocus()

    def _load_apps(self):
        """Scan and populate the app list."""
        self._apps = scan_applications()
        self._populate_list(self._apps)
        self.count_label.setText(f"{len(self._apps)} applications found")

    def _populate_list(self, apps):
        """Fill the list widget with app entries."""
        self.app_list.clear()
        for app in apps:
            item = QListWidgetItem()
            item.setText(app.name)
            item.setData(Qt.UserRole, app)

            # Load icon
            if app.icon_path:
                icon = QIcon(app.icon_path)
                if not icon.isNull():
                    item.setIcon(icon)

            if app.comment:
                item.setToolTip(app.comment)

            self.app_list.addItem(item)

    def _on_search(self, text):
        """Filter app list by search text."""
        query = text.lower().strip()
        if not query:
            self._populate_list(self._apps)
            self.count_label.setText(f"{len(self._apps)} applications found")
            return

        filtered = [
            app for app in self._apps
            if query in app.name.lower()
            or query in app.comment.lower()
            or any(query in c.lower() for c in app.categories)
        ]
        self._populate_list(filtered)
        self.count_label.setText(f"{len(filtered)} of {len(self._apps)} applications")

    def _on_selection_changed(self, current, previous):
        """Update info label when selection changes."""
        if current is None:
            self.info_label.setText("")
            self.ok_button.setEnabled(False)
            self._selected_app = None
            return

        app = current.data(Qt.UserRole)
        self._selected_app = app
        self.ok_button.setEnabled(True)

        icon_status = "has icon" if app.icon_path else "no icon found"
        self.info_label.setText(
            f"Exec: {app.exec_cmd}\n"
            f"Icon: {app.icon_name} ({icon_status})\n"
            f"Categories: {', '.join(app.categories[:5]) or 'none'}"
        )

    def _on_double_click(self, item):
        """Accept on double-click."""
        self._selected_app = item.data(Qt.UserRole)
        self.accept()

    def _on_accept(self):
        """Accept current selection."""
        if self._selected_app:
            self.accept()

    def get_selected_app(self) -> AppEntry:
        """Return the selected AppEntry, or None."""
        return self._selected_app
