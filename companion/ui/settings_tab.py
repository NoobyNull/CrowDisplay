"""
Settings Tab: Comprehensive display settings panel for the editor.
"""

import logging

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QSpinBox,
    QCheckBox,
    QColorDialog,
    QAbstractItemView,
    QScrollArea,
    QListWidget,
    QListWidgetItem,
    QWidget,
)
from PySide6.QtCore import Qt, Signal

from companion.ui.no_scroll_combo import NoScrollComboBox
from companion.ui.editor_utils import _int_to_qcolor, _qcolor_to_int

logger = logging.getLogger(__name__)


class SettingsTab(QScrollArea):
    """Comprehensive display settings panel shown instead of canvas when Settings is active."""

    settings_changed = Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._updating = False
        self._http_client = None

        self.setWidgetResizable(True)
        self.setStyleSheet("""
            QScrollArea { background: #0d1117; border: none; }
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                color: #FFD700;
                border: 1px solid #30363d;
                border-radius: 6px;
                margin-top: 14px;
                padding: 12px 10px 10px 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                background: #0d1117;
                color: #FFD700;
            }
            QLabel { color: #c9d1d9; font-size: 12px; }
            QCheckBox { color: #c9d1d9; font-size: 12px; }
            QCheckBox::indicator { width: 14px; height: 14px; }
            QSpinBox, QComboBox {
                background: #161b22; color: #c9d1d9; border: 1px solid #30363d;
                border-radius: 4px; padding: 3px 6px; font-size: 12px;
            }
            QPushButton {
                background: #21262d; color: #c9d1d9; border: 1px solid #30363d;
                border-radius: 4px; padding: 4px 10px; font-size: 12px;
            }
            QPushButton:hover { background: #30363d; }
            QListWidget, QTreeWidget {
                background: #161b22; color: #c9d1d9; border: 1px solid #30363d;
                border-radius: 4px; font-size: 12px;
            }
            QProgressBar {
                background: #161b22; border: 1px solid #30363d; border-radius: 4px;
                text-align: center; color: #c9d1d9; font-size: 11px;
            }
            QProgressBar::chunk { background: #238636; border-radius: 3px; }
        """)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        title = QLabel("Display Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFD700; margin-bottom: 4px;")
        layout.addWidget(title)

        # 1. Clock Settings
        clock_group = QGroupBox("Clock")
        clock_layout = QVBoxLayout()

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Time Format:"))
        self.clock_24h_check = QCheckBox("24-hour")
        self.clock_24h_check.stateChanged.connect(self._on_setting_changed)
        fmt_row.addWidget(self.clock_24h_check)
        fmt_row.addStretch()
        clock_layout.addLayout(fmt_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Clock Color:"))
        self.clock_color_btn = QPushButton()
        self.clock_color_btn.setFixedSize(40, 24)
        self.clock_color_btn.clicked.connect(self._on_clock_color_clicked)
        color_row.addWidget(self.clock_color_btn)
        color_row.addStretch()
        clock_layout.addLayout(color_row)

        clock_group.setLayout(clock_layout)
        layout.addWidget(clock_group)

        # 2. Slideshow Settings
        slideshow_group = QGroupBox("Slideshow")
        ss_layout = QVBoxLayout()

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Interval (sec):"))
        self.slideshow_interval_spin = QSpinBox()
        self.slideshow_interval_spin.setRange(5, 300)
        self.slideshow_interval_spin.setValue(30)
        self.slideshow_interval_spin.setFocusPolicy(Qt.StrongFocus)
        self.slideshow_interval_spin.valueChanged.connect(self._on_setting_changed)
        interval_row.addWidget(self.slideshow_interval_spin)
        interval_row.addStretch()
        ss_layout.addLayout(interval_row)

        trans_row = QHBoxLayout()
        trans_row.addWidget(QLabel("Transition:"))
        self.transition_combo = NoScrollComboBox()
        self.transition_combo.addItem("Fade", "fade")
        self.transition_combo.addItem("Slide", "slide")
        self.transition_combo.addItem("None", "none")
        self.transition_combo.currentIndexChanged.connect(self._on_setting_changed)
        trans_row.addWidget(self.transition_combo)
        trans_row.addStretch()
        ss_layout.addLayout(trans_row)

        # Pictures list
        pics_label = QLabel("Pictures to upload:")
        pics_label.setStyleSheet("color: #aaa; font-size: 11px; margin-top: 6px;")
        ss_layout.addWidget(pics_label)

        self.slideshow_pic_list = QListWidget()
        self.slideshow_pic_list.setMaximumHeight(120)
        self.slideshow_pic_list.setStyleSheet(
            "QListWidget { background: #161b22; border: 1px solid #333; color: #ccc; font-size: 11px; }"
        )
        self.slideshow_pic_list.setSelectionMode(QListWidget.ExtendedSelection)
        ss_layout.addWidget(self.slideshow_pic_list)

        pic_btn_row = QHBoxLayout()
        self.slideshow_add_btn = QPushButton("Add...")
        self.slideshow_add_btn.setStyleSheet(
            "QPushButton { background: #238636; color: #fff; border: 1px solid #2ea043; "
            "border-radius: 4px; padding: 4px 10px; font-size: 12px; }"
            "QPushButton:hover { background: #2ea043; }"
        )
        self.slideshow_add_btn.clicked.connect(self._on_slideshow_add)
        pic_btn_row.addWidget(self.slideshow_add_btn)

        self.slideshow_remove_btn = QPushButton("Remove")
        self.slideshow_remove_btn.setEnabled(False)
        self.slideshow_remove_btn.clicked.connect(self._on_slideshow_remove)
        pic_btn_row.addWidget(self.slideshow_remove_btn)

        self.slideshow_upload_btn = QPushButton("Upload to Device")
        self.slideshow_upload_btn.setEnabled(False)
        self.slideshow_upload_btn.setStyleSheet(
            "QPushButton { background: #3498DB; color: #fff; border: 1px solid #2980B9; "
            "border-radius: 4px; padding: 4px 10px; font-size: 12px; }"
            "QPushButton:hover { background: #2980B9; }"
            "QPushButton:disabled { background: #555; color: #888; border: 1px solid #444; }"
        )
        # Connected by EditorMainWindow after construction
        pic_btn_row.addWidget(self.slideshow_upload_btn)
        pic_btn_row.addStretch()
        ss_layout.addLayout(pic_btn_row)

        self.slideshow_pic_list.itemSelectionChanged.connect(
            lambda: self.slideshow_remove_btn.setEnabled(len(self.slideshow_pic_list.selectedItems()) > 0)
        )

        info = QLabel("Add images, then click Upload to send to device via bridge + WiFi.")
        info.setStyleSheet("color: #888; font-size: 10px; font-style: italic;")
        info.setWordWrap(True)
        ss_layout.addWidget(info)

        slideshow_group.setLayout(ss_layout)
        layout.addWidget(slideshow_group)

        # 3. Power Settings
        power_group = QGroupBox("Power Management")
        power_layout = QVBoxLayout()

        dim_row = QHBoxLayout()
        dim_row.addWidget(QLabel("Dim Timeout (sec):"))
        self.dim_timeout_spin = QSpinBox()
        self.dim_timeout_spin.setRange(0, 600)
        self.dim_timeout_spin.setValue(60)
        self.dim_timeout_spin.setFocusPolicy(Qt.StrongFocus)
        self.dim_timeout_spin.setSpecialValueText("Never")
        self.dim_timeout_spin.valueChanged.connect(self._on_setting_changed)
        dim_row.addWidget(self.dim_timeout_spin)
        dim_row.addStretch()
        power_layout.addLayout(dim_row)

        sleep_row = QHBoxLayout()
        sleep_row.addWidget(QLabel("Sleep Timeout (sec):"))
        self.sleep_timeout_spin = QSpinBox()
        self.sleep_timeout_spin.setRange(0, 3600)
        self.sleep_timeout_spin.setValue(300)
        self.sleep_timeout_spin.setFocusPolicy(Qt.StrongFocus)
        self.sleep_timeout_spin.setSpecialValueText("Never")
        self.sleep_timeout_spin.valueChanged.connect(self._on_setting_changed)
        sleep_row.addWidget(self.sleep_timeout_spin)
        sleep_row.addStretch()
        power_layout.addLayout(sleep_row)

        self.wake_on_touch_check = QCheckBox("Wake on touch")
        self.wake_on_touch_check.stateChanged.connect(self._on_setting_changed)
        power_layout.addWidget(self.wake_on_touch_check)

        power_group.setLayout(power_layout)
        layout.addWidget(power_group)

        # 3.5 System Monitor Settings
        sysmon_group = QGroupBox("System Monitor")
        sysmon_layout = QVBoxLayout()

        # Network interface selector
        net_row = QHBoxLayout()
        net_row.addWidget(QLabel("Network Interface:"))
        self.net_interface_combo = NoScrollComboBox()
        self.net_interface_combo.addItem("All (aggregate)", "")
        try:
            import psutil
            for nic in sorted(psutil.net_if_addrs().keys()):
                self.net_interface_combo.addItem(nic, nic)
        except Exception:
            pass
        self.net_interface_combo.currentIndexChanged.connect(self._on_setting_changed)
        net_row.addWidget(self.net_interface_combo)
        sysmon_layout.addLayout(net_row)

        # Disk usage mount point selector
        disk_mount_row = QHBoxLayout()
        disk_mount_row.addWidget(QLabel("Disk (Usage):"))
        self.disk_mount_combo = NoScrollComboBox()
        try:
            import psutil
            mounts = set()
            for part in psutil.disk_partitions():
                mounts.add(part.mountpoint)
            for mp in sorted(mounts):
                self.disk_mount_combo.addItem(mp, mp)
        except Exception:
            self.disk_mount_combo.addItem("/", "/")
        self.disk_mount_combo.currentIndexChanged.connect(self._on_setting_changed)
        disk_mount_row.addWidget(self.disk_mount_combo)
        sysmon_layout.addLayout(disk_mount_row)

        # Disk I/O device selector
        disk_dev_row = QHBoxLayout()
        disk_dev_row.addWidget(QLabel("Disk (I/O):"))
        self.disk_device_combo = NoScrollComboBox()
        self.disk_device_combo.addItem("All (aggregate)", "")
        try:
            import psutil
            for dev in sorted(psutil.disk_io_counters(perdisk=True).keys()):
                self.disk_device_combo.addItem(dev, dev)
        except Exception:
            pass
        self.disk_device_combo.currentIndexChanged.connect(self._on_setting_changed)
        disk_dev_row.addWidget(self.disk_device_combo)
        sysmon_layout.addLayout(disk_dev_row)

        # Process update interval
        proc_row = QHBoxLayout()
        proc_row.addWidget(QLabel("Process Update:"))
        self.proc_interval_spin = QSpinBox()
        self.proc_interval_spin.setRange(1, 60)
        self.proc_interval_spin.setValue(30)
        self.proc_interval_spin.setSuffix(" sec")
        self.proc_interval_spin.setFocusPolicy(Qt.StrongFocus)
        self.proc_interval_spin.valueChanged.connect(self._on_setting_changed)
        proc_row.addWidget(self.proc_interval_spin)
        proc_row.addStretch()
        sysmon_layout.addLayout(proc_row)

        sysmon_group.setLayout(sysmon_layout)
        layout.addWidget(sysmon_group)

        # 4. Mode Cycle Settings
        mode_group = QGroupBox("Display Mode Rotation")
        mode_layout = QVBoxLayout()

        mode_names = ["Hotkeys", "Clock", "Slideshow", "Standby"]
        self.mode_checks = []
        checks_row = QHBoxLayout()
        for i, name in enumerate(mode_names):
            cb = QCheckBox(name)
            cb.setProperty("mode_id", i)
            cb.stateChanged.connect(self._on_mode_cycle_changed)
            checks_row.addWidget(cb)
            self.mode_checks.append(cb)
        mode_layout.addLayout(checks_row)

        mode_layout.addWidget(QLabel("Rotation Order:"))
        self.mode_order_list = QListWidget()
        self.mode_order_list.setMaximumHeight(100)
        self.mode_order_list.setDragDropMode(QAbstractItemView.InternalMove)
        mode_layout.addWidget(self.mode_order_list)

        order_btns = QHBoxLayout()
        self.mode_up_btn = QPushButton("Move Up")
        self.mode_up_btn.clicked.connect(self._on_mode_up)
        order_btns.addWidget(self.mode_up_btn)
        self.mode_down_btn = QPushButton("Move Down")
        self.mode_down_btn.clicked.connect(self._on_mode_down)
        order_btns.addWidget(self.mode_down_btn)
        order_btns.addStretch()
        mode_layout.addLayout(order_btns)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 5. SD Card Management
        sd_group = QGroupBox("SD Card")
        sd_layout = QVBoxLayout()

        self.sd_status_label = QLabel("Connect to device first")
        self.sd_status_label.setStyleSheet("color: #888; font-size: 11px;")
        sd_layout.addWidget(self.sd_status_label)

        sd_btn_row = QHBoxLayout()
        self.sd_refresh_btn = QPushButton("Refresh")
        self.sd_refresh_btn.clicked.connect(self._on_sd_refresh)
        sd_btn_row.addWidget(self.sd_refresh_btn)
        self.sd_delete_btn = QPushButton("Delete Selected")
        self.sd_delete_btn.clicked.connect(self._on_sd_delete)
        self.sd_delete_btn.setEnabled(False)
        sd_btn_row.addWidget(self.sd_delete_btn)
        self.sd_upload_btn = QPushButton("Upload to Slideshow")
        self.sd_upload_btn.setStyleSheet(
            "QPushButton { background: #238636; color: #fff; border: 1px solid #2ea043; "
            "border-radius: 4px; padding: 4px 10px; font-size: 12px; }"
            "QPushButton:hover { background: #2ea043; }"
        )
        self.sd_upload_btn.clicked.connect(self._on_sd_upload_slideshow)
        sd_btn_row.addWidget(self.sd_upload_btn)
        sd_btn_row.addStretch()
        sd_layout.addLayout(sd_btn_row)

        from PySide6.QtWidgets import QProgressBar
        self.sd_usage_bar = QProgressBar()
        self.sd_usage_bar.setFormat("%v MB / %m MB")
        self.sd_usage_bar.setMaximumHeight(20)
        self.sd_usage_bar.setValue(0)
        self.sd_usage_bar.setMaximum(1)
        sd_layout.addWidget(self.sd_usage_bar)

        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        self.sd_tree = QTreeWidget()
        self.sd_tree.setHeaderLabels(["Name", "Size", "Type"])
        self.sd_tree.setMaximumHeight(200)
        self.sd_tree.setColumnWidth(0, 200)
        self.sd_tree.setColumnWidth(1, 80)
        self.sd_tree.itemSelectionChanged.connect(self._on_sd_selection_changed)
        sd_layout.addWidget(self.sd_tree)

        sd_group.setLayout(sd_layout)
        layout.addWidget(sd_group)

        layout.addStretch()
        self.setWidget(container)

    def load_from_config(self):
        """Populate settings from config dict."""
        self._updating = True
        ds = self.config_manager.config.get("display_settings", {})

        self.clock_24h_check.setChecked(ds.get("clock_24h", True))
        clock_color = ds.get("clock_color_theme", 0xFFFFFF)
        self._set_color_btn(self.clock_color_btn, clock_color)

        self.slideshow_interval_spin.setValue(ds.get("slideshow_interval_sec", 30))
        transition = ds.get("slideshow_transition", "fade")
        for i in range(self.transition_combo.count()):
            if self.transition_combo.itemData(i) == transition:
                self.transition_combo.setCurrentIndex(i)
                break

        self.dim_timeout_spin.setValue(ds.get("dim_timeout_sec", 60))
        self.sleep_timeout_spin.setValue(ds.get("sleep_timeout_sec", 300))
        self.wake_on_touch_check.setChecked(ds.get("wake_on_touch", True))

        # System Monitor settings (stored at config root level)
        net_iface = self.config_manager.config.get("net_interface", "") or ""
        idx = self.net_interface_combo.findData(net_iface)
        if idx >= 0:
            self.net_interface_combo.setCurrentIndex(idx)
        else:
            self.net_interface_combo.setCurrentIndex(0)

        disk_mount = self.config_manager.config.get("disk_mount", "/") or "/"
        idx = self.disk_mount_combo.findData(disk_mount)
        if idx >= 0:
            self.disk_mount_combo.setCurrentIndex(idx)
        else:
            self.disk_mount_combo.setCurrentIndex(0)

        disk_dev = self.config_manager.config.get("disk_device", "") or ""
        idx = self.disk_device_combo.findData(disk_dev)
        if idx >= 0:
            self.disk_device_combo.setCurrentIndex(idx)
        else:
            self.disk_device_combo.setCurrentIndex(0)

        self.proc_interval_spin.setValue(self.config_manager.config.get("proc_update_interval", 30))

        # Mode cycle
        mode_cycle = self.config_manager.config.get("mode_cycle", [0, 1, 2, 3])
        for cb in self.mode_checks:
            cb.setChecked(cb.property("mode_id") in mode_cycle)
        self._rebuild_mode_order_list(mode_cycle)

        self._updating = False

    def _on_setting_changed(self, *args):
        if self._updating:
            return
        self._save_to_config()
        self.settings_changed.emit()

    def _on_clock_color_clicked(self):
        current = self.clock_color_btn.property("color_value") or 0xFFFFFF
        qc = _int_to_qcolor(current)
        new_color = QColorDialog.getColor(qc, self, "Clock Color")
        if new_color.isValid():
            self._set_color_btn(self.clock_color_btn, _qcolor_to_int(new_color))
            if not self._updating:
                self._save_to_config()
                self.settings_changed.emit()

    def _set_color_btn(self, btn, color_val):
        qc = _int_to_qcolor(color_val)
        btn.setStyleSheet(f"background-color: {qc.name()}; border: 1px solid #555;")
        btn.setProperty("color_value", color_val)

    def _on_mode_cycle_changed(self, *args):
        if self._updating:
            return
        # Rebuild mode order list from checked modes
        checked = [cb.property("mode_id") for cb in self.mode_checks if cb.isChecked()]
        # Preserve existing order for modes that are still checked
        current_order = self._get_mode_order()
        new_order = [m for m in current_order if m in checked]
        # Add newly checked modes at the end
        for m in checked:
            if m not in new_order:
                new_order.append(m)
        self._rebuild_mode_order_list(new_order)
        self._save_to_config()
        self.settings_changed.emit()

    def _rebuild_mode_order_list(self, mode_cycle):
        mode_names = {0: "Hotkeys", 1: "Clock", 2: "Slideshow", 3: "Standby"}
        self.mode_order_list.clear()
        for m in mode_cycle:
            item = QListWidgetItem(mode_names.get(m, f"Mode {m}"))
            item.setData(Qt.UserRole, m)
            self.mode_order_list.addItem(item)

    def _get_mode_order(self):
        order = []
        for i in range(self.mode_order_list.count()):
            item = self.mode_order_list.item(i)
            order.append(item.data(Qt.UserRole))
        return order

    def _on_mode_up(self):
        row = self.mode_order_list.currentRow()
        if row > 0:
            item = self.mode_order_list.takeItem(row)
            self.mode_order_list.insertItem(row - 1, item)
            self.mode_order_list.setCurrentRow(row - 1)
            self._save_to_config()
            self.settings_changed.emit()

    def _on_mode_down(self):
        row = self.mode_order_list.currentRow()
        if row >= 0 and row < self.mode_order_list.count() - 1:
            item = self.mode_order_list.takeItem(row)
            self.mode_order_list.insertItem(row + 1, item)
            self.mode_order_list.setCurrentRow(row + 1)
            self._save_to_config()
            self.settings_changed.emit()

    def _save_to_config(self):
        ds = self.config_manager.config.setdefault("display_settings", {})
        ds["clock_24h"] = self.clock_24h_check.isChecked()
        ds["clock_color_theme"] = self.clock_color_btn.property("color_value") or 0xFFFFFF
        ds["slideshow_interval_sec"] = self.slideshow_interval_spin.value()
        ds["slideshow_transition"] = self.transition_combo.currentData() or "fade"
        ds["dim_timeout_sec"] = self.dim_timeout_spin.value()
        ds["sleep_timeout_sec"] = self.sleep_timeout_spin.value()
        ds["wake_on_touch"] = self.wake_on_touch_check.isChecked()
        self.config_manager.config["mode_cycle"] = self._get_mode_order()
        # System Monitor settings (config root level)
        self.config_manager.config["net_interface"] = self.net_interface_combo.currentData() or ""
        self.config_manager.config["disk_mount"] = self.disk_mount_combo.currentData() or "/"
        self.config_manager.config["disk_device"] = self.disk_device_combo.currentData() or ""
        self.config_manager.config["proc_update_interval"] = self.proc_interval_spin.value()

    # -- SD Card Management --

    def set_http_client(self, client):
        """Set the HTTP client for SD card operations."""
        self._http_client = client
        if client:
            self.sd_status_label.setText(f"Connected to {client.device_ip}")
            self.sd_status_label.setStyleSheet("color: #2ECC71; font-size: 11px;")
        else:
            self.sd_status_label.setText("Connect to device first")
            self.sd_status_label.setStyleSheet("color: #888; font-size: 11px;")

    def _on_sd_refresh(self):
        if not self._http_client:
            self.sd_status_label.setText("Not connected -- deploy config to connect")
            self.sd_status_label.setStyleSheet("color: #E74C3C; font-size: 11px;")
            return

        try:
            # Get usage
            usage = self._http_client.sd_usage()
            total = usage.get("total_mb", 0)
            used = usage.get("used_mb", 0)
            self.sd_usage_bar.setMaximum(max(total, 1))
            self.sd_usage_bar.setValue(used)
            self.sd_usage_bar.setFormat(f"{used} MB / {total} MB")

            # Get file listing
            listing = self._http_client.sd_list("/")
            self.sd_tree.clear()
            from PySide6.QtWidgets import QTreeWidgetItem
            for f in listing.get("files", []):
                name = f.get("name", "?")
                size = f.get("size", 0)
                is_dir = f.get("dir", False)
                size_str = self._format_size(size) if not is_dir else ""
                type_str = "DIR" if is_dir else "FILE"
                item = QTreeWidgetItem([name, size_str, type_str])
                item.setData(0, Qt.UserRole, f"/{name}")
                self.sd_tree.addTopLevelItem(item)

            self.sd_status_label.setText(f"Connected to {self._http_client.device_ip}")
            self.sd_status_label.setStyleSheet("color: #2ECC71; font-size: 11px;")

        except Exception as e:
            self.sd_status_label.setText(f"Error: {e}")
            self.sd_status_label.setStyleSheet("color: #E74C3C; font-size: 11px;")

    def _on_sd_selection_changed(self):
        items = self.sd_tree.selectedItems()
        self.sd_delete_btn.setEnabled(bool(items))

    def _on_sd_delete(self):
        items = self.sd_tree.selectedItems()
        if not items:
            return
        item = items[0]
        path = item.data(0, Qt.UserRole)
        if not path:
            return

        reply = QMessageBox.question(
            self, "Delete File",
            f"Delete {path} from SD card?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        if not self._http_client:
            return

        try:
            self._http_client.sd_delete(path)
            self._on_sd_refresh()  # Refresh listing
        except Exception as e:
            QMessageBox.warning(self, "Delete Failed", str(e))

    def _on_slideshow_add(self):
        """Add images to the slideshow upload queue."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images for Slideshow", "",
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.svg)"
        )
        if not files:
            return
        import os
        for f in files:
            # Avoid duplicates
            existing = [self.slideshow_pic_list.item(i).data(Qt.UserRole)
                        for i in range(self.slideshow_pic_list.count())]
            if f not in existing:
                item = QListWidgetItem(os.path.basename(f))
                item.setData(Qt.UserRole, f)
                self.slideshow_pic_list.addItem(item)
        self.slideshow_upload_btn.setEnabled(self.slideshow_pic_list.count() > 0)

    def _on_slideshow_remove(self):
        """Remove selected images from the slideshow upload queue."""
        for item in self.slideshow_pic_list.selectedItems():
            self.slideshow_pic_list.takeItem(self.slideshow_pic_list.row(item))
        self.slideshow_upload_btn.setEnabled(self.slideshow_pic_list.count() > 0)

    def _on_sd_upload_slideshow(self):
        """Rewired: opens the same slideshow upload dialog as File > Upload Pictures."""
        self._on_upload_pictures()

        # Auto-refresh file list
        if uploaded > 0:
            self._on_sd_refresh()

    @staticmethod
    def _format_size(size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"


# ============================================================
# Hardware Input Section
