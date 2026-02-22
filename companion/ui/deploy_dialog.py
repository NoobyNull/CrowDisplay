"""
Deploy Dialog: One-click deploy via USB bridge + WiFi auto-connect.

Orchestrates the full deploy sequence:
1. Open bridge USB HID
2. Send CONFIG_MODE (display starts SoftAP)
3. Connect PC WiFi to CrowPanel-Config
4. Wait for device HTTP health check
5. Upload images (if any)
6. Upload config JSON
7. Send CONFIG_DONE (display reloads, exits AP)
8. Restore previous WiFi
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QMessageBox,
)
from PySide6.QtCore import QThread, Signal

from companion.http_client import HTTPClient, HTTPClientError
from companion.bridge_device import BridgeDevice, BridgeDeviceError
from companion.wifi_manager import WiFiManager, WiFiManagerError

import json
import os
import time
import logging

logger = logging.getLogger(__name__)


def _resolve_deploy_images(config):
    """Walk all widgets, resolve icon_source → system path, optimize to PNG bytes.

    Returns dict of {filename: png_bytes} and a modified config dict with icon_path set.
    The original config dict is not modified.
    """
    import copy
    from companion.image_optimizer import optimize_for_widget

    deploy_config = copy.deepcopy(config)
    images = {}

    for profile in deploy_config.get("profiles", []):
        for page in profile.get("pages", []):
            for widget in page.get("widgets", []):
                icon_source = widget.get("icon_source", "")
                icon_source_type = widget.get("icon_source_type", "")
                if not icon_source or not icon_source_type:
                    widget.pop("icon_path", None)
                    continue

                # Resolve to filesystem path
                source_path = None
                if icon_source_type == "file":
                    source_path = icon_source if os.path.exists(icon_source) else None
                elif icon_source_type == "freedesktop":
                    from companion.app_scanner import _resolve_icon_path, _get_icon_theme
                    source_path = _resolve_icon_path(icon_source, _get_icon_theme()) or None

                if not source_path:
                    logger.warning("Icon source not found: %s (%s)", icon_source, icon_source_type)
                    widget.pop("icon_path", None)
                    continue

                # Generate safe filename
                base = os.path.splitext(os.path.basename(icon_source))[0] or icon_source
                safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
                filename = f"{safe_name}.png"

                # Optimize at full widget size
                try:
                    w = widget.get("width", 180)
                    h = widget.get("height", 100)
                    has_label = widget.get("show_label", True) and bool(widget.get("label", ""))
                    png_data = optimize_for_widget(source_path, w, h, has_label=has_label)
                    images[filename] = png_data
                    widget["icon_path"] = f"/icons/{filename}"
                except Exception as e:
                    logger.warning("Failed to optimize icon %s: %s", source_path, e)
                    widget.pop("icon_path", None)

    # Resolve page background images (separate dict — uploaded to /bkgnds/)
    bg_images = {}
    for profile in deploy_config.get("profiles", []):
        for page in profile.get("pages", []):
            bg_src = page.get("bg_image", "")
            if not bg_src or not os.path.exists(bg_src):
                page.pop("bg_image", None)
                continue
            base = os.path.splitext(os.path.basename(bg_src))[0]
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
            filename = f"bg_{safe_name}.sjpg"
            try:
                from companion.image_optimizer import optimize_for_sjpg
                sjpg_data = optimize_for_sjpg(bg_src)
                bg_images[filename] = sjpg_data
                page["bg_image"] = f"/bkgnds/{filename}"
            except Exception as e:
                logger.warning("Failed to optimize bg image %s: %s", bg_src, e)
                page.pop("bg_image", None)

    return images, bg_images, deploy_config

# Deploy step definitions: (key, label)
DEPLOY_STEPS = [
    ("bridge", "Open bridge USB connection"),
    ("config_mode", "Signal display to enter config mode"),
    ("ap_wait", "Wait for AP startup"),
    ("wifi_connect", "Connect WiFi to CrowPanel-Config"),
    ("health", "Wait for device to respond"),
    ("images", "Upload images"),
    ("config", "Upload configuration"),
    ("config_done", "Signal display to reload"),
    ("wifi_restore", "Restore previous WiFi"),
]


class DeployWorker(QThread):
    """Worker thread that orchestrates the full deploy sequence."""

    step_started = Signal(str)   # step key
    step_done = Signal(str)      # step key
    deploy_success = Signal()
    deploy_warning = Signal(str) # non-fatal warning message
    deploy_failed = Signal(str)  # error message

    def __init__(self, config_manager):
        super().__init__()
        # Resolve icons and bg images at deploy time from system sources
        images, bg_images, deploy_config = _resolve_deploy_images(config_manager.config)
        self.json_str = json.dumps(deploy_config, indent=2)
        self.pending_images = images      # {filename: png_bytes} → /icons/
        self.pending_bg_images = bg_images  # {filename: png_bytes} → /bkgnds/
        self._bridge = None
        self._wifi = None

    def run(self):
        """Execute full deploy sequence with error recovery."""
        self._bridge = BridgeDevice()
        self._wifi = WiFiManager()

        try:
            # 1. Open bridge
            self.step_started.emit("bridge")
            self._bridge.open()
            self.step_done.emit("bridge")

            # 2. Send CONFIG_MODE
            self.step_started.emit("config_mode")
            self._bridge.send_config_mode()
            self.step_done.emit("config_mode")

            # 3. Wait for AP startup
            self.step_started.emit("ap_wait")
            time.sleep(3)
            self.step_done.emit("ap_wait")

            # 4. Connect WiFi
            self.step_started.emit("wifi_connect")
            self._wifi.connect_to_crowpanel(timeout=15)
            self.step_done.emit("wifi_connect")

            # 5. Wait for device health
            self.step_started.emit("health")
            client = HTTPClient()
            if not client.wait_for_device(timeout=10, interval=1):
                raise HTTPClientError("Device not responding after WiFi connect")
            self.step_done.emit("health")

            # 6. Upload images (non-fatal: warn but continue if upload fails)
            self.step_started.emit("images")
            image_warnings = []
            if self.pending_images:
                for filename, data in self.pending_images.items():
                    try:
                        result = client.upload_image(filename, data)
                        if not result.get("success"):
                            image_warnings.append(f"{filename}: {result.get('error', 'unknown')}")
                    except Exception as e:
                        image_warnings.append(f"{filename}: {e}")
            if self.pending_bg_images:
                for filename, data in self.pending_bg_images.items():
                    try:
                        result = client.sd_upload_image(filename, data, folder="bkgnds")
                        if not result.get("success"):
                            image_warnings.append(f"bg/{filename}: {result.get('error', 'unknown')}")
                    except Exception as e:
                        image_warnings.append(f"bg/{filename}: {e}")
            self.step_done.emit("images")

            # 7. Upload config
            self.step_started.emit("config")
            result = client.upload_config(self.json_str)
            if not result.get("success"):
                raise HTTPClientError(
                    result.get("error", "Config upload rejected by device")
                )
            self.step_done.emit("config")

            # 8. Send CONFIG_DONE
            self.step_started.emit("config_done")
            self._bridge.send_config_done()
            self.step_done.emit("config_done")

            # 9. Restore WiFi
            self.step_started.emit("wifi_restore")
            self._wifi.restore_previous_wifi()
            self.step_done.emit("wifi_restore")

            self.deploy_success.emit()
            if image_warnings:
                warn_msg = "Some icons failed to upload:\n" + "\n".join(image_warnings)
                self.deploy_warning.emit(warn_msg)

        except (BridgeDeviceError, WiFiManagerError, HTTPClientError) as e:
            self._cleanup()
            self.deploy_failed.emit(str(e))
        except Exception as e:
            self._cleanup()
            self.deploy_failed.emit(f"Unexpected error: {e}")

    def _cleanup(self):
        """Best-effort cleanup: send CONFIG_DONE and restore WiFi."""
        try:
            if self._bridge:
                self._bridge.send_config_done()
        except Exception:
            pass
        try:
            if self._wifi:
                self._wifi.restore_previous_wifi()
        except Exception:
            pass
        try:
            if self._bridge:
                self._bridge.close()
        except Exception:
            pass


class StepLabel(QLabel):
    """A step indicator label with status icon."""

    PENDING = 0
    ACTIVE = 1
    DONE = 2
    ERROR = 3

    _STYLES = {
        PENDING: "color: #666666;",
        ACTIVE:  "color: #3498DB; font-weight: bold;",
        DONE:    "color: #2ECC71;",
        ERROR:   "color: #E74C3C;",
    }
    _ICONS = {
        PENDING: "  ",
        ACTIVE:  "  ",
        DONE:    "  ",
        ERROR:   "  ",
    }

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self._state = self.PENDING
        self._update()

    def set_state(self, state: int):
        self._state = state
        self._update()

    def _update(self):
        icon = self._ICONS.get(self._state, "  ")
        self.setText(f"{icon}{self._text}")
        self.setStyleSheet(self._STYLES.get(self._state, ""))


class DeployDialog(QDialog):
    """One-click deploy dialog with step-by-step progress."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.deploy_worker = None
        self.setWindowTitle("Deploy to Device")
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("One-Click Deploy")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #3498DB;")
        layout.addWidget(header)

        desc = QLabel("Deploys config via USB bridge + WiFi auto-connect.")
        desc.setStyleSheet("color: #999999; margin-bottom: 8px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Step labels
        self.step_labels: dict[str, StepLabel] = {}
        for key, label in DEPLOY_STEPS:
            sl = StepLabel(label)
            self.step_labels[key] = sl
            layout.addWidget(sl)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status message
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888888; margin-top: 4px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.deploy_btn = QPushButton("Deploy")
        self.deploy_btn.setMinimumHeight(40)
        self.deploy_btn.setStyleSheet(
            "background-color: #2ECC71; color: white; font-weight: bold; "
            "padding: 8px 32px; border-radius: 4px;"
        )
        self.deploy_btn.clicked.connect(self._on_deploy)
        button_layout.addWidget(self.deploy_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _on_deploy(self):
        """Start the deploy sequence."""
        self.deploy_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Starting deploy...")
        self.status_label.setStyleSheet("color: #3498DB;")

        # Reset all steps to pending
        for sl in self.step_labels.values():
            sl.set_state(StepLabel.PENDING)

        self.deploy_worker = DeployWorker(self.config_manager)
        self.deploy_worker.step_started.connect(self._on_step_started)
        self.deploy_worker.step_done.connect(self._on_step_done)
        self.deploy_worker.deploy_success.connect(self._on_success)
        self.deploy_worker.deploy_warning.connect(self._on_warning)
        self.deploy_worker.deploy_failed.connect(self._on_failed)
        self.deploy_worker.start()

    def _on_step_started(self, key: str):
        """Mark step as active."""
        if key in self.step_labels:
            self.step_labels[key].set_state(StepLabel.ACTIVE)

    def _on_step_done(self, key: str):
        """Mark step as done."""
        if key in self.step_labels:
            self.step_labels[key].set_state(StepLabel.DONE)

    def _on_success(self):
        """Deploy completed successfully."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Deploy complete!")
        self.status_label.setStyleSheet("color: #2ECC71; font-weight: bold;")

        QMessageBox.information(
            self,
            "Deployment Successful",
            "Config deployed to device.\nThe display will rebuild its UI.",
        )
        self.accept()

    def _on_warning(self, warn_msg: str):
        """Deploy succeeded but with warnings."""
        self.status_label.setText(f"Warning: {warn_msg}")
        self.status_label.setStyleSheet("color: #F39C12;")
        # Mark image step as warning (use DONE style, not error)
        if "images" in self.step_labels:
            self.step_labels["images"].set_state(StepLabel.DONE)

    def _on_failed(self, error_msg: str):
        """Deploy failed."""
        self.progress_bar.setVisible(False)
        self.deploy_btn.setEnabled(True)
        self.status_label.setText(f"Failed: {error_msg}")
        self.status_label.setStyleSheet("color: #E74C3C;")

        # Mark any active steps as error
        for sl in self.step_labels.values():
            if sl._state == StepLabel.ACTIVE:
                sl.set_state(StepLabel.ERROR)

        QMessageBox.critical(
            self,
            "Deployment Failed",
            f"Deploy failed:\n\n{error_msg}",
        )
