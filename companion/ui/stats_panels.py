"""
Stats Panels: StatsHeaderPanel and NotificationsPanel for the editor.
"""

import logging

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGroupBox,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QColorDialog,
    QAbstractItemView,
    QListWidget,
    QLineEdit,
)
from PySide6.QtCore import Qt, Signal

from companion.ui.no_scroll_combo import NoScrollComboBox
from companion.ui.editor_constants import (
    STAT_TYPE_OPTIONS,
    STAT_DEFAULT_COLORS,
    DEFAULT_STATS_HEADER,
)
from companion.ui.editor_utils import _int_to_qcolor, _qcolor_to_int

logger = logging.getLogger(__name__)


class StatsHeaderPanel(QGroupBox):
    """Stats Header configuration panel with type dropdown, color picker, and reorder"""

    stats_changed = Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Stats Header", parent)
        self.config_manager = config_manager
        self._updating = False

        layout = QVBoxLayout()

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

        self.preview_label = QLabel("")
        self.preview_label.setMinimumHeight(30)
        self.preview_label.setStyleSheet("background: #0d1b2a; padding: 4px; border-radius: 4px;")
        layout.addWidget(self.preview_label)

        self.setLayout(layout)

    def load_from_config(self):
        self._updating = True
        stats = self.config_manager.config.get("stats_header", DEFAULT_STATS_HEADER)
        self.table.setRowCount(0)
        for stat in stats:
            self._add_row(stat.get("type", 0x01), stat.get("color", 0xFFFFFF))
        self._updating = False
        self._update_preview()

    def _add_row(self, type_id, color):
        row = self.table.rowCount()
        self.table.insertRow(row)

        combo = NoScrollComboBox()
        for name, tid in STAT_TYPE_OPTIONS:
            combo.addItem(name, tid)
        for i, (_, tid) in enumerate(STAT_TYPE_OPTIONS):
            if tid == type_id:
                combo.setCurrentIndex(i)
                break
        combo.currentIndexChanged.connect(self._on_stat_changed)
        self.table.setCellWidget(row, 0, combo)

        color_btn = QPushButton()
        qc = _int_to_qcolor(color)
        color_btn.setStyleSheet(f"background-color: {qc.name()}; border: 1px solid #555;")
        color_btn.setFixedSize(50, 24)
        color_btn.setProperty("color_value", color)
        color_btn.clicked.connect(lambda checked, r=row: self._on_color_clicked(r))
        self.table.setCellWidget(row, 1, color_btn)

        pos_item = QTableWidgetItem(str(row))
        pos_item.setFlags(pos_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 2, pos_item)

    def _on_color_clicked(self, row):
        color_btn = self.table.cellWidget(row, 1)
        if not color_btn:
            return
        current = color_btn.property("color_value") or 0xFFFFFF
        qc = _int_to_qcolor(current)
        new_color = QColorDialog.getColor(qc, self, "Stat Color")
        if new_color.isValid():
            color_val = _qcolor_to_int(new_color)
            color_btn.setStyleSheet(f"background-color: {new_color.name()}; border: 1px solid #555;")
            color_btn.setProperty("color_value", color_val)
            self._on_stat_changed()

    def _on_stat_changed(self):
        if self._updating:
            return
        self._save_to_config()
        self._update_preview()
        self.stats_changed.emit()

    def _on_add_stat(self):
        if self.table.rowCount() >= 8:
            return
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
        row = self.table.currentRow()
        if row > 0:
            self._swap_rows(row, row - 1)
            self.table.selectRow(row - 1)
            self._renumber_positions()
            self._save_to_config()
            self._update_preview()
            self.stats_changed.emit()

    def _on_move_down(self):
        row = self.table.currentRow()
        if row >= 0 and row < self.table.rowCount() - 1:
            self._swap_rows(row, row + 1)
            self.table.selectRow(row + 1)
            self._renumber_positions()
            self._save_to_config()
            self._update_preview()
            self.stats_changed.emit()

    def _swap_rows(self, row_a, row_b):
        combo_a = self.table.cellWidget(row_a, 0)
        combo_b = self.table.cellWidget(row_b, 0)
        color_a = self.table.cellWidget(row_a, 1)
        color_b = self.table.cellWidget(row_b, 1)

        type_a, color_val_a = combo_a.currentData(), color_a.property("color_value")
        type_b, color_val_b = combo_b.currentData(), color_b.property("color_value")

        for i, (_, tid) in enumerate(STAT_TYPE_OPTIONS):
            if tid == type_b:
                combo_a.setCurrentIndex(i)
                break
        for i, (_, tid) in enumerate(STAT_TYPE_OPTIONS):
            if tid == type_a:
                combo_b.setCurrentIndex(i)
                break

        qc_b = _int_to_qcolor(color_val_b)
        color_a.setStyleSheet(f"background-color: {qc_b.name()}; border: 1px solid #555;")
        color_a.setProperty("color_value", color_val_b)

        qc_a = _int_to_qcolor(color_val_a)
        color_b.setStyleSheet(f"background-color: {qc_a.name()}; border: 1px solid #555;")
        color_b.setProperty("color_value", color_val_a)

    def _on_reset_defaults(self):
        self._updating = True
        self.table.setRowCount(0)
        for stat in DEFAULT_STATS_HEADER:
            self._add_row(stat["type"], stat["color"])
        self._updating = False
        self._save_to_config()
        self._update_preview()
        self.stats_changed.emit()

    def _renumber_positions(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 2)
            if item:
                item.setText(str(row))

    def _save_to_config(self):
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


# ============================================================
# Notifications Panel (unchanged)

# ============================================================

class NotificationsPanel(QGroupBox):
    """Notification forwarding configuration panel"""

    notifications_changed = Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Notifications", parent)
        self.config_manager = config_manager

        layout = QVBoxLayout()

        self.enabled_checkbox = QCheckBox("Enable notification forwarding")
        self.enabled_checkbox.stateChanged.connect(self._on_changed)
        layout.addWidget(self.enabled_checkbox)

        info_label = QLabel(
            '<span style="color: #888; font-size: 10px;">'
            "Empty list = forward ALL notifications. "
            'Run <code>dbus-monitor --session interface=org.freedesktop.Notifications</code> '
            "to discover app names."
            "</span>"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.filter_list = QListWidget()
        self.filter_list.setMaximumHeight(120)
        layout.addWidget(self.filter_list)

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
        config = self.config_manager.config
        self.enabled_checkbox.setChecked(config.get("notifications_enabled", False))
        self.filter_list.clear()
        for app in config.get("notification_filter", []):
            self.filter_list.addItem(str(app))

    def _on_add_app(self):
        text = self.app_name_input.text().strip()
        if not text:
            return
        for i in range(self.filter_list.count()):
            if self.filter_list.item(i).text() == text:
                return
        self.filter_list.addItem(text)
        self.app_name_input.clear()
        self._save_to_config()
        self.notifications_changed.emit()

    def _on_remove_app(self):
        row = self.filter_list.currentRow()
        if row >= 0:
            self.filter_list.takeItem(row)
            self._save_to_config()
            self.notifications_changed.emit()

    def _on_changed(self):
        self._save_to_config()
        self.notifications_changed.emit()

    def _save_to_config(self):
        self.config_manager.config["notifications_enabled"] = self.enabled_checkbox.isChecked()
        apps = []
        for i in range(self.filter_list.count()):
            apps.append(self.filter_list.item(i).text())
        self.config_manager.config["notification_filter"] = apps


from companion.ui.canvas_items import CanvasWidgetItem, ResizeHandle
from companion.ui.canvas_scene import CanvasScene, CanvasView, ItemsPalette


# Classes CanvasWidgetItem, ResizeHandle, CanvasScene, CanvasView, ItemsPalette
# have been extracted to companion.ui.canvas_items and companion.ui.canvas_scene


# ============================================================
# Properties Panel -- widget property editor (replaces ButtonEditor)
