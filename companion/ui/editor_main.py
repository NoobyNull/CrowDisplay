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
    QListWidget,
    QLineEdit,
    QToolTip,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QKeySequence, QAction

from companion.config_manager import get_config_manager
from companion.ui.button_editor import ButtonEditor
from companion.ui.deploy_dialog import DeployDialog
from companion.lvgl_symbols import SYMBOL_BY_UTF8

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
]

# Default stat colors by type ID
STAT_DEFAULT_COLORS = {
    0x01: 0x3498DB, 0x02: 0x2ECC71, 0x03: 0xE67E22, 0x04: 0xE74C3C,
    0x05: 0xF1C40F, 0x06: 0x7F8C8D, 0x07: 0x1ABC9C, 0x08: 0x1ABC9C,
    0x09: 0x3498DB, 0x0A: 0xE67E22, 0x0B: 0x9B59B6, 0x0C: 0x7F8C8D,
    0x0D: 0x2ECC71, 0x0E: 0xE74C3C, 0x0F: 0xE67E22, 0x10: 0x7F8C8D,
    0x11: 0xE67E22, 0x12: 0xE74C3C, 0x13: 0x1ABC9C, 0x14: 0x1ABC9C,
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


class StatsHeaderPanel(QGroupBox):
    """Stats Header configuration panel with type dropdown, color picker, and reorder"""

    stats_changed = Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Stats Header", parent)
        self.config_manager = config_manager
        self._updating = False

        layout = QVBoxLayout()

        # Table for stat rows
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Type", "Color", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(1, 70)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(2, 40)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setDragDropMode(QAbstractItemView.InternalMove)
        self.table.setMaximumHeight(200)
        layout.addWidget(self.table)

        # Buttons row
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Stat")
        self.add_btn.clicked.connect(self._on_add_stat)
        self.remove_btn = QPushButton("- Remove")
        self.remove_btn.clicked.connect(self._on_remove_stat)
        self.up_btn = QPushButton("Up")
        self.up_btn.clicked.connect(self._on_move_up)
        self.down_btn = QPushButton("Down")
        self.down_btn.clicked.connect(self._on_move_down)
        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.clicked.connect(self._on_reset_defaults)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        # Live preview bar
        self.preview_label = QLabel("")
        self.preview_label.setMinimumHeight(30)
        self.preview_label.setStyleSheet("background: #0d1b2a; padding: 4px; border-radius: 4px;")
        layout.addWidget(self.preview_label)

        self.setLayout(layout)

    def load_from_config(self):
        """Load stats_header from config into table"""
        self._updating = True
        stats = self.config_manager.config.get("stats_header", DEFAULT_STATS_HEADER)
        self.table.setRowCount(0)
        for stat in stats:
            self._add_row(stat.get("type", 0x01), stat.get("color", 0xFFFFFF))
        self._updating = False
        self._update_preview()

    def _add_row(self, type_id, color):
        """Add a stat row to the table"""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Type dropdown
        combo = QComboBox()
        for name, tid in STAT_TYPE_OPTIONS:
            combo.addItem(name, tid)
        # Set current
        for i, (_, tid) in enumerate(STAT_TYPE_OPTIONS):
            if tid == type_id:
                combo.setCurrentIndex(i)
                break
        combo.currentIndexChanged.connect(self._on_stat_changed)
        self.table.setCellWidget(row, 0, combo)

        # Color button
        color_btn = QPushButton()
        qc = QColor((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
        color_btn.setStyleSheet(f"background-color: {qc.name()}; border: 1px solid #555;")
        color_btn.setFixedSize(50, 24)
        color_btn.setProperty("color_value", color)
        color_btn.clicked.connect(lambda checked, r=row: self._on_color_clicked(r))
        self.table.setCellWidget(row, 1, color_btn)

        # Position indicator (auto from row index)
        pos_item = QTableWidgetItem(str(row))
        pos_item.setFlags(pos_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 2, pos_item)

    def _on_color_clicked(self, row):
        """Color button clicked -- open color picker"""
        color_btn = self.table.cellWidget(row, 1)
        if not color_btn:
            return
        current = color_btn.property("color_value") or 0xFFFFFF
        qc = QColor((current >> 16) & 0xFF, (current >> 8) & 0xFF, current & 0xFF)
        new_color = QColorDialog.getColor(qc, self, "Stat Color")
        if new_color.isValid():
            color_val = (new_color.red() << 16) | (new_color.green() << 8) | new_color.blue()
            color_btn.setStyleSheet(f"background-color: {new_color.name()}; border: 1px solid #555;")
            color_btn.setProperty("color_value", color_val)
            self._on_stat_changed()

    def _on_stat_changed(self):
        """A stat type or color was changed"""
        if self._updating:
            return
        self._save_to_config()
        self._update_preview()
        self.stats_changed.emit()

    def _on_add_stat(self):
        """Add a new stat row"""
        if self.table.rowCount() >= 8:
            return
        # Pick next type not already used
        used_types = set()
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            if combo:
                used_types.add(combo.currentData())
        new_type = 0x01
        for _, tid in STAT_TYPE_OPTIONS:
            if tid not in used_types:
                new_type = tid
                break
        color = STAT_DEFAULT_COLORS.get(new_type, 0xFFFFFF)
        self._add_row(new_type, color)
        self._renumber_positions()
        self._save_to_config()
        self._update_preview()
        self.stats_changed.emit()

    def _on_remove_stat(self):
        """Remove selected stat row"""
        if self.table.rowCount() <= 1:
            return
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._renumber_positions()
            self._save_to_config()
            self._update_preview()
            self.stats_changed.emit()

    def _on_move_up(self):
        """Move selected row up"""
        row = self.table.currentRow()
        if row > 0:
            self._swap_rows(row, row - 1)
            self.table.selectRow(row - 1)
            self._renumber_positions()
            self._save_to_config()
            self._update_preview()
            self.stats_changed.emit()

    def _on_move_down(self):
        """Move selected row down"""
        row = self.table.currentRow()
        if row >= 0 and row < self.table.rowCount() - 1:
            self._swap_rows(row, row + 1)
            self.table.selectRow(row + 1)
            self._renumber_positions()
            self._save_to_config()
            self._update_preview()
            self.stats_changed.emit()

    def _swap_rows(self, row_a, row_b):
        """Swap data between two rows"""
        # Get data from both rows
        combo_a = self.table.cellWidget(row_a, 0)
        combo_b = self.table.cellWidget(row_b, 0)
        color_a = self.table.cellWidget(row_a, 1)
        color_b = self.table.cellWidget(row_b, 1)

        type_a, color_val_a = combo_a.currentData(), color_a.property("color_value")
        type_b, color_val_b = combo_b.currentData(), color_b.property("color_value")

        # Set swapped values
        for i, (_, tid) in enumerate(STAT_TYPE_OPTIONS):
            if tid == type_b:
                combo_a.setCurrentIndex(i)
                break
        for i, (_, tid) in enumerate(STAT_TYPE_OPTIONS):
            if tid == type_a:
                combo_b.setCurrentIndex(i)
                break

        qc_b = QColor((color_val_b >> 16) & 0xFF, (color_val_b >> 8) & 0xFF, color_val_b & 0xFF)
        color_a.setStyleSheet(f"background-color: {qc_b.name()}; border: 1px solid #555;")
        color_a.setProperty("color_value", color_val_b)

        qc_a = QColor((color_val_a >> 16) & 0xFF, (color_val_a >> 8) & 0xFF, color_val_a & 0xFF)
        color_b.setStyleSheet(f"background-color: {qc_a.name()}; border: 1px solid #555;")
        color_b.setProperty("color_value", color_val_a)

    def _on_reset_defaults(self):
        """Reset to default stats header"""
        self._updating = True
        self.table.setRowCount(0)
        for stat in DEFAULT_STATS_HEADER:
            self._add_row(stat["type"], stat["color"])
        self._updating = False
        self._save_to_config()
        self._update_preview()
        self.stats_changed.emit()

    def _renumber_positions(self):
        """Update position column after reorder"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 2)
            if item:
                item.setText(str(row))

    def _save_to_config(self):
        """Save table data back to config"""
        stats_header = []
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            color_btn = self.table.cellWidget(row, 1)
            if combo and color_btn:
                stats_header.append({
                    "type": combo.currentData(),
                    "color": color_btn.property("color_value") or 0xFFFFFF,
                    "position": row,
                })
        self.config_manager.config["stats_header"] = stats_header

    def _update_preview(self):
        """Update the live preview bar"""
        parts = []
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            color_btn = self.table.cellWidget(row, 1)
            if combo and color_btn:
                name = combo.currentText()
                color_val = color_btn.property("color_value") or 0xFFFFFF
                hex_color = f"#{color_val:06X}"
                parts.append(f'<span style="color:{hex_color}">{name}</span>')
        if parts:
            self.preview_label.setText(
                '<span style="font-size:11px;">' + " | ".join(parts) + "</span>"
            )
        else:
            self.preview_label.setText("")


class NotificationsPanel(QGroupBox):
    """Notification forwarding configuration panel"""

    notifications_changed = Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Notifications", parent)
        self.config_manager = config_manager

        layout = QVBoxLayout()

        # Enable checkbox
        self.enabled_checkbox = QCheckBox("Enable notification forwarding")
        self.enabled_checkbox.stateChanged.connect(self._on_changed)
        layout.addWidget(self.enabled_checkbox)

        # Info label
        info_label = QLabel(
            '<span style="color: #888; font-size: 10px;">'
            "Empty list = forward ALL notifications. "
            'Run <code>dbus-monitor --session interface=org.freedesktop.Notifications</code> '
            "to discover app names."
            "</span>"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # App filter list
        self.filter_list = QListWidget()
        self.filter_list.setMaximumHeight(120)
        layout.addWidget(self.filter_list)

        # Add row: line edit + add button
        add_row = QHBoxLayout()
        self.app_name_input = QLineEdit()
        self.app_name_input.setPlaceholderText("e.g., Slack, Discord, Thunderbird, Signal")
        self.app_name_input.returnPressed.connect(self._on_add_app)
        add_row.addWidget(self.app_name_input)

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._on_add_app)
        add_row.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._on_remove_app)
        add_row.addWidget(self.remove_btn)

        layout.addLayout(add_row)
        self.setLayout(layout)

    def load_from_config(self):
        """Load notification settings from config"""
        config = self.config_manager.config
        self.enabled_checkbox.setChecked(config.get("notifications_enabled", False))
        self.filter_list.clear()
        for app in config.get("notification_filter", []):
            self.filter_list.addItem(str(app))

    def _on_add_app(self):
        """Add app name to filter list"""
        text = self.app_name_input.text().strip()
        if not text:
            return
        # Check for duplicates
        for i in range(self.filter_list.count()):
            if self.filter_list.item(i).text() == text:
                return
        self.filter_list.addItem(text)
        self.app_name_input.clear()
        self._save_to_config()
        self.notifications_changed.emit()

    def _on_remove_app(self):
        """Remove selected app from filter list"""
        row = self.filter_list.currentRow()
        if row >= 0:
            self.filter_list.takeItem(row)
            self._save_to_config()
            self.notifications_changed.emit()

    def _on_changed(self):
        """Checkbox toggled"""
        self._save_to_config()
        self.notifications_changed.emit()

    def _save_to_config(self):
        """Save notification settings to config"""
        self.config_manager.config["notifications_enabled"] = self.enabled_checkbox.isChecked()
        apps = []
        for i in range(self.filter_list.count()):
            apps.append(self.filter_list.item(i).text())
        self.config_manager.config["notification_filter"] = apps


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

        # Stats Header panel
        self.stats_panel = StatsHeaderPanel(self.config_manager)
        self.stats_panel.stats_changed.connect(self._on_stats_header_changed)
        right_layout.addWidget(self.stats_panel)
        self.stats_panel.load_from_config()

        # Notifications panel
        self.notifications_panel = NotificationsPanel(self.config_manager)
        self.notifications_panel.notifications_changed.connect(self._on_notifications_changed)
        right_layout.addWidget(self.notifications_panel)
        self.notifications_panel.load_from_config()

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
            self._load_display_mode_settings()
            self.stats_panel.load_from_config()
            self.notifications_panel.load_from_config()
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
                self._load_display_mode_settings()
                self.stats_panel.load_from_config()
                self.notifications_panel.load_from_config()
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

    def _on_stats_header_changed(self):
        """Stats header panel changed"""
        self.statusBar().showMessage("Stats header updated")

    def _on_notifications_changed(self):
        """Notifications panel changed"""
        self.statusBar().showMessage("Notification settings updated")

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
