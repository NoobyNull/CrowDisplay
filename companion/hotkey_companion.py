#!/usr/bin/env python3
"""
Hotkey Bridge Companion - System Stats Streamer

Collects live system metrics (CPU, RAM, GPU, temps, network, disk) and
streams them to the HotkeyBridge ESP32-S3 over USB HID output reports
at 1 Hz. The bridge relays these stats to the CrowPanel display via
ESP-NOW for rendering in the stats header bar.

Also listens for systemd PrepareForShutdown D-Bus signal to notify the
display bridge before PC powers off (enabling clock mode), and sends
epoch time sync with each stats update for the display clock.

Usage:
    python3 hotkey_companion.py          # Run directly
    systemctl --user start hotkey-companion  # Run as service

Dependencies:
    pip install hidapi psutil pynvml
    pip install dbus-next  # Optional: for shutdown detection
"""

import hid
import json
import psutil
import struct
import time
import sys
import signal
import logging
import os
import threading
import asyncio

from companion.action_executor import execute_action
from companion.config_manager import get_config_manager, DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_PATH

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VENDOR_ID = 0x303A          # Espressif
PRODUCT_ID = 0x1001         # CrowPanel HotkeyBridge
PRODUCT_STRING = "HotkeyBridge"
UPDATE_INTERVAL = 1.0       # Seconds between stat reports (1 Hz)

# Legacy StatsPayload format (v0.9.0 backwards compatibility)
STATS_FORMAT = "<BBBBBBhh"  # 6 x uint8 + 2 x int16 = 10 bytes

# TLV stat type IDs (must match StatType enum in shared/protocol.h)
STAT_TYPES = {
    'cpu_percent':    0x01, 'ram_percent':    0x02, 'gpu_percent':    0x03,
    'cpu_temp':       0x04, 'gpu_temp':       0x05, 'disk_percent':   0x06,
    'net_up':         0x07, 'net_down':       0x08, 'cpu_freq':       0x09,
    'gpu_freq':       0x0A, 'swap_percent':   0x0B, 'uptime_hours':   0x0C,
    'battery_pct':    0x0D, 'fan_rpm':        0x0E, 'load_avg':       0x0F,
    'proc_count':     0x10, 'gpu_mem_pct':    0x11, 'gpu_power_w':    0x12,
    'disk_read_kbs':  0x13, 'disk_write_kbs': 0x14,
}

# Reverse lookup: type_id -> name
STAT_ID_TO_NAME = {v: k for k, v in STAT_TYPES.items()}

# Default stats header config (matches original 8 hardcoded stats)
DEFAULT_STATS_CONFIG = [
    {"type": 0x01, "color": 0x3498DB, "position": 0},  # cpu_percent
    {"type": 0x02, "color": 0x2ECC71, "position": 1},  # ram_percent
    {"type": 0x03, "color": 0xE67E22, "position": 2},  # gpu_percent
    {"type": 0x04, "color": 0xE74C3C, "position": 3},  # cpu_temp
    {"type": 0x05, "color": 0xF1C40F, "position": 4},  # gpu_temp
    {"type": 0x07, "color": 0x1ABC9C, "position": 5},  # net_up
    {"type": 0x08, "color": 0x1ABC9C, "position": 6},  # net_down
    {"type": 0x06, "color": 0x7F8C8D, "position": 7},  # disk_percent
]

# HID vendor message type prefixes (first byte after report ID)
MSG_STATS        = 0x03
MSG_POWER_STATE  = 0x05
MSG_TIME_SYNC    = 0x06
MSG_NOTIFICATION = 0x08
MSG_BUTTON_PRESS = 0x0B

# Power state values
POWER_SHUTDOWN = 0
POWER_WAKE     = 1
POWER_LOCKED   = 2

# Retry interval when bridge is not found
RETRY_INTERVAL = 5.0

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

running = True
shutdown_event = threading.Event()
lock_event = threading.Event()
unlock_event = threading.Event()

# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def _signal_handler(signum, frame):
    global running
    logging.info("Received signal %d, shutting down...", signum)
    running = False


# ---------------------------------------------------------------------------
# D-Bus shutdown listener
# ---------------------------------------------------------------------------

def _run_dbus_listener():
    """Entry point for the D-Bus listener thread. Creates an asyncio
    event loop and runs the async shutdown listener."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_dbus_shutdown_listener())
    except Exception as exc:
        logging.debug("D-Bus listener loop exited: %s", exc)
    finally:
        loop.close()


async def start_dbus_shutdown_listener():
    """Connect to the system D-Bus, take a shutdown inhibitor lock, and
    listen for the PrepareForShutdown signal from logind.

    When PrepareForShutdown(True) fires, sets shutdown_event so the main
    thread can send MSG_POWER_STATE to the bridge, then releases the
    inhibitor lock to allow shutdown to proceed.

    Gracefully degrades if dbus-next is not installed or the system bus
    is unavailable.
    """
    try:
        from dbus_next.aio import MessageBus
        from dbus_next import BusType
    except ImportError:
        logging.warning(
            "dbus-next not installed -- shutdown detection disabled. "
            "Install with: pip install dbus-next"
        )
        return

    try:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    except Exception as exc:
        logging.warning("Cannot connect to system D-Bus: %s", exc)
        return

    try:
        introspection = await bus.introspect(
            "org.freedesktop.login1", "/org/freedesktop/login1"
        )
        proxy = bus.get_proxy_object(
            "org.freedesktop.login1",
            "/org/freedesktop/login1",
            introspection,
        )
        manager = proxy.get_interface("org.freedesktop.login1.Manager")

        # Take a delay inhibitor lock so we have time to send the HID
        # shutdown message before the system powers off.
        inhibit_fd = await manager.call_inhibit(
            "shutdown",
            "HotkeyCompanion",
            "Sending shutdown signal to display bridge",
            "delay",
        )
        # dbus-next returns the fd as an int
        if hasattr(inhibit_fd, 'fileno'):
            inhibit_fd = inhibit_fd.fileno()
        logging.info("Shutdown inhibitor lock acquired (fd=%s)", inhibit_fd)

        def on_prepare_for_shutdown(start):
            if start:
                logging.info("PrepareForShutdown(True) received")
                shutdown_event.set()
                # Release the inhibitor lock so shutdown can proceed
                try:
                    os.close(inhibit_fd)
                    logging.info("Inhibitor lock released")
                except OSError:
                    pass

        manager.on_prepare_for_shutdown(on_prepare_for_shutdown)
        logging.info("D-Bus shutdown listener active")

        await bus.wait_for_disconnect()
    except Exception as exc:
        logging.warning("D-Bus shutdown listener error: %s", exc)


# ---------------------------------------------------------------------------
# D-Bus session lock listener
# ---------------------------------------------------------------------------

def _run_session_lock_listener():
    """Entry point for session lock listener thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_start_session_lock_listener())
    except Exception as exc:
        logging.debug("Session lock listener loop exited: %s", exc)
    finally:
        loop.close()


async def _start_session_lock_listener():
    """Listen for Lock/Unlock signals on the logind session object.

    Uses org.freedesktop.login1.Session interface on the current session.
    Gracefully degrades if dbus-next is unavailable.
    """
    try:
        from dbus_next.aio import MessageBus
        from dbus_next import BusType
    except ImportError:
        logging.warning("dbus-next not installed -- session lock detection disabled")
        return

    try:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    except Exception as exc:
        logging.warning("Cannot connect to system D-Bus for lock listener: %s", exc)
        return

    try:
        # Get the current session path from logind
        introspection = await bus.introspect(
            "org.freedesktop.login1", "/org/freedesktop/login1"
        )
        proxy = bus.get_proxy_object(
            "org.freedesktop.login1",
            "/org/freedesktop/login1",
            introspection,
        )
        manager = proxy.get_interface("org.freedesktop.login1.Manager")

        # Get our session — try by PID first, fall back to current user's
        # graphical session (needed when launched from a non-session context)
        try:
            session_path = await manager.call_get_session_by_pid(os.getpid())
        except Exception:
            import getpass
            username = getpass.getuser()
            sessions = await manager.call_list_sessions()
            # sessions is list of (id, uid, user, seat, path)
            session_path = None
            for sess in sessions:
                sid, uid, user, seat, path = sess
                if user == username:
                    session_path = path
                    break
            if session_path is None:
                logging.warning("No logind session found for user %s", username)
                return
        logging.info("Session lock listener: session path = %s", session_path)

        session_introspection = await bus.introspect(
            "org.freedesktop.login1", session_path
        )
        session_proxy = bus.get_proxy_object(
            "org.freedesktop.login1",
            session_path,
            session_introspection,
        )
        session = session_proxy.get_interface("org.freedesktop.login1.Session")

        session.on_lock(lambda: _on_session_lock_change(True))
        session.on_unlock(lambda: _on_session_lock_change(False))
        logging.info("D-Bus session lock listener active")

        await bus.wait_for_disconnect()
    except Exception as exc:
        logging.warning("Session lock listener error: %s", exc)


def _on_session_lock_change(locked):
    if locked:
        logging.info("Session locked")
        lock_event.set()
        unlock_event.clear()
    else:
        logging.info("Session unlocked")
        unlock_event.set()
        lock_event.clear()


# ---------------------------------------------------------------------------
# D-Bus notification listener
# ---------------------------------------------------------------------------

class NotificationListener:
    """Monitors D-Bus session bus for desktop notifications and forwards
    matching ones (by app name filter) via a callback.

    If app_filter is empty, all notifications are forwarded.
    """

    def __init__(self, app_filter: set, callback):
        self.app_filter = app_filter
        self.callback = callback

    async def run(self):
        try:
            from dbus_next.aio import MessageBus
            from dbus_next import BusType, MessageType, Message
        except ImportError:
            logging.warning(
                "dbus-next not installed -- notification forwarding disabled. "
                "Install with: pip install dbus-next"
            )
            return

        try:
            bus = await MessageBus(bus_type=BusType.SESSION).connect()
        except Exception as exc:
            logging.warning("Cannot connect to session D-Bus: %s", exc)
            return

        try:
            # Add match rule to intercept Notify method calls
            await bus.call(
                Message(
                    destination='org.freedesktop.DBus',
                    path='/org/freedesktop/DBus',
                    interface='org.freedesktop.DBus',
                    member='AddMatch',
                    signature='s',
                    body=["type='method_call',interface='org.freedesktop.Notifications',member='Notify'"]
                )
            )

            def message_filter(msg):
                if (msg.message_type == MessageType.METHOD_CALL and
                    msg.interface == 'org.freedesktop.Notifications' and
                    msg.member == 'Notify'):
                    args = msg.body
                    if len(args) >= 5:
                        app_name = str(args[0])
                        summary = str(args[3])
                        body = str(args[4])
                        if not self.app_filter or app_name in self.app_filter:
                            logging.info("Forwarding notification: %s - %s", app_name, summary)
                            try:
                                self.callback(app_name, summary, body)
                            except Exception as exc:
                                logging.debug("Notification callback error: %s", exc)

            bus.add_message_handler(message_filter)
            logging.info("D-Bus notification listener active (filter: %s)",
                         list(self.app_filter) if self.app_filter else "ALL")
            await bus.wait_for_disconnect()
        except Exception as exc:
            logging.warning("D-Bus notification listener error: %s", exc)


def _run_notification_listener(app_filter, callback):
    """Entry point for notification listener thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        listener = NotificationListener(app_filter, callback)
        loop.run_until_complete(listener.run())
    except Exception as exc:
        logging.debug("Notification listener loop exited: %s", exc)
    finally:
        loop.close()


def send_notification_to_display(device, app_name, summary, body, hid_lock=None):
    """Encode and send a MSG_NOTIFICATION payload to the bridge.

    NotificationMsg: app_name[32] + summary[100] + body[116] = 248 bytes.
    Packet: [0x00 report ID] [0x08 MSG_NOTIFICATION] [248-byte payload]
    """
    app_bytes = app_name.encode('utf-8')[:31] + b'\x00'
    sum_bytes = summary.encode('utf-8')[:99] + b'\x00'
    body_bytes = body.encode('utf-8')[:115] + b'\x00'

    payload = (app_bytes.ljust(32, b'\x00') +
               sum_bytes.ljust(100, b'\x00') +
               body_bytes.ljust(116, b'\x00'))

    try:
        if hid_lock:
            with hid_lock:
                device.write(b"\x06" + bytes([MSG_NOTIFICATION]) + payload)
        else:
            device.write(b"\x06" + bytes([MSG_NOTIFICATION]) + payload)
    except (IOError, OSError) as exc:
        logging.debug("Failed to send notification: %s", exc)


# ---------------------------------------------------------------------------
# Notification config loading
# ---------------------------------------------------------------------------

def load_notification_config(config_path=None):
    """Load notification settings from config.json.

    Returns (enabled: bool, filter_set: set of app name strings).
    """
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            enabled = data.get("notifications_enabled", False)
            filter_list = data.get("notification_filter", [])
            if isinstance(filter_list, list):
                return enabled, set(str(s) for s in filter_list)
        except (json.JSONDecodeError, IOError) as exc:
            logging.warning("Failed to load notification config: %s", exc)
    return False, set()


def load_follow_lock_config(config_path=None):
    """Load follow_lock setting from config.json. Default True."""
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            return bool(data.get("follow_lock", True))
        except (json.JSONDecodeError, IOError):
            pass
    return True


# ---------------------------------------------------------------------------
# Vendor HID read thread
# ---------------------------------------------------------------------------

def _vendor_read_thread(device, hid_lock, config_mgr):
    """Background thread: reads vendor HID input reports from bridge."""
    global running
    while running:
        try:
            with hid_lock:
                data = device.read(63, timeout=100)
            if data and len(data) >= 3:
                msg_type = data[0]
                if msg_type == MSG_BUTTON_PRESS:
                    page_idx = data[1]
                    widget_idx = data[2]
                    logging.info("Button press: page=%d widget=%d", page_idx, widget_idx)
                    # Execute action on a separate thread to avoid blocking reads
                    threading.Thread(
                        target=execute_action,
                        args=(config_mgr, page_idx, widget_idx),
                        daemon=True
                    ).start()
        except (IOError, OSError):
            logging.warning("Vendor HID read error, device may have disconnected")
            break
        except Exception as exc:
            logging.debug("Vendor read thread error: %s", exc)


# ---------------------------------------------------------------------------
# Config file watcher
# ---------------------------------------------------------------------------

def _start_config_watcher(config_path, config_mgr):
    """Start watching config file for changes, reload on modification."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        logging.warning("watchdog not installed -- config auto-reload disabled. "
                       "Install with: pip install watchdog")
        return None

    class ConfigReloadHandler(FileSystemEventHandler):
        def __init__(self):
            self._timer = None
            self._debounce_sec = 0.5

        def on_modified(self, event):
            if os.path.abspath(event.src_path) == os.path.abspath(config_path):
                if self._timer:
                    self._timer.cancel()
                self._timer = threading.Timer(self._debounce_sec, self._reload)
                self._timer.start()

        def _reload(self):
            if config_mgr.load_json_file(config_path):
                logging.info("Config reloaded from %s", config_path)
            else:
                logging.warning("Config reload failed from %s", config_path)

    observer = Observer()
    handler = ConfigReloadHandler()
    observer.schedule(handler, os.path.dirname(os.path.abspath(config_path)), recursive=False)
    observer.daemon = True
    observer.start()
    logging.info("Config file watcher started for %s", config_path)
    return observer


# ---------------------------------------------------------------------------
# Power state and time sync helpers
# ---------------------------------------------------------------------------

def send_power_state(device, state, hid_lock=None):
    """Send a MSG_POWER_STATE message to the bridge.

    Packet: [0x00 report ID] [0x05 MSG_POWER_STATE] [state byte]
    """
    try:
        if hid_lock:
            with hid_lock:
                device.write(b"\x06" + bytes([MSG_POWER_STATE, state]))
        else:
            device.write(b"\x06" + bytes([MSG_POWER_STATE, state]))
        state_names = {POWER_SHUTDOWN: "SHUTDOWN", POWER_WAKE: "WAKE", POWER_LOCKED: "LOCKED"}
        logging.info("Sent power state: %s", state_names.get(state, f"0x{state:02X}"))
    except (IOError, OSError) as exc:
        logging.warning("Failed to send power state: %s", exc)


def send_time_sync(device, hid_lock=None):
    """Send a MSG_TIME_SYNC message with current epoch seconds.

    Packet: [0x00 report ID] [0x06 MSG_TIME_SYNC] [uint32 LE epoch]
    """
    epoch = int(time.time())
    try:
        if hid_lock:
            with hid_lock:
                device.write(b"\x06" + bytes([MSG_TIME_SYNC]) + struct.pack("<I", epoch))
        else:
            device.write(b"\x06" + bytes([MSG_TIME_SYNC]) + struct.pack("<I", epoch))
    except (IOError, OSError) as exc:
        logging.debug("Failed to send time sync: %s", exc)


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

    def collect_extended(self):
        """Return (gpu_mem_pct, gpu_power_w, gpu_freq_mhz) for NVIDIA GPUs.

        Returns (0xFF, 0, 0) if not NVIDIA or on error.
        """
        if self.gpu_type != "nvidia":
            return (0xFF, 0, 0)
        try:
            import pynvml
            # GPU memory
            mem = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
            gpu_mem_pct = min(int(mem.used * 100 / mem.total), 100) if mem.total > 0 else 0xFF
            # GPU power
            try:
                power_mw = pynvml.nvmlDeviceGetPowerUsage(self._nvml_handle)
                gpu_power_w = min(int(power_mw / 1000), 0xFFFF)
            except Exception:
                gpu_power_w = 0
            # GPU clock
            try:
                clock = pynvml.nvmlDeviceGetClockInfo(self._nvml_handle, pynvml.NVML_CLOCK_GRAPHICS)
                gpu_freq_mhz = min(int(clock), 0xFFFF)
            except Exception:
                gpu_freq_mhz = 0
            return (gpu_mem_pct, gpu_power_w, gpu_freq_mhz)
        except Exception as exc:
            logging.debug("NVIDIA extended stats failed: %s", exc)
            return (0xFF, 0, 0)


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
# TLV encoding
# ---------------------------------------------------------------------------

def encode_stats_tlv(stats_list):
    """Encode a list of (stat_type_id, value) pairs into TLV packet bytes.

    Format: [count] [type1][len1][val1...] [type2][len2][val2...] ...
    Values < 256 use 1 byte, values >= 256 use 2 bytes (little-endian).
    """
    packet = bytearray([len(stats_list)])
    for stat_type, value in stats_list:
        packet.append(stat_type)
        if value < 256:
            packet.append(1)
            packet.append(value & 0xFF)
        else:
            packet.append(2)
            packet.extend(struct.pack('<H', value & 0xFFFF))
    return bytes(packet)


# ---------------------------------------------------------------------------
# Stats config loading
# ---------------------------------------------------------------------------

def load_stats_config(config_path=None):
    """Load stats_header config from config.json file.

    Returns (stat_type_ids, net_interface, disk_device, disk_mount).
    - net_interface: NIC name (e.g. "enp6s0") or None for aggregate
    - disk_device:   device name for I/O (e.g. "nvme0n1") or None for aggregate
    - disk_mount:    mount path for usage % (e.g. "/home") or "/" default
    """
    net_interface = None
    disk_device = None
    disk_mount = "/"

    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            net_interface = data.get("net_interface") or None
            disk_device = data.get("disk_device") or None
            disk_mount = data.get("disk_mount") or "/"
            stats_header = data.get("stats_header")
            if stats_header and isinstance(stats_header, list):
                type_ids = [s.get("type", 0) for s in stats_header if isinstance(s, dict)]
                type_ids = [t for t in type_ids if 1 <= t <= 0x14]
                if type_ids:
                    logging.info("Loaded %d stat types from config: %s",
                                 len(type_ids),
                                 [STAT_ID_TO_NAME.get(t, f"0x{t:02X}") for t in type_ids])
                    return (type_ids, net_interface, disk_device, disk_mount)
        except (json.JSONDecodeError, IOError, KeyError) as exc:
            logging.warning("Failed to load stats config: %s", exc)

    # Default: original 8 stats
    return ([s["type"] for s in DEFAULT_STATS_CONFIG], net_interface, disk_device, disk_mount)


# ---------------------------------------------------------------------------
# Expanded stat collectors
# ---------------------------------------------------------------------------

def get_swap_percent():
    """Return swap usage percent, or 0xFF if unavailable."""
    try:
        swap = psutil.swap_memory()
        return min(int(swap.percent), 100)
    except Exception:
        return 0xFF


def get_cpu_freq_mhz():
    """Return current CPU frequency in MHz, or 0."""
    try:
        freq = psutil.cpu_freq()
        if freq:
            return min(int(freq.current), 0xFFFF)
    except Exception:
        pass
    return 0


def get_uptime_hours():
    """Return system uptime in hours."""
    try:
        boot = psutil.boot_time()
        return min(int((time.time() - boot) / 3600), 0xFFFF)
    except Exception:
        return 0


def get_battery_percent():
    """Return battery percentage, or 0xFF if no battery."""
    try:
        bat = psutil.sensors_battery()
        if bat is not None:
            return min(int(bat.percent), 100)
    except Exception:
        pass
    return 0xFF


def get_fan_rpm():
    """Return first fan RPM, or 0."""
    try:
        fans = psutil.sensors_fans()
        if fans:
            for fan_list in fans.values():
                if fan_list:
                    return min(int(fan_list[0].current), 0xFFFF)
    except Exception:
        pass
    return 0


def get_load_avg_x100():
    """Return 1-min load average x 100 as uint16."""
    try:
        load1, _, _ = os.getloadavg()
        return min(int(load1 * 100), 0xFFFF)
    except Exception:
        return 0


def get_proc_count():
    """Return number of running processes."""
    try:
        return min(len(psutil.pids()), 0xFFFF)
    except Exception:
        return 0


def get_disk_io(prev_disk_io, dt, disk_device=None):
    """Return (read_kbs, write_kbs, current_counters).

    If disk_device is set (e.g. "nvme0n1"), report I/O for that device only.
    Otherwise report aggregate across all disks.
    """
    try:
        if disk_device:
            per_disk = psutil.disk_io_counters(perdisk=True)
            curr = per_disk.get(disk_device)
            if curr is None:
                logging.warning("Disk device '%s' not found, available: %s",
                                disk_device, list(per_disk.keys()))
                return (0, 0, prev_disk_io)
        else:
            curr = psutil.disk_io_counters()
        if prev_disk_io is None:
            return (0, 0, curr)
        read_kbs = int((curr.read_bytes - prev_disk_io.read_bytes) / dt / 1024)
        write_kbs = int((curr.write_bytes - prev_disk_io.write_bytes) / dt / 1024)
        return (max(0, min(read_kbs, 0xFFFF)), max(0, min(write_kbs, 0xFFFF)), curr)
    except Exception:
        return (0, 0, prev_disk_io)


# ---------------------------------------------------------------------------
# Stats collection (TLV + legacy)
# ---------------------------------------------------------------------------

def collect_stats_tlv(gpu_collector, enabled_types, prev_net, prev_time, prev_disk_io,
                      net_interface=None, disk_device=None, disk_mount="/"):
    """Collect system metrics based on enabled types and return TLV-encoded bytes.

    Returns (tlv_bytes, current_net_counters, current_time, current_disk_io).
    Only collects stats that are in enabled_types (saves CPU on unused psutil calls).

    net_interface: NIC name for per-interface network stats, or None for aggregate.
    disk_device:   device name for per-disk I/O stats, or None for aggregate.
    disk_mount:    mount path for disk usage %, defaults to "/".
    """
    now = time.time()
    dt = now - prev_time
    if dt <= 0:
        dt = 1.0

    enabled_set = set(enabled_types)
    stats_list = []
    curr_net = prev_net
    curr_disk_io = prev_disk_io

    # CPU percent
    if STAT_TYPES['cpu_percent'] in enabled_set:
        try:
            val = min(int(psutil.cpu_percent(interval=None)), 100)
        except Exception:
            val = 0
        stats_list.append((STAT_TYPES['cpu_percent'], val))

    # RAM percent
    if STAT_TYPES['ram_percent'] in enabled_set:
        try:
            val = min(int(psutil.virtual_memory().percent), 100)
        except Exception:
            val = 0
        stats_list.append((STAT_TYPES['ram_percent'], val))

    # GPU percent & temp
    need_gpu = (STAT_TYPES['gpu_percent'] in enabled_set or
                STAT_TYPES['gpu_temp'] in enabled_set or
                STAT_TYPES['gpu_mem_pct'] in enabled_set or
                STAT_TYPES['gpu_power_w'] in enabled_set or
                STAT_TYPES['gpu_freq'] in enabled_set)
    if need_gpu:
        gpu_pct, gpu_temp = gpu_collector.collect()
        if STAT_TYPES['gpu_percent'] in enabled_set:
            stats_list.append((STAT_TYPES['gpu_percent'], gpu_pct))
        if STAT_TYPES['gpu_temp'] in enabled_set:
            stats_list.append((STAT_TYPES['gpu_temp'], gpu_temp))
        # Extended GPU stats (NVIDIA only)
        if gpu_collector.gpu_type == "nvidia":
            gpu_mem, gpu_power, gpu_freq = gpu_collector.collect_extended()
            if STAT_TYPES['gpu_mem_pct'] in enabled_set:
                stats_list.append((STAT_TYPES['gpu_mem_pct'], gpu_mem))
            if STAT_TYPES['gpu_power_w'] in enabled_set:
                stats_list.append((STAT_TYPES['gpu_power_w'], gpu_power))
            if STAT_TYPES['gpu_freq'] in enabled_set:
                stats_list.append((STAT_TYPES['gpu_freq'], gpu_freq))
        else:
            if STAT_TYPES['gpu_mem_pct'] in enabled_set:
                stats_list.append((STAT_TYPES['gpu_mem_pct'], 0xFF))
            if STAT_TYPES['gpu_power_w'] in enabled_set:
                stats_list.append((STAT_TYPES['gpu_power_w'], 0))
            if STAT_TYPES['gpu_freq'] in enabled_set:
                stats_list.append((STAT_TYPES['gpu_freq'], 0))

    # CPU temp
    if STAT_TYPES['cpu_temp'] in enabled_set:
        stats_list.append((STAT_TYPES['cpu_temp'], get_cpu_temp()))

    # Disk percent (configurable mount point)
    if STAT_TYPES['disk_percent'] in enabled_set:
        try:
            val = min(int(psutil.disk_usage(disk_mount).percent), 100)
        except Exception:
            val = 0
        stats_list.append((STAT_TYPES['disk_percent'], val))

    # Network (per-interface or aggregate)
    if STAT_TYPES['net_up'] in enabled_set or STAT_TYPES['net_down'] in enabled_set:
        try:
            if net_interface:
                per_nic = psutil.net_io_counters(pernic=True)
                curr_net = per_nic.get(net_interface)
                if curr_net is None:
                    logging.warning("NIC '%s' not found, available: %s",
                                    net_interface, list(per_nic.keys()))
                    curr_net = prev_net
            else:
                curr_net = psutil.net_io_counters()
            net_up = int((curr_net.bytes_sent - prev_net.bytes_sent) / dt / 1024)
            net_down = int((curr_net.bytes_recv - prev_net.bytes_recv) / dt / 1024)
            net_up = max(0, min(net_up, 0xFFFF))
            net_down = max(0, min(net_down, 0xFFFF))
        except Exception:
            curr_net = prev_net
            net_up = 0
            net_down = 0
        if STAT_TYPES['net_up'] in enabled_set:
            stats_list.append((STAT_TYPES['net_up'], net_up))
        if STAT_TYPES['net_down'] in enabled_set:
            stats_list.append((STAT_TYPES['net_down'], net_down))

    # CPU freq
    if STAT_TYPES['cpu_freq'] in enabled_set:
        stats_list.append((STAT_TYPES['cpu_freq'], get_cpu_freq_mhz()))

    # Swap
    if STAT_TYPES['swap_percent'] in enabled_set:
        stats_list.append((STAT_TYPES['swap_percent'], get_swap_percent()))

    # Uptime
    if STAT_TYPES['uptime_hours'] in enabled_set:
        stats_list.append((STAT_TYPES['uptime_hours'], get_uptime_hours()))

    # Battery
    if STAT_TYPES['battery_pct'] in enabled_set:
        stats_list.append((STAT_TYPES['battery_pct'], get_battery_percent()))

    # Fan RPM
    if STAT_TYPES['fan_rpm'] in enabled_set:
        stats_list.append((STAT_TYPES['fan_rpm'], get_fan_rpm()))

    # Load average
    if STAT_TYPES['load_avg'] in enabled_set:
        stats_list.append((STAT_TYPES['load_avg'], get_load_avg_x100()))

    # Process count
    if STAT_TYPES['proc_count'] in enabled_set:
        stats_list.append((STAT_TYPES['proc_count'], get_proc_count()))

    # Disk I/O (per-device or aggregate)
    if STAT_TYPES['disk_read_kbs'] in enabled_set or STAT_TYPES['disk_write_kbs'] in enabled_set:
        read_kbs, write_kbs, curr_disk_io = get_disk_io(prev_disk_io, dt, disk_device)
        if STAT_TYPES['disk_read_kbs'] in enabled_set:
            stats_list.append((STAT_TYPES['disk_read_kbs'], read_kbs))
        if STAT_TYPES['disk_write_kbs'] in enabled_set:
            stats_list.append((STAT_TYPES['disk_write_kbs'], write_kbs))

    tlv_bytes = encode_stats_tlv(stats_list)
    return (tlv_bytes, curr_net, now, curr_disk_io)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

class CompanionService:
    """Background service: bridge communication, stats streaming, action dispatch.

    Runs all work in daemon threads. Call start() to begin, stop() to shut down.
    Status callbacks (on_bridge_connected, on_bridge_disconnected, on_stats_sent,
    on_button_press) are called from background threads — use Qt signals or
    thread-safe mechanisms if updating UI.
    """

    def __init__(self, config_manager=None):
        self._running = False
        self._device = None
        self._hid_lock = threading.Lock()
        self._config_mgr = config_manager or get_config_manager()
        self._config_path = str(DEFAULT_CONFIG_PATH)
        self._config_watcher = None
        self._gpu = None
        self._stats_thread = None
        self._vendor_thread = None
        self._enabled_stat_types = []
        self._net_interface = None
        self._disk_device = None
        self._disk_mount = "/"

        # Status callbacks
        self.on_bridge_connected = None
        self.on_bridge_disconnected = None
        self.on_stats_sent = None
        self.on_button_press = None

        # Readable state
        self._bridge_connected = False
        self._stats_count = 0

    @property
    def is_bridge_connected(self) -> bool:
        return self._bridge_connected

    @property
    def status_text(self) -> str:
        if self._bridge_connected:
            return f"Bridge: Connected, Stats: {len(self._enabled_stat_types)} types @ 1Hz"
        return "Bridge: Disconnected"

    def start(self):
        """Start all background threads (non-blocking)."""
        if self._running:
            return

        self._running = True
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Load config
        self._config_mgr.load_json_file(self._config_path)
        self._load_device_config()
        logging.info("Enabled stat types: %s",
                     [STAT_ID_TO_NAME.get(t, f"0x{t:02X}") for t in self._enabled_stat_types])

        # Initialize GPU collector
        self._gpu = GPUCollector()
        psutil.cpu_percent()  # Prime — first call always returns 0

        # Start config file watcher
        self._config_watcher = _start_config_watcher(self._config_path, self._config_mgr)

        # D-Bus shutdown listener
        threading.Thread(target=_run_dbus_listener, daemon=True).start()

        # Session lock listener (for follow_lock feature)
        self._follow_lock = load_follow_lock_config(self._config_path)
        if self._follow_lock:
            threading.Thread(target=_run_session_lock_listener, daemon=True).start()
            logging.info("Session lock following enabled")
        else:
            logging.info("Session lock following disabled")

        # Notification forwarding
        notif_enabled, notif_filter = load_notification_config(self._config_path)
        if notif_enabled:
            logging.info("Notification forwarding enabled (filter: %s)",
                         list(notif_filter) if notif_filter else "ALL")
        else:
            logging.info("Notification forwarding disabled")

        # Main stats + bridge thread
        self._stats_thread = threading.Thread(
            target=self._stats_loop, args=(notif_enabled, notif_filter), daemon=True
        )
        self._stats_thread.start()

    def stop(self):
        """Clean shutdown of all threads."""
        self._running = False
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
        self._bridge_connected = False
        logging.info("CompanionService stopped.")

    def _load_device_config(self):
        """Load stat types and device selection from config."""
        (self._enabled_stat_types, self._net_interface,
         self._disk_device, self._disk_mount) = load_stats_config(self._config_path)
        if self._net_interface:
            logging.info("Network interface: %s", self._net_interface)
        if self._disk_device:
            logging.info("Disk device: %s", self._disk_device)
        if self._disk_mount != "/":
            logging.info("Disk mount: %s", self._disk_mount)

    def reload_config(self):
        """Reload config from disk."""
        if self._config_mgr.load_json_file(self._config_path):
            self._load_device_config()
            logging.info("Config reloaded, %d stat types", len(self._enabled_stat_types))

    def _set_bridge_connected(self, connected):
        prev = self._bridge_connected
        self._bridge_connected = connected
        if connected and not prev:
            if self.on_bridge_connected:
                self.on_bridge_connected()
        elif not connected and prev:
            if self.on_bridge_disconnected:
                self.on_bridge_disconnected()

    def _connect_bridge(self):
        """Discover and connect to bridge. Blocks until connected or stopped."""
        while self._running:
            path = find_bridge()
            if path is not None:
                try:
                    self._device = hid.Device(path=path)
                    logging.info("Connected to %s (manufacturer=%s, serial=%s)",
                                 self._device.product,
                                 self._device.manufacturer,
                                 self._device.serial)
                    self._set_bridge_connected(True)
                    return True
                except Exception as exc:
                    logging.error("Failed to open bridge: %s", exc)
                    self._device = None
            logging.info("Bridge not found, retrying in %.0fs...", RETRY_INTERVAL)
            time.sleep(RETRY_INTERVAL)
        return False

    def _vendor_read_loop(self):
        """Background: reads vendor HID input reports from bridge."""
        while self._running and self._device is not None:
            try:
                with self._hid_lock:
                    data = self._device.read(63, timeout=100)
                if data and len(data) >= 3:
                    msg_type = data[0]
                    if msg_type == MSG_BUTTON_PRESS:
                        page_idx = data[1]
                        widget_idx = data[2]
                        logging.info("Button press: page=%d widget=%d", page_idx, widget_idx)
                        if self.on_button_press:
                            self.on_button_press(page_idx, widget_idx)
                        threading.Thread(
                            target=execute_action,
                            args=(self._config_mgr, page_idx, widget_idx),
                            daemon=True
                        ).start()
            except (IOError, OSError):
                logging.warning("Vendor HID read error, device may have disconnected")
                break
            except Exception as exc:
                logging.debug("Vendor read thread error: %s", exc)

    def _stats_loop(self, notif_enabled, notif_filter):
        """Main loop: bridge discovery, stats streaming, reconnection."""
        global running

        if not self._connect_bridge():
            return

        # Start vendor read thread
        self._vendor_thread = threading.Thread(target=self._vendor_read_loop, daemon=True)
        self._vendor_thread.start()

        # Start notification listener if enabled
        if notif_enabled and self._device is not None:
            threading.Thread(
                target=_run_notification_listener,
                args=(notif_filter,
                      lambda app, s, b: send_notification_to_display(
                          self._device, app, s, b, self._hid_lock)),
                daemon=True
            ).start()

        # Initialize baselines (per-interface/device if configured)
        try:
            if self._net_interface:
                prev_net = psutil.net_io_counters(pernic=True).get(self._net_interface)
                if prev_net is None:
                    logging.warning("NIC '%s' not found, falling back to aggregate", self._net_interface)
                    prev_net = psutil.net_io_counters()
            else:
                prev_net = psutil.net_io_counters()
        except Exception:
            prev_net = psutil.net_io_counters()
        prev_time = time.time()
        prev_disk_io = None
        try:
            if self._disk_device:
                per_disk = psutil.disk_io_counters(perdisk=True)
                prev_disk_io = per_disk.get(self._disk_device)
                if prev_disk_io is None:
                    logging.warning("Disk '%s' not found, falling back to aggregate", self._disk_device)
                    prev_disk_io = psutil.disk_io_counters()
            else:
                prev_disk_io = psutil.disk_io_counters()
        except Exception:
            pass

        logging.info("Streaming TLV stats at %.1f Hz (%d stat types)",
                     1.0 / UPDATE_INTERVAL, len(self._enabled_stat_types))

        pc_locked = False

        while self._running:
            if shutdown_event.is_set():
                logging.info("System shutdown detected, notifying bridge...")
                send_power_state(self._device, POWER_SHUTDOWN, self._hid_lock)
                self._running = False
                running = False
                break

            # Session lock/unlock detection
            if self._follow_lock:
                if lock_event.is_set() and not pc_locked:
                    pc_locked = True
                    logging.info("Sending POWER_LOCKED to display")
                    send_power_state(self._device, POWER_LOCKED, self._hid_lock)
                elif unlock_event.is_set() and pc_locked:
                    pc_locked = False
                    logging.info("Sending POWER_WAKE to display (unlocked)")
                    send_power_state(self._device, POWER_WAKE, self._hid_lock)

            time.sleep(UPDATE_INTERVAL)
            if not self._running:
                break

            # Skip sending stats while PC is locked (display is in clock mode)
            if pc_locked:
                continue

            packed, prev_net, prev_time, prev_disk_io = collect_stats_tlv(
                self._gpu, self._enabled_stat_types, prev_net, prev_time, prev_disk_io,
                self._net_interface, self._disk_device, self._disk_mount
            )

            try:
                with self._hid_lock:
                    self._device.write(b"\x06" + bytes([MSG_STATS]) + packed)
                self._stats_count += 1
                if self.on_stats_sent:
                    self.on_stats_sent()
            except (IOError, OSError) as exc:
                logging.warning("HID write failed (device disconnected?): %s", exc)
                try:
                    self._device.close()
                except Exception:
                    pass
                self._device = None
                self._set_bridge_connected(False)

                # Reconnect
                if not self._connect_bridge():
                    break
                # Restart vendor read thread for new device
                self._vendor_thread = threading.Thread(
                    target=self._vendor_read_loop, daemon=True
                )
                self._vendor_thread.start()
                prev_net = psutil.net_io_counters()
                prev_time = time.time()
                continue

            if self._device is not None:
                send_time_sync(self._device, self._hid_lock)

        # Clean up
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
        self._set_bridge_connected(False)


# ---------------------------------------------------------------------------
# Headless CLI entry point
# ---------------------------------------------------------------------------

def main():
    global running

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logging.info("Hotkey Bridge Companion starting (headless)...")

    service = CompanionService()
    service.start()

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    service.stop()
    logging.info("Companion stopped.")


if __name__ == "__main__":
    main()
