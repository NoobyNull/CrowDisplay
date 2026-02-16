"""
WiFi Manager: Automate WiFi switching via nmcli for one-click deploy.

Saves current SSID, connects to CrowPanel-Config AP, and restores
previous WiFi after deploy completes.
"""

import subprocess
import time
import logging

logger = logging.getLogger(__name__)

CROWPANEL_SSID = "CrowPanel-Config"


class WiFiManagerError(Exception):
    """Raised when WiFi operations fail."""
    pass


class WiFiManager:
    """Wraps nmcli for WiFi network switching."""

    def __init__(self):
        self._previous_ssid: str | None = None

    def get_current_ssid(self) -> str | None:
        """Return the currently connected WiFi SSID, or None."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().splitlines():
                if line.startswith("yes:"):
                    return line.split(":", 1)[1]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug("get_current_ssid failed: %s", e)
        return None

    def wait_for_ap(self, timeout: float = 15.0) -> bool:
        """Rescan WiFi and wait until CrowPanel-Config AP is visible.

        Returns True if found, False if timed out.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                # Force a rescan
                subprocess.run(
                    ["nmcli", "dev", "wifi", "rescan"],
                    capture_output=True, timeout=5,
                )
                time.sleep(1)
                # List visible SSIDs
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "ssid", "dev", "wifi", "list"],
                    capture_output=True, text=True, timeout=5,
                )
                ssids = result.stdout.strip().splitlines()
                if CROWPANEL_SSID in ssids:
                    logger.info("AP '%s' found in scan results", CROWPANEL_SSID)
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                logger.debug("WiFi scan failed: %s", e)
            time.sleep(1)
        return False

    def connect_to_crowpanel(self, timeout: float = 15.0) -> None:
        """Save current SSID and connect to CrowPanel-Config AP.

        Raises WiFiManagerError if connection fails within timeout.
        """
        self._previous_ssid = self.get_current_ssid()
        logger.info("Saved previous SSID: %s", self._previous_ssid)

        # Wait for AP to appear in scan results
        if not self.wait_for_ap(timeout=15):
            raise WiFiManagerError(
                f"'{CROWPANEL_SSID}' not found. Display may not have entered config mode."
            )

        # Try connecting (nmcli will create a connection profile if needed)
        try:
            result = subprocess.run(
                ["nmcli", "dev", "wifi", "connect", CROWPANEL_SSID],
                capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip()
                raise WiFiManagerError(
                    f"nmcli connect failed: {stderr}"
                )
        except subprocess.TimeoutExpired:
            raise WiFiManagerError(
                f"WiFi connect to {CROWPANEL_SSID} timed out after {timeout}s"
            )
        except FileNotFoundError:
            raise WiFiManagerError(
                "nmcli not found. Install NetworkManager or connect manually."
            )

        # Poll until connected (nmcli connect is usually synchronous, but verify)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = self.get_current_ssid()
            if current == CROWPANEL_SSID:
                logger.info("Connected to %s", CROWPANEL_SSID)
                return
            time.sleep(0.5)

        raise WiFiManagerError(
            f"Connected to {CROWPANEL_SSID} but SSID verification timed out"
        )

    def restore_previous_wifi(self) -> None:
        """Reconnect to the previously saved SSID.

        Best-effort: logs warnings but does not raise on failure.
        """
        if not self._previous_ssid:
            logger.info("No previous SSID to restore")
            return

        ssid = self._previous_ssid
        self._previous_ssid = None
        logger.info("Restoring WiFi to: %s", ssid)

        try:
            result = subprocess.run(
                ["nmcli", "con", "up", ssid],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                logger.warning("WiFi restore failed: %s", result.stderr.strip())
            else:
                logger.info("WiFi restored to %s", ssid)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.warning("WiFi restore error: %s", e)

    @property
    def previous_ssid(self) -> str | None:
        return self._previous_ssid
