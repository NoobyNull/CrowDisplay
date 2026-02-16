---
created: 2026-02-15T23:00:00.000Z
title: Configurable stats header with selectable and placeable monitors
area: ui
files:
  - display/ui.cpp:166-270
  - display/ui.h:13-16
  - display/config.h
  - shared/protocol.h:40-49
  - companion/hotkey_companion.py:361-420
  - companion/ui/editor_main.py
  - companion/config_manager.py
---

## Problem

The stats header bar is currently hardcoded: fixed layout, fixed stats (CPU%, RAM%, GPU%, CPU temp, GPU temp, disk%, net up/down), fixed order, no user control. Users want to:

1. **Select which monitors to show** -- not everyone has a GPU, some want swap instead of disk, some want per-core CPU temps
2. **Place monitors in a chosen order/position** -- arrange the header widgets how they want
3. **More monitor types** -- expand beyond the current 8 stats to cover everything psutil and system APIs can provide

Current stats payload (protocol.h) is a fixed 10-byte struct with only 8 fields. The display renders them in a hardcoded 2-row layout.

## Solution

**Expanded monitor types the companion app can collect:**

Already available via psutil:
- CPU % (overall) -- exists
- CPU % per-core (psutil.cpu_percent(percpu=True))
- CPU frequency (psutil.cpu_freq())
- RAM % -- exists
- RAM used/total GB (psutil.virtual_memory())
- Swap % (psutil.swap_memory())
- Disk % -- exists
- Disk read/write speed (psutil.disk_io_counters())
- Network up/down -- exists
- Network interface name + IP
- Battery % (psutil.sensors_battery()) -- for laptops
- CPU temp -- exists
- Fan speed (psutil.sensors_fans())
- System uptime (psutil.boot_time())
- Load average (os.getloadavg())
- Process count (len(psutil.pids()))

GPU (pynvml / sysfs):
- GPU % -- exists
- GPU temp -- exists
- GPU memory used/total (pynvml.nvmlDeviceGetMemoryInfo)
- GPU power draw (pynvml.nvmlDeviceGetPowerUsage)
- GPU clock speed (pynvml.nvmlDeviceGetClockInfo)

**Config schema (display/config.h):**
- Add `StatsHeaderConfig` struct to AppConfig:
  ```
  struct StatsMonitor {
      std::string type;    // "cpu_percent", "ram_percent", "gpu_temp", etc.
      uint8_t position;    // 0-based slot in header (left to right)
      uint8_t width;       // 1=compact, 2=wide (for graphs or dual values)
  };
  struct StatsHeaderConfig {
      bool enabled;
      std::vector<StatsMonitor> monitors;  // ordered list of what to show
  };
  ```
- Store in config.json alongside profiles

**Protocol extension (shared/protocol.h):**
- Expand StatsPayload or add a flexible MSG_STATS_EXT with key-value pairs
- Option A: Expand fixed struct with more fields (simple, limited)
- Option B: Variable-length payload with type+value pairs (flexible, more complex)
- Recommendation: Option B with a simple TLV (type-length-value) encoding, since the ESP-NOW 250-byte limit gives plenty of room for ~20 stats

**Display (display/ui.cpp):**
- Replace hardcoded 2-row layout with a dynamic row that renders only configured monitors
- Each monitor type has a render function (icon + value + unit)
- Position/order driven by StatsHeaderConfig

**Editor (companion/ui/editor_main.py or new stats_config panel):**
- "Stats Header" configuration page in the editor
- Checklist of available monitor types with drag-to-reorder
- Preview of header layout
- Width option per monitor (compact vs wide)

**Companion app (companion/hotkey_companion.py):**
- Read the stats config to know which monitors to collect
- Only collect and send the enabled monitors (saves USB bandwidth)
- New collection functions for expanded stats (swap, disk I/O, GPU memory, fan speed, etc.)
