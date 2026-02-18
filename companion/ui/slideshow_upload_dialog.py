"""
Slideshow Upload Dialog: One-click picture upload via USB bridge + WiFi auto-connect.

Orchestrates the same sequence as deploy:
1. Open bridge USB HID
2. Send CONFIG_MODE (display starts SoftAP)
3. Wait for AP startup
4. Connect PC WiFi to CrowPanel-Config
5. Wait for device HTTP health check
6. Upload optimized SJPG images to /pictures/
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
from companion.ui.deploy_dialog import StepLabel

import os
import time
import logging

logger = logging.getLogger(__name__)

UPLOAD_STEPS = [
    ("bridge", "Open bridge USB connection"),
    ("config_mode", "Signal display to enter config mode"),
    ("ap_wait", "Wait for AP startup"),
    ("wifi_connect", "Connect WiFi to CrowPanel-Config"),
    ("health", "Wait for device to respond"),
    ("upload", "Upload pictures"),
    ("config_done", "Signal display to reload"),
    ("wifi_restore", "Restore previous WiFi"),
]


class SlideshowUploadWorker(QThread):
    """Worker thread that orchestrates the full slideshow upload sequence."""

    step_started = Signal(str)    # step key
    step_done = Signal(str)       # step key
    upload_progress = Signal(int, int)  # (current, total)
    upload_success = Signal()
    upload_failed = Signal(str)   # error message

    def __init__(self, file_paths: list[str]):
        super().__init__()
        self._file_paths = file_paths
        self._bridge = None
        self._wifi = None

    def run(self):
        """Execute full upload sequence with error recovery."""
        from companion.image_optimizer import optimize_for_slideshow

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

            # 6. Upload images
            self.step_started.emit("upload")
            total = len(self._file_paths)
            errors = []
            for i, path in enumerate(self._file_paths):
                self.upload_progress.emit(i + 1, total)
                basename = os.path.basename(path)
                name_root = os.path.splitext(basename)[0]
                dest_name = name_root + ".sjpg"

                try:
                    data = optimize_for_slideshow(path)
                    result = client.sd_upload_image(dest_name, data, folder="pictures")
                    if not result.get("success"):
                        errors.append(f"{basename}: {result.get('error', 'unknown')}")
                except Exception as e:
                    errors.append(f"{basename}: {e}")

            self.step_done.emit("upload")

            # 7. Send CONFIG_DONE
            self.step_started.emit("config_done")
            self._bridge.send_config_done()
            self.step_done.emit("config_done")

            # 8. Restore WiFi
            self.step_started.emit("wifi_restore")
            self._wifi.restore_previous_wifi()
            self.step_done.emit("wifi_restore")

            if errors:
                err_msg = f"Uploaded {total - len(errors)}/{total} images.\nFailed:\n" + "\n".join(errors)
                self.upload_failed.emit(err_msg)
            else:
                self.upload_success.emit()

        except (BridgeDeviceError, WiFiManagerError, HTTPClientError) as e:
            self._cleanup()
            self.upload_failed.emit(str(e))
        except Exception as e:
            self._cleanup()
            self.upload_failed.emit(f"Unexpected error: {e}")

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


class SlideshowUploadDialog(QDialog):
    """One-click slideshow upload dialog with step-by-step progress."""

    def __init__(self, file_paths: list[str], parent=None):
        super().__init__(parent)
        self._file_paths = file_paths
        self._worker = None
        self.setWindowTitle("Upload Pictures to Slideshow")
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Upload Pictures")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #3498DB;")
        layout.addWidget(header)

        desc = QLabel(f"Uploading {len(file_paths)} image(s) via USB bridge + WiFi auto-connect.")
        desc.setStyleSheet("color: #999999; margin-bottom: 8px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Step labels
        self.step_labels: dict[str, StepLabel] = {}
        for key, label in UPLOAD_STEPS:
            sl = StepLabel(label)
            self.step_labels[key] = sl
            layout.addWidget(sl)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(file_paths))
        self.progress_bar.setValue(0)
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

        self.upload_btn = QPushButton("Upload")
        self.upload_btn.setMinimumHeight(40)
        self.upload_btn.setStyleSheet(
            "background-color: #2ECC71; color: white; font-weight: bold; "
            "padding: 8px 32px; border-radius: 4px;"
        )
        self.upload_btn.clicked.connect(self._on_upload)
        button_layout.addWidget(self.upload_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _on_upload(self):
        """Start the upload sequence."""
        self.upload_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting upload...")
        self.status_label.setStyleSheet("color: #3498DB;")

        for sl in self.step_labels.values():
            sl.set_state(StepLabel.PENDING)

        self._worker = SlideshowUploadWorker(self._file_paths)
        self._worker.step_started.connect(self._on_step_started)
        self._worker.step_done.connect(self._on_step_done)
        self._worker.upload_progress.connect(self._on_upload_progress)
        self._worker.upload_success.connect(self._on_success)
        self._worker.upload_failed.connect(self._on_failed)
        self._worker.start()

    def _on_step_started(self, key: str):
        if key in self.step_labels:
            self.step_labels[key].set_state(StepLabel.ACTIVE)

    def _on_step_done(self, key: str):
        if key in self.step_labels:
            self.step_labels[key].set_state(StepLabel.DONE)

    def _on_upload_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Uploading image {current}/{total}...")

    def _on_success(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("Upload complete!")
        self.status_label.setStyleSheet("color: #2ECC71; font-weight: bold;")

        QMessageBox.information(
            self,
            "Upload Successful",
            f"Uploaded {len(self._file_paths)} picture(s) to device.",
        )
        self.accept()

    def _on_failed(self, error_msg: str):
        self.progress_bar.setVisible(False)
        self.upload_btn.setEnabled(True)
        self.status_label.setText(f"Failed: {error_msg}")
        self.status_label.setStyleSheet("color: #E74C3C;")

        for sl in self.step_labels.values():
            if sl._state == StepLabel.ACTIVE:
                sl.set_state(StepLabel.ERROR)

        QMessageBox.critical(
            self,
            "Upload Failed",
            f"Upload failed:\n\n{error_msg}",
        )
