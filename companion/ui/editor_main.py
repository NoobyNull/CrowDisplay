"""
Editor Main Window: WYSIWYG Canvas Editor with widget palette and properties panel

Displays 800x480 canvas in center, items palette on left, properties panel on right.
Drag widgets from palette to canvas, move/resize with snap-to-grid.
Page toolbar for page management at bottom. Deploy button sends config to device.
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
    QListWidgetItem,
    QLineEdit,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsRectItem,
    QGraphicsItem,
    QSplitter,
    QTabWidget,
    QMenu,
)
from PySide6.QtCore import Qt, Signal, QSize, QRectF, QPointF, QMimeData, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QPen,
    QBrush,
    QPainter,
    QPixmap,
    QDrag,
)

from companion.config_manager import (
    get_config_manager,
    WIDGET_HOTKEY_BUTTON,
    WIDGET_STAT_MONITOR,
    WIDGET_STATUS_BAR,
    WIDGET_CLOCK,
    WIDGET_TEXT_LABEL,
    WIDGET_SEPARATOR,
    WIDGET_PAGE_NAV,
    WIDGET_TYPE_NAMES,
    WIDGET_DEFAULT_SIZES,
    WIDGET_TYPE_MAX,
    ACTION_HOTKEY,
    ACTION_MEDIA_KEY,
    ACTION_LAUNCH_APP,
    ACTION_SHELL_CMD,
    ACTION_OPEN_URL,
    MOD_NONE,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    SNAP_GRID,
    WIDGET_MIN_W,
    WIDGET_MIN_H,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_PATH,
    DEFAULT_ICONS_DIR,
    make_default_widget,
)
from companion.ui.icon_picker import IconPicker
from companion.ui.keyboard_recorder import KeyboardRecorder
from companion.ui.deploy_dialog import DeployDialog
from companion.ui.no_scroll_combo import NoScrollComboBox
from companion.lvgl_symbols import SYMBOL_BY_UTF8
import os
import threading
from pathlib import Path

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

# Reverse lookup: stat type ID → display name
STAT_TYPE_NAMES = {tid: name for name, tid in STAT_TYPE_OPTIONS}

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

# Media key options: (display_name, consumer_code)
MEDIA_KEY_OPTIONS = [
    ("Play/Pause", 0xCD),
    ("Next Track", 0xB5),
    ("Previous Track", 0xB6),
    ("Stop", 0xB7),
    ("Volume Up", 0xE9),
    ("Volume Down", 0xEA),
    ("Mute", 0xE2),
    ("Browser Home", 0x0223),
    ("Browser Back", 0x0224),
]

# Widget palette icons (Unicode for display in list)
WIDGET_PALETTE_ICONS = {
    WIDGET_HOTKEY_BUTTON: "\u2328",  # keyboard
    WIDGET_STAT_MONITOR: "\u2261",   # bars
    WIDGET_STATUS_BAR: "\u2501",     # horizontal line
    WIDGET_CLOCK: "\u23F0",          # clock
    WIDGET_TEXT_LABEL: "\u0054",     # T
    WIDGET_SEPARATOR: "\u2500",      # line
    WIDGET_PAGE_NAV: "\u2022\u2022\u2022",  # dots
}


def _int_to_qcolor(color_val):
    """Convert 0xRRGGBB int to QColor."""
    return QColor((color_val >> 16) & 0xFF, (color_val >> 8) & 0xFF, color_val & 0xFF)


def _qcolor_to_int(qcolor):
    """Convert QColor to 0xRRGGBB int."""
    return (qcolor.red() << 16) | (qcolor.green() << 8) | qcolor.blue()


# ============================================================
# Stats Header Panel (unchanged from v1, still used for global stats config)
# ============================================================

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


# ============================================================
# Canvas Widget Item -- represents a widget on the 800x480 canvas
# ============================================================

class CanvasWidgetItem(QGraphicsRectItem):
    """A widget item on the canvas. Movable, selectable, snaps to grid."""

    def __init__(self, widget_dict, widget_idx):
        self._w = max(WIDGET_MIN_W, widget_dict.get("width", 180))
        self._h = max(WIDGET_MIN_H, widget_dict.get("height", 100))
        super().__init__(0, 0, self._w, self._h)

        self.widget_dict = widget_dict
        self.widget_idx = widget_idx
        self.widget_id = widget_dict.get("widget_id", "")
        self._suppress_notify = True
        self._icon_pixmap = None  # QPixmap cache for icon image

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        x = widget_dict.get("x", 0)
        y = widget_dict.get("y", 0)
        self.setPos(x, y)
        self._suppress_notify = False

        self._update_appearance()

    def set_size(self, w, h):
        """Set widget size (called during resize)."""
        w = max(WIDGET_MIN_W, int(w))
        h = max(WIDGET_MIN_H, int(h))
        self._w = w
        self._h = h
        self.setRect(0, 0, w, h)
        self._update_appearance()

    def set_icon_pixmap(self, pixmap):
        """Set a QPixmap to render as the button icon image."""
        self._icon_pixmap = pixmap
        self.update()

    def update_from_dict(self, widget_dict):
        """Update appearance from widget dict (called when properties change)."""
        self._suppress_notify = True
        self.widget_dict = widget_dict
        x = widget_dict.get("x", 0)
        y = widget_dict.get("y", 0)
        w = max(WIDGET_MIN_W, widget_dict.get("width", 180))
        h = max(WIDGET_MIN_H, widget_dict.get("height", 100))
        self.setPos(x, y)
        self._w = w
        self._h = h
        self.setRect(0, 0, w, h)
        self._update_appearance()
        self._suppress_notify = False

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # Snap to grid and clamp to display bounds
            x = round(value.x() / SNAP_GRID) * SNAP_GRID
            y = round(value.y() / SNAP_GRID) * SNAP_GRID
            x = max(0, min(DISPLAY_WIDTH - self._w, x))
            y = max(0, min(DISPLAY_HEIGHT - self._h, y))
            new_pos = QPointF(x, y)

            # Multi-select group move: apply the same delta to other selected items
            if not self._suppress_notify and self.isSelected():
                dx = new_pos.x() - self.pos().x()
                dy = new_pos.y() - self.pos().y()
                if (dx != 0 or dy != 0) and self.scene():
                    for other in self.scene().selectedItems():
                        if other is not self and isinstance(other, CanvasWidgetItem):
                            ox = other.pos().x() + dx
                            oy = other.pos().y() + dy
                            ox = max(0, min(DISPLAY_WIDTH - other._w, round(ox / SNAP_GRID) * SNAP_GRID))
                            oy = max(0, min(DISPLAY_HEIGHT - other._h, round(oy / SNAP_GRID) * SNAP_GRID))
                            other._suppress_notify = True
                            other.setPos(ox, oy)
                            other._suppress_notify = False
                            if hasattr(self.scene(), "on_widget_moved"):
                                self.scene().on_widget_moved(other)

            return new_pos
        if change == QGraphicsItem.ItemPositionHasChanged and not self._suppress_notify:
            scene = self.scene()
            if scene and hasattr(scene, "on_widget_moved"):
                scene.on_widget_moved(self)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            scene = self.scene()
            if scene and hasattr(scene, "on_selection_changed"):
                scene.on_selection_changed()
        return super().itemChange(change, value)

    def _update_appearance(self):
        """Update pen/brush based on widget type."""
        wtype = self.widget_dict.get("widget_type", WIDGET_HOTKEY_BUTTON)
        color = self.widget_dict.get("color", 0xFFFFFF)
        bg_color = self.widget_dict.get("bg_color", 0)
        qcolor = _int_to_qcolor(color)

        if wtype == WIDGET_HOTKEY_BUTTON:
            if bg_color:
                bg_qcolor = _int_to_qcolor(bg_color)
                self.setBrush(QBrush(bg_qcolor))
                self.setPen(QPen(bg_qcolor.darker(130), 2))
            else:
                self.setBrush(QBrush(QColor(0, 0, 0, 0)))
                self.setPen(QPen(QColor("#555"), 1, Qt.DashLine))
        elif wtype == WIDGET_STATUS_BAR:
            bg = _int_to_qcolor(bg_color) if bg_color else QColor("#16213e")
            self.setBrush(QBrush(bg))
            self.setPen(QPen(bg.lighter(130), 1))
        elif wtype == WIDGET_STAT_MONITOR:
            self.setBrush(QBrush(QColor("#1a1f2e")))
            self.setPen(QPen(qcolor, 2))
        elif wtype == WIDGET_CLOCK:
            self.setBrush(QBrush(QColor("#0d1117")))
            self.setPen(QPen(qcolor, 2))
        elif wtype == WIDGET_TEXT_LABEL:
            self.setBrush(QBrush(QColor(0, 0, 0, 0)))
            self.setPen(QPen(QColor("#333"), 1, Qt.DashLine))
        elif wtype == WIDGET_SEPARATOR:
            self.setBrush(QBrush(qcolor))
            self.setPen(QPen(qcolor, 1))
        elif wtype == WIDGET_PAGE_NAV:
            self.setBrush(QBrush(QColor(0, 0, 0, 40)))
            self.setPen(QPen(QColor("#555"), 1, Qt.DashLine))
        else:
            self.setBrush(QBrush(QColor("#333")))
            self.setPen(QPen(QColor("#666"), 1))

    def paint(self, painter, option, widget=None):
        # Draw base rectangle
        super().paint(painter, option, widget)

        wtype = self.widget_dict.get("widget_type", WIDGET_HOTKEY_BUTTON)
        rect = self.rect()
        color = self.widget_dict.get("color", 0xFFFFFF)
        qcolor = _int_to_qcolor(color)

        if wtype == WIDGET_HOTKEY_BUTTON:
            self._paint_hotkey_button(painter, rect, qcolor)
        elif wtype == WIDGET_STAT_MONITOR:
            self._paint_stat_monitor(painter, rect, qcolor)
        elif wtype == WIDGET_STATUS_BAR:
            self._paint_status_bar(painter, rect, qcolor)
        elif wtype == WIDGET_CLOCK:
            self._paint_clock(painter, rect, qcolor)
        elif wtype == WIDGET_TEXT_LABEL:
            self._paint_text_label(painter, rect, qcolor)
        elif wtype == WIDGET_SEPARATOR:
            self._paint_separator(painter, rect, qcolor)
        elif wtype == WIDGET_PAGE_NAV:
            self._paint_page_nav(painter, rect, qcolor)

        # Selection highlight
        if self.isSelected():
            painter.setPen(QPen(QColor("#FFD700"), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect.adjusted(-1, -1, 1, 1))

        # Overlap warning: red outline if colliding with another widget
        if self.scene():
            colliders = [
                c for c in self.collidingItems()
                if isinstance(c, CanvasWidgetItem)
            ]
            if colliders:
                painter.setPen(QPen(QColor("#FF4444"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))

    def _paint_hotkey_button(self, painter, rect, qcolor):
        text_color = qcolor  # color field is now the text/foreground color

        label = self.widget_dict.get("label", "")

        # If we have an icon pixmap (from image picker), draw it
        if self._icon_pixmap and not self._icon_pixmap.isNull():
            # Scale pixmap to fit ~60% width, ~50% height area
            icon_w = max(16, int(rect.width() * 0.6))
            icon_h = max(16, int(rect.height() * 0.5))
            scaled = self._icon_pixmap.scaled(
                icon_w, icon_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            if label:
                # Image on top, label below
                img_x = rect.center().x() - scaled.width() / 2
                img_y = rect.top() + 4
                painter.drawPixmap(int(img_x), int(img_y), scaled)
                painter.setPen(text_color)
                painter.setFont(QFont("Arial", 8))
                label_rect = QRectF(rect.left(), img_y + scaled.height() + 2,
                                    rect.width(), rect.bottom() - (img_y + scaled.height() + 2))
                painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, label)
            else:
                # Center the image
                img_x = rect.center().x() - scaled.width() / 2
                img_y = rect.center().y() - scaled.height() / 2
                painter.drawPixmap(int(img_x), int(img_y), scaled)
            return

        # Fall back to symbol icon
        icon = self.widget_dict.get("icon", "")
        icon_display = ""
        if icon:
            icon_bytes = icon.encode("utf-8")
            if icon_bytes in SYMBOL_BY_UTF8:
                icon_display = SYMBOL_BY_UTF8[icon_bytes][0]
            else:
                icon_display = "?"

        painter.setPen(text_color)
        if icon_display and label:
            painter.setFont(QFont("Arial", 9))
            painter.drawText(rect.adjusted(4, 2, -4, -rect.height() / 2), Qt.AlignCenter, icon_display)
            painter.setFont(QFont("Arial", 8))
            painter.drawText(rect.adjusted(4, rect.height() / 2 - 4, -4, -2), Qt.AlignCenter, label)
        elif label:
            painter.setFont(QFont("Arial", 9))
            painter.drawText(rect, Qt.AlignCenter, label)
        elif icon_display:
            painter.setFont(QFont("Arial", 11))
            painter.drawText(rect, Qt.AlignCenter, icon_display)

    def _paint_stat_monitor(self, painter, rect, qcolor):
        label = self.widget_dict.get("label", "Stat")
        painter.setPen(qcolor)
        painter.setFont(QFont("Arial", 8))
        painter.drawText(rect.adjusted(4, 2, -4, -rect.height() / 2), Qt.AlignLeft | Qt.AlignVCenter, label)
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(rect.adjusted(4, rect.height() / 2, -4, -2), Qt.AlignLeft | Qt.AlignVCenter, "--%")

    def _paint_status_bar(self, painter, rect, qcolor):
        painter.setPen(qcolor)
        painter.setFont(QFont("Arial", 9))
        left_x = rect.left() + 8
        # Left side: page label
        label = self.widget_dict.get("label", "Hotkeys")
        painter.drawText(QRectF(left_x, rect.top(), 120, rect.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, label)
        # Right side: status items (right-aligned)
        right_parts = []
        if self.widget_dict.get("show_wifi", True):
            right_parts.append("WiFi --dBm")
        if self.widget_dict.get("show_battery", True):
            right_parts.append("BAT --%")
        if self.widget_dict.get("show_time", True):
            right_parts.append("00:00")
        if right_parts:
            status_text = "  |  ".join(right_parts)
            painter.drawText(rect.adjusted(0, 0, -8, 0),
                             Qt.AlignRight | Qt.AlignVCenter, status_text)

    def _paint_clock(self, painter, rect, qcolor):
        painter.setPen(qcolor)
        if self.widget_dict.get("clock_analog", False):
            # Draw circle for analog clock
            cx, cy = rect.center().x(), rect.center().y()
            r = min(rect.width(), rect.height()) / 2 - 4
            painter.drawEllipse(QPointF(cx, cy), r, r)
            painter.setFont(QFont("Arial", 7))
            painter.drawText(rect, Qt.AlignCenter, "12")
        else:
            painter.setFont(QFont("Arial", 14, QFont.Bold))
            painter.drawText(rect, Qt.AlignCenter, "00:00")

    def _paint_text_label(self, painter, rect, qcolor):
        label = self.widget_dict.get("label", "Label")
        font_size = self.widget_dict.get("font_size", 16)
        text_align = self.widget_dict.get("text_align", 1)
        qt_align = {0: Qt.AlignLeft, 1: Qt.AlignHCenter, 2: Qt.AlignRight}.get(text_align, Qt.AlignHCenter)
        painter.setPen(qcolor)
        painter.setFont(QFont("Arial", max(7, font_size // 2)))
        painter.drawText(rect.adjusted(4, 0, -4, 0), qt_align | Qt.AlignVCenter, label)

    def _paint_separator(self, painter, rect, qcolor):
        thickness = self.widget_dict.get("thickness", 2)
        painter.setPen(QPen(qcolor, max(1, thickness)))
        if self.widget_dict.get("separator_vertical", False):
            cx = rect.center().x()
            painter.drawLine(int(cx), int(rect.top() + 2), int(cx), int(rect.bottom() - 2))
        else:
            cy = rect.center().y()
            painter.drawLine(int(rect.left() + 2), int(cy), int(rect.right() - 2), int(cy))

    def _paint_page_nav(self, painter, rect, qcolor):
        painter.setPen(Qt.NoPen)
        dot_r = 4
        spacing = 14
        # Read actual page count from scene
        page_count = 1
        if self.scene() and hasattr(self.scene(), 'page_count'):
            page_count = max(1, self.scene().page_count)
        cx = rect.center().x()
        cy = rect.center().y()
        total_w = (page_count - 1) * spacing
        start_x = cx - total_w / 2
        for i in range(page_count):
            x = start_x + i * spacing
            if i == 0:
                painter.setBrush(QBrush(qcolor))
            else:
                painter.setBrush(QBrush(QColor("#555")))
            painter.drawEllipse(QPointF(x, cy), dot_r, dot_r)


# ============================================================
# Resize Handle -- 8 handles for resizing selected widget
# ============================================================

class ResizeHandle(QGraphicsRectItem):
    """A small square handle for resizing a CanvasWidgetItem."""

    HANDLE_SIZE = 8
    TL, T, TR, L, R, BL, B, BR = range(8)

    CURSORS = {
        0: Qt.SizeFDiagCursor,  # TL
        1: Qt.SizeVerCursor,    # T
        2: Qt.SizeBDiagCursor,  # TR
        3: Qt.SizeHorCursor,    # L
        4: Qt.SizeHorCursor,    # R
        5: Qt.SizeBDiagCursor,  # BL
        6: Qt.SizeVerCursor,    # B
        7: Qt.SizeFDiagCursor,  # BR
    }

    def __init__(self, handle_pos, tracked_item):
        s = self.HANDLE_SIZE
        super().__init__(-s / 2, -s / 2, s, s)
        self.handle_pos = handle_pos
        self.tracked_item = tracked_item
        self.setBrush(QBrush(QColor("#FFD700")))
        self.setPen(QPen(QColor("#B8860B"), 1))
        self.setZValue(1000)
        self.setCursor(self.CURSORS.get(handle_pos, Qt.ArrowCursor))
        self.setAcceptHoverEvents(True)
        self._dragging = False
        self._drag_start = None
        self._start_rect = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.scenePos()
            item = self.tracked_item
            self._start_rect = QRectF(
                item.pos().x(), item.pos().y(), item._w, item._h
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging or self._start_rect is None:
            return

        delta = event.scenePos() - self._drag_start
        r = QRectF(self._start_rect)

        if self.handle_pos in (self.TL, self.L, self.BL):
            r.setLeft(r.left() + delta.x())
        if self.handle_pos in (self.TR, self.R, self.BR):
            r.setRight(r.right() + delta.x())
        if self.handle_pos in (self.TL, self.T, self.TR):
            r.setTop(r.top() + delta.y())
        if self.handle_pos in (self.BL, self.B, self.BR):
            r.setBottom(r.bottom() + delta.y())

        # Snap to grid
        x = round(r.x() / SNAP_GRID) * SNAP_GRID
        y = round(r.y() / SNAP_GRID) * SNAP_GRID
        w = round(r.width() / SNAP_GRID) * SNAP_GRID
        h = round(r.height() / SNAP_GRID) * SNAP_GRID

        # Enforce minimum size
        if w < WIDGET_MIN_W:
            if self.handle_pos in (self.TL, self.L, self.BL):
                x = self._start_rect.right() - WIDGET_MIN_W
            w = WIDGET_MIN_W
        if h < WIDGET_MIN_H:
            if self.handle_pos in (self.TL, self.T, self.TR):
                y = self._start_rect.bottom() - WIDGET_MIN_H
            h = WIDGET_MIN_H

        # Clamp to display
        x = max(0, x)
        y = max(0, y)
        if x + w > DISPLAY_WIDTH:
            w = DISPLAY_WIDTH - x
        if y + h > DISPLAY_HEIGHT:
            h = DISPLAY_HEIGHT - y

        self.tracked_item._suppress_notify = True
        self.tracked_item.setPos(x, y)
        self.tracked_item.set_size(w, h)
        self.tracked_item._suppress_notify = False

        scene = self.scene()
        if scene and hasattr(scene, "update_handles"):
            scene.update_handles()

        event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            scene = self.scene()
            if scene and hasattr(scene, "on_widget_resized"):
                scene.on_widget_resized(self.tracked_item)
            event.accept()


# ============================================================
# Canvas Scene -- 800x480 with grid, drag-drop, selection management
# ============================================================

class CanvasScene(QGraphicsScene):
    """The 800x480 display canvas with grid lines and widget management."""

    widget_selected = Signal(str)    # widget_id
    widget_deselected = Signal()
    widget_geometry_changed = Signal(str, int, int, int, int)  # widget_id, x, y, w, h
    widget_dropped = Signal(int, int, int)  # type, x, y

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        self._handles = []
        self._tracked_item = None
        self._clipboard = []  # list of widget dicts for copy/paste
        self._multi_move_origin = None  # for group drag
        self.page_count = 1  # updated by EditorMainWindow when pages change

    def drawBackground(self, painter, rect):
        # Fill everything outside the canvas dark
        painter.fillRect(rect, QColor("#06090f"))
        # Fill the canvas area
        canvas = QRectF(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        painter.fillRect(canvas, QColor("#0D1117"))
        # Subtle grid lines (only inside canvas)
        pen = QPen(QColor("#1a1f2e"), 0.5)
        painter.setPen(pen)
        for x in range(0, DISPLAY_WIDTH + 1, SNAP_GRID):
            painter.drawLine(x, 0, x, DISPLAY_HEIGHT)
        for y in range(0, DISPLAY_HEIGHT + 1, SNAP_GRID):
            painter.drawLine(0, y, DISPLAY_WIDTH, y)
        # Canvas border
        painter.setPen(QPen(QColor("#30363d"), 2))
        painter.drawRect(canvas)

    def on_selection_changed(self):
        """Called when item selection changes."""
        selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]
        if len(selected) == 1:
            item = selected[0]
            self._show_handles(item)
            self.widget_selected.emit(item.widget_id)
        else:
            self._clear_handles()
            self.widget_deselected.emit()

    def on_widget_moved(self, item):
        """Called when a widget item has been moved."""
        x, y = int(item.pos().x()), int(item.pos().y())
        self.widget_geometry_changed.emit(item.widget_id, x, y, item._w, item._h)
        self.update_handles()

    def on_widget_resized(self, item):
        """Called when a widget item has been resized (handle released)."""
        x, y = int(item.pos().x()), int(item.pos().y())
        self.widget_geometry_changed.emit(item.widget_id, x, y, item._w, item._h)

    def _show_handles(self, item):
        """Show resize handles around the given item."""
        self._clear_handles()
        self._tracked_item = item
        for hp in range(8):
            handle = ResizeHandle(hp, item)
            self.addItem(handle)
            self._handles.append(handle)
        self.update_handles()

    def _clear_handles(self):
        """Remove all resize handles from scene."""
        for handle in self._handles:
            self.removeItem(handle)
        self._handles.clear()
        self._tracked_item = None

    def update_handles(self):
        """Reposition handles around tracked item."""
        if not self._tracked_item or not self._handles:
            return
        item = self._tracked_item
        x, y = item.pos().x(), item.pos().y()
        w, h = item._w, item._h
        positions = [
            (x, y),                    # TL
            (x + w / 2, y),            # T
            (x + w, y),                # TR
            (x, y + h / 2),            # L
            (x + w, y + h / 2),        # R
            (x, y + h),                # BL
            (x + w / 2, y + h),        # B
            (x + w, y + h),            # BR
        ]
        for handle, pos in zip(self._handles, positions):
            handle.setPos(pos[0], pos[1])

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-widget-type"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-widget-type"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-widget-type"):
            data = event.mimeData().data("application/x-widget-type")
            widget_type = int(bytes(data).decode())
            pos = event.scenePos()
            x = round(pos.x() / SNAP_GRID) * SNAP_GRID
            y = round(pos.y() / SNAP_GRID) * SNAP_GRID
            # Clamp to display
            dw, dh = WIDGET_DEFAULT_SIZES.get(widget_type, (180, 100))
            x = max(0, min(DISPLAY_WIDTH - dw, x))
            y = max(0, min(DISPLAY_HEIGHT - dh, y))
            self.widget_dropped.emit(widget_type, int(x), int(y))
            event.acceptProposedAction()

    def contextMenuEvent(self, event):
        """Right-click context menu for canvas items."""
        items_at = [i for i in self.items(event.scenePos()) if isinstance(i, CanvasWidgetItem)]
        selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]

        # If right-clicked on an unselected item, select it
        if items_at and items_at[0] not in selected:
            self.clearSelection()
            items_at[0].setSelected(True)
            selected = [items_at[0]]

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: #1c2128; color: #e0e0e0; border: 1px solid #333; }"
            "QMenu::item:selected { background: #2d333b; }"
            "QMenu::separator { background: #333; height: 1px; margin: 4px 8px; }"
        )

        if selected:
            count = len(selected)
            label = f"{count} widgets" if count > 1 else "widget"

            # Copy
            copy_action = menu.addAction(f"Copy {label}")
            copy_action.setShortcut(QKeySequence.Copy)

            # Duplicate
            dup_action = menu.addAction(f"Duplicate {label}")
            dup_action.setShortcut(QKeySequence("Ctrl+D"))

            menu.addSeparator()

            # Move to page submenu
            move_menu = menu.addMenu("Move to Page...")
            page_actions = []
            if hasattr(self, "_get_page_list"):
                for page_idx, page_name in self._get_page_list():
                    if page_idx != self._current_page:
                        pa = move_menu.addAction(page_name)
                        pa.setData(page_idx)
                        page_actions.append(pa)
            if not page_actions:
                move_menu.setEnabled(False)

            menu.addSeparator()

            # Z-order
            front_action = menu.addAction("Bring to Front")
            back_action = menu.addAction("Send to Back")

            menu.addSeparator()

            # Delete
            del_action = menu.addAction(f"Delete {label}")
            del_action.setShortcut(QKeySequence.Delete)
        else:
            copy_action = dup_action = front_action = back_action = del_action = None
            page_actions = []

        # Paste (always available if clipboard has content)
        menu.addSeparator()
        paste_action = menu.addAction("Paste")
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.setEnabled(bool(self._clipboard))

        # Execute
        action = menu.exec(event.screenPos())
        if action is None:
            return

        if action == copy_action:
            self._copy_selected(selected)
        elif action == del_action:
            self._delete_selected(selected)
        elif action == dup_action:
            self._copy_selected(selected)
            self._paste_at(event.scenePos())
        elif action == paste_action:
            self._paste_at(event.scenePos())
        elif action == front_action:
            max_z = max((i.zValue() for i in self.items() if isinstance(i, CanvasWidgetItem)), default=0)
            for item in selected:
                item.setZValue(max_z + 1)
        elif action == back_action:
            min_z = min((i.zValue() for i in self.items() if isinstance(i, CanvasWidgetItem)), default=0)
            for item in selected:
                item.setZValue(min_z - 1)
        elif action in page_actions:
            target_page = action.data()
            if hasattr(self, "_on_move_to_page"):
                self._on_move_to_page([i.widget_id for i in selected], target_page)

    def _copy_selected(self, selected):
        """Copy selected widget dicts to clipboard."""
        import copy
        self._clipboard = []
        for item in selected:
            d = copy.deepcopy(item.widget_dict)
            self._clipboard.append(d)

    def _paste_at(self, scene_pos):
        """Paste clipboard widgets near the given position."""
        if not self._clipboard or not hasattr(self, "_on_paste_callback"):
            return
        import copy
        offset = 20
        widgets = []
        for d in self._clipboard:
            nd = copy.deepcopy(d)
            nd["x"] = min(DISPLAY_WIDTH - nd.get("width", 100), max(0, nd["x"] + offset))
            nd["y"] = min(DISPLAY_HEIGHT - nd.get("height", 100), max(0, nd["y"] + offset))
            widgets.append(nd)
        self._on_paste_callback(widgets)

    def _delete_selected(self, selected):
        """Delete selected items."""
        for item in selected:
            self.removeItem(item)
        self._clear_handles()
        if hasattr(self, "_on_delete_callback"):
            self._on_delete_callback([item.widget_id for item in selected])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]
            if selected:
                self._delete_selected(selected)
        elif event.matches(QKeySequence.Copy):
            selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]
            if selected:
                self._copy_selected(selected)
        elif event.matches(QKeySequence.Paste):
            # Paste at center of view
            views = self.views()
            if views:
                center = views[0].mapToScene(views[0].viewport().rect().center())
                self._paste_at(center)
        elif event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
            selected = [i for i in self.selectedItems() if isinstance(i, CanvasWidgetItem)]
            if selected:
                self._copy_selected(selected)
                center = selected[0].pos()
                self._paste_at(QPointF(center.x(), center.y()))
        else:
            super().keyPressEvent(event)


# ============================================================
# Canvas View -- scaled view with aspect ratio
# ============================================================

class CanvasView(QGraphicsView):
    """Scaled view of the 800x480 canvas, always fits to available space."""

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setAcceptDrops(True)
        self.setMinimumSize(400, 250)
        # Disable scrollbars -- canvas must always fit in view
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("background: #0a0e14; border: 1px solid #333;")

    def _fit(self):
        # Small margin so the canvas border is visible
        margin = 10
        r = self.scene().sceneRect().adjusted(-margin, -margin, margin, margin)
        self.fitInView(r, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit)  # defer so layout is settled


# ============================================================
# Items Palette -- drag source for widget types
# ============================================================

class ItemsPalette(QListWidget):
    """Left sidebar with draggable widget types."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setMaximumWidth(150)
        self.setMinimumWidth(120)
        self.setIconSize(QSize(20, 20))
        self.setStyleSheet(
            "QListWidget { background: #161b22; border: 1px solid #333; }"
            "QListWidget::item { padding: 8px 4px; color: #e0e0e0; }"
            "QListWidget::item:hover { background: #21262d; }"
        )

        for wtype in range(WIDGET_TYPE_MAX + 1):
            name = WIDGET_TYPE_NAMES.get(wtype, f"Type {wtype}")
            icon_char = WIDGET_PALETTE_ICONS.get(wtype, "?")
            item = QListWidgetItem(f"{icon_char}  {name}")
            item.setData(Qt.UserRole, wtype)
            self.addItem(item)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        wtype = item.data(Qt.UserRole)
        mime.setData("application/x-widget-type", str(wtype).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)


# ============================================================
# Properties Panel -- widget property editor (replaces ButtonEditor)
# ============================================================

class PropertiesPanel(QScrollArea):
    """Right sidebar for editing selected widget properties."""

    widget_updated = Signal(str, dict)  # widget_id, updated widget_dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)
        self._updating = False
        self._widget_idx = -1
        self._widget_id = ""
        self._widget_dict = None

        container = QWidget()
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(4, 4, 4, 4)

        # Type label
        self.type_label = QLabel("No widget selected")
        self.type_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #FFD700;")
        self.main_layout.addWidget(self.type_label)

        # Position group
        pos_group = QGroupBox("Position && Size")
        pos_layout = QGridLayout()
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, DISPLAY_WIDTH)
        self.x_spin.setSingleStep(SNAP_GRID)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, DISPLAY_HEIGHT)
        self.y_spin.setSingleStep(SNAP_GRID)
        self.w_spin = QSpinBox()
        self.w_spin.setRange(WIDGET_MIN_W, DISPLAY_WIDTH)
        self.w_spin.setSingleStep(SNAP_GRID)
        self.h_spin = QSpinBox()
        self.h_spin.setRange(WIDGET_MIN_H, DISPLAY_HEIGHT)
        self.h_spin.setSingleStep(SNAP_GRID)
        pos_layout.addWidget(QLabel("X:"), 0, 0)
        pos_layout.addWidget(self.x_spin, 0, 1)
        pos_layout.addWidget(QLabel("Y:"), 0, 2)
        pos_layout.addWidget(self.y_spin, 0, 3)
        pos_layout.addWidget(QLabel("W:"), 1, 0)
        pos_layout.addWidget(self.w_spin, 1, 1)
        pos_layout.addWidget(QLabel("H:"), 1, 2)
        pos_layout.addWidget(self.h_spin, 1, 3)
        pos_group.setLayout(pos_layout)
        self.main_layout.addWidget(pos_group)

        for spin in (self.x_spin, self.y_spin, self.w_spin, self.h_spin):
            spin.valueChanged.connect(self._on_position_changed)
            spin.setFocusPolicy(Qt.StrongFocus)

        # Common group: label + color
        common_group = QGroupBox("Common")
        common_layout = QVBoxLayout()

        common_layout.addWidget(QLabel("Label:"))
        self.label_input = QLineEdit()
        self.label_input.setMaxLength(32)
        self.label_input.textChanged.connect(self._on_property_changed)
        common_layout.addWidget(self.label_input)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color:"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(40, 24)
        self.color_btn.clicked.connect(self._on_color_clicked)
        color_row.addWidget(self.color_btn)
        color_row.addWidget(QLabel("BG:"))
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(40, 24)
        self.bg_color_btn.clicked.connect(self._on_bg_color_clicked)
        color_row.addWidget(self.bg_color_btn)
        self.bg_transparent_cb = QCheckBox("Transparent")
        self.bg_transparent_cb.stateChanged.connect(self._on_bg_transparent_changed)
        color_row.addWidget(self.bg_transparent_cb)
        color_row.addStretch()
        common_layout.addLayout(color_row)

        common_group.setLayout(common_layout)
        self.main_layout.addWidget(common_group)

        # Hotkey Button group
        self.hotkey_group = QGroupBox("Hotkey Button")
        hotkey_layout = QVBoxLayout()

        # Quick-fill from installed app
        self.from_app_btn = QPushButton("From App...")
        self.from_app_btn.setToolTip("Pick an installed application to auto-fill icon, label, and description")
        self.from_app_btn.clicked.connect(self._on_from_app_clicked)
        hotkey_layout.addWidget(self.from_app_btn)

        hotkey_layout.addWidget(QLabel("Description:"))
        self.description_input = QLineEdit()
        self.description_input.setMaxLength(32)
        self.description_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.description_input)

        hotkey_layout.addWidget(QLabel("Icon:"))
        self.icon_picker = IconPicker()
        self.icon_picker.icon_selected.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.icon_picker)

        # Icon image picker (overrides symbol icon)
        hotkey_layout.addWidget(QLabel("Icon Image:"))
        img_row = QHBoxLayout()
        self.icon_image_btn = QPushButton("Browse...")
        self.icon_image_btn.clicked.connect(self._on_icon_image_browse)
        img_row.addWidget(self.icon_image_btn)
        self.icon_image_clear_btn = QPushButton("Clear")
        self.icon_image_clear_btn.clicked.connect(self._on_icon_image_clear)
        self.icon_image_clear_btn.setVisible(False)
        img_row.addWidget(self.icon_image_clear_btn)
        hotkey_layout.addLayout(img_row)
        self.icon_image_label = QLabel("")
        self.icon_image_label.setStyleSheet("color: #888; font-size: 11px;")
        self.icon_image_label.setWordWrap(True)
        hotkey_layout.addWidget(self.icon_image_label)
        self.icon_image_preview = QLabel()
        self.icon_image_preview.setFixedSize(64, 64)
        self.icon_image_preview.setAlignment(Qt.AlignCenter)
        self.icon_image_preview.setStyleSheet("border: 1px solid #444; background: #1a1a2e;")
        self.icon_image_preview.setVisible(False)
        hotkey_layout.addWidget(self.icon_image_preview)

        # Internal state for pending image upload
        self._pending_icon_image_data = {}  # keyed by widget_id: (filename, bytes)

        hotkey_layout.addWidget(QLabel("Action Type:"))
        self.action_type_combo = NoScrollComboBox()
        self.action_type_combo.addItem("Keyboard Shortcut", ACTION_HOTKEY)
        self.action_type_combo.addItem("Media Key", ACTION_MEDIA_KEY)
        self.action_type_combo.addItem("Launch App", ACTION_LAUNCH_APP)
        self.action_type_combo.addItem("Shell Command", ACTION_SHELL_CMD)
        self.action_type_combo.addItem("Open URL", ACTION_OPEN_URL)
        self.action_type_combo.currentIndexChanged.connect(self._on_action_type_changed)
        hotkey_layout.addWidget(self.action_type_combo)

        self.shortcut_label = QLabel("Shortcut:")
        hotkey_layout.addWidget(self.shortcut_label)
        self.keyboard_recorder = KeyboardRecorder()
        self.keyboard_recorder.shortcut_confirmed.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.keyboard_recorder)

        self.media_key_label = QLabel("Media Key:")
        self.media_key_label.setVisible(False)
        hotkey_layout.addWidget(self.media_key_label)
        self.media_key_combo = NoScrollComboBox()
        for name, code in MEDIA_KEY_OPTIONS:
            self.media_key_combo.addItem(f"{name} (0x{code:02X})", code)
        self.media_key_combo.currentIndexChanged.connect(self._on_property_changed)
        self.media_key_combo.setVisible(False)
        hotkey_layout.addWidget(self.media_key_combo)

        # Launch App section
        self.launch_app_label = QLabel("Application:")
        self.launch_app_label.setVisible(False)
        hotkey_layout.addWidget(self.launch_app_label)
        self.app_picker_combo = NoScrollComboBox()
        self.app_picker_combo.setVisible(False)
        self.app_picker_combo.currentIndexChanged.connect(self._on_app_picker_changed)
        hotkey_layout.addWidget(self.app_picker_combo)
        self._apps_loaded = False

        self.launch_cmd_label = QLabel("Launch Command:")
        self.launch_cmd_label.setVisible(False)
        hotkey_layout.addWidget(self.launch_cmd_label)
        self.launch_cmd_input = QLineEdit()
        self.launch_cmd_input.setPlaceholderText("Exec command (auto-filled)")
        self.launch_cmd_input.setVisible(False)
        self.launch_cmd_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.launch_cmd_input)

        self.launch_wm_class_label = QLabel("WM_CLASS:")
        self.launch_wm_class_label.setVisible(False)
        hotkey_layout.addWidget(self.launch_wm_class_label)
        self.launch_wm_class_input = QLineEdit()
        self.launch_wm_class_input.setPlaceholderText("WM_CLASS (for focus-or-launch)")
        self.launch_wm_class_input.setVisible(False)
        self.launch_wm_class_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.launch_wm_class_input)

        self.focus_or_launch_check = QCheckBox("Focus existing window if running")
        self.focus_or_launch_check.setChecked(True)
        self.focus_or_launch_check.setVisible(False)
        self.focus_or_launch_check.stateChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.focus_or_launch_check)

        # Shell Command section
        self.shell_cmd_label = QLabel("Shell Command:")
        self.shell_cmd_label.setVisible(False)
        hotkey_layout.addWidget(self.shell_cmd_label)
        self.shell_cmd_input = QLineEdit()
        self.shell_cmd_input.setPlaceholderText("e.g., notify-send 'Hello'")
        self.shell_cmd_input.setVisible(False)
        self.shell_cmd_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.shell_cmd_input)

        # Open URL section
        self.url_label = QLabel("URL:")
        self.url_label.setVisible(False)
        hotkey_layout.addWidget(self.url_label)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.setVisible(False)
        self.url_input.textChanged.connect(self._on_property_changed)
        hotkey_layout.addWidget(self.url_input)

        pressed_row = QHBoxLayout()
        self.auto_darken_check = QCheckBox("Auto-darken")
        self.auto_darken_check.setChecked(True)
        self.auto_darken_check.stateChanged.connect(self._on_auto_darken_changed)
        pressed_row.addWidget(self.auto_darken_check)
        self.pressed_color_btn = QPushButton()
        self.pressed_color_btn.setFixedSize(40, 24)
        self.pressed_color_btn.setVisible(False)
        self.pressed_color_btn.clicked.connect(self._on_pressed_color_clicked)
        pressed_row.addWidget(self.pressed_color_btn)
        pressed_row.addStretch()
        hotkey_layout.addLayout(pressed_row)

        self.hotkey_group.setLayout(hotkey_layout)
        self.main_layout.addWidget(self.hotkey_group)

        # Stat Monitor group
        self.stat_group = QGroupBox("Stat Monitor")
        stat_layout = QVBoxLayout()
        stat_layout.addWidget(QLabel("Stat Type:"))
        self.stat_type_combo = NoScrollComboBox()
        for name, tid in STAT_TYPE_OPTIONS:
            self.stat_type_combo.addItem(name, tid)
        self.stat_type_combo.currentIndexChanged.connect(self._on_stat_type_changed)
        stat_layout.addWidget(self.stat_type_combo)
        self.stat_group.setLayout(stat_layout)
        self.main_layout.addWidget(self.stat_group)

        # Status Bar group
        self.status_bar_group = QGroupBox("Status Bar")
        sb_layout = QVBoxLayout()
        self.show_wifi_check = QCheckBox("Show WiFi")
        self.show_wifi_check.stateChanged.connect(self._on_property_changed)
        sb_layout.addWidget(self.show_wifi_check)
        self.show_battery_check = QCheckBox("Show Battery")
        self.show_battery_check.stateChanged.connect(self._on_property_changed)
        sb_layout.addWidget(self.show_battery_check)
        self.show_time_check = QCheckBox("Show Time")
        self.show_time_check.stateChanged.connect(self._on_property_changed)
        sb_layout.addWidget(self.show_time_check)
        self.status_bar_group.setLayout(sb_layout)
        self.main_layout.addWidget(self.status_bar_group)

        # Clock group
        self.clock_group = QGroupBox("Clock")
        clock_layout = QVBoxLayout()
        self.clock_analog_check = QCheckBox("Analog clock")
        self.clock_analog_check.stateChanged.connect(self._on_property_changed)
        clock_layout.addWidget(self.clock_analog_check)
        self.clock_group.setLayout(clock_layout)
        self.main_layout.addWidget(self.clock_group)

        # Text Label group
        self.text_group = QGroupBox("Text Label")
        text_layout = QVBoxLayout()
        text_layout.addWidget(QLabel("Font Size:"))
        self.font_size_combo = NoScrollComboBox()
        for size in [12, 14, 16, 20, 22, 28, 40]:
            self.font_size_combo.addItem(str(size), size)
        self.font_size_combo.currentIndexChanged.connect(self._on_property_changed)
        text_layout.addWidget(self.font_size_combo)
        text_layout.addWidget(QLabel("Alignment:"))
        self.text_align_combo = NoScrollComboBox()
        self.text_align_combo.addItem("Left", 0)
        self.text_align_combo.addItem("Center", 1)
        self.text_align_combo.addItem("Right", 2)
        self.text_align_combo.currentIndexChanged.connect(self._on_property_changed)
        text_layout.addWidget(self.text_align_combo)
        self.text_group.setLayout(text_layout)
        self.main_layout.addWidget(self.text_group)

        # Separator group
        self.separator_group = QGroupBox("Separator")
        sep_layout = QVBoxLayout()
        self.sep_vertical_check = QCheckBox("Vertical")
        self.sep_vertical_check.stateChanged.connect(self._on_property_changed)
        sep_layout.addWidget(self.sep_vertical_check)
        sep_layout.addWidget(QLabel("Thickness:"))
        self.thickness_spin = QSpinBox()
        self.thickness_spin.setRange(1, 8)
        self.thickness_spin.setValue(2)
        self.thickness_spin.setFocusPolicy(Qt.StrongFocus)
        self.thickness_spin.valueChanged.connect(self._on_property_changed)
        sep_layout.addWidget(self.thickness_spin)
        self.separator_group.setLayout(sep_layout)
        self.main_layout.addWidget(self.separator_group)

        self.main_layout.addStretch()
        self.setWidget(container)

        # Initially hide all type-specific groups
        self._hide_all_groups()

    def _hide_all_groups(self):
        self.hotkey_group.setVisible(False)
        self.stat_group.setVisible(False)
        self.status_bar_group.setVisible(False)
        self.clock_group.setVisible(False)
        self.text_group.setVisible(False)
        self.separator_group.setVisible(False)

    def clear_selection(self):
        """Clear the properties panel (no widget selected)."""
        self._widget_idx = -1
        self._widget_id = ""
        self._widget_dict = None
        self.type_label.setText("No widget selected")
        self._hide_all_groups()

    def load_widget(self, widget_dict, widget_idx):
        """Load widget data into the properties panel."""
        self._updating = True
        self._widget_dict = widget_dict
        self._widget_idx = widget_idx
        self._widget_id = widget_dict.get("widget_id", "")

        wtype = widget_dict.get("widget_type", WIDGET_HOTKEY_BUTTON)
        type_name = WIDGET_TYPE_NAMES.get(wtype, f"Type {wtype}")
        self.type_label.setText(f"{type_name} (#{widget_idx})")

        # Position
        self.x_spin.setValue(widget_dict.get("x", 0))
        self.y_spin.setValue(widget_dict.get("y", 0))
        self.w_spin.setValue(widget_dict.get("width", 180))
        self.h_spin.setValue(widget_dict.get("height", 100))

        # Common
        self.label_input.setText(widget_dict.get("label", ""))
        self._set_color_btn(self.color_btn, widget_dict.get("color", 0xFFFFFF))
        bg_val = widget_dict.get("bg_color", 0)
        self._set_color_btn(self.bg_color_btn, bg_val)
        self.bg_transparent_cb.setChecked(bg_val == 0)
        self.bg_color_btn.setEnabled(bg_val != 0)

        # Show/hide type-specific groups
        self._hide_all_groups()

        if wtype == WIDGET_HOTKEY_BUTTON:
            self.hotkey_group.setVisible(True)
            self.description_input.setText(widget_dict.get("description", ""))
            self.icon_picker.set_symbol(widget_dict.get("icon", ""))

            # Restore image picker state
            icon_path = widget_dict.get("icon_path", "")
            if self._widget_id in self._pending_icon_image_data:
                filename = self._pending_icon_image_data[self._widget_id][0]
                data = self._pending_icon_image_data[self._widget_id][1]
                self.icon_image_label.setText(f"{filename} ({len(data)} bytes)")
                self.icon_image_clear_btn.setVisible(True)
                from PySide6.QtGui import QPixmap
                pixmap = QPixmap()
                pixmap.loadFromData(data, "PNG")
                self.icon_image_preview.setPixmap(
                    pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                self.icon_image_preview.setVisible(True)
            elif icon_path:
                import os
                self.icon_image_label.setText(os.path.basename(icon_path))
                self.icon_image_clear_btn.setVisible(True)
                self.icon_image_preview.setVisible(False)
            else:
                self.icon_image_label.setText("")
                self.icon_image_clear_btn.setVisible(False)
                self.icon_image_preview.setVisible(False)
                self.icon_image_preview.clear()

            action_type = widget_dict.get("action_type", ACTION_HOTKEY)
            # Find correct index by matching itemData
            for i in range(self.action_type_combo.count()):
                if self.action_type_combo.itemData(i) == action_type:
                    self.action_type_combo.setCurrentIndex(i)
                    break
            self._update_action_visibility(action_type)
            self.keyboard_recorder.set_shortcut(
                widget_dict.get("modifiers", 0), widget_dict.get("keycode", 0)
            )
            self._set_media_key_combo(widget_dict.get("consumer_code", 0))

            # Load launch app fields
            self.launch_cmd_input.setText(widget_dict.get("launch_command", ""))
            self.launch_wm_class_input.setText(widget_dict.get("launch_wm_class", ""))
            self.focus_or_launch_check.setChecked(widget_dict.get("launch_focus_or_launch", True))

            # Load shell command
            self.shell_cmd_input.setText(widget_dict.get("shell_command", ""))

            # Load URL
            self.url_input.setText(widget_dict.get("url", ""))

            pressed = widget_dict.get("pressed_color", 0)
            self.auto_darken_check.setChecked(pressed == 0)
            self.pressed_color_btn.setVisible(pressed != 0)
            if pressed != 0:
                self._set_color_btn(self.pressed_color_btn, pressed)

        elif wtype == WIDGET_STAT_MONITOR:
            self.stat_group.setVisible(True)
            st = widget_dict.get("stat_type", 0x01)
            for i in range(self.stat_type_combo.count()):
                if self.stat_type_combo.itemData(i) == st:
                    self.stat_type_combo.setCurrentIndex(i)
                    break

        elif wtype == WIDGET_STATUS_BAR:
            self.status_bar_group.setVisible(True)
            self.show_wifi_check.setChecked(widget_dict.get("show_wifi", True))
            self.show_battery_check.setChecked(widget_dict.get("show_battery", True))
            self.show_time_check.setChecked(widget_dict.get("show_time", True))

        elif wtype == WIDGET_CLOCK:
            self.clock_group.setVisible(True)
            self.clock_analog_check.setChecked(widget_dict.get("clock_analog", False))

        elif wtype == WIDGET_TEXT_LABEL:
            self.text_group.setVisible(True)
            fs = widget_dict.get("font_size", 16)
            for i in range(self.font_size_combo.count()):
                if self.font_size_combo.itemData(i) == fs:
                    self.font_size_combo.setCurrentIndex(i)
                    break
            ta = widget_dict.get("text_align", 1)
            self.text_align_combo.setCurrentIndex(ta)

        elif wtype == WIDGET_SEPARATOR:
            self.separator_group.setVisible(True)
            self.sep_vertical_check.setChecked(widget_dict.get("separator_vertical", False))
            self.thickness_spin.setValue(widget_dict.get("thickness", 2))

        self._updating = False

    def update_position(self, x, y, w, h):
        """Update position spinboxes without triggering property changed."""
        self._updating = True
        self.x_spin.setValue(x)
        self.y_spin.setValue(y)
        self.w_spin.setValue(w)
        self.h_spin.setValue(h)
        self._updating = False

    def _get_widget_dict(self):
        """Build widget dict from current panel state."""
        if self._widget_dict is None:
            return None

        d = dict(self._widget_dict)
        d["x"] = self.x_spin.value()
        d["y"] = self.y_spin.value()
        d["width"] = self.w_spin.value()
        d["height"] = self.h_spin.value()
        d["label"] = self.label_input.text()
        d["color"] = self.color_btn.property("color_value") or 0xFFFFFF
        d["bg_color"] = 0 if self.bg_transparent_cb.isChecked() else (self.bg_color_btn.property("color_value") or 0)

        wtype = d.get("widget_type", WIDGET_HOTKEY_BUTTON)

        if wtype == WIDGET_HOTKEY_BUTTON:
            d["description"] = self.description_input.text()
            d["icon"] = self.icon_picker.get_symbol()
            # Set icon_path if an image is pending for this widget
            if self._widget_id in self._pending_icon_image_data:
                filename = self._pending_icon_image_data[self._widget_id][0]
                d["icon_path"] = f"/icons/{filename}"
            else:
                d["icon_path"] = ""
            action_type = self.action_type_combo.currentData()
            d["action_type"] = action_type
            if action_type == ACTION_MEDIA_KEY:
                d["consumer_code"] = self.media_key_combo.currentData() or 0
                d["modifiers"] = 0
                d["keycode"] = 0
            elif action_type == ACTION_HOTKEY:
                d["consumer_code"] = 0
                d["modifiers"] = self.keyboard_recorder.current_modifiers
                d["keycode"] = self.keyboard_recorder.current_keycode
            else:
                d["consumer_code"] = 0
                d["modifiers"] = 0
                d["keycode"] = 0

            # Always include all action-type fields
            d["launch_command"] = self.launch_cmd_input.text()
            d["launch_wm_class"] = self.launch_wm_class_input.text()
            d["launch_focus_or_launch"] = self.focus_or_launch_check.isChecked()
            d["shell_command"] = self.shell_cmd_input.text()
            d["url"] = self.url_input.text()

            d["pressed_color"] = 0 if self.auto_darken_check.isChecked() else (
                self.pressed_color_btn.property("color_value") or 0xFF0000
            )

        elif wtype == WIDGET_STAT_MONITOR:
            d["stat_type"] = self.stat_type_combo.currentData() or 0x01

        elif wtype == WIDGET_STATUS_BAR:
            d["show_wifi"] = self.show_wifi_check.isChecked()
            d["show_battery"] = self.show_battery_check.isChecked()
            d["show_time"] = self.show_time_check.isChecked()

        elif wtype == WIDGET_CLOCK:
            d["clock_analog"] = self.clock_analog_check.isChecked()

        elif wtype == WIDGET_TEXT_LABEL:
            d["font_size"] = self.font_size_combo.currentData() or 16
            d["text_align"] = self.text_align_combo.currentData()

        elif wtype == WIDGET_SEPARATOR:
            d["separator_vertical"] = self.sep_vertical_check.isChecked()
            d["thickness"] = self.thickness_spin.value()

        return d

    def _on_position_changed(self):
        if not self._updating:
            self._emit_update()

    def _on_property_changed(self, *args):
        if not self._updating:
            self._emit_update()

    def _on_stat_type_changed(self, *args):
        """When stat type changes, auto-update label to match the stat name."""
        if not self._updating:
            stat_id = self.stat_type_combo.currentData()
            if stat_id is not None:
                new_label = STAT_TYPE_NAMES.get(stat_id, "Stat")
                # Only auto-set if label is empty or matches a known stat name
                current = self.label_input.text().strip()
                if not current or current in STAT_TYPE_NAMES.values():
                    self._updating = True
                    self.label_input.setText(new_label)
                    self._updating = False
            self._emit_update()

    def _on_action_type_changed(self):
        action_type = self.action_type_combo.currentData()
        self._update_action_visibility(action_type)
        if not self._updating:
            self._emit_update()

    def _update_action_visibility(self, action_type):
        """Show/hide action-specific widgets based on selected action type."""
        # Shortcut section
        is_hotkey = (action_type == ACTION_HOTKEY)
        self.keyboard_recorder.setVisible(is_hotkey)
        self.shortcut_label.setVisible(is_hotkey)

        # Media key section
        is_media = (action_type == ACTION_MEDIA_KEY)
        self.media_key_combo.setVisible(is_media)
        self.media_key_label.setVisible(is_media)

        # Launch app section
        is_launch = (action_type == ACTION_LAUNCH_APP)
        self.launch_app_label.setVisible(is_launch)
        self.app_picker_combo.setVisible(is_launch)
        self.launch_cmd_label.setVisible(is_launch)
        self.launch_cmd_input.setVisible(is_launch)
        self.launch_wm_class_label.setVisible(is_launch)
        self.launch_wm_class_input.setVisible(is_launch)
        self.focus_or_launch_check.setVisible(is_launch)
        if is_launch:
            self._ensure_apps_loaded()

        # Shell command section
        is_shell = (action_type == ACTION_SHELL_CMD)
        self.shell_cmd_label.setVisible(is_shell)
        self.shell_cmd_input.setVisible(is_shell)

        # URL section
        is_url = (action_type == ACTION_OPEN_URL)
        self.url_label.setVisible(is_url)
        self.url_input.setVisible(is_url)

    def _ensure_apps_loaded(self):
        """Lazy-load applications list into app_picker_combo."""
        if self._apps_loaded:
            return
        self._apps_loaded = True
        self.app_picker_combo.clear()
        self.app_picker_combo.addItem("(Custom)", None)
        try:
            from companion.app_scanner import scan_applications
            apps = scan_applications()
            for app in apps:
                self.app_picker_combo.addItem(app.name, app)
        except Exception:
            pass

    def _on_app_picker_changed(self, index):
        """App picker dropdown changed -- auto-fill launch fields."""
        if self._updating:
            return
        app = self.app_picker_combo.currentData()
        if app is None:
            return
        self._updating = True
        self.launch_cmd_input.setText(app.exec_cmd)
        wm_class = app.wm_class if hasattr(app, 'wm_class') and app.wm_class else app.name
        self.launch_wm_class_input.setText(wm_class)
        self._updating = False
        if not self._updating:
            self._emit_update()

    def _on_from_app_clicked(self):
        """Open app picker dialog and auto-fill button from selected app."""
        from companion.ui.app_picker_dialog import AppPickerDialog

        dialog = AppPickerDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        app = dialog.get_selected_app()
        if not app:
            return

        self._updating = True

        # Set label (truncate to fit)
        name = app.name[:20]
        self.label_input.setText(name)

        # Set description from exec command (clean up %u, %U, etc.)
        import re
        clean_exec = re.sub(r'\s*%[a-zA-Z]', '', app.exec_cmd).strip()
        self.description_input.setText(clean_exec[:32])

        self._updating = False

        # Process icon if available
        if app.icon_path:
            try:
                from companion.image_optimizer import optimize_for_widget
                w = self.w_spin.value()
                h = self.h_spin.value()
                png_data = optimize_for_widget(app.icon_path, w, h)

                # Sanitize filename
                safe_name = "".join(
                    c if c.isalnum() or c in "-_" else "_"
                    for c in app.icon_name
                )
                filename = f"{safe_name}.png"

                # Store for deploy
                self._pending_icon_image_data[self._widget_id] = (filename, png_data)

                # Update UI
                self.icon_image_label.setText(f"{filename} ({len(png_data)} bytes)")
                self.icon_image_clear_btn.setVisible(True)

                # Show preview
                from PySide6.QtGui import QPixmap
                pixmap = QPixmap()
                pixmap.loadFromData(png_data, "PNG")
                self.icon_image_preview.setPixmap(
                    pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                self.icon_image_preview.setVisible(True)
            except Exception as e:
                # Icon processing failed, no big deal — label/desc still set
                self.icon_image_label.setText(f"Icon error: {e}")

        self._emit_update()

    def _on_icon_image_browse(self):
        """Open file dialog to pick an icon image."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Icon Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if not path:
            return

        try:
            from companion.image_optimizer import optimize_for_widget
            w = self.w_spin.value()
            h = self.h_spin.value()
            png_data = optimize_for_widget(path, w, h)

            # Generate filename from widget label or index
            import os
            base = os.path.splitext(os.path.basename(path))[0]
            # Sanitize filename
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
            filename = f"{safe_name}.png"

            # Store for deploy
            self._pending_icon_image_data[self._widget_id] = (filename, png_data)

            # Update UI
            self.icon_image_label.setText(f"{filename} ({len(png_data)} bytes)")
            self.icon_image_clear_btn.setVisible(True)

            # Show preview
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap()
            pixmap.loadFromData(png_data, "PNG")
            self.icon_image_preview.setPixmap(
                pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.icon_image_preview.setVisible(True)

            if not self._updating:
                self._emit_update()
        except Exception as e:
            QMessageBox.warning(self, "Image Error", f"Failed to process image:\n{e}")

    def _on_icon_image_clear(self):
        """Clear selected icon image, revert to symbol."""
        if self._widget_id in self._pending_icon_image_data:
            del self._pending_icon_image_data[self._widget_id]
        self.icon_image_label.setText("")
        self.icon_image_clear_btn.setVisible(False)
        self.icon_image_preview.setVisible(False)
        self.icon_image_preview.clear()
        if not self._updating:
            self._emit_update()

    def get_pending_images(self) -> dict:
        """Return dict of widget_id -> (filename, png_bytes) for deploy."""
        return dict(self._pending_icon_image_data)

    def _on_auto_darken_changed(self):
        is_auto = self.auto_darken_check.isChecked()
        self.pressed_color_btn.setVisible(not is_auto)
        if not self._updating:
            self._emit_update()

    def _on_color_clicked(self):
        current = self.color_btn.property("color_value") or 0xFFFFFF
        qc = _int_to_qcolor(current)
        new_color = QColorDialog.getColor(qc, self, "Widget Color")
        if new_color.isValid():
            self._set_color_btn(self.color_btn, _qcolor_to_int(new_color))
            if not self._updating:
                self._emit_update()

    def _on_bg_color_clicked(self):
        current = self.bg_color_btn.property("color_value") or 0
        qc = _int_to_qcolor(current)
        new_color = QColorDialog.getColor(qc, self, "Background Color")
        if new_color.isValid():
            self._set_color_btn(self.bg_color_btn, _qcolor_to_int(new_color))
            if not self._updating:
                self._emit_update()

    def _on_bg_transparent_changed(self, state):
        checked = state == Qt.Checked.value if hasattr(Qt.Checked, 'value') else state == 2
        self.bg_color_btn.setEnabled(not checked)
        if checked:
            self._set_color_btn(self.bg_color_btn, 0)
        if not self._updating:
            self._emit_update()

    def _on_pressed_color_clicked(self):
        current = self.pressed_color_btn.property("color_value") or 0xFF0000
        qc = _int_to_qcolor(current)
        new_color = QColorDialog.getColor(qc, self, "Pressed Color")
        if new_color.isValid():
            self._set_color_btn(self.pressed_color_btn, _qcolor_to_int(new_color))
            if not self._updating:
                self._emit_update()

    def _set_color_btn(self, btn, color_val):
        qc = _int_to_qcolor(color_val)
        btn.setStyleSheet(f"background-color: {qc.name()}; border: 1px solid #555;")
        btn.setProperty("color_value", color_val)

    def _set_media_key_combo(self, consumer_code):
        for i in range(self.media_key_combo.count()):
            if self.media_key_combo.itemData(i) == consumer_code:
                self.media_key_combo.setCurrentIndex(i)
                return
        if self.media_key_combo.count() > 0:
            self.media_key_combo.setCurrentIndex(0)

    def _emit_update(self):
        if self._widget_id:
            d = self._get_widget_dict()
            if d is not None:
                self.widget_updated.emit(self._widget_id, d)


# ============================================================
# Editor Main Window
# ============================================================

class EditorMainWindow(QMainWindow):
    """Main editor window with WYSIWYG canvas, palette, and properties."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.current_page = 0
        self._current_file_path = None  # Track last saved/loaded file path
        self._tray_mode = False  # Set True by tray app to hide on close instead of quit
        self.setWindowTitle("CrowPanel Editor")
        self.setMinimumSize(1100, 700)

        # Canvas items tracked by stable widget_id
        self._canvas_items = {}  # widget_id -> CanvasWidgetItem

        # Central widget with splitter layout
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Left: Items palette
        self.palette = ItemsPalette()
        main_layout.addWidget(self.palette)

        # Center: Canvas + page toolbar
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.canvas_scene = CanvasScene()
        self.canvas_view = CanvasView(self.canvas_scene)
        center_layout.addWidget(self.canvas_view, stretch=1)

        # Page toolbar
        page_toolbar = QWidget()
        page_layout = QHBoxLayout(page_toolbar)
        page_layout.setContentsMargins(4, 2, 4, 2)

        self.prev_page_btn = QPushButton("< Prev")
        self.prev_page_btn.clicked.connect(self._on_prev_page)
        self.page_label = QLabel("Page 1 / 1")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.next_page_btn = QPushButton("Next >")
        self.next_page_btn.clicked.connect(self._on_next_page)
        self.add_page_btn = QPushButton("+ Add")
        self.add_page_btn.clicked.connect(self._on_add_page)
        self.remove_page_btn = QPushButton("- Remove")
        self.remove_page_btn.clicked.connect(self._on_remove_page)
        self.rename_page_btn = QPushButton("Rename")
        self.rename_page_btn.clicked.connect(self._on_rename_page)

        page_layout.addWidget(self.prev_page_btn)
        page_layout.addWidget(self.page_label, stretch=1)
        page_layout.addWidget(self.next_page_btn)
        page_layout.addWidget(self.add_page_btn)
        page_layout.addWidget(self.remove_page_btn)
        page_layout.addWidget(self.rename_page_btn)

        # Test Action button
        self.test_action_btn = QPushButton("Test Action")
        self.test_action_btn.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold;")
        self.test_action_btn.setToolTip("Fire the currently configured action on this PC")
        self.test_action_btn.clicked.connect(self._on_test_action_clicked)
        page_layout.addWidget(self.test_action_btn)

        # Deploy button
        self.deploy_btn = QPushButton("Deploy")
        self.deploy_btn.setStyleSheet("background-color: #2ECC71; color: white; font-weight: bold;")
        self.deploy_btn.clicked.connect(self._on_deploy_clicked)
        page_layout.addWidget(self.deploy_btn)

        center_layout.addWidget(page_toolbar)
        main_layout.addWidget(center_widget, stretch=1)

        # Right: Tabbed panel (Widget Properties | Settings | Stats | Notifications)
        right_tabs = QTabWidget()
        right_tabs.setMaximumWidth(320)
        right_tabs.setMinimumWidth(240)
        right_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #333; background: #161b22; }"
            "QTabBar::tab { background: #0d1117; color: #8b949e; padding: 6px 12px; "
            "  border: 1px solid #333; border-bottom: none; }"
            "QTabBar::tab:selected { background: #161b22; color: #e0e0e0; }"
        )

        # Tab 1: Widget Properties
        self.properties_panel = PropertiesPanel()
        self.properties_panel.widget_updated.connect(self._on_widget_property_changed)
        right_tabs.addTab(self.properties_panel, "Widget")

        # Tab 2: Display Settings
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(4, 8, 4, 4)

        display_group = QGroupBox("Display Modes")
        display_layout = QGridLayout()
        display_layout.addWidget(QLabel("Default mode:"), 0, 0)
        self.mode_dropdown = NoScrollComboBox()
        self.mode_dropdown.addItems(["Hotkeys", "Clock", "Picture Frame", "Standby"])
        self.mode_dropdown.currentIndexChanged.connect(self._on_display_mode_changed)
        display_layout.addWidget(self.mode_dropdown, 0, 1)
        display_layout.addWidget(QLabel("Slideshow (sec):"), 1, 0)
        self.slideshow_spinbox = QSpinBox()
        self.slideshow_spinbox.setRange(5, 300)
        self.slideshow_spinbox.setValue(30)
        self.slideshow_spinbox.setFocusPolicy(Qt.StrongFocus)
        self.slideshow_spinbox.valueChanged.connect(self._on_display_mode_changed)
        display_layout.addWidget(self.slideshow_spinbox, 1, 1)
        self.analog_checkbox = QCheckBox("Analog clock")
        self.analog_checkbox.stateChanged.connect(self._on_display_mode_changed)
        display_layout.addWidget(self.analog_checkbox, 2, 0, 1, 2)
        display_group.setLayout(display_layout)
        settings_layout.addWidget(display_group)
        settings_layout.addStretch()
        right_tabs.addTab(settings_widget, "Settings")

        # Tab 3: Stats Header
        self.stats_panel = StatsHeaderPanel(self.config_manager)
        self.stats_panel.stats_changed.connect(self._on_stats_header_changed)
        right_tabs.addTab(self.stats_panel, "Stats")

        # Tab 4: Notifications
        self.notifications_panel = NotificationsPanel(self.config_manager)
        self.notifications_panel.notifications_changed.connect(self._on_notifications_changed)
        right_tabs.addTab(self.notifications_panel, "Notifs")

        main_layout.addWidget(right_tabs)

        self.setCentralWidget(central_widget)

        # Connect canvas signals
        self.canvas_scene.widget_selected.connect(self._on_canvas_widget_selected)
        self.canvas_scene.widget_deselected.connect(self._on_canvas_widget_deselected)
        self.canvas_scene.widget_geometry_changed.connect(self._on_canvas_geometry_changed)
        self.canvas_scene.widget_dropped.connect(self._on_canvas_widget_dropped)
        self.canvas_scene._on_delete_callback = self._on_canvas_widget_deleted
        self.canvas_scene._on_paste_callback = self._on_canvas_paste
        self.canvas_scene._on_move_to_page = self._on_move_widgets_to_page
        self.canvas_scene._get_page_list = self._get_page_list
        self.canvas_scene._current_page = self.current_page

        # Menu bar
        self._create_menu_bar()

        # Status bar
        self.statusBar().showMessage("Ready")

        # Auto-load last config (or default)
        self._auto_load_config()
        self._load_saved_images()

        # Load initial state from config
        self._load_display_mode_settings()
        self.stats_panel.load_from_config()
        self.notifications_panel.load_from_config()
        self._rebuild_canvas()
        self._update_page_display()

        # Size window so canvas is 1:1 with the display (800x480)
        # Canvas view needs ~20px for border/margin, page toolbar ~40px, menubar ~30px, statusbar ~25px
        canvas_chrome_w = 22  # border + padding
        canvas_chrome_h = 22
        palette_w = self.palette.minimumWidth() + 8  # 120 + spacing
        right_w = right_tabs.minimumWidth() + 8       # 240 + spacing
        margins = 8 + 8  # main_layout margins
        toolbar_h = 40   # page toolbar
        menubar_h = 30
        statusbar_h = 25

        ideal_w = palette_w + canvas_chrome_w + DISPLAY_WIDTH + right_w + margins
        ideal_h = canvas_chrome_h + DISPLAY_HEIGHT + toolbar_h + menubar_h + statusbar_h + margins

        # Clamp to available screen size
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            ideal_w = min(ideal_w, avail.width())
            ideal_h = min(ideal_h, avail.height())
        self.resize(ideal_w, ideal_h)

    def _auto_load_config(self):
        """Load config from default path if it exists."""
        if DEFAULT_CONFIG_PATH.is_file():
            if self.config_manager.load_json_file(str(DEFAULT_CONFIG_PATH)):
                self._current_file_path = str(DEFAULT_CONFIG_PATH)
                self.statusBar().showMessage(f"Loaded: {DEFAULT_CONFIG_PATH}")

    def _auto_save_config(self):
        """Save config and icon images to the current file path (or default)."""
        path = self._current_file_path or str(DEFAULT_CONFIG_PATH)
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.config_manager.save_json_file(path)
        self._save_pending_images()

    def _resolve_widget_idx(self, widget_id: str) -> int:
        """Find positional index of widget by its stable widget_id. Returns -1 if not found."""
        page = self.config_manager.get_page(self.current_page)
        if page is None:
            return -1
        for idx, w in enumerate(page.get("widgets", [])):
            if w.get("widget_id") == widget_id:
                return idx
        return -1

    def _save_pending_images(self):
        """Persist pending icon images to ~/.config/crowpanel/icons/."""
        pending = self.properties_panel.get_pending_images()
        if not pending:
            return
        DEFAULT_ICONS_DIR.mkdir(parents=True, exist_ok=True)
        for widget_idx, (filename, png_data) in pending.items():
            icon_file = DEFAULT_ICONS_DIR / filename
            icon_file.write_bytes(png_data)

    def _load_saved_images(self):
        """Restore icon images from disk into pending_icon_image_data."""
        if not DEFAULT_ICONS_DIR.is_dir():
            return
        # Walk all pages/widgets looking for icon_path entries
        for page_idx in range(self.config_manager.get_page_count()):
            page = self.config_manager.get_page(page_idx)
            if not page:
                continue
            for widget in page.get("widgets", []):
                icon_path = widget.get("icon_path", "")
                if not icon_path:
                    continue
                wid = widget.get("widget_id", "")
                if not wid:
                    continue
                filename = os.path.basename(icon_path)
                local_file = DEFAULT_ICONS_DIR / filename
                if local_file.is_file():
                    png_data = local_file.read_bytes()
                    self.properties_panel._pending_icon_image_data[wid] = (filename, png_data)

    def closeEvent(self, event):
        """Auto-save config on window close. In tray mode, hide instead of quit."""
        self._auto_save_config()
        if self._tray_mode:
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)

    def _create_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        new_action = file_menu.addAction("New")
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._on_file_new)

        open_action = file_menu.addAction("Open...")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._on_file_open)

        save_action = file_menu.addAction("Save")
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._on_file_save)

        save_as_action = file_menu.addAction("Save As...")
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._on_file_save_as)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def _rebuild_canvas(self):
        """Rebuild canvas items from current page config."""
        # Clear existing items (except handles)
        self.canvas_scene._clear_handles()
        for item in list(self._canvas_items.values()):
            self.canvas_scene.removeItem(item)
        self._canvas_items.clear()

        # Keep scene in sync with current page
        self.canvas_scene._current_page = self.current_page

        page = self.config_manager.get_page(self.current_page)
        if page is None:
            return

        widgets = page.get("widgets", [])
        pending = self.properties_panel.get_pending_images()
        for idx, widget_dict in enumerate(widgets):
            wid = widget_dict.get("widget_id", "")
            item = CanvasWidgetItem(widget_dict, idx)
            # Restore icon pixmap from pending image data
            if wid in pending:
                from PySide6.QtGui import QPixmap
                pixmap = QPixmap()
                pixmap.loadFromData(pending[wid][1], "PNG")
                item.set_icon_pixmap(pixmap)
            self.canvas_scene.addItem(item)
            self._canvas_items[wid] = item

    def _update_page_display(self):
        page_count = self.config_manager.get_page_count()
        page = self.config_manager.get_page(self.current_page)
        page_name = page.get("name", "") if page else ""

        self.page_label.setText(f"{page_name} ({self.current_page + 1} / {page_count})")
        self.prev_page_btn.setEnabled(self.current_page > 0)
        self.next_page_btn.setEnabled(self.current_page < page_count - 1)
        self.remove_page_btn.setEnabled(page_count > 1)

        # Update page nav dot widgets
        if self.canvas_scene.page_count != page_count:
            self.canvas_scene.page_count = page_count
            for item in self._canvas_items.values():
                if item.widget_dict.get("type") == WIDGET_PAGE_NAV:
                    item.update()

    # -- Canvas signal handlers --

    def _on_canvas_widget_selected(self, widget_id):
        widget_idx = self._resolve_widget_idx(widget_id)
        if widget_idx < 0:
            return
        widget_dict = self.config_manager.get_widget(self.current_page, widget_idx)
        if widget_dict:
            self.properties_panel.load_widget(widget_dict, widget_idx)
            wtype_name = WIDGET_TYPE_NAMES.get(widget_dict.get("widget_type", 0), "Widget")
            self.statusBar().showMessage(f"Selected: {wtype_name} #{widget_idx}")

    def _on_canvas_widget_deselected(self):
        self.properties_panel.clear_selection()
        self.statusBar().showMessage("Ready")

    def _on_canvas_geometry_changed(self, widget_id, x, y, w, h):
        """Canvas item was moved or resized."""
        widget_idx = self._resolve_widget_idx(widget_id)
        if widget_idx < 0:
            return
        widget_dict = self.config_manager.get_widget(self.current_page, widget_idx)
        if widget_dict:
            widget_dict["x"] = x
            widget_dict["y"] = y
            widget_dict["width"] = w
            widget_dict["height"] = h
            self.config_manager.set_widget(self.current_page, widget_idx, widget_dict)
            # Update position readout in properties panel
            self.properties_panel.update_position(x, y, w, h)

    def _on_canvas_widget_dropped(self, widget_type, x, y):
        """Widget dropped from palette onto canvas."""
        widget_dict = make_default_widget(widget_type, x, y)
        # Stat monitors get their label from the stat type name
        if widget_type == WIDGET_STAT_MONITOR:
            st = widget_dict.get("stat_type", 0x01)
            widget_dict["label"] = STAT_TYPE_NAMES.get(st, "Stat")
        widget_idx = self.config_manager.add_widget(self.current_page, widget_dict)
        if widget_idx >= 0:
            wid = widget_dict.get("widget_id", "")
            item = CanvasWidgetItem(widget_dict, widget_idx)
            self.canvas_scene.addItem(item)
            self._canvas_items[wid] = item
            # Select the new item
            self.canvas_scene.clearSelection()
            item.setSelected(True)
            type_name = WIDGET_TYPE_NAMES.get(widget_type, "Widget")
            self.statusBar().showMessage(f"Added: {type_name} at ({x}, {y})")

    def _on_canvas_widget_deleted(self, widget_ids):
        """Widget(s) deleted from canvas (Delete key)."""
        # Remove items from canvas and resolve indices for config_manager
        indices_to_remove = []
        for wid in widget_ids:
            if wid in self._canvas_items:
                del self._canvas_items[wid]
            idx = self._resolve_widget_idx(wid)
            if idx >= 0:
                indices_to_remove.append(idx)
        # Remove from config_manager in reverse order to maintain indices
        for idx in sorted(indices_to_remove, reverse=True):
            self.config_manager.remove_widget(self.current_page, idx)

        # Rebuild canvas to fix indices
        self.properties_panel.clear_selection()
        self._rebuild_canvas()
        self.statusBar().showMessage(f"Deleted {len(widget_ids)} widget(s)")

    def _on_canvas_paste(self, widget_dicts):
        """Paste widgets from clipboard onto current page."""
        import uuid as _uuid
        self.canvas_scene.clearSelection()
        for wd in widget_dicts:
            # Each pasted widget gets a fresh widget_id
            wd["widget_id"] = str(_uuid.uuid4())
            widget_idx = self.config_manager.add_widget(self.current_page, wd)
            if widget_idx >= 0:
                wid = wd["widget_id"]
                item = CanvasWidgetItem(wd, widget_idx)
                self.canvas_scene.addItem(item)
                self._canvas_items[wid] = item
                item.setSelected(True)
        self.statusBar().showMessage(f"Pasted {len(widget_dicts)} widget(s)")

    def _on_move_widgets_to_page(self, widget_ids, target_page):
        """Move widgets from current page to target page."""
        import copy
        moved = 0
        # Resolve to positional indices and remove in reverse order
        id_idx_pairs = []
        for wid in widget_ids:
            idx = self._resolve_widget_idx(wid)
            if idx >= 0:
                id_idx_pairs.append((wid, idx))
        for wid, idx in sorted(id_idx_pairs, key=lambda p: p[1], reverse=True):
            wd = self.config_manager.get_widget(self.current_page, idx)
            if wd:
                self.config_manager.add_widget(target_page, copy.deepcopy(wd))
                self.config_manager.remove_widget(self.current_page, idx)
                moved += 1
        self.properties_panel.clear_selection()
        self._rebuild_canvas()
        target_name = ""
        tp = self.config_manager.get_page(target_page)
        if tp:
            target_name = tp.get("name", f"Page {target_page + 1}")
        self.statusBar().showMessage(f"Moved {moved} widget(s) to {target_name}")

    def _get_page_list(self):
        """Return list of (page_idx, page_name) for all pages."""
        result = []
        for i in range(self.config_manager.get_page_count()):
            page = self.config_manager.get_page(i)
            name = page.get("name", f"Page {i + 1}") if page else f"Page {i + 1}"
            result.append((i, name))
        return result

    # -- Properties panel handler --

    def _on_widget_property_changed(self, widget_id, widget_dict):
        """Properties panel emitted an update."""
        widget_idx = self._resolve_widget_idx(widget_id)
        if widget_idx < 0:
            return
        self.config_manager.set_widget(self.current_page, widget_idx, widget_dict)
        # Update the canvas item appearance
        if widget_id in self._canvas_items:
            item = self._canvas_items[widget_id]
            item.update_from_dict(widget_dict)
            # Sync icon pixmap from pending image data
            pending = self.properties_panel.get_pending_images()
            if widget_id in pending:
                from PySide6.QtGui import QPixmap
                pixmap = QPixmap()
                pixmap.loadFromData(pending[widget_id][1], "PNG")
                item.set_icon_pixmap(pixmap)
            else:
                item.set_icon_pixmap(None)
            self.canvas_scene.update_handles()

    # -- Page navigation --

    def _on_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.properties_panel.clear_selection()
            self._rebuild_canvas()
            self._update_page_display()

    def _on_next_page(self):
        if self.current_page < self.config_manager.get_page_count() - 1:
            self.current_page += 1
            self.properties_panel.clear_selection()
            self._rebuild_canvas()
            self._update_page_display()

    def _on_add_page(self):
        page_count = self.config_manager.get_page_count()
        new_name = f"Page {page_count + 1}"
        if self.config_manager.add_page(new_name):
            self._update_page_display()
            self.statusBar().showMessage(f"Added page: {new_name}")

    def _on_remove_page(self):
        if self.config_manager.get_page_count() <= 1:
            QMessageBox.warning(self, "Error", "Cannot remove the last page")
            return
        if self.config_manager.remove_page(self.current_page):
            if self.current_page >= self.config_manager.get_page_count():
                self.current_page -= 1
            self.properties_panel.clear_selection()
            self._rebuild_canvas()
            self._update_page_display()
            self.statusBar().showMessage("Removed page")

    def _on_rename_page(self):
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

    # -- File operations --

    def _on_file_new(self):
        reply = QMessageBox.question(
            self, "New Config", "Create new config? (unsaved changes will be lost)"
        )
        if reply == QMessageBox.Yes:
            self.config_manager.new_config()
            self.current_page = 0
            self.properties_panel.clear_selection()
            self._rebuild_canvas()
            self._update_page_display()
            self._load_display_mode_settings()
            self.stats_panel.load_from_config()
            self.notifications_panel.load_from_config()
            self.statusBar().showMessage("Created new config")

    def _on_file_open(self):
        start_dir = str(Path(self._current_file_path).parent) if self._current_file_path else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Config File", start_dir, "JSON Files (*.json)"
        )
        if file_path:
            if self.config_manager.load_json_file(file_path):
                self._current_file_path = file_path
                self.current_page = 0
                self.properties_panel.clear_selection()
                self._rebuild_canvas()
                self._update_page_display()
                self._load_display_mode_settings()
                self.stats_panel.load_from_config()
                self.notifications_panel.load_from_config()
                self.statusBar().showMessage(f"Loaded: {file_path}")
            else:
                QMessageBox.critical(self, "Error", f"Failed to load: {file_path}")

    def _on_file_save(self):
        """Save to current path (or default). No dialog."""
        is_valid, error_msg = self.config_manager.validate()
        if not is_valid:
            QMessageBox.critical(self, "Validation Error", error_msg)
            return
        path = self._current_file_path or str(DEFAULT_CONFIG_PATH)
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if self.config_manager.save_json_file(path):
            self._current_file_path = path
            self.statusBar().showMessage(f"Saved: {path}")
        else:
            QMessageBox.critical(self, "Error", f"Failed to save: {path}")

    def _on_file_save_as(self):
        """Save to a user-chosen path."""
        is_valid, error_msg = self.config_manager.validate()
        if not is_valid:
            QMessageBox.critical(self, "Validation Error", error_msg)
            return
        start_dir = str(Path(self._current_file_path).parent) if self._current_file_path else ""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Config File", start_dir, "JSON Files (*.json)"
        )
        if file_path:
            if self.config_manager.save_json_file(file_path):
                self._current_file_path = file_path
                self.statusBar().showMessage(f"Saved: {file_path}")
            else:
                QMessageBox.critical(self, "Error", f"Failed to save: {file_path}")

    # -- Settings handlers --

    def _load_display_mode_settings(self):
        config = self.config_manager.config
        self.mode_dropdown.setCurrentIndex(config.get("default_mode", 0))
        self.slideshow_spinbox.setValue(config.get("slideshow_interval_sec", 30))
        self.analog_checkbox.setChecked(config.get("clock_analog", False))

    def _on_display_mode_changed(self):
        self.config_manager.config["default_mode"] = self.mode_dropdown.currentIndex()
        self.config_manager.config["slideshow_interval_sec"] = self.slideshow_spinbox.value()
        self.config_manager.config["clock_analog"] = self.analog_checkbox.isChecked()

    def _on_stats_header_changed(self):
        self.statusBar().showMessage("Stats header updated")

    def _on_notifications_changed(self):
        self.statusBar().showMessage("Notification settings updated")

    def _on_test_action_clicked(self):
        """Fire the currently configured action directly on the PC."""
        widget_dict = self.properties_panel._get_widget_dict()
        if widget_dict is None:
            self.statusBar().showMessage("No widget selected -- select a hotkey button first")
            return

        wtype = widget_dict.get("widget_type", WIDGET_HOTKEY_BUTTON)
        if wtype != WIDGET_HOTKEY_BUTTON:
            self.statusBar().showMessage("Test Action only works on hotkey buttons")
            return

        from companion.action_executor import (
            _exec_launch_app,
            _exec_shell_cmd,
            _exec_open_url,
            _exec_keyboard_shortcut,
            _exec_media_key,
        )

        action_type = widget_dict.get("action_type", ACTION_HOTKEY)
        action_names = {
            ACTION_HOTKEY: "Keyboard Shortcut",
            ACTION_MEDIA_KEY: "Media Key",
            ACTION_LAUNCH_APP: "Launch App",
            ACTION_SHELL_CMD: "Shell Command",
            ACTION_OPEN_URL: "Open URL",
        }
        action_name = action_names.get(action_type, f"Unknown({action_type})")
        self.statusBar().showMessage(f"Testing {action_name}...")

        def _run_test():
            try:
                if action_type == ACTION_LAUNCH_APP:
                    cmd = widget_dict.get("launch_command", "")
                    if not cmd:
                        QMetaObject.invokeMethod(self.statusBar(), "showMessage",
                            Qt.QueuedConnection, Q_ARG(str, "Test failed: no launch command set"))
                        return
                    _exec_launch_app(widget_dict)
                elif action_type == ACTION_SHELL_CMD:
                    cmd = widget_dict.get("shell_command", "")
                    if not cmd:
                        QMetaObject.invokeMethod(self.statusBar(), "showMessage",
                            Qt.QueuedConnection, Q_ARG(str, "Test failed: no shell command set"))
                        return
                    _exec_shell_cmd(widget_dict)
                elif action_type == ACTION_OPEN_URL:
                    url = widget_dict.get("url", "")
                    if not url:
                        QMetaObject.invokeMethod(self.statusBar(), "showMessage",
                            Qt.QueuedConnection, Q_ARG(str, "Test failed: no URL set"))
                        return
                    _exec_open_url(widget_dict)
                elif action_type == ACTION_MEDIA_KEY:
                    _exec_media_key(widget_dict)
                elif action_type == ACTION_HOTKEY:
                    _exec_keyboard_shortcut(widget_dict)
                QMetaObject.invokeMethod(self.statusBar(), "showMessage",
                    Qt.QueuedConnection, Q_ARG(str, f"Test fired: {action_name}"))
            except Exception as exc:
                logging.error("Test action failed: %s", exc)
                QMetaObject.invokeMethod(self.statusBar(), "showMessage",
                    Qt.QueuedConnection, Q_ARG(str, f"Test failed: {exc}"))

        threading.Thread(target=_run_test, daemon=True).start()

    def _on_deploy_clicked(self):
        is_valid, error_msg = self.config_manager.validate()
        if not is_valid:
            QMessageBox.critical(self, "Validation Error", error_msg)
            return
        # Gather pending icon images from properties panel
        pending_images = self.properties_panel.get_pending_images()
        deploy_dialog = DeployDialog(self.config_manager, self, pending_images=pending_images)
        result = deploy_dialog.exec()
        if result == QDialog.Accepted:
            self._auto_save_config()
            self.statusBar().showMessage("Config deployed and saved")
