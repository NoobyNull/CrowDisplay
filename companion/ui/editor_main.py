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
    QSpinBox,
    QCheckBox,
    QTabWidget,
)
from PySide6.QtCore import Qt, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import QKeySequence

from companion.config_manager import (
    WIDGET_HOTKEY_BUTTON,
    WIDGET_STAT_MONITOR,
    WIDGET_PAGE_NAV,
    WIDGET_TYPE_NAMES,
    ACTION_HOTKEY,
    ACTION_MEDIA_KEY,
    ACTION_LAUNCH_APP,
    ACTION_SHELL_CMD,
    ACTION_OPEN_URL,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_PATH,
    FACTORY_CONFIG_PATH,
    make_default_widget,
)
from companion.ui.deploy_dialog import DeployDialog
from companion.ui.slideshow_upload_dialog import SlideshowUploadDialog
from companion.ui.no_scroll_combo import NoScrollComboBox
from companion.ui.editor_constants import STAT_TYPE_NAMES
from companion.ui.templates import PAGE_TEMPLATES, _generate_smart_default_config
from companion.ui.canvas_items import CanvasWidgetItem
from companion.ui.canvas_scene import CanvasScene, CanvasView, ItemsPalette
from companion.ui.stats_panels import StatsHeaderPanel, NotificationsPanel
from companion.ui.properties_panel import PropertiesPanel
from companion.ui.settings_tab import SettingsTab
from companion.ui.hardware_section import HardwareSection

import os
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# Editor Main Window
# ============================================================

class EditorMainWindow(QMainWindow):
    """Main editor window with WYSIWYG canvas, palette, and properties."""

    def __init__(self, config_manager, parent=None, companion_service=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._companion_service = companion_service  # May be None when editor runs standalone
        self.current_page = 0
        self._current_file_path = None  # Track last saved/loaded file path
        self._tray_mode = False  # Set True by tray app to hide on close instead of quit
        self.setWindowTitle("CrowPanel Editor")
        self.setMinimumSize(1100, 700)

        # Debounced auto-save: fires 300ms after last change
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._auto_save_config)

        # Undo/redo stacks (config snapshots, max 20)
        import copy as _copy
        self._undo_stack = []
        self._redo_stack = []
        self._undo_max = 20
        self._copy = _copy

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

        # Settings tab (shown instead of canvas when Settings mode is active)
        self.settings_tab = SettingsTab(self.config_manager)
        self.settings_tab.settings_changed.connect(self._on_settings_tab_changed)
        self.settings_tab.slideshow_upload_btn.clicked.connect(self._on_upload_pictures)

        # Stacked widget to swap between canvas and settings
        from PySide6.QtWidgets import QStackedWidget
        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(self.canvas_view)    # index 0: canvas
        self.center_stack.addWidget(self.settings_tab)   # index 1: settings
        self.center_stack.setCurrentIndex(0)
        self._settings_mode = False
        center_layout.addWidget(self.center_stack, stretch=1)

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
        self.bg_image_btn = QPushButton("BG")
        self.bg_image_btn.setToolTip("Set page background image")
        self.bg_image_btn.clicked.connect(self._on_set_bg_image)

        page_layout.addWidget(self.prev_page_btn)
        page_layout.addWidget(self.page_label, stretch=1)
        page_layout.addWidget(self.next_page_btn)
        page_layout.addWidget(self.add_page_btn)
        page_layout.addWidget(self.remove_page_btn)
        page_layout.addWidget(self.rename_page_btn)
        page_layout.addWidget(self.bg_image_btn)

        # Settings toggle button
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setStyleSheet(
            "QPushButton { background: #333; color: #aaa; font-weight: bold; padding: 4px 12px; "
            "border: 1px solid #555; border-radius: 3px; }"
            "QPushButton:checked { background: #FFD700; color: #000; }"
        )
        self.settings_btn.setCheckable(True)
        self.settings_btn.clicked.connect(self._on_settings_toggled)
        page_layout.addWidget(self.settings_btn)

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

        # Hardware input section between canvas and page toolbar
        self.hardware_section = HardwareSection(self.config_manager)
        self.hardware_section.hw_input_selected.connect(self._on_hw_input_selected)
        self.hardware_section.setMinimumHeight(80)
        self.hardware_section.setMaximumHeight(100)
        center_layout.addWidget(self.hardware_section)

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
        self.properties_panel.hw_config_updated.connect(self._on_hw_config_changed)
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
        self.canvas_scene.delete_requested.connect(self._on_canvas_widget_deleted)
        self.canvas_scene.paste_requested.connect(self._on_canvas_paste)
        self.canvas_scene.move_to_page_requested.connect(self._on_move_widgets_to_page)
        self.canvas_scene.current_page_index = self.current_page

        # Menu bar
        self._create_menu_bar()

        # Status bar
        self.statusBar().showMessage("Ready")

        # Auto-load last config (or default)
        self._auto_load_config()

        # Load initial state from config
        self._load_display_mode_settings()
        self.stats_panel.load_from_config()
        self.notifications_panel.load_from_config()
        self.settings_tab.load_from_config()
        self.hardware_section.update_labels()
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
        """Load user config, fall back to factory default, then generate smart default."""
        if DEFAULT_CONFIG_PATH.is_file():
            if self.config_manager.load_json_file(str(DEFAULT_CONFIG_PATH)):
                self._current_file_path = str(DEFAULT_CONFIG_PATH)
                self.statusBar().showMessage(f"Loaded: {DEFAULT_CONFIG_PATH}")
                return
        if FACTORY_CONFIG_PATH.is_file():
            if self.config_manager.load_json_file(str(FACTORY_CONFIG_PATH)):
                # Loaded factory — user saves will go to config.json
                self._current_file_path = str(DEFAULT_CONFIG_PATH)
                self.statusBar().showMessage("Loaded factory defaults")
                return
        # No config at all: generate smart default
        logger.info("No config found, generating smart default...")
        smart_config = _generate_smart_default_config()
        self.config_manager.config = smart_config
        self._current_file_path = str(DEFAULT_CONFIG_PATH)
        self.statusBar().showMessage("Generated smart default config from KDE favorites")

    def _mark_dirty(self):
        """Push undo snapshot and schedule debounced save to disk."""
        snapshot = self._copy.deepcopy(self.config_manager.config)
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._undo_max:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._save_timer.start()

    def _undo(self):
        if not self._undo_stack:
            self.statusBar().showMessage("Nothing to undo")
            return
        self._redo_stack.append(self._copy.deepcopy(self.config_manager.config))
        if len(self._redo_stack) > self._undo_max:
            self._redo_stack.pop(0)
        self.config_manager.config = self._undo_stack.pop()
        self._rebuild_canvas()
        self._save_timer.start()
        self.statusBar().showMessage("Undo")

    def _redo(self):
        if not self._redo_stack:
            self.statusBar().showMessage("Nothing to redo")
            return
        self._undo_stack.append(self._copy.deepcopy(self.config_manager.config))
        self.config_manager.config = self._redo_stack.pop()
        self._rebuild_canvas()
        self._save_timer.start()
        self.statusBar().showMessage("Redo")

    def _auto_save_config(self):
        """Save config to the current file path (or default)."""
        path = self._current_file_path or str(DEFAULT_CONFIG_PATH)
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.config_manager.save_json_file(path)

    def _resolve_widget_idx(self, widget_id: str) -> int:
        """Find positional index of widget by its stable widget_id. Returns -1 if not found."""
        page = self.config_manager.get_page(self.current_page)
        if page is None:
            return -1
        for idx, w in enumerate(page.get("widgets", [])):
            if w.get("widget_id") == widget_id:
                return idx
        return -1

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

        upload_pictures_action = file_menu.addAction("Upload Pictures...")
        upload_pictures_action.triggered.connect(self._on_upload_pictures)

        file_menu.addSeparator()

        factory_action = file_menu.addAction("Reset to Factory Defaults")
        factory_action.triggered.connect(self._on_factory_reset)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

        edit_menu = menubar.addMenu("Edit")
        undo_action = edit_menu.addAction("Undo")
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        undo_action.triggered.connect(self._undo)
        redo_action = edit_menu.addAction("Redo")
        redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        redo_action.triggered.connect(self._redo)

        templates_menu = menubar.addMenu("Templates")
        for label, fn in PAGE_TEMPLATES:
            action = templates_menu.addAction(label)
            action.triggered.connect(lambda checked=False, f=fn: self._apply_template(f))

    def _apply_template(self, template_fn):
        """Apply a page template — replace current page or add as new page."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Apply Template")
        msg.setText("How would you like to apply this template?")
        replace_btn = msg.addButton("Replace Current Page", QMessageBox.AcceptRole)
        new_btn = msg.addButton("Add as New Page", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Cancel)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == replace_btn:
            widgets = template_fn()
            page = self.config_manager.get_page(self.current_page)
            if page is not None:
                page["widgets"] = widgets
                self._mark_dirty()
                self.properties_panel.clear_selection()
                self._rebuild_canvas()
                self.statusBar().showMessage("Template applied to current page")
        elif clicked == new_btn:
            widgets = template_fn()
            page_count = self.config_manager.get_page_count()
            new_name = f"Page {page_count + 1}"
            if self.config_manager.add_page(new_name):
                # Navigate to the new page and set its widgets
                new_idx = self.config_manager.get_page_count() - 1
                new_page = self.config_manager.get_page(new_idx)
                if new_page is not None:
                    new_page["widgets"] = widgets
                self.current_page = new_idx
                self._mark_dirty()
                self.properties_panel.clear_selection()
                self._rebuild_canvas()
                self._update_page_display()
                self.statusBar().showMessage(f"Template added as {new_name}")

    def _rebuild_canvas(self):
        """Rebuild canvas items from current page config."""
        # Clear existing items (except handles)
        self.canvas_scene._clear_handles()
        for item in list(self._canvas_items.values()):
            self.canvas_scene.removeItem(item)
        self._canvas_items.clear()

        # Keep scene in sync with current page
        self.canvas_scene.current_page_index = self.current_page

        page = self.config_manager.get_page(self.current_page)
        if page is None:
            return

        widgets = page.get("widgets", [])
        for idx, widget_dict in enumerate(widgets):
            wid = widget_dict.get("widget_id", "")
            item = CanvasWidgetItem(widget_dict, idx)
            # Resolve icon from source (freedesktop or file path)
            item.resolve_icon()
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

        # Keep scene in sync with page state
        self.canvas_scene.current_page_index = self.current_page
        self.canvas_scene.page_list = self._get_page_list()

        # Update page nav dot widgets
        if self.canvas_scene.page_count != page_count:
            self.canvas_scene.page_count = page_count
            for item in self._canvas_items.values():
                if item.widget_dict.get("type") == WIDGET_PAGE_NAV:
                    item.update()

    # -- Canvas signal handlers --

    def _on_canvas_widget_selected(self, widget_id):
        # Deselect hardware inputs when canvas widget is selected
        self.hardware_section.deselect()
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
            self._mark_dirty()
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
            self._mark_dirty()
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
        self._mark_dirty()
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
        self._mark_dirty()
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
        self._mark_dirty()
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
        self._mark_dirty()
        # Update the canvas item appearance
        if widget_id in self._canvas_items:
            item = self._canvas_items[widget_id]
            item.update_from_dict(widget_dict)
            # Resolve icon from source dynamically
            item.resolve_icon()
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
            self._mark_dirty()
            self._update_page_display()
            self.statusBar().showMessage(f"Added page: {new_name}")

    def _on_remove_page(self):
        if self.config_manager.get_page_count() <= 1:
            QMessageBox.warning(self, "Error", "Cannot remove the last page")
            return
        if self.config_manager.remove_page(self.current_page):
            self._mark_dirty()
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
            self._mark_dirty()
            self._update_page_display()

    def _on_set_bg_image(self):
        page = self.config_manager.get_page(self.current_page)
        if page is None:
            return
        current_bg = page.get("bg_image", "")
        # Offer clear option if already set
        if current_bg:
            reply = QMessageBox.question(
                self, "Background Image",
                f"Current: {os.path.basename(current_bg)}\n\nChange or clear?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Reset,
            )
            if reply == QMessageBox.Reset:
                page.pop("bg_image", None)
                self._mark_dirty()
                self.statusBar().showMessage("Background image cleared")
                return
            if reply != QMessageBox.Yes:
                return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image", "",
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.svg);;All Files (*)"
        )
        if path:
            page["bg_image"] = path
            self._mark_dirty()
            self.statusBar().showMessage(f"Background: {os.path.basename(path)}")

    # -- File operations --

    def _on_factory_reset(self):
        """Reset to factory defaults — delete user config and reload factory.json."""
        if not FACTORY_CONFIG_PATH.is_file():
            QMessageBox.warning(self, "Factory Reset", "No factory.json found.")
            return
        reply = QMessageBox.question(
            self, "Factory Reset",
            "Reset to factory defaults? Your current config will be deleted.",
        )
        if reply == QMessageBox.Yes:
            # Remove user config so next save creates a fresh one
            if DEFAULT_CONFIG_PATH.is_file():
                DEFAULT_CONFIG_PATH.unlink()
            self.config_manager.load_json_file(str(FACTORY_CONFIG_PATH))
            self._current_file_path = str(DEFAULT_CONFIG_PATH)
            self.current_page = 0
            self.properties_panel.clear_selection()
            self._rebuild_canvas()
            self._update_page_display()
            self._load_display_mode_settings()
            self.stats_panel.load_from_config()
            self.notifications_panel.load_from_config()
            self.settings_tab.load_from_config()
            self.hardware_section.update_labels()
            self.statusBar().showMessage("Reset to factory defaults")

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
            self.settings_tab.load_from_config()
            self.hardware_section.update_labels()
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
                self.settings_tab.load_from_config()
                self.hardware_section.update_labels()
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

    def _on_settings_toggled(self, checked):
        """Toggle between canvas view and settings view."""
        self._settings_mode = checked
        if checked:
            self.center_stack.setCurrentIndex(1)  # Show settings tab
            self.settings_tab.load_from_config()
            self.properties_panel.clear_selection()
            self.hardware_section.deselect()
            self.hardware_section.setVisible(False)
            self.page_label.setText("Settings")
            self.prev_page_btn.setEnabled(False)
            self.next_page_btn.setEnabled(False)
            self.add_page_btn.setEnabled(False)
            self.remove_page_btn.setEnabled(False)
            self.rename_page_btn.setEnabled(False)
            self.statusBar().showMessage("Settings mode")
        else:
            self.center_stack.setCurrentIndex(0)  # Show canvas
            self.hardware_section.setVisible(True)
            self._rebuild_canvas()
            self._update_page_display()
            self.add_page_btn.setEnabled(True)
            self.rename_page_btn.setEnabled(True)
            self.statusBar().showMessage("Ready")

    def _on_settings_tab_changed(self):
        self._mark_dirty()
        self.statusBar().showMessage("Display settings updated")

    # -- Hardware input handlers --

    def _on_hw_input_selected(self, hw_type, index):
        """Hardware button or encoder clicked in the hardware section."""
        # Deselect any canvas widget
        self.canvas_scene.clearSelection()
        self.properties_panel.load_hardware_input(
            self.config_manager, hw_type, index
        )
        if hw_type == "button":
            self.statusBar().showMessage(f"Selected: Hardware Button {index + 1}")
        else:
            self.statusBar().showMessage("Selected: Rotary Encoder")

    def _on_hw_config_changed(self):
        """Hardware config changed in properties panel -- update button labels."""
        self._mark_dirty()
        self.hardware_section.update_labels()

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
        # Release the companion service's bridge so deploy can use it exclusively
        if self._companion_service:
            self._companion_service.release_bridge()
        try:
            deploy_dialog = DeployDialog(self.config_manager, self)
            result = deploy_dialog.exec()
            if result == QDialog.Accepted:
                self._auto_save_config()
                self.statusBar().showMessage("Config deployed and saved")
        finally:
            if self._companion_service:
                self._companion_service.reclaim_bridge()
                self._companion_service.reload_config()
                logging.info("Companion service config reloaded after deploy")

    def _on_upload_pictures(self):
        """Upload pictures via bridge + WiFi. Uses queued list or opens file picker."""
        pic_list = self.settings_tab.slideshow_pic_list
        files = []
        if pic_list.count() > 0:
            for i in range(pic_list.count()):
                files.append(pic_list.item(i).data(Qt.UserRole))
        else:
            # Fallback: open file picker (from File menu path)
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select Images for Slideshow", "",
                "Images (*.jpg *.jpeg *.png *.gif *.webp *.svg)"
            )
        if not files:
            return

        if self._companion_service:
            self._companion_service.release_bridge()
        try:
            dialog = SlideshowUploadDialog(files, self)
            if dialog.exec() == QDialog.Accepted:
                pic_list.clear()
                self.settings_tab.slideshow_upload_btn.setEnabled(False)
        finally:
            if self._companion_service:
                self._companion_service.reclaim_bridge()
