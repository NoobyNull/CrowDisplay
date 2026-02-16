"""
Deploy Dialog: Modal dialog for device connection and config upload

Shows device IP input, connection status, upload progress, and error messages.
Integrates with HTTPClient for actual device communication.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from companion.http_client import HTTPClient, HTTPClientError
from companion.config_manager import get_config_manager


class UploadWorker(QThread):
    """Worker thread for async config upload (images first, then config)"""

    upload_started = Signal()
    upload_progress = Signal(str)
    upload_success = Signal(dict)
    upload_failed = Signal(str)

    def __init__(self, device_ip: str, json_str: str, pending_images: dict = None):
        super().__init__()
        self.device_ip = device_ip
        self.json_str = json_str
        self.pending_images = pending_images or {}

    def run(self):
        """Execute upload in background thread: images first, then config"""
        self.upload_started.emit()

        try:
            client = HTTPClient(device_ip=self.device_ip)

            # Upload pending images first
            if self.pending_images:
                total = len(self.pending_images)
                for i, (widget_idx, (filename, data)) in enumerate(self.pending_images.items()):
                    self.upload_progress.emit(f"Uploading images... ({i + 1}/{total})")
                    result = client.upload_image(filename, data)
                    if not result.get("success"):
                        error_msg = result.get("error", f"Failed to upload {filename}")
                        self.upload_failed.emit(error_msg)
                        return

            # Upload config
            self.upload_progress.emit("Deploying config...")
            result = client.upload_config(self.json_str)

            if result["success"]:
                self.upload_success.emit(result)
            else:
                error_msg = result.get("error", "Unknown error")
                self.upload_failed.emit(error_msg)

        except HTTPClientError as e:
            self.upload_failed.emit(str(e))
        except Exception as e:
            self.upload_failed.emit(f"Unexpected error: {str(e)}")


class DeployDialog(QDialog):
    """Modal dialog for device deployment"""

    def __init__(self, config_manager, parent=None, pending_images=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.pending_images = pending_images or {}
        self.upload_worker = None
        self.setWindowTitle("Deploy to Device")
        self.setMinimumWidth(400)
        self.setModal(True)

        # Device IP input
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel("Device IP:"))
        self.ip_input = QLineEdit()
        self.ip_input.setText("192.168.4.1")
        ip_layout.addWidget(self.ip_input)

        # Test connection button
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._on_test_connection)
        ip_layout.addWidget(self.test_btn)

        # Status label
        self.status_label = QLabel("(not connected)")
        self.status_label.setStyleSheet("color: #888888;")

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)

        # Deploy button
        self.deploy_btn = QPushButton("Deploy")
        self.deploy_btn.setMinimumHeight(40)
        self.deploy_btn.setEnabled(False)
        self.deploy_btn.setStyleSheet("background-color: #2ECC71; color: white; font-weight: bold;")
        self.deploy_btn.clicked.connect(self._on_deploy)

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        # Buttons layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.deploy_btn)
        button_layout.addWidget(self.cancel_btn)

        # Main layout
        layout = QVBoxLayout(self)
        layout.addLayout(ip_layout)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _on_test_connection(self):
        """Test connection to device"""
        device_ip = self.ip_input.text().strip()
        if not device_ip:
            self.status_label.setText("❌ Enter device IP")
            self.status_label.setStyleSheet("color: #CC0000;")
            self.deploy_btn.setEnabled(False)
            return

        self.test_btn.setEnabled(False)
        self.status_label.setText("Testing connection...")
        self.status_label.setStyleSheet("color: #0077FF;")

        try:
            client = HTTPClient(device_ip=device_ip)
            if client.health_check():
                self.status_label.setText("✓ Connected to device")
                self.status_label.setStyleSheet("color: #00AA00;")
                self.deploy_btn.setEnabled(True)
            else:
                self.status_label.setText("✗ Cannot reach device")
                self.status_label.setStyleSheet("color: #CC0000;")
                self.deploy_btn.setEnabled(False)
        except Exception as e:
            self.status_label.setText(f"✗ Error: {str(e)}")
            self.status_label.setStyleSheet("color: #CC0000;")
            self.deploy_btn.setEnabled(False)
        finally:
            self.test_btn.setEnabled(True)

    def _on_deploy(self):
        """Deploy config to device"""
        device_ip = self.ip_input.text().strip()
        json_str = self.config_manager.to_json()

        # Start upload in worker thread (images + config)
        self.upload_worker = UploadWorker(device_ip, json_str, self.pending_images)
        self.upload_worker.upload_started.connect(self._on_upload_started)
        self.upload_worker.upload_progress.connect(self._on_upload_progress)
        self.upload_worker.upload_success.connect(self._on_upload_success)
        self.upload_worker.upload_failed.connect(self._on_upload_failed)
        self.upload_worker.start()

    def _on_upload_started(self):
        """Upload started"""
        self.deploy_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Uploading...")
        self.status_label.setStyleSheet("color: #0077FF;")

    def _on_upload_progress(self, message: str):
        """Upload progress update"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #0077FF;")

    def _on_upload_success(self, result: dict):
        """Upload succeeded"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("✓ Config deployed! Device rebuilding UI...")
        self.status_label.setStyleSheet("color: #00AA00;")

        # Show success message and close in 2 seconds
        QMessageBox.information(
            self,
            "Deployment Successful",
            "Config has been uploaded to the device.\n\nThe device will rebuild its UI to match the new layout.",
        )
        self.accept()

    def _on_upload_failed(self, error_msg: str):
        """Upload failed"""
        self.progress_bar.setVisible(False)
        self.deploy_btn.setEnabled(True)
        self.status_label.setText(f"✗ Upload failed")
        self.status_label.setStyleSheet("color: #CC0000;")

        QMessageBox.critical(
            self,
            "Deployment Failed",
            f"Failed to upload config:\n\n{error_msg}\n\nCheck device IP and try again.",
        )
