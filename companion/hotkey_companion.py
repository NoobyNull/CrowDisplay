#!/usr/bin/env python3
"""
Hotkey Bridge Companion - System Stats Streamer

Collects live system metrics (CPU, RAM, GPU, temps, network, disk) and
streams them to the HotkeyBridge ESP32-S3 over USB HID output reports
at 1 Hz. The bridge relays these stats to the CrowPanel display via
ESP-NOW for rendering in the stats header bar.

Usage:
    python3 hotkey_companion.py          # Run directly
    systemctl --user start hotkey-companion  # Run as service

Dependencies:
    pip install hidapi psutil pynvml
"""

import hid
import psutil
import struct
import time
import sys
import signal
import logging
import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VENDOR_ID = 0x303A          # Espressif
PRODUCT_ID = 0x0002         # Default ESP32-S3 TinyUSB
PRODUCT_STRING = "HotkeyBridge"
UPDATE_INTERVAL = 1.0       # Seconds between stat reports (1 Hz)

# Matches StatsPayload in shared/protocol.h:
#   uint8  cpu_percent
#   uint8  ram_percent
#   uint8  gpu_percent     (0xFF = unavailable)
#   uint8  cpu_temp        (0xFF = unavailable)
#   uint8  gpu_temp        (0xFF = unavailable)
#   uint8  disk_percent
#   uint16 net_up_kbps     (little-endian)
#   uint16 net_down_kbps   (little-endian)
STATS_FORMAT = "<BBBBBBhh"  # 6 x uint8 + 2 x int16 = 10 bytes

# Retry interval when bridge is not found
RETRY_INTERVAL = 5.0

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

running = True

# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def _signal_handler(signum, frame):
    global running
    logging.info("Received signal %d, shutting down...", signum)
    running = False


# ---------------------------------------------------------------------------
# GPU stats collector
# ---------------------------------------------------------------------------

class GPUCollector:
    """Collects GPU utilization and temperature.

    Tries NVIDIA (pynvml) first, then AMD (sysfs). If neither is
    available, returns 0xFF for both metrics.
    """

    def __init__(self):
        self.gpu_type = None  # 'nvidia', 'amd', or None
        self._nvml_handle = None
        self._amd_gpu_busy_path = None
        self._amd_temp_path = None
        self._init_nvidia()
        if self.gpu_type is None:
            self._init_amd()
        if self.gpu_type is None:
            logging.info("No GPU detected -- gpu_percent and gpu_temp will be 0xFF")

    def _init_nvidia(self):
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(self._nvml_handle)
            if isinstance(name, bytes):
                name = name.decode()
            logging.info("NVIDIA GPU detected: %s", name)
            self.gpu_type = "nvidia"
        except ImportError:
            logging.debug("pynvml not installed, skipping NVIDIA")
        except Exception as exc:
            logging.debug("NVIDIA init failed: %s", exc)

    def _init_amd(self):
        gpu_busy = "/sys/class/drm/card0/device/gpu_busy_percent"
        if os.path.isfile(gpu_busy):
            self._amd_gpu_busy_path = gpu_busy
            # Find hwmon temperature file
            hwmon_base = "/sys/class/drm/card0/device/hwmon"
            if os.path.isdir(hwmon_base):
                for entry in os.listdir(hwmon_base):
                    temp_path = os.path.join(hwmon_base, entry, "temp1_input")
                    if os.path.isfile(temp_path):
                        self._amd_temp_path = temp_path
                        break
            logging.info("AMD GPU detected (sysfs)")
            self.gpu_type = "amd"

    def collect(self):
        """Return (gpu_percent, gpu_temp) as ints. 0xFF if unavailable."""
        if self.gpu_type == "nvidia":
            return self._collect_nvidia()
        elif self.gpu_type == "amd":
            return self._collect_amd()
        return (0xFF, 0xFF)

    def _collect_nvidia(self):
        try:
            import pynvml
            util = pynvml.nvmlDeviceGetUtilizationRates(self._nvml_handle)
            temp = pynvml.nvmlDeviceGetTemperature(
                self._nvml_handle, pynvml.NVML_TEMPERATURE_GPU
            )
            return (min(int(util.gpu), 100), min(int(temp), 254))
        except Exception as exc:
            logging.debug("NVIDIA read failed: %s", exc)
            return (0xFF, 0xFF)

    def _collect_amd(self):
        gpu_percent = 0xFF
        gpu_temp = 0xFF
        try:
            with open(self._amd_gpu_busy_path) as f:
                gpu_percent = min(int(f.read().strip()), 100)
        except Exception:
            pass
        if self._amd_temp_path:
            try:
                with open(self._amd_temp_path) as f:
                    # sysfs reports millidegrees
                    gpu_temp = min(int(f.read().strip()) // 1000, 254)
            except Exception:
                pass
        return (gpu_percent, gpu_temp)


# ---------------------------------------------------------------------------
# Bridge discovery
# ---------------------------------------------------------------------------

def find_bridge():
    """Scan for the HotkeyBridge USB HID device.

    Returns the device path (bytes) of the vendor-defined HID interface,
    or None if no bridge is found.
    """
    devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    if not devices:
        logging.debug("No devices found with VID=0x%04X PID=0x%04X", VENDOR_ID, PRODUCT_ID)
        return None

    logging.debug("Found %d HID interface(s) for VID=0x%04X PID=0x%04X:",
                  len(devices), VENDOR_ID, PRODUCT_ID)

    vendor_path = None
    fallback_path = None

    for dev in devices:
        product = dev.get("product_string", "")
        usage_page = dev.get("usage_page", 0)
        path = dev.get("path", b"")
        logging.debug("  path=%s product=%s usage_page=0x%04X usage=0x%04X",
                      path, product, usage_page, dev.get("usage", 0))

        if product != PRODUCT_STRING:
            continue

        # Prefer the vendor-defined usage page (0xFF00+)
        if usage_page >= 0xFF00:
            vendor_path = path
        elif fallback_path is None:
            fallback_path = path

    chosen = vendor_path or fallback_path
    if chosen:
        logging.info("Bridge found at path: %s", chosen)
    else:
        logging.debug("No matching product string '%s' found", PRODUCT_STRING)
    return chosen


# ---------------------------------------------------------------------------
# CPU temperature
# ---------------------------------------------------------------------------

def get_cpu_temp():
    """Read CPU temperature from psutil. Returns int Celsius or 0xFF."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return 0xFF
        for name in ("coretemp", "k10temp", "zenpower", "acpitz"):
            if name in temps:
                entries = temps[name]
                if entries:
                    return min(int(entries[0].current), 254)
        # Fall back to first available sensor
        for sensor_list in temps.values():
            if sensor_list:
                return min(int(sensor_list[0].current), 254)
    except Exception:
        pass
    return 0xFF


# ---------------------------------------------------------------------------
# Stats collection
# ---------------------------------------------------------------------------

def collect_stats(gpu_collector, prev_net, prev_time):
    """Collect system metrics and pack into StatsPayload bytes.

    Returns (packed_bytes, current_net_counters, current_time).
    """
    now = time.time()
    dt = now - prev_time
    if dt <= 0:
        dt = 1.0  # Avoid division by zero on first call

    # CPU (interval=None uses the cached value from previous psutil call)
    try:
        cpu_percent = min(int(psutil.cpu_percent(interval=None)), 100)
    except Exception:
        cpu_percent = 0

    # RAM
    try:
        ram_percent = min(int(psutil.virtual_memory().percent), 100)
    except Exception:
        ram_percent = 0

    # GPU
    gpu_percent, gpu_temp = gpu_collector.collect()

    # CPU temperature
    cpu_temp = get_cpu_temp()

    # Disk
    try:
        disk_percent = min(int(psutil.disk_usage("/").percent), 100)
    except Exception:
        disk_percent = 0

    # Network delta (KB/s)
    try:
        curr_net = psutil.net_io_counters()
        net_up_kbps = int((curr_net.bytes_sent - prev_net.bytes_sent) / dt / 1024)
        net_down_kbps = int((curr_net.bytes_recv - prev_net.bytes_recv) / dt / 1024)
        # Clamp to int16 range (struct format uses signed h, but values are positive)
        net_up_kbps = max(0, min(net_up_kbps, 32767))
        net_down_kbps = max(0, min(net_down_kbps, 32767))
    except Exception:
        curr_net = prev_net
        net_up_kbps = 0
        net_down_kbps = 0

    packed = struct.pack(
        STATS_FORMAT,
        cpu_percent,
        ram_percent,
        gpu_percent,
        cpu_temp,
        gpu_temp,
        disk_percent,
        net_up_kbps,
        net_down_kbps,
    )

    return (packed, curr_net, now)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global running

    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Signal handlers for clean shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logging.info("Hotkey Bridge Companion starting...")

    # Initialize GPU collector once at startup
    gpu = GPUCollector()

    # Prime psutil.cpu_percent() -- first call always returns 0
    psutil.cpu_percent()

    # Discover and connect to bridge
    device = None
    while running:
        path = find_bridge()
        if path is not None:
            try:
                device = hid.Device(path=path)
                logging.info(
                    "Connected to %s (manufacturer=%s, serial=%s)",
                    device.product,
                    device.manufacturer,
                    device.serial,
                )
                break
            except Exception as exc:
                logging.error("Failed to open bridge: %s", exc)
                device = None
        logging.info("Bridge not found, retrying in %.0fs...", RETRY_INTERVAL)
        time.sleep(RETRY_INTERVAL)

    if not running or device is None:
        logging.info("Shutting down (no bridge connected)")
        return

    # Initialize network baseline
    prev_net = psutil.net_io_counters()
    prev_time = time.time()

    # Main stats loop
    logging.info("Streaming stats at %.1f Hz", 1.0 / UPDATE_INTERVAL)
    while running:
        time.sleep(UPDATE_INTERVAL)
        if not running:
            break

        packed, prev_net, prev_time = collect_stats(gpu, prev_net, prev_time)

        try:
            # Leading 0x00 is the HID report ID byte required by hidapi on
            # Linux. If the vendor device uses a specific report ID, adjust
            # this byte accordingly.
            device.write(b"\x00" + packed)
        except (IOError, OSError) as exc:
            logging.warning("HID write failed (device disconnected?): %s", exc)
            try:
                device.close()
            except Exception:
                pass
            device = None

            # Retry discovery loop
            while running:
                logging.info("Reconnecting to bridge...")
                path = find_bridge()
                if path is not None:
                    try:
                        device = hid.Device(path=path)
                        logging.info("Reconnected to %s", device.product)
                        prev_net = psutil.net_io_counters()
                        prev_time = time.time()
                        break
                    except Exception:
                        pass
                time.sleep(RETRY_INTERVAL)

            if device is None:
                break

    # Clean shutdown
    if device is not None:
        try:
            device.close()
        except Exception:
            pass
    logging.info("Companion stopped.")


if __name__ == "__main__":
    main()
