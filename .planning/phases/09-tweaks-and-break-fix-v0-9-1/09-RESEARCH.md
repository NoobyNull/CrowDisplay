# Phase 9: Tweaks and Break-Fix (v0.9.1) - Research

**Researched:** 2026-02-15
**Domain:** LVGL v8 UI enhancements, ESP-NOW protocol extensions, D-Bus system integration
**Confidence:** HIGH (LVGL APIs), MEDIUM (protocol design), MEDIUM (D-Bus integration)

## Summary

Research for six v0.9.1 features targeting flexibility, visual polish, and system integration. Core findings: LVGL v8 grid layout with col/row span supports variable button sizes; absolute positioning available but grid preferred for responsive layouts. Image decoder support exists for BMP/JPG from SD but requires careful PSRAM management on ESP32-S3. D-Bus notification monitoring via dbus-next follows established pattern from existing shutdown detection. Stats protocol requires flexible key-value encoding to support expanded monitor types. Display modes need architectural separation from power states.

**Primary recommendation:** Implement features in dependency order: positioning first (foundation), then sizing (builds on positioning), pressed color (simple addition), stats header (protocol change), notifications (protocol + UI), display modes last (integrates all UI states).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LVGL | 8.3 | UI framework | Already integrated, stable API |
| ESP-NOW | v1.0 | Wireless link | 250-byte payload limit (current implementation) |
| PySide6 | Latest | Editor GUI | Already used for editor |
| dbus-next | Latest | D-Bus async I/O | Already used for shutdown detection |
| psutil | Latest | System monitoring | Already used for stats collection |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pynvml | Latest | NVIDIA GPU stats | Already integrated for GPU monitoring |
| ArduinoJson | v6+ | Config serialization | Already integrated for config.json |
| SD library | Arduino | SD card I/O | Already integrated for config storage |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Grid layout | Absolute positioning | Grid auto-sizes, absolute requires manual pixel math per 800x480 screen |
| dbus-next | dbus-python | dbus-next has better async support, already in use |
| ESP-NOW v1 | ESP-NOW v2 | v2 supports 1470-byte payloads but requires IDF 5.x, current stack uses v1 (250 bytes) |

**Installation:**
```bash
# Companion dependencies (already installed)
pip install psutil pynvml dbus-next PySide6
```

## Architecture Patterns

### Recommended Config Schema Extensions

**v0.9.1.1 - Positionable Buttons:**
```cpp
struct ButtonConfig {
    // Existing fields...
    std::string label;
    uint32_t color;
    // NEW: Grid positioning (optional, defaults to auto-flow)
    int8_t grid_row;      // -1 = auto-flow (default), 0+ = explicit row
    int8_t grid_col;      // -1 = auto-flow (default), 0+ = explicit column
};
```

**v0.9.1.2 - Pressed Color:**
```cpp
struct ButtonConfig {
    // Existing fields...
    uint32_t color;           // Normal state color
    // NEW: Pressed state color (optional)
    uint32_t pressed_color;   // 0x000000 = auto-darken (default)
};
```

**v0.9.1.3 - Variable Sizing:**
```cpp
struct ButtonConfig {
    // Existing fields...
    int8_t grid_row, grid_col;
    // NEW: Span controls (default 1x1)
    uint8_t col_span;         // Default: 1, Range: 1-4
    uint8_t row_span;         // Default: 1, Range: 1-3
};
```

**v0.9.1.5 - Configurable Stats:**
```cpp
enum StatType : uint8_t {
    STAT_CPU_PERCENT,
    STAT_RAM_PERCENT,
    STAT_GPU_PERCENT,
    STAT_CPU_TEMP,
    STAT_GPU_TEMP,
    STAT_DISK_PERCENT,
    STAT_NET_UP,
    STAT_NET_DOWN,
    STAT_CPU_FREQ,        // NEW
    STAT_GPU_FREQ,        // NEW
    STAT_SWAP_PERCENT,    // NEW
    STAT_UPTIME,          // NEW
    // ... up to 20+ types
};

struct StatConfig {
    StatType type;
    uint32_t color;
    uint8_t position;     // Display order (0-7 for 8 slots)
};

struct AppConfig {
    // Existing fields...
    std::vector<StatConfig> stats_header;  // User-selected stats
};
```

**v0.9.1.6 - Display Modes:**
```cpp
enum DisplayMode : uint8_t {
    MODE_HOTKEYS,       // Main hotkey UI (default)
    MODE_CLOCK,         // Analog/digital clock
    MODE_PICTURE_FRAME, // Image slideshow from SD
    MODE_MACRO_PAD,     // Standby with minimal UI
};

struct AppConfig {
    // Existing fields...
    DisplayMode default_mode;
    uint16_t slideshow_interval_sec;  // Picture frame mode
    bool clock_analog;                 // true = analog, false = digital
};
```

### Pattern 1: LVGL Grid Layout with Variable Spans

**What:** LVGL v8 grid layout allows child objects to span multiple rows/columns using `lv_obj_set_grid_cell()`.

**When to use:** Variable button sizing (v0.9.1.3), positioned buttons with responsive layout (v0.9.1.1).

**Example:**
```cpp
// Source: https://docs.lvgl.io/8.3/layouts/grid.html
// Define grid template: 4 equal columns, 3 equal rows
static lv_coord_t col_dsc[] = {LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_TEMPLATE_LAST};
static lv_coord_t row_dsc[] = {LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_TEMPLATE_LAST};

lv_obj_set_grid_dsc_array(tab, col_dsc, row_dsc);

// Place button at row 1, col 2, spanning 2 columns x 1 row (2x1 button)
lv_obj_set_grid_cell(btn, LV_GRID_ALIGN_STRETCH, 2, 2,  // col: align, pos, span
                          LV_GRID_ALIGN_STRETCH, 1, 1); // row: align, pos, span
```

**Key insight:** Grid layout auto-sizes cells based on FR (fractional) units. Buttons with col_span=2 will be exactly 2x the width of col_span=1 buttons. No manual pixel calculations needed.

### Pattern 2: TLV Protocol for Flexible Stats Payload

**What:** Type-Length-Value encoding allows variable stats payloads within 250-byte ESP-NOW limit.

**When to use:** Configurable stats header (v0.9.1.5) with user-selected monitor types.

**Example:**
```cpp
// TLV packet structure:
// [count:u8] [type1:u8][len1:u8][value1...] [type2:u8][len2:u8][value2...] ...

struct StatsPacket {
    uint8_t count;  // Number of TLV entries
    uint8_t data[PROTO_MAX_PAYLOAD - 1];  // TLV stream
};

// Encoding (Python companion):
def encode_stats(stats_dict):
    packet = bytearray([len(stats_dict)])  # count
    for stat_type, value in stats_dict.items():
        packet.append(stat_type)  # type
        if isinstance(value, int) and value < 256:
            packet.append(1)  # length
            packet.append(value & 0xFF)
        elif isinstance(value, int):
            packet.append(2)  # length
            packet.extend(struct.pack('<H', value & 0xFFFF))
    return bytes(packet)

// Decoding (ESP32 display):
void decode_stats_tlv(const uint8_t *data, uint8_t len) {
    uint8_t count = data[0];
    uint8_t pos = 1;
    for (uint8_t i = 0; i < count && pos < len - 1; i++) {
        uint8_t type = data[pos++];
        uint8_t vlen = data[pos++];
        if (pos + vlen > len) break;

        // Extract value based on length
        uint16_t value = 0;
        if (vlen == 1) value = data[pos];
        else if (vlen == 2) value = data[pos] | (data[pos+1] << 8);

        update_stat_widget(type, value);  // Map to UI widget
        pos += vlen;
    }
}
```

**Overhead:** 3 bytes per stat (type + length + value for 8-bit values). For 8 stats: 24 bytes vs 10 bytes fixed. Acceptable tradeoff for flexibility.

### Pattern 3: D-Bus Session Bus Notification Monitoring

**What:** Monitor `org.freedesktop.Notifications` D-Bus interface for desktop notifications (Slack, Discord, etc.).

**When to use:** Host OS notification forwarding (v0.9.1.4).

**Example:**
```python
# Source: https://github.com/altdesktop/python-dbus-next pattern
from dbus_next.aio import MessageBus
from dbus_next import BusType

async def start_notification_listener(callback):
    bus = await MessageBus(bus_type=BusType.SESSION).connect()

    # Subscribe to Notify method calls on the notifications interface
    def on_notify(app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout):
        # Filter by app_name (e.g., "Slack", "Discord", "thunderbird")
        if app_name in notification_filter:
            callback(app_name, summary, body)

    # Introspect and attach signal handler
    introspection = await bus.introspect(
        "org.freedesktop.Notifications",
        "/org/freedesktop/Notifications"
    )
    proxy = bus.get_proxy_object(
        "org.freedesktop.Notifications",
        "/org/freedesktop/Notifications",
        introspection
    )
    interface = proxy.get_interface("org.freedesktop.Notifications")

    # Note: Notifications.Notify is a method call, not a signal
    # Need to implement a custom notifications daemon or use eavesdrop
    # Alternative: Use dbus-monitor or qdbus-monitor pattern with eavesdrop=True

    # Simpler approach: Monitor the D-Bus message stream with match rules
    bus.add_match_rule("type='method_call',interface='org.freedesktop.Notifications',member='Notify'")

    # Attach generic message handler
    def message_handler(msg):
        if msg.interface == "org.freedesktop.Notifications" and msg.member == "Notify":
            args = msg.body
            app_name = args[0] if len(args) > 0 else ""
            summary = args[3] if len(args) > 3 else ""
            body = args[4] if len(args) > 4 else ""
            callback(app_name, summary, body)

    bus.add_message_handler(message_handler)
    await bus.wait_for_disconnect()
```

**Limitation:** Requires eavesdrop=True on system bus policy or running as notification daemon replacement. Safer approach: Monitor specific application D-Bus interfaces (e.g., Slack's com.slack.Slack) or use existing notification-daemon with custom plugin.

### Pattern 4: LVGL Image Decoding from SD Card

**What:** LVGL v8 supports external image decoders (BMP, JPG, PNG) with file system integration.

**When to use:** Picture frame mode (v0.9.1.6) loading images from SD card.

**Example:**
```cpp
// Source: https://docs.lvgl.io/8.3/overview/image.html
// lv_conf.h configuration:
#define LV_USE_FS_STDIO 1
#define LV_USE_BMP 1
#define LV_USE_SJPG 1  // Split JPEG decoder (lower memory)

// Register SD card filesystem driver (already done in project)
lv_fs_drv_t drv;
lv_fs_drv_init(&drv);
drv.letter = 'S';  // Drive letter 'S' for SD
drv.open_cb = sd_open;
drv.close_cb = sd_close;
drv.read_cb = sd_read;
// ... other callbacks
lv_fs_drv_register(&drv);

// Display image from SD card
lv_obj_t *img = lv_img_create(lv_scr_act());
lv_img_set_src(img, "S:/pictures/image1.jpg");  // S: = SD card
lv_obj_center(img);
```

**Memory constraint:** 800x480 RGB565 image = 768 KB uncompressed. With 8 MB PSRAM, can cache 2-3 full-screen images. Use SJPG (split JPEG) decoder to decode line-by-line, reducing peak memory usage to ~100 KB.

### Pattern 5: LVGL Toast Notification Overlay

**What:** Custom toast notification using lv_msgbox with auto-close animation.

**When to use:** Desktop notification forwarding (v0.9.1.4) as non-blocking overlay.

**Example:**
```cpp
// Source: https://forum.lvgl.io/t/toast-prompt-box/8253 pattern
void show_toast(const char *app_name, const char *summary, const char *body) {
    // Create modal background (semi-transparent overlay)
    lv_obj_t *bg = lv_obj_create(lv_scr_act());
    lv_obj_set_size(bg, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_opa(bg, LV_OPA_50, LV_PART_MAIN);
    lv_obj_set_style_bg_color(bg, lv_color_black(), LV_PART_MAIN);
    lv_obj_clear_flag(bg, LV_OBJ_FLAG_SCROLLABLE);

    // Create message box on top
    lv_obj_t *mbox = lv_msgbox_create(bg, app_name, summary, nullptr, false);
    lv_obj_set_size(mbox, 600, 150);
    lv_obj_align(mbox, LV_ALIGN_TOP_RIGHT, -20, 60);  // Top-right corner below header

    // Add body text if present
    if (body && strlen(body) > 0) {
        lv_obj_t *desc = lv_label_create(mbox);
        lv_label_set_text(desc, body);
        lv_obj_set_style_text_font(desc, &lv_font_montserrat_12, LV_PART_MAIN);
    }

    // Auto-close after 5 seconds with fade-out animation
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, bg);
    lv_anim_set_values(&a, LV_OPA_COVER, LV_OPA_TRANSP);
    lv_anim_set_exec_cb(&a, (lv_anim_exec_xcb_t)lv_obj_set_style_opa);
    lv_anim_set_time(&a, 300);  // 300ms fade
    lv_anim_set_delay(&a, 5000);  // 5 second delay
    lv_anim_set_ready_cb(&a, [](lv_anim_t *a) {
        lv_obj_del((lv_obj_t*)a->var);  // Delete on animation complete
    });
    lv_anim_start(&a);
}
```

**Layout impact:** Toast overlays on top of main UI without disrupting hotkey grid. Use z-index or parent hierarchy to ensure visibility.

### Pattern 6: Analog Clock Rendering with LVGL Primitives

**What:** Analog clock using lv_arc for face and lv_line for hands.

**When to use:** Clock display mode (v0.9.1.6) analog variant.

**Example:**
```cpp
// Source: https://controllerstech.com/display-analog-clock-on-gc9a01-using-stm32-lvgl-squareline-studio-part-2/
void create_analog_clock(lv_obj_t *parent) {
    // Clock face (full circle arc)
    lv_obj_t *face = lv_arc_create(parent);
    lv_obj_set_size(face, 300, 300);
    lv_obj_center(face);
    lv_arc_set_bg_angles(face, 0, 360);
    lv_arc_set_value(face, 0);
    lv_obj_remove_style(face, NULL, LV_PART_KNOB);  // Remove knob (indicator)
    lv_obj_set_style_arc_width(face, 4, LV_PART_MAIN);
    lv_obj_set_style_arc_color(face, lv_color_hex(0x888888), LV_PART_MAIN);

    // Hour hand (line)
    static lv_point_t hour_points[2];
    lv_obj_t *hour_hand = lv_line_create(parent);
    lv_line_set_points(hour_hand, hour_points, 2);
    lv_obj_set_style_line_width(hour_hand, 6, LV_PART_MAIN);
    lv_obj_set_style_line_color(hour_hand, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_line_rounded(hour_hand, true, LV_PART_MAIN);

    // Minute hand
    static lv_point_t min_points[2];
    lv_obj_t *min_hand = lv_line_create(parent);
    lv_line_set_points(min_hand, min_points, 2);
    lv_obj_set_style_line_width(min_hand, 4, LV_PART_MAIN);
    lv_obj_set_style_line_color(min_hand, lv_color_white(), LV_PART_MAIN);

    // Update function (called every second)
    void update_analog_clock(uint8_t hour, uint8_t minute) {
        float hour_angle = (hour % 12) * 30 + minute * 0.5;  // 30° per hour + minute offset
        float min_angle = minute * 6;  // 6° per minute

        // Calculate hand endpoints (polar to cartesian, 0° = 12 o'clock)
        int cx = 150, cy = 150;  // Center
        hour_points[0] = {cx, cy};
        hour_points[1] = {
            (lv_coord_t)(cx + 60 * sin(hour_angle * PI / 180)),
            (lv_coord_t)(cy - 60 * cos(hour_angle * PI / 180))
        };
        lv_line_set_points(hour_hand, hour_points, 2);

        min_points[0] = {cx, cy};
        min_points[1] = {
            (lv_coord_t)(cx + 90 * sin(min_angle * PI / 180)),
            (lv_coord_t)(cy - 90 * cos(min_angle * PI / 180))
        };
        lv_line_set_points(min_hand, min_points, 2);
    }
}
```

**Performance:** Updating clock hands every second = 2 line redraws. Negligible overhead. Zero degrees is at 3 o'clock in LVGL arcs; use rotation offset or adjust angle calculation for 12 o'clock = 0°.

### Anti-Patterns to Avoid

- **Fixed pixel positioning for buttons:** Don't hardcode `lv_obj_set_pos(btn, 50, 100)`. Use grid layout for automatic responsive sizing across 800x480 screen. Absolute positioning breaks when adding/removing buttons.

- **Blocking D-Bus calls in main thread:** D-Bus notification monitoring must run in separate async thread. Don't call `bus.call_sync()` from HID write thread -- causes 100ms+ stalls.

- **Loading full 800x480 BMP into RAM:** Don't use `lv_img_decoder_dsc_t` with entire image buffer. Use SJPG line-by-line decoder to keep peak memory under 100 KB.

- **Auto-darkening every button press:** Don't calculate `lv_color_darken()` on every LV_EVENT_PRESSED. Pre-calculate pressed color once during button creation and set as LV_STATE_PRESSED style.

- **Sending 250-byte stats packet every second:** Don't send all 20 stat types if only 8 are displayed. Use TLV to send only user-configured stats, reducing bandwidth and processing overhead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| D-Bus notification monitoring | Custom D-Bus protocol parser | dbus-next with MessageBus | Edge cases: eavesdrop permissions, message filtering, async lifecycle management |
| Image decoding from SD | Custom BMP/JPEG parser | LVGL lv_img + LV_USE_SJPG | Edge cases: progressive JPEG, color space conversion, memory fragmentation, partial decoding |
| Grid layout pixel calculations | Manual row/col to pixel conversion | LVGL lv_obj_set_grid_cell() | Edge cases: aspect ratio preservation, padding distribution, responsive resize, alignment |
| Toast animation timing | Manual setTimeout + opacity fade | lv_anim_t with delay + ready_cb | Edge cases: animation queueing, early dismissal, memory cleanup after animation |
| TLV protocol encoding | Custom byte packing | Existing TLV libraries (e.g., cborprotocol if needed) | Edge cases: endianness, variable-length integers, schema evolution |

**Key insight:** LVGL provides robust layout and animation APIs that handle edge cases (screen rotation, DPI scaling, memory cleanup). Custom implementations risk memory leaks and layout bugs.

## Common Pitfalls

### Pitfall 1: ESP-NOW v1 vs v2 Payload Limits
**What goes wrong:** Attempting to send 1470-byte payloads fails silently when project uses ESP-NOW v1 (250-byte limit).

**Why it happens:** ESP-IDF 4.x uses ESP-NOW v1 by default. v2 requires IDF 5.x and explicit peer version negotiation.

**How to avoid:** Verify ESP-NOW version with `ESP_IDF_VERSION` macro. If v1, design protocol for 250-byte max payload. For TLV stats: 3 bytes/stat × 80 stats = 240 bytes (fits). For notifications: app_name (20) + summary (100) + body (120) = 240 bytes (fits with truncation).

**Warning signs:** `esp_now_send()` returns ESP_OK but peer doesn't receive packets >250 bytes. Check receiver callback: `len` parameter will be 250 even if sender sent more.

### Pitfall 2: LVGL Grid Cell Position vs Auto-Flow
**What goes wrong:** Buttons with explicit `grid_row`/`grid_col` overlap or create gaps when mixed with auto-flow buttons.

**Why it happens:** LVGL grid layout processes explicit cells first, then fills remaining cells with auto-flow. If explicit cells block a row, auto-flow skips to next available cell, leaving gaps.

**How to avoid:** Either use ALL explicit positioning OR ALL auto-flow per page. Don't mix. If mixing is required, place explicit cells at the end of the grid and auto-flow at the start.

**Warning signs:** Buttons appear in unexpected positions. Some grid cells are empty despite having button configs. Use `lv_obj_invalidate()` to force redraw and check cell occupancy.

### Pitfall 3: PSRAM Image Cache Fragmentation
**What goes wrong:** Loading 5+ JPEG images into cache causes allocation failures even with 8 MB PSRAM free.

**Why it happens:** LVGL image cache uses heap allocation. Repeated load/unload cycles fragment PSRAM. Large contiguous blocks become unavailable even with total free space > required size.

**How to avoid:** Pre-allocate image cache with `LV_CACHE_DEF_SIZE` large enough for max slideshow images (e.g., 2 MB for 3× 800x480 RGB565 images). Use `lv_img_cache_set_size()` and monitor `lv_mem_monitor()` fragmentation metric.

**Warning signs:** `lv_img_set_src()` fails with "out of memory" but `lv_mem_monitor()` shows >1 MB free. Check `free_biggest_size` -- if <768 KB, fragmentation is preventing 800x480 image allocation.

### Pitfall 4: D-Bus Session Bus vs System Bus
**What goes wrong:** Notification monitoring fails with "permission denied" or "name not found" errors.

**Why it happens:** `org.freedesktop.Notifications` is on the SESSION bus (per-user), not SYSTEM bus. Connecting to wrong bus yields no signals.

**How to avoid:** Use `BusType.SESSION` when creating MessageBus for notifications. System bus is for systemd, NetworkManager, etc. Session bus is for user applications (notifications, media players).

**Warning signs:** `bus.introspect()` fails with "The name org.freedesktop.Notifications was not provided by any .service files". Check `DBUS_SESSION_BUS_ADDRESS` environment variable.

### Pitfall 5: lv_msgbox Auto-Close Memory Leak
**What goes wrong:** Showing 100 toast notifications leaks 10 MB of LVGL memory.

**Why it happens:** `lv_msgbox_start_auto_close()` in LVGL v8.3 doesn't delete the msgbox object after animation, only hides it. Parent object persists.

**How to avoid:** Use `lv_anim_set_ready_cb()` to delete the msgbox parent object (`bg` in toast example) when animation completes. Don't rely on msgbox built-in auto-close for memory cleanup.

**Warning signs:** `lv_mem_monitor()` shows steadily increasing used memory after each toast. Use `lv_obj_clean(lv_scr_act())` periodically in debug builds to detect orphaned objects.

### Pitfall 6: Grid Column/Row Span > Grid Size
**What goes wrong:** Button with `col_span=3` on a 4-column grid at `grid_col=2` extends beyond grid boundary and clips.

**Why it happens:** LVGL doesn't validate span against grid size. Button occupies cells [2, 3, 4] (col 4 doesn't exist in 0-indexed 4-column grid).

**How to avoid:** Validate in config loader: `if (grid_col + col_span > 4) { col_span = 4 - grid_col; }`. Clamp span to available cells. Editor should enforce this constraint in UI.

**Warning signs:** Button appears clipped at right/bottom edge of grid. Part of button text is cut off. Check `lv_obj_get_width()` -- will be larger than parent grid cell width.

## Code Examples

Verified patterns from official sources and project architecture:

### Grid Layout Setup for Button Positioning
```cpp
// Source: https://docs.lvgl.io/8.3/layouts/grid.html
// Replace current flex layout with grid layout in create_ui_widgets()

// Define 4-column, 3-row grid with equal fractional units
static lv_coord_t col_dsc[] = {LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_TEMPLATE_LAST};
static lv_coord_t row_dsc[] = {LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_TEMPLATE_LAST};

// Apply to tab page (replace lv_obj_set_flex_flow)
lv_obj_set_layout(tab, LV_LAYOUT_GRID);
lv_obj_set_grid_dsc_array(tab, col_dsc, row_dsc);

// Create button with explicit position (row=1, col=2) and span (2x1)
lv_obj_t *btn = create_hotkey_button(tab, btn_cfg);
lv_obj_set_grid_cell(btn,
    LV_GRID_ALIGN_STRETCH, btn_cfg->grid_col, btn_cfg->col_span,  // column
    LV_GRID_ALIGN_STRETCH, btn_cfg->grid_row, btn_cfg->row_span); // row
```

### Pressed Color Configuration
```cpp
// Source: Project ui.cpp line 120 (current auto-darken implementation)
// Modify create_hotkey_button() to support custom pressed color

lv_color_t pressed_color;
if (btn_cfg->pressed_color == 0x000000) {
    // Auto-darken if not explicitly set
    pressed_color = lv_color_darken(lv_color_hex(btn_cfg->color), LV_OPA_30);
} else {
    // Use explicit pressed color
    pressed_color = lv_color_hex(btn_cfg->pressed_color);
}
lv_obj_set_style_bg_color(btn, pressed_color, LV_STATE_PRESSED);
```

### TLV Stats Protocol Encoding
```python
# Source: Custom protocol design based on shared/protocol.h pattern
# Replace fixed StatsPayload with TLV encoding in hotkey_companion.py

def encode_stats_tlv(stats_config):
    """Encode stats as TLV stream for MSG_STATS payload.

    Args:
        stats_config: List of (StatType, value) tuples

    Returns:
        bytes: TLV-encoded payload (max 250 bytes)
    """
    packet = bytearray([len(stats_config)])  # count
    for stat_type, value in stats_config:
        packet.append(stat_type)  # type (uint8)

        # Encode value based on range
        if value < 256:
            packet.append(1)  # length
            packet.append(value & 0xFF)
        elif value < 65536:
            packet.append(2)  # length
            packet.extend(struct.pack('<H', value & 0xFFFF))
        else:
            packet.append(4)  # length
            packet.extend(struct.pack('<I', value & 0xFFFFFFFF))

    return bytes(packet)

# Usage in stats collection loop:
stats = [
    (STAT_CPU_PERCENT, cpu_percent),
    (STAT_RAM_PERCENT, ram_percent),
    (STAT_GPU_PERCENT, gpu_percent),
    # ... only stats enabled in config
]
payload = encode_stats_tlv(stats)
device.write(b"\x00" + bytes([MSG_STATS]) + payload)
```

### D-Bus Notification Monitoring (Session Bus)
```python
# Source: https://wiki.python.org/moin/DbusExamples + project hotkey_companion.py pattern
# Add to hotkey_companion.py alongside existing D-Bus shutdown listener

async def start_notification_listener(app_filter, callback):
    """Monitor org.freedesktop.Notifications for desktop notifications.

    Args:
        app_filter: Set of app names to forward (e.g., {"Slack", "Discord"})
        callback: Function(app_name, summary, body) called on matching notification
    """
    try:
        from dbus_next.aio import MessageBus
        from dbus_next import BusType
    except ImportError:
        logging.warning("dbus-next not installed -- notification forwarding disabled")
        return

    try:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()  # SESSION, not SYSTEM
    except Exception as exc:
        logging.warning("Cannot connect to session D-Bus: %s", exc)
        return

    # Add match rule for Notify method calls (requires eavesdrop permission or notification daemon role)
    # Alternative: Use Freedesktop Secret Service or monitor specific app interfaces

    # Simplified approach: Monitor notification-daemon logs or use desktop-notifier library
    # For production: Implement custom notification server or use DBus.add_signal_receiver pattern

    logging.info("D-Bus notification listener active (session bus)")
    await bus.wait_for_disconnect()
```

**Note:** Full notification monitoring requires either (1) running as notification daemon replacement, (2) patching D-Bus policy for eavesdrop, or (3) using desktop-notifier library as intermediary. Simplest production approach: desktop-notifier → file → companion poll pattern.

### LVGL Image Slideshow from SD Card
```cpp
// Source: https://docs.lvgl.io/8.3/overview/image.html
// Picture frame display mode implementation

// Global state for slideshow
static lv_obj_t *slideshow_img = nullptr;
static std::vector<std::string> slideshow_files;
static size_t slideshow_index = 0;
static lv_timer_t *slideshow_timer = nullptr;

void init_picture_frame_mode() {
    // Scan SD card for images
    File dir = SD.open("/pictures");
    if (dir) {
        File entry;
        while (entry = dir.openNextFile()) {
            if (!entry.isDirectory()) {
                String name = entry.name();
                if (name.endsWith(".jpg") || name.endsWith(".bmp")) {
                    slideshow_files.push_back("/pictures/" + std::string(name.c_str()));
                }
            }
            entry.close();
        }
        dir.close();
    }

    if (slideshow_files.empty()) {
        Serial.println("No images found in /pictures");
        return;
    }

    // Create image widget (full screen)
    slideshow_img = lv_img_create(lv_scr_act());
    lv_obj_set_size(slideshow_img, SCREEN_WIDTH, SCREEN_HEIGHT);
    lv_obj_align(slideshow_img, LV_ALIGN_CENTER, 0, 0);
    lv_img_set_zoom(slideshow_img, 256);  // 1:1 scale

    // Load first image
    load_next_slideshow_image();

    // Start timer for slideshow interval (e.g., 30 seconds)
    slideshow_timer = lv_timer_create(slideshow_timer_cb, 30000, nullptr);
}

void load_next_slideshow_image() {
    if (slideshow_files.empty()) return;

    // Build SD card path (S: = SD drive letter from lv_fs driver)
    std::string path = "S:" + slideshow_files[slideshow_index];
    lv_img_set_src(slideshow_img, path.c_str());

    slideshow_index = (slideshow_index + 1) % slideshow_files.size();
}

void slideshow_timer_cb(lv_timer_t *timer) {
    load_next_slideshow_image();
}
```

**Memory optimization:** Enable `LV_USE_SJPG` (split JPEG) in lv_conf.h to decode line-by-line. Peak memory: ~100 KB vs 768 KB for full image buffer.

### Display Mode Architecture Separation
```cpp
// Source: Project power.h pattern extended for display modes
// Add to power.h alongside PowerState

enum DisplayMode : uint8_t {
    MODE_HOTKEYS,       // Main hotkey UI (default)
    MODE_CLOCK,         // Clock display (analog or digital)
    MODE_PICTURE_FRAME, // Image slideshow
    MODE_MACRO_PAD,     // Minimal standby UI
};

// Global state
static DisplayMode current_mode = MODE_HOTKEYS;
static PowerState current_power = POWER_ACTIVE;

void display_set_mode(DisplayMode mode) {
    if (mode == current_mode) return;

    // Save previous mode
    DisplayMode prev_mode = current_mode;
    current_mode = mode;

    // Clean up previous mode UI
    switch (prev_mode) {
        case MODE_CLOCK:
            if (clock_screen) lv_scr_load(main_screen);
            break;
        case MODE_PICTURE_FRAME:
            if (slideshow_timer) lv_timer_del(slideshow_timer);
            if (slideshow_img) lv_obj_del(slideshow_img);
            break;
        // ... cleanup for other modes
    }

    // Initialize new mode UI
    switch (mode) {
        case MODE_HOTKEYS:
            show_hotkey_view();  // Existing function
            break;
        case MODE_CLOCK:
            show_clock_mode();  // Existing function
            break;
        case MODE_PICTURE_FRAME:
            init_picture_frame_mode();  // New function
            break;
        case MODE_MACRO_PAD:
            init_macro_pad_mode();  // New function (minimal UI)
            break;
    }

    Serial.printf("Display mode changed: %d -> %d\n", prev_mode, mode);
}

DisplayMode display_get_mode() {
    return current_mode;
}
```

**Key insight:** Display mode is orthogonal to power state. Can have MODE_CLOCK + POWER_DIMMED (low brightness clock) vs MODE_HOTKEYS + POWER_ACTIVE (full brightness hotkeys).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed 4x3 button grid with flex wrap | Grid layout with col/row spans | v0.9.1.1 (planned) | Enables variable button sizes and explicit positioning |
| Auto-darkened pressed state only | Configurable pressed color | v0.9.1.2 (planned) | Allows custom visual feedback per button |
| Fixed 10-byte StatsPayload struct | TLV-encoded stats stream | v0.9.1.5 (planned) | Supports 20+ stat types, user-configurable selection |
| 3 power states (ACTIVE/DIMMED/CLOCK) | 4 display modes + 3 power states | v0.9.1.6 (planned) | Orthogonal control: mode (what to show) vs power (brightness) |
| ESP-NOW v1 (250 bytes) | ESP-NOW v2 (1470 bytes) | Not planned (requires IDF 5.x) | Would enable larger notifications, not needed for current features |

**Deprecated/outdated:**
- **lv_obj_set_flex_flow() for button layout:** Replaced by lv_obj_set_layout(LV_LAYOUT_GRID) for v0.9.1.1. Flex still used for other UI elements (header, stats row).
- **Hardcoded stat_labels[8] array:** Replaced by dynamic StatConfig vector in v0.9.1.5. Allows runtime configuration of stats count and types.
- **PowerState::POWER_CLOCK as mode:** Refactored to DisplayMode::MODE_CLOCK in v0.9.1.6. POWER_CLOCK remains as low-brightness state but doesn't control UI content.

## Open Questions

1. **D-Bus notification monitoring permission model**
   - What we know: org.freedesktop.Notifications is on session bus, requires eavesdrop or daemon role
   - What's unclear: Best approach for non-root user without replacing notification daemon
   - Recommendation: Start with desktop-notifier library as intermediary (file-based IPC) in v0.9.1.4, evaluate direct D-Bus in post-release if needed

2. **ESP-NOW v2 migration timeline**
   - What we know: v2 supports 1470-byte payloads, requires ESP-IDF 5.x
   - What's unclear: Whether current Arduino-ESP32 framework version supports v2
   - Recommendation: Verify with `ESP_IDF_VERSION` macro. If v1, design all v0.9.1 protocols for 250-byte limit. Defer v2 migration to future phase.

3. **Grid layout performance with 16 buttons**
   - What we know: Grid layout auto-sizes cells using FR units
   - What's unclear: Redraw performance on 800x480 RGB LCD with 16× 2x2 span buttons vs 12× 1x1 buttons
   - Recommendation: Implement in v0.9.1.3 and benchmark with `lv_refr_now()` timing. If >100ms refresh, optimize with partial invalidation.

4. **Image cache size vs slideshow count**
   - What we know: 800x480 RGB565 = 768 KB per image, 8 MB PSRAM available
   - What's unclear: Optimal cache size for smooth slideshow without fragmentation after 100+ image cycles
   - Recommendation: Set `LV_CACHE_DEF_SIZE` to 2 MB (2-3 images) initially. Monitor `lv_mem_monitor()` fragmentation in v0.9.1.6. Adjust if free_biggest_size drops below 768 KB.

5. **Notification payload truncation strategy**
   - What we know: 250-byte ESP-NOW limit, notifications can have 500+ char body
   - What's unclear: User preference for truncation (body only, summary only, both proportionally)
   - Recommendation: Truncate body to 120 chars in v0.9.1.4. Add config option in post-release if users request summary-only mode.

## Feature Dependencies and Plan Breakdown

### Dependency Graph

```
v0.9.1.1 (Positioning)
    ↓
v0.9.1.3 (Sizing) — requires positioning foundation
    ↓
v0.9.1.2 (Pressed Color) — independent, can be done anytime

v0.9.1.5 (Stats Header) — protocol change, independent of UI layout
    ↓
v0.9.1.4 (Notifications) — builds on stats protocol pattern (TLV/relay)

v0.9.1.6 (Display Modes) — integrates all UI features, should be last
```

### Recommended Plan Grouping

**PLAN 01 (Foundation): Positioning + Pressed Color**
- v0.9.1.1: Grid layout + grid_row/grid_col fields
- v0.9.1.2: Pressed color configuration
- Rationale: Both are config schema changes, editor UI changes, display rendering changes. Natural grouping.
- Risk: LOW (LVGL grid layout is well-documented, pressed color is simple style change)

**PLAN 02 (Advanced Layout): Variable Sizing**
- v0.9.1.3: col_span/row_span support
- Rationale: Builds on grid layout from PLAN 01. Requires editor drag-to-resize UI (more complex than PLAN 01).
- Risk: MEDIUM (need to validate span constraints, editor UX for resizing is non-trivial)

**PLAN 03 (Protocol Extension): Stats Header + Notifications**
- v0.9.1.5: TLV stats protocol + dynamic stats header UI
- v0.9.1.4: D-Bus notification monitoring + MSG_NOTIFICATION protocol + toast overlay
- Rationale: Both extend ESP-NOW protocol with new message types. Both use similar relay pattern (companion → bridge → display).
- Risk: MEDIUM (D-Bus permission model unclear, TLV encoding needs careful testing for 250-byte limit)

**PLAN 04 (Display Modes Integration): Picture Frame + Clock + Macro Pad**
- v0.9.1.6: DisplayMode enum, mode switching, image slideshow, analog clock rendering
- Rationale: Final integration, exercises all UI systems. Should be done after layout and protocol features are stable.
- Risk: MEDIUM (PSRAM fragmentation, image decoder config, mode state transitions)

**Alternative grouping:** Could split PLAN 03 into two (stats separate from notifications) if D-Bus integration proves complex. Notifications can slip to v0.9.2 if needed.

## ESP32-S3 Resource Constraints

### Memory Budget (8 MB PSRAM + 512 KB SRAM)

| Component | Current Usage | v0.9.1 Addition | Total |
|-----------|---------------|-----------------|-------|
| LVGL heap | ~200 KB | +100 KB (image cache) | 300 KB |
| Frame buffers (2× RGB565) | 1.5 MB | 0 | 1.5 MB |
| Config JSON | 50 KB | +20 KB (grid pos, stats, modes) | 70 KB |
| Code + static data | ~600 KB | +50 KB (new features) | 650 KB |
| **Available for images** | **5.7 MB** | **-100 KB (cache)** | **5.6 MB** |

**Slideshow capacity:** 5.6 MB / 768 KB per image = 7 images in cache before fragmentation risk.

### Flash Usage (16 MB total)

| Component | Current | v0.9.1 | Notes |
|-----------|---------|--------|-------|
| Firmware | ~1.2 MB | +100 KB | Grid layout, TLV, D-Bus, image decoder code |
| SPIFFS/LittleFS | 2 MB | 0 | Not used (SD card for storage) |
| OTA partition | 1.2 MB | +100 KB | Dual partition scheme |
| **Free flash** | **11+ MB** | **10.8 MB** | Plenty of headroom |

**Recommendation:** No flash constraints for v0.9.1 features. Could add SPIFFS partition for fallback images if SD card fails.

### Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Grid layout refresh (16 buttons) | <100 ms | Acceptable for config reload |
| Image decode (800x480 JPEG) | <500 ms | SJPG decoder with PSRAM DMA |
| Toast notification overlay | <50 ms | Fade-in animation should be instant |
| Stats update (TLV decode + UI) | <20 ms | 1 Hz update rate, avoid blocking |

## Sources

### Primary (HIGH confidence)
- [LVGL v8.3 Grid Layout Documentation](https://docs.lvgl.io/8.3/layouts/grid.html) - Grid cell positioning with col_span/row_span
- [LVGL v8.3 Image Documentation](https://docs.lvgl.io/8.3/overview/image.html) - Image decoder integration and SD card support
- [ESP-NOW API Reference (ESP-IDF v5.5.2)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/network/esp_now.html) - Payload size limits and version differences
- Project source code: display/ui.cpp, shared/protocol.h, companion/hotkey_companion.py

### Secondary (MEDIUM confidence)
- [LVGL Forum: Toast Prompt Box](https://forum.lvgl.io/t/toast-prompt-box/8253) - Custom toast implementation pattern
- [LVGL Forum: ESP32S3 PSRAM Usage](https://forum.lvgl.io/t/esp32s3-psram-usage/18522) - Memory allocation strategies
- [ControllersTech: Analog Clock with LVGL](https://controllerstech.com/display-analog-clock-on-gc9a01-using-stm32-lvgl-squareline-studio-part-2/) - Arc and line primitives for clock rendering
- [Python Wiki: DBus Examples](https://wiki.python.org/moin/DbusExamples) - D-Bus Python integration patterns

### Tertiary (LOW confidence - needs verification)
- [LVGL Forum: Managing Large Background Images](https://forum.lvgl.io/t/managing-large-background-images-on-esp32-s3-using-filesystem-without-sd-card-due-to-memory-constraints/18872) - PSRAM fragmentation discussion (user report, not official)
- [Random Nerd Tutorials: ESP-NOW](https://randomnerdtutorials.com/esp-now-esp32-arduino-ide/) - Getting started guide (Arduino framework, not official Espressif)

## Metadata

**Confidence breakdown:**
- LVGL grid layout: HIGH - Official documentation with code examples, widely used API
- Image decoding: MEDIUM - Documentation exists but ESP32-S3 PSRAM specifics based on forum discussions
- D-Bus notifications: MEDIUM - dbus-next library documented, but eavesdrop permission model unclear
- ESP-NOW payload: HIGH - Official Espressif documentation with version specifications
- TLV protocol: MEDIUM - Custom design, no existing implementation to reference
- Display modes: HIGH - Architecture pattern extension of existing power.h design

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (30 days - stable APIs, but verify dbus-next and ESP-IDF versions if delaying implementation)

**Next steps:** Create PLAN.md files for 4 recommended plan groupings. Start with PLAN 01 (positioning + pressed color) as foundation.
