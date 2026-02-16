"""
Editor Main Window: PySide6 main window with button grid and control panels

Displays 4x3 button grid on left, button editor + deploy controls on right.
File menu for new/open/save with keyboard shortcuts (Ctrl+N/O/S).
Page toolbar for page management (prev/next, add, remove, rename, reorder).
Status bar shows selected button and deployment status.
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QDialog,
    QGroupBox,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QColorDialog,
    QAbstractItemView,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QKeySequence, QAction

from companion.config_manager import get_config_manager
from companion.ui.button_editor import ButtonEditor
from companion.ui.deploy_dialog import DeployDialog
from companion.lvgl_symbols import SYMBOL_BY_UTF8


class ButtonGridWidget(QWidget):
    """Custom widget for 4x3 button grid display"""

    # Signal emitted when a button is clicked
    # Payload: (page_idx, button_idx)
    button_clicked = Signal(int, int)

    # Signal emitted when grid needs refresh
    grid_updated = Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.selected_button = None
        self.buttons = []  # 2D list of button widgets
        self.current_page = 0

        layout = QGridLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Create 4x3 grid of buttons
        for row in range(3):
            row_buttons = []
            for col in range(4):
                btn = QPushButton()
                btn.setMinimumSize(QSize(100, 80))
                btn.setFont(QFont("Arial", 10))
                btn.clicked.connect(lambda checked, r=row, c=col: self._on_button_clicked(r, c))
                layout.addWidget(btn, row, col)
                row_buttons.append(btn)
            self.buttons.append(row_buttons)

        self.setLayout(layout)
        self.config_manager.config_changed_callback = self.refresh_grid

    def refresh_grid(self):
        """Refresh button grid display from config"""
        page = self.config_manager.get_page(self.current_page)
        if page is None:
            return

        buttons_data = page.get("buttons", [])

        # Clear all cells first
        for row in range(3):
            for col in range(4):
                btn = self.buttons[row][col]
                btn.setText("")
                btn.setStyleSheet("background-color: #f0f0f0;")
                btn.setToolTip("")

        # Place buttons: explicit grid positions first, then auto-flow
        auto_row, auto_col = 0, 0
        for button_idx, button_dict in enumerate(buttons_data):
            label = button_dict.get("label", "")
            description = button_dict.get("description", "")
            color = button_dict.get("color", 0x3498DB)
            icon = button_dict.get("icon", "")
            grid_row = button_dict.get("grid_row", -1)
            grid_col = button_dict.get("grid_col", -1)
            pressed_color = button_dict.get("pressed_color", 0x000000)

            # Determine grid cell
            if grid_row >= 0 and grid_col >= 0:
                target_row, target_col = grid_row, grid_col
            else:
                target_row, target_col = auto_row, auto_col
                auto_col += 1
                if auto_col >= 4:
                    auto_col = 0
                    auto_row += 1

            if target_row >= 3 or target_col >= 4:
                continue

            btn = self.buttons[target_row][target_col]

            # Resolve icon display
            icon_display = ""
            if icon:
                icon_bytes = icon.encode("utf-8")
                if icon_bytes in SYMBOL_BY_UTF8:
                    icon_display = SYMBOL_BY_UTF8[icon_bytes][0]
                elif len(icon) == 1 and ord(icon) >= 0xF000:
                    icon_display = "?"
                else:
                    icon_display = icon

            # Format button text
            parts = []
            if icon_display:
                parts.append(icon_display)
            parts.append(label)
            if description:
                parts.append(description)
            btn.setText("\n".join(parts))

            # Tooltip with position and pressed color info
            pos_info = f"Grid: ({target_row}, {target_col})"
            if grid_row >= 0 and grid_col >= 0:
                pos_info += " [explicit]"
            pressed_info = "Pressed: auto-darken" if pressed_color == 0 else f"Pressed: #{pressed_color:06X}"
            btn.setToolTip(f"{pos_info}\n{pressed_info}")

            # Set background color with luminance-based text contrast
            qcolor = self._value_to_qcolor(color)
            lum = 0.299 * qcolor.red() + 0.587 * qcolor.green() + 0.114 * qcolor.blue()
            text_color = "#000" if lum > 140 else "#FFF"

            # Selected button highlight
            is_selected = (self.current_page, button_idx) == self.selected_button
            border_style = "border: 3px solid #FFD700;" if is_selected else "border: 2px solid #555;"

            btn.setStyleSheet(
                f"background-color: {qcolor.name()}; color: {text_color}; "
                f"{border_style} border-radius: 4px;"
            )

        self.grid_updated.emit()

    def set_page(self, page_idx: int):
        """Switch to different page"""
        if self.config_manager.get_page(page_idx) is not None:
            self.current_page = page_idx
            self.selected_button = None
            self.refresh_grid()

    def get_selected_button(self) -> tuple | None:
        """Get currently selected button as (page_idx, button_idx)"""
        return self.selected_button

    def _on_button_clicked(self, row: int, col: int):
        """Button in grid was clicked"""
        button_idx = row * 4 + col
        self.selected_button = (self.current_page, button_idx)
        self.refresh_grid()
        self.button_clicked.emit(self.current_page, button_idx)

    def _value_to_qcolor(self, color_val: int) -> QColor:
        """Convert RGB hex value to QColor"""
        r = (color_val >> 16) & 0xFF
        g = (color_val >> 8) & 0xFF
        b = color_val & 0xFF
        return QColor(r, g, b)


class EditorMainWindow(QMainWindow):
    """Main editor window with grid and controls"""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.current_page = 0
        self.setWindowTitle("CrowPanel Editor")
        self.setMinimumSize(1000, 700)

        # Create central widget
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)

        # Left panel: button grid
        self.button_grid = ButtonGridWidget(self.config_manager)
        self.button_grid.button_clicked.connect(self._on_grid_button_clicked)
        main_layout.addWidget(self.button_grid, stretch=2)

        # Right panel: controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Page toolbar
        page_toolbar_layout = QHBoxLayout()
        self.prev_page_btn = QPushButton("< Prev")
        self.prev_page_btn.clicked.connect(self._on_prev_page)
        self.page_label = QLabel("Page 1 / 3")
        self.next_page_btn = QPushButton("Next >")
        self.next_page_btn.clicked.connect(self._on_next_page)
        self.add_page_btn = QPushButton("+ Add")
        self.add_page_btn.clicked.connect(self._on_add_page)
        self.remove_page_btn = QPushButton("- Remove")
        self.remove_page_btn.clicked.connect(self._on_remove_page)
        self.rename_page_btn = QPushButton("Rename")
        self.rename_page_btn.clicked.connect(self._on_rename_page)
        self.move_left_btn = QPushButton("Move Left")
        self.move_left_btn.clicked.connect(self._on_move_page_left)
        self.move_right_btn = QPushButton("Move Right")
        self.move_right_btn.clicked.connect(self._on_move_page_right)

        page_toolbar_layout.addWidget(self.prev_page_btn)
        page_toolbar_layout.addWidget(self.page_label)
        page_toolbar_layout.addWidget(self.next_page_btn)
        right_layout.addLayout(page_toolbar_layout)

        # Page management row
        page_mgmt_layout = QHBoxLayout()
        page_mgmt_layout.addWidget(self.add_page_btn)
        page_mgmt_layout.addWidget(self.remove_page_btn)
        page_mgmt_layout.addWidget(self.rename_page_btn)
        page_mgmt_layout.addWidget(self.move_left_btn)
        page_mgmt_layout.addWidget(self.move_right_btn)
        right_layout.addLayout(page_mgmt_layout)

        # Button editor panel
        self.button_editor = ButtonEditor()
        self.button_editor.button_updated.connect(self._on_button_updated)
        right_layout.addWidget(self.button_editor)

        # Display Modes panel
        display_group = QGroupBox("Display Modes")
        display_layout = QGridLayout()

        display_layout.addWidget(QLabel("Default mode:"), 0, 0)
        self.mode_dropdown = QComboBox()
        self.mode_dropdown.addItems(["Hotkeys", "Clock", "Picture Frame", "Standby"])
        self.mode_dropdown.currentIndexChanged.connect(self._on_display_mode_changed)
        display_layout.addWidget(self.mode_dropdown, 0, 1)

        display_layout.addWidget(QLabel("Slideshow interval (sec):"), 1, 0)
        self.slideshow_spinbox = QSpinBox()
        self.slideshow_spinbox.setRange(5, 300)
        self.slideshow_spinbox.setValue(30)
        self.slideshow_spinbox.valueChanged.connect(self._on_display_mode_changed)
        display_layout.addWidget(self.slideshow_spinbox, 1, 1)

        self.analog_checkbox = QCheckBox("Analog clock")
        self.analog_checkbox.stateChanged.connect(self._on_display_mode_changed)
        display_layout.addWidget(self.analog_checkbox, 2, 0, 1, 2)

        display_group.setLayout(display_layout)
        right_layout.addWidget(display_group)

        # Load display mode settings from config
        self._load_display_mode_settings()

        # Deploy button
        self.deploy_btn = QPushButton("Deploy to Device")
        self.deploy_btn.setMinimumHeight(40)
        self.deploy_btn.setStyleSheet("background-color: #2ECC71; color: white; font-weight: bold;")
        self.deploy_btn.clicked.connect(self._on_deploy_clicked)
        right_layout.addWidget(self.deploy_btn)

        main_layout.addWidget(right_panel, stretch=1)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Create menu bar with keyboard shortcuts
        self._create_menu_bar()

        # Create status bar
        self.statusBar().showMessage("Ready")
        self.status_label = QLabel("No button selected")
        self.statusBar().addWidget(self.status_label)

        # Load initial page
        self._update_page_display()
        self.button_grid.refresh_grid()

    def _create_menu_bar(self):
        """Create File menu with keyboard shortcuts"""
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        new_action = file_menu.addAction("New")
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._on_file_new)

        open_action = file_menu.addAction("Open...")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._on_file_open)

        save_action = file_menu.addAction("Save...")
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._on_file_save)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def _update_page_display(self):
        """Update page buttons and labels"""
        page_count = self.config_manager.get_page_count()
        page_name = ""
        page = self.config_manager.get_page(self.current_page)
        if page:
            page_name = page.get("name", "")

        self.page_label.setText(f"{page_name} ({self.current_page + 1} / {page_count})")
        self.prev_page_btn.setEnabled(self.current_page > 0)
        self.next_page_btn.setEnabled(self.current_page < page_count - 1)
        self.remove_page_btn.setEnabled(page_count > 1)
        self.move_left_btn.setEnabled(self.current_page > 0)
        self.move_right_btn.setEnabled(self.current_page < page_count - 1)

    def _on_grid_button_clicked(self, page_idx: int, button_idx: int):
        """Button in grid was clicked"""
        button = self.config_manager.get_button(page_idx, button_idx)
        if button:
            self.button_editor.load_button(button, page_idx, button_idx)
            self.status_label.setText(f"Editing: Page {page_idx + 1}, Button {button_idx + 1}")
            self.button_grid.refresh_grid()

    def _on_button_updated(self, button_dict: dict):
        """Button editor emitted update"""
        page_idx, button_idx = self.button_grid.get_selected_button() or (self.current_page, 0)
        self.config_manager.set_button(page_idx, button_idx, button_dict)
        self.button_grid.refresh_grid()

    def _on_prev_page(self):
        """Previous page button clicked"""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_page_display()
            self.button_grid.set_page(self.current_page)

    def _on_next_page(self):
        """Next page button clicked"""
        if self.current_page < self.config_manager.get_page_count() - 1:
            self.current_page += 1
            self._update_page_display()
            self.button_grid.set_page(self.current_page)

    def _on_add_page(self):
        """Add page button clicked"""
        page_count = self.config_manager.get_page_count()
        new_page_name = f"Page {page_count + 1}"
        if self.config_manager.add_page(new_page_name):
            self._update_page_display()
            self.statusBar().showMessage(f"Added page: {new_page_name}")

    def _on_remove_page(self):
        """Remove page button clicked"""
        if self.config_manager.get_page_count() <= 1:
            QMessageBox.warning(self, "Error", "Cannot remove the last page")
            return

        if self.config_manager.remove_page(self.current_page):
            if self.current_page >= self.config_manager.get_page_count():
                self.current_page -= 1
            self._update_page_display()
            self.button_grid.set_page(self.current_page)
            self.statusBar().showMessage("Removed page")

    def _on_rename_page(self):
        """Rename current page via input dialog"""
        page = self.config_manager.get_page(self.current_page)
        if page is None:
            return
        current_name = page.get("name", "")
        new_name, ok = QInputDialog.getText(
            self, "Rename Page", "Page name:", text=current_name
        )
        if ok and new_name.strip():
            self.config_manager.rename_page(self.current_page, new_name.strip())
            self._update_page_display()
            self.statusBar().showMessage(f"Renamed page to: {new_name.strip()}")

    def _on_move_page_left(self):
        """Move current page one position left"""
        if self.current_page > 0:
            if self.config_manager.reorder_page(self.current_page, self.current_page - 1):
                self.current_page -= 1
                self._update_page_display()
                self.button_grid.set_page(self.current_page)
                self.statusBar().showMessage("Moved page left")

    def _on_move_page_right(self):
        """Move current page one position right"""
        if self.current_page < self.config_manager.get_page_count() - 1:
            if self.config_manager.reorder_page(self.current_page, self.current_page + 1):
                self.current_page += 1
                self._update_page_display()
                self.button_grid.set_page(self.current_page)
                self.statusBar().showMessage("Moved page right")

    def _on_file_new(self):
        """New file"""
        reply = QMessageBox.question(
            self, "New Config", "Create new config? (unsaved changes will be lost)"
        )
        if reply == QMessageBox.Yes:
            self.config_manager.new_config()
            self.current_page = 0
            self._update_page_display()
            self.button_grid.set_page(0)
            self.statusBar().showMessage("Created new config")

    def _on_file_open(self):
        """Open JSON file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Config File", "", "JSON Files (*.json)"
        )
        if file_path:
            if self.config_manager.load_json_file(file_path):
                self.current_page = 0
                self._update_page_display()
                self.button_grid.set_page(0)
                self.statusBar().showMessage(f"Loaded: {file_path}")
            else:
                QMessageBox.critical(self, "Error", f"Failed to load: {file_path}")

    def _on_file_save(self):
        """Save JSON file"""
        is_valid, error_msg = self.config_manager.validate()
        if not is_valid:
            QMessageBox.critical(self, "Validation Error", error_msg)
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Config File", "", "JSON Files (*.json)"
        )
        if file_path:
            if self.config_manager.save_json_file(file_path):
                self.statusBar().showMessage(f"Saved: {file_path}")
            else:
                QMessageBox.critical(self, "Error", f"Failed to save: {file_path}")

    def _load_display_mode_settings(self):
        """Load display mode settings from config into UI"""
        config = self.config_manager.config
        self.mode_dropdown.setCurrentIndex(config.get("default_mode", 0))
        self.slideshow_spinbox.setValue(config.get("slideshow_interval_sec", 30))
        self.analog_checkbox.setChecked(config.get("clock_analog", False))

    def _on_display_mode_changed(self):
        """Display mode settings changed in UI"""
        self.config_manager.config["default_mode"] = self.mode_dropdown.currentIndex()
        self.config_manager.config["slideshow_interval_sec"] = self.slideshow_spinbox.value()
        self.config_manager.config["clock_analog"] = self.analog_checkbox.isChecked()

    def _on_deploy_clicked(self):
        """Deploy button clicked"""
        is_valid, error_msg = self.config_manager.validate()
        if not is_valid:
            QMessageBox.critical(self, "Validation Error", error_msg)
            return

        # Show deploy dialog
        deploy_dialog = DeployDialog(self.config_manager, self)
        result = deploy_dialog.exec()
        if result == QDialog.Accepted:
            self.statusBar().showMessage("Config deployed to device")
