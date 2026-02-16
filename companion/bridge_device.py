"""
Bridge Device: USB HID interface for sending commands to the ESP32-S3 bridge.

Reuses discovery logic from hotkey_companion.py. Provides a context manager
for safe open/close and methods to send CONFIG_MODE and CONFIG_DONE messages.
"""

import logging

logger = logging.getLogger(__name__)

VENDOR_ID = 0x303A
PRODUCT_ID = 0x1001
PRODUCT_STRING = "HotkeyBridge"

# Message types (must match shared/protocol.h)
MSG_CONFIG_MODE = 0x09
MSG_CONFIG_DONE = 0x0A


class BridgeDeviceError(Exception):
    """Raised when bridge operations fail."""
    pass


class BridgeDevice:
    """USB HID interface to the HotkeyBridge ESP32-S3."""

    def __init__(self):
        self._device = None

    def open(self) -> None:
        """Find and open the HotkeyBridge USB HID device.

        Raises BridgeDeviceError if bridge is not found or cannot be opened.
        """
        try:
            import hid
        except ImportError:
            raise BridgeDeviceError(
                "hidapi not installed. Install with: pip install hidapi"
            )

        devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)

        vendor_path = None
        fallback_path = None

        for dev in devices:
            product = dev.get("product_string", "")
            usage_page = dev.get("usage_page", 0)
            path = dev.get("path", b"")

            if product != PRODUCT_STRING:
                continue

            if usage_page >= 0xFF00:
                vendor_path = path
            elif fallback_path is None:
                fallback_path = path

        chosen = vendor_path or fallback_path
        if not chosen:
            raise BridgeDeviceError(
                "Bridge not found. Is it plugged in via USB?"
            )

        try:
            self._device = hid.Device(path=chosen)
            logger.info("Bridge opened: %s", chosen)
        except Exception as e:
            raise BridgeDeviceError(f"Failed to open bridge: {e}")

    def close(self) -> None:
        """Close the HID device."""
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None

    def send_config_mode(self) -> None:
        """Send MSG_CONFIG_MODE to put display into SoftAP config mode."""
        self._send(MSG_CONFIG_MODE)
        logger.info("Sent CONFIG_MODE to bridge")

    def send_config_done(self) -> None:
        """Send MSG_CONFIG_DONE to reload config and exit AP mode."""
        self._send(MSG_CONFIG_DONE)
        logger.info("Sent CONFIG_DONE to bridge")

    def _send(self, msg_type: int) -> None:
        """Send a zero-payload message to the bridge.

        Packet format: [0x00 report ID] [msg_type] [0-pad to 64 bytes]
        Must be padded to full 64-byte report for USBHIDVendor to receive it.
        """
        if not self._device:
            raise BridgeDeviceError("Bridge not open")
        try:
            buf = bytearray(64)
            buf[0] = 0x06   # HID report ID for vendor interface
            buf[1] = msg_type
            self._device.write(bytes(buf))
        except (IOError, OSError) as e:
            raise BridgeDeviceError(f"HID write failed: {e}")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
