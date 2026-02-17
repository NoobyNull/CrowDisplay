"""
HTTP Client: Handle communication with CrowPanel device SoftAP HTTP server

Posts config JSON to /api/config/upload endpoint with retry logic.
Parses device responses and provides error feedback.
"""

import requests
import time
from typing import Dict, Any


class HTTPClientError(Exception):
    """Custom exception for HTTP client errors"""

    pass


class HTTPClient:
    """HTTP client for device communication"""

    def __init__(self, device_ip: str = "192.168.4.1", port: int = 80, timeout: int = 10):
        self.device_ip = device_ip
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{device_ip}:{port}"

    def health_check(self) -> bool:
        """
        Check if device is reachable via /api/health endpoint.
        Returns True if device responds with 200, False otherwise.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/health",
                timeout=3,
            )
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False
        except Exception:
            return False

    def wait_for_device(self, timeout: float = 10.0, interval: float = 1.0) -> bool:
        """
        Poll health_check until device responds or timeout expires.

        Args:
            timeout: Maximum seconds to wait
            interval: Seconds between poll attempts

        Returns:
            True if device responded, False if timed out
        """
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.health_check():
                return True
            time.sleep(interval)
        return False

    def upload_config(self, json_str: str, filename: str = "config.json") -> Dict[str, Any]:
        """
        Upload config JSON to device.

        Args:
            json_str: JSON config as string
            filename: Filename for upload (default: config.json)

        Returns:
            Dict with keys:
            - "success": bool (True if device accepted and processed)
            - "error": str (error message if success=False, empty if success=True)

        Raises:
            HTTPClientError: On connection or request failure
        """
        url = f"{self.base_url}/api/config/upload"

        # Prepare multipart form-data
        files = {
            "config": (filename, json_str, "application/json"),
        }

        # Retry logic: up to 3 attempts with 5-second interval
        for attempt in range(3):
            try:
                response = requests.post(
                    url,
                    files=files,
                    timeout=self.timeout,
                )

                # Parse response
                if response.status_code == 200:
                    # Success response
                    try:
                        data = response.json()
                        return {
                            "success": data.get("success", True),
                            "error": data.get("error", ""),
                        }
                    except Exception:
                        # Assume success if 200 and no JSON
                        return {"success": True, "error": ""}

                elif response.status_code == 400:
                    # Error response
                    try:
                        data = response.json()
                        return {
                            "success": False,
                            "error": data.get("error", "Device validation failed"),
                        }
                    except Exception:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text[:100]}",
                        }

                else:
                    # Other HTTP error
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.reason}",
                    }

            except requests.Timeout:
                error_msg = f"Connection timeout (attempt {attempt + 1}/3)"
                if attempt < 2:
                    # Retry after delay
                    time.sleep(5)
                    continue
                else:
                    raise HTTPClientError(error_msg)

            except requests.ConnectionError:
                error_msg = f"Cannot reach device (attempt {attempt + 1}/3)"
                if attempt < 2:
                    # Retry after delay
                    time.sleep(5)
                    continue
                else:
                    raise HTTPClientError(error_msg)

            except Exception as e:
                raise HTTPClientError(f"Request failed: {str(e)}")

        raise HTTPClientError("Upload failed after 3 attempts")

    def upload_image(self, filename: str, data: bytes) -> Dict[str, Any]:
        """
        Upload an image file to device SD card.

        Args:
            filename: Destination filename (e.g., "calc.png")
            data: Raw image bytes (PNG)

        Returns:
            Dict with "success" and "path" or "error" keys

        Raises:
            HTTPClientError: On connection failure
        """
        url = f"{self.base_url}/api/image/upload"

        files = {
            "image": (filename, data, "image/png"),
        }

        try:
            response = requests.post(url, files=files, timeout=self.timeout)

            if response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    return {"success": True, "path": f"/icons/{filename}"}
            else:
                try:
                    return response.json()
                except Exception:
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except requests.Timeout:
            raise HTTPClientError("Image upload timeout")
        except requests.ConnectionError:
            raise HTTPClientError("Cannot reach device for image upload")
        except Exception as e:
            raise HTTPClientError(f"Image upload failed: {str(e)}")

    def sd_usage(self) -> Dict[str, Any]:
        """
        Get SD card usage stats.

        Returns:
            Dict with "total_mb", "used_mb", "free_mb" keys

        Raises:
            HTTPClientError: On connection failure
        """
        url = f"{self.base_url}/api/sd/usage"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            raise HTTPClientError("SD usage request timeout")
        except requests.ConnectionError:
            raise HTTPClientError("Cannot reach device")
        except Exception as e:
            raise HTTPClientError(f"SD usage failed: {str(e)}")

    def sd_list(self, path: str = "/") -> Dict[str, Any]:
        """
        List files in SD card directory.

        Args:
            path: Directory path on SD card (default: root)

        Returns:
            Dict with "path" and "files" keys

        Raises:
            HTTPClientError: On connection failure
        """
        url = f"{self.base_url}/api/sd/list"
        try:
            response = requests.get(url, params={"path": path}, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            raise HTTPClientError("SD list request timeout")
        except requests.ConnectionError:
            raise HTTPClientError("Cannot reach device")
        except Exception as e:
            raise HTTPClientError(f"SD list failed: {str(e)}")

    def sd_delete(self, path: str) -> Dict[str, Any]:
        """
        Delete a file from SD card.

        Args:
            path: File path on SD card to delete

        Returns:
            Dict with "success" key

        Raises:
            HTTPClientError: On connection failure or 403 (protected file)
        """
        url = f"{self.base_url}/api/sd/delete"
        try:
            response = requests.post(url, json={"path": path}, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            raise HTTPClientError("SD delete request timeout")
        except requests.ConnectionError:
            raise HTTPClientError("Cannot reach device")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                raise HTTPClientError("Cannot delete protected file (config.json)")
            raise HTTPClientError(f"SD delete failed: {str(e)}")
        except Exception as e:
            raise HTTPClientError(f"SD delete failed: {str(e)}")
