# Phase 7: Config Server (SoftAP + HTTP) - Research

**Researched:** 2026-02-15
**Domain:** ESP32-S3 WiFi SoftAP + HTTP server for JSON config upload with ESP-NOW coexistence
**Confidence:** HIGH

## Summary

Phase 7 unifies the existing separate `config_server.cpp` and `ota.cpp` modules into a single SoftAP lifecycle manager, adds a UI trigger (tappable config icon in the header), implements inactivity timeout, and solves the ESP-NOW + SoftAP channel coexistence problem. The foundational code already exists: `config_server.cpp` has a working WebServer with JSON upload/validation/SD-write/rebuild pipeline, and `ota.cpp` has a working firmware upload via `Update.h`. The primary engineering challenge is merging these into one server, adding channel pinning so ESP-NOW stays functional, and building the config mode UI screen.

The ESP32-S3 has a single 2.4 GHz radio. In `WIFI_AP_STA` mode (which both existing modules already use), SoftAP and ESP-NOW share the same physical channel. The critical requirement is that both the display and bridge ESP32 devices operate on the same WiFi channel. Currently neither device explicitly pins a channel -- `peer.channel = 0` (auto) on both sides, and `WiFi.softAP()` is called without a channel parameter (defaults to channel 1). This works by accident in the current code because SoftAP defaults to channel 1 and ESP-NOW auto-selects channel 0 which means "current channel." However, this must be made explicit for reliability.

**Primary recommendation:** Merge `ota.cpp` into `config_server.cpp` as a unified SoftAP manager. Pin WiFi channel 1 explicitly on both display and bridge. Add config mode UI screen (similar to existing OTA screen pattern). Implement application-level inactivity timeout using `millis()` tracking of last HTTP request or client connection.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| WebServer (Arduino ESP32) | built-in | HTTP server for config + OTA upload | Already used in both config_server.cpp and ota.cpp |
| Update.h (Arduino ESP32) | built-in | OTA firmware flashing | Already used in ota.cpp, handles flash write safely |
| WiFi.h (Arduino ESP32) | built-in | SoftAP lifecycle, channel control | Already used throughout project |
| esp_wifi.h (ESP-IDF) | built-in | `esp_wifi_set_channel()` for explicit channel pinning | Required for ESP-NOW coexistence |
| ArduinoJson | ^7.4.0 | JSON validation of uploaded configs | Already in platformio.ini, used in config_server.cpp |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ArduinoOTA | built-in | PlatformIO network upload support | Optional convenience, currently in ota.cpp |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WebServer (sync) | ESPAsyncWebServer | Async handles concurrent requests better, but adds dependency and has known memory leak issues on ESP32; sync WebServer is already working and sufficient for single-client config upload |
| ArduinoOTA | Pure HTTP OTA only | ArduinoOTA adds PlatformIO `--upload-port` convenience; dropping it saves ~10KB flash but loses developer UX |

## Architecture Patterns

### Current File Structure (before Phase 7)
```
display/
  config_server.cpp  -- SoftAP + WebServer + config upload (working)
  config_server.h    -- Header
  ota.cpp            -- Separate SoftAP + WebServer + OTA upload (working)
  ota.h              -- Header
  espnow_link.cpp    -- ESP-NOW with peer.channel=0 (auto)
  ui.cpp             -- OTA button in header, OTA screen, no config button
  main.cpp           -- Polls both config_server and ota separately
```

### Target File Structure (after Phase 7)
```
display/
  config_server.cpp  -- Unified SoftAP manager: config upload + OTA + timeout
  config_server.h    -- Unified header (absorbs ota.h functions)
  espnow_link.cpp    -- ESP-NOW with peer.channel=1 (explicit)
  ui.cpp             -- Config icon in header, config mode screen with SSID/pass/IP
  main.cpp           -- Single config_server_poll() call, no separate ota_poll()
  (ota.cpp DELETED)  -- Merged into config_server.cpp
  (ota.h DELETED)    -- Merged into config_server.h
```

### Pattern 1: Unified SoftAP Lifecycle Manager
**What:** Single module owns WiFi mode transitions (STA -> AP_STA -> STA), WebServer lifecycle, channel pinning, and inactivity timeout. Both config upload and OTA firmware upload are endpoints on the same WebServer instance.
**When to use:** Whenever the device needs WiFi SoftAP for any purpose.
**Why:** The current codebase has TWO independent SoftAP managers (config_server.cpp and ota.cpp) that each create their own WebServer on port 80, each call WiFi.softAP() independently, and cannot run simultaneously. Merging eliminates the conflict and simplifies main loop polling.

**Example:**
```cpp
// Unified config_server.cpp
#include <WiFi.h>
#include <WebServer.h>
#include <Update.h>
#include <esp_wifi.h>

#define CONFIG_SSID     "CrowPanel-Config"
#define CONFIG_PASS     "crowconfig"
#define CONFIG_CHANNEL  1
#define INACTIVITY_TIMEOUT_MS (5 * 60 * 1000)  // 5 minutes

static WebServer *web_server = nullptr;
static uint32_t last_activity_time = 0;
static bool active = false;

bool config_server_start() {
    if (active) return true;

    // AP_STA keeps ESP-NOW alive alongside SoftAP
    WiFi.mode(WIFI_AP_STA);

    // Explicit channel 1 for SoftAP -- must match ESP-NOW channel
    if (!WiFi.softAP(CONFIG_SSID, CONFIG_PASS, CONFIG_CHANNEL)) {
        WiFi.mode(WIFI_STA);
        return false;
    }

    // Re-pin channel after mode change (defensive)
    esp_wifi_set_channel(CONFIG_CHANNEL, WIFI_SECOND_CHAN_NONE);

    web_server = new WebServer(80);
    // Config endpoints
    web_server->on("/", HTTP_GET, handle_root_page);
    web_server->on("/api/config/upload", HTTP_POST, handle_config_done, handle_config_upload);
    // OTA endpoint
    web_server->on("/update", HTTP_POST, handle_ota_done, handle_ota_upload);
    web_server->begin();

    last_activity_time = millis();
    active = true;
    return true;
}
```
Source: Derived from existing `display/config_server.cpp` and `display/ota.cpp` patterns

### Pattern 2: Application-Level Inactivity Timeout
**What:** Track `millis()` of last HTTP request or SoftAP client event. In the poll function, check if timeout exceeded and auto-stop.
**When to use:** WIFI-05 requires 5-minute auto-stop on inactivity.
**Why:** ESP32 SoftAP has no configurable application-level inactivity API. The default 5-minute client-disconnect timer is for WiFi-layer station timeouts, not HTTP request inactivity. Must implement at application level.

**Example:**
```cpp
void config_server_poll() {
    if (!active || !web_server) return;

    web_server->handleClient();

    // Reset activity timer on any connected client
    if (WiFi.softAPgetStationNum() > 0) {
        last_activity_time = millis();
    }

    // Auto-stop after inactivity timeout
    if (millis() - last_activity_time > INACTIVITY_TIMEOUT_MS) {
        Serial.println("Config server: inactivity timeout, stopping");
        config_server_stop();
        // Return to main screen from config mode screen
        hide_config_screen();
    }
}
```
Source: Application-level pattern, no ESP-IDF API for this

### Pattern 3: Config Mode UI Screen (follows existing OTA screen pattern)
**What:** Dedicated LVGL screen showing SSID, password, IP address, and "Apply & Exit" button. Created once in `create_ui()`, shown/hidden on demand.
**When to use:** WIFI-01 and WIFI-04 require a UI trigger and info display.
**Why:** The existing `ota_screen` in `ui.cpp` is the exact pattern -- a separate `lv_obj_t*` screen created with `lv_obj_create(NULL)`, loaded with `lv_scr_load()`, with an exit button that toggles back. The config screen follows the same structure.

**Example:**
```cpp
// In create_ui(), alongside ota_screen creation:
config_screen = lv_obj_create(NULL);
// ... title, SSID label, password label, IP label, "Apply & Exit" button

// In header, add config icon button (next to OTA button):
lv_obj_t *cfg_btn = lv_label_create(header);
lv_label_set_text(cfg_btn, LV_SYMBOL_SETTINGS);  // gear icon
lv_obj_align(cfg_btn, LV_ALIGN_RIGHT_MID, -135, 0);  // left of brightness btn
lv_obj_add_flag(cfg_btn, LV_OBJ_FLAG_CLICKABLE);
lv_obj_add_event_cb(cfg_btn, config_btn_event_cb, LV_EVENT_CLICKED, nullptr);
```
Source: Existing `display/ui.cpp` OTA screen pattern (lines 505-531)

### Pattern 4: Channel Pinning for ESP-NOW Coexistence
**What:** Both display and bridge explicitly pin to WiFi channel 1. ESP-NOW peer registration uses channel 1 (not 0/auto). After any WiFi mode change, re-pin channel.
**When to use:** Always, on both devices. WIFI-07 requirement.
**Why:** ESP32 has one radio. In AP_STA mode, SoftAP channel dictates the radio's operating frequency. ESP-NOW peers configured with channel=0 use "current channel" which works but is fragile. Explicit channel=1 on all parties ensures deterministic behavior.

**Example (display espnow_link.cpp change):**
```cpp
void espnow_link_init() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    // Pin to channel 1 before ESP-NOW init
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

    esp_now_init();

    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, broadcast_addr, 6);
    peer.channel = 1;  // Was 0 (auto), now explicit
    peer.encrypt = false;
    esp_now_add_peer(&peer);
    // ...
}
```

**Example (bridge espnow_link.cpp change):**
```cpp
void espnow_link_init() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    // Pin to channel 1 to match display SoftAP channel
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

    esp_now_init();
    esp_now_register_recv_cb(on_recv);
    // ...
}

// Also update peer registration:
peer.channel = 1;  // Was 0 (auto)
```
Source: [ESP-IDF ESP-NOW docs](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/network/esp_now.html), [ESP32 Forum: ESP-NOW + WiFi channel](https://www.esp32.com/viewtopic.php?t=12772)

### Anti-Patterns to Avoid
- **Two SoftAP managers:** Never have config_server.cpp and ota.cpp both independently managing WiFi mode and SoftAP. One module owns the WiFi lifecycle.
- **WiFi.mode(WIFI_OFF) during transition:** The prior plan (05-03-PLAN.md) called `WiFi.mode(WIFI_OFF)` before starting SoftAP. This kills ESP-NOW. Use `WiFi.mode(WIFI_AP_STA)` directly from `WIFI_STA` -- the existing code already does this correctly.
- **Channel 0 (auto) for ESP-NOW peers:** Works by accident but breaks when SoftAP channel changes. Always use explicit channel number.
- **Blocking SD writes in upload handler:** The existing `handle_config_upload()` already buffers to PSRAM and writes at `UPLOAD_FILE_END`. Do not change this to stream-write during `UPLOAD_FILE_WRITE` -- it would block the HTTP response and risk partial writes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OTA firmware flashing | Custom flash-write logic | `Update.h` (begin/write/end) | Handles partition selection, checksum, rollback safely |
| HTTP multipart parsing | Custom multipart parser | `WebServer` upload handlers | Already handles chunked transfer, content-type boundaries |
| JSON validation | Custom JSON tokenizer | `ArduinoJson::deserializeJson()` | Already in use, handles nested objects, memory-safe with PSRAM |
| WiFi channel management | Custom channel-scan logic | `esp_wifi_set_channel()` + `WiFi.softAP(ssid, pass, channel)` | ESP-IDF handles radio configuration correctly |
| Inactivity timeout | Complex timer/watchdog | Simple `millis()` comparison in poll loop | No need for FreeRTOS timers; poll loop runs every 5ms |

**Key insight:** All the building blocks exist in the current codebase. Phase 7 is primarily an integration and hardening task, not a greenfield implementation.

## Common Pitfalls

### Pitfall 1: ESP-NOW Channel Mismatch When SoftAP Starts
**What goes wrong:** SoftAP defaults to channel 1. Bridge may be on a different channel (or channel auto-select picks differently). ESP-NOW packets silently fail.
**Why it happens:** ESP32 single radio. AP_STA locks both interfaces to same channel. Both devices currently use `peer.channel = 0` (auto).
**How to avoid:** Explicit `peer.channel = 1` on both display and bridge. `WiFi.softAP(ssid, pass, 1)` with channel parameter. `esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE)` after mode changes.
**Warning signs:** `espnow_get_rssi()` drops to 0 after SoftAP starts. Bridge stops receiving heartbeat pings.
**Confidence:** HIGH -- verified against [ESP-IDF WiFi Driver docs](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi.html) and [ESP-NOW API docs](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/network/esp_now.html)

### Pitfall 2: Channel Re-Pin After WiFi Mode Transition
**What goes wrong:** After `config_server_stop()` calls `WiFi.mode(WIFI_STA)`, the channel may reset. ESP-NOW peer channel setting becomes stale.
**Why it happens:** `WiFi.mode()` reinitializes the WiFi driver, potentially resetting channel configuration.
**How to avoid:** After every `WiFi.mode()` call, immediately re-pin with `esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE)`. The existing `config_server_stop()` already calls `WiFi.mode(WIFI_STA)` -- add channel re-pin after it.
**Warning signs:** ESP-NOW works before config mode, breaks after exiting config mode.
**Confidence:** MEDIUM -- documented behavior in ESP-IDF but needs hardware validation

### Pitfall 3: Dual SoftAP Conflict (Config Server vs OTA)
**What goes wrong:** If both `config_server_start()` and `ota_start()` are called, they each create a WebServer on port 80 and call `WiFi.softAP()` with different SSIDs. Only one can work.
**Why it happens:** Current code has two independent SoftAP managers that don't know about each other.
**How to avoid:** Merge ota.cpp into config_server.cpp. Single WebServer instance, single SoftAP lifecycle, multiple HTTP endpoints.
**Warning signs:** Second `WiFi.softAP()` call fails silently or overrides the first.
**Confidence:** HIGH -- observable in current codebase

### Pitfall 4: No Error Response on Upload Failure
**What goes wrong:** The current `handle_config_upload()` sets error state via static variables but `handle_config_done()` always returns `{"success": true}` (line 234: `bool success = true`). User thinks upload succeeded when it failed.
**Why it happens:** The upload handler (called during multipart chunks) and the completion handler (called after all chunks) don't share error state properly.
**How to avoid:** Use a static error flag/message set during `handle_config_upload()`, checked in `handle_config_done()` to return proper error JSON.
**Warning signs:** Server returns 200 OK with `{"success": true}` for corrupt JSON uploads.
**Confidence:** HIGH -- visible in current `display/config_server.cpp` lines 231-239

### Pitfall 5: Memory Exhaustion During Concurrent Upload + ESP-NOW
**What goes wrong:** Config upload allocates 64KB PSRAM buffer. WiFi AP_STA mode uses ~50-70KB internal SRAM for WiFi stack. LVGL uses 96KB internal SRAM. Combined, this leaves very little headroom.
**Why it happens:** ESP32-S3 has ~390KB internal SRAM total, shared between LVGL (96KB), WiFi stack (~70KB in AP mode), FreeRTOS tasks, Arduino loop stack (8KB default), and general heap.
**How to avoid:** Config buffer is already in PSRAM (`ps_malloc`), which is correct. Monitor `ESP.getFreeHeap()` before starting SoftAP -- refuse to start if free heap < 50KB. Consider increasing Arduino loop stack to 16KB (`-DARDUINO_LOOP_STACK_SIZE=16384` in platformio.ini build_flags) if stack overflow occurs during upload + SD write.
**Warning signs:** Random crashes during upload, `malloc()` returns NULL, watchdog timer resets.
**Confidence:** MEDIUM -- theoretical based on memory budgeting, needs hardware validation

## Code Examples

### Merging OTA into Config Server WebServer
```cpp
// Source: Derived from display/ota.cpp lines 33-62 and display/config_server.cpp lines 241-263

// In unified config_server_start():
web_server = new WebServer(80);

// Root page: combined landing with config upload + OTA links
web_server->on("/", HTTP_GET, handle_root_page);

// Config upload endpoints (existing)
web_server->on("/api/config/upload", HTTP_POST, handle_config_done, handle_config_upload);

// OTA firmware upload (moved from ota.cpp)
web_server->on("/update", HTTP_POST, handle_ota_done, handle_ota_upload);

// ArduinoOTA for PlatformIO (optional)
ArduinoOTA.setHostname("crowpanel");
ArduinoOTA.begin();

web_server->begin();
```

### Config Mode Screen UI
```cpp
// Source: Follows display/ui.cpp OTA screen pattern (lines 505-531)

// Config mode screen (created once in create_ui, persists across rebuilds)
static lv_obj_t *config_screen = nullptr;
static lv_obj_t *config_info_label = nullptr;

// In create_ui():
config_screen = lv_obj_create(NULL);
lv_obj_set_style_bg_color(config_screen, lv_color_hex(0x0d1b2a), LV_PART_MAIN);

lv_obj_t *cfg_title = lv_label_create(config_screen);
lv_label_set_text(cfg_title, LV_SYMBOL_SETTINGS "  Config Upload Mode");
// ... same pattern as ota_screen

config_info_label = lv_label_create(config_screen);
// Updated dynamically when config mode starts:
// "Connect to WiFi: CrowPanel-Config\nPassword: crowconfig\n\nUpload: http://192.168.4.1"

// "Apply & Exit" button
lv_obj_t *exit_btn = lv_btn_create(config_screen);
lv_obj_add_event_cb(exit_btn, config_exit_event_cb, LV_EVENT_CLICKED, nullptr);
```

### Inactivity Timeout with Client Tracking
```cpp
// Application-level timeout in config_server_poll()
void config_server_poll() {
    if (!active || !web_server) return;

    web_server->handleClient();

    // Also handle ArduinoOTA if enabled
    ArduinoOTA.handle();

    // Track activity: any connected station resets the timer
    if (WiFi.softAPgetStationNum() > 0) {
        last_activity_time = millis();
    }

    // 5-minute inactivity auto-stop
    if (millis() - last_activity_time > INACTIVITY_TIMEOUT_MS) {
        config_server_stop();
        hide_config_screen();  // Return to main hotkey view
    }
}
```

### Bridge Channel Pinning (both devices must change)
```cpp
// bridge/espnow_link.cpp -- add esp_wifi_set_channel after WiFi.mode(WIFI_STA)
#include <esp_wifi.h>

void espnow_link_init() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);  // NEW: explicit channel 1
    // ... rest unchanged, but peer.channel = 1 (was 0)
}
```

### Proper Upload Error Propagation
```cpp
// Fix for current bug: handle_config_done always returns success
static bool g_upload_success = false;
static String g_upload_error = "";

static void handle_config_upload() {
    HTTPUpload &upload = web_server->upload();

    if (upload.status == UPLOAD_FILE_START) {
        g_upload_success = false;
        g_upload_error = "";
        // ... allocate buffer
    }
    else if (upload.status == UPLOAD_FILE_WRITE) {
        // ... buffer data, set error on overflow
        if (overflow) {
            g_upload_error = "File too large (max 64KB)";
            return;
        }
    }
    else if (upload.status == UPLOAD_FILE_END) {
        // ... validate, write SD, reload config
        if (all_ok) {
            g_upload_success = true;
        } else {
            g_upload_error = "JSON validation failed";
        }
    }
}

static void handle_config_done() {
    if (g_upload_success) {
        web_server->send(200, "application/json", "{\"success\":true}");
    } else {
        String resp = "{\"success\":false,\"error\":\"" + g_upload_error + "\"}";
        web_server->send(400, "application/json", resp);
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ESPAsyncWebServer | WebServer (sync, Arduino built-in) | Already in project | Simpler, no external dependency, sufficient for single-client config upload |
| `peer.channel = 0` (auto) | `peer.channel = 1` (explicit) | Phase 7 | Deterministic ESP-NOW channel, no silent failures |
| Separate ota.cpp + config_server.cpp | Unified config_server.cpp | Phase 7 | Eliminates dual-SoftAP conflict, single WiFi lifecycle |
| OTA-only SoftAP with hardcoded OTA_SSID | Config-focused SoftAP with OTA as secondary endpoint | Phase 7 | User sees one SSID for all wireless management |

**Deprecated/outdated:**
- `ota.cpp` / `ota.h`: Will be deleted after merge into config_server.cpp. All OTA functionality preserved as HTTP endpoints.
- `ArduinoOTA` standalone: Still works but becomes a secondary feature (PlatformIO convenience) behind the unified WebServer.

## Open Questions

1. **WiFi channel re-pin after mode transition: does it always work?**
   - What we know: `esp_wifi_set_channel()` documentation says it should not be called when STA is connected to an external AP. In pure STA mode (our case -- no router connection), it should be safe.
   - What's unclear: Whether `WiFi.mode(WIFI_STA)` after `WiFi.softAPdisconnect(true)` resets the channel, requiring re-pin. The existing code does not re-pin.
   - Recommendation: Add `esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE)` after every `WiFi.mode()` call. Verify with hardware test: start config mode, stop config mode, verify ESP-NOW still works.

2. **Should ArduinoOTA be kept or dropped?**
   - What we know: ArduinoOTA enables `pio run -t upload --upload-port <IP>` which is convenient for developers. It adds ~10KB flash. The HTTP OTA upload (`/update` endpoint) covers the same functionality for end users.
   - What's unclear: Whether any user workflow depends on ArduinoOTA specifically.
   - Recommendation: Keep ArduinoOTA in the unified server for developer convenience. It costs negligible resources and the code is already written.

3. **Config mode vs OTA mode: separate screens or combined?**
   - What we know: Requirements say config icon triggers config mode (WIFI-01). OTA is "merged into same HTTP server" (WIFI-06). Currently there's a separate OTA screen with OTA button.
   - What's unclear: Should there be one config mode that includes OTA, or should the OTA button remain separate?
   - Recommendation: Single config mode screen that mentions both config upload URL and OTA upload URL. Replace the separate OTA button with the config button. One button, one mode, one SoftAP. The HTML landing page shows both upload forms.

4. **ESP-NOW packet loss during active HTTP transfer: how bad is it?**
   - What we know: WiFi radio time-shares between SoftAP (serving HTTP) and ESP-NOW. During large HTTP transfers, ESP-NOW may experience higher latency or dropped packets.
   - What's unclear: Actual packet loss rate during a ~4KB config upload (takes < 1 second) vs a ~1MB firmware upload (takes ~10 seconds).
   - Recommendation: Accept minor ESP-NOW disruption during upload. Config uploads are small and fast. Firmware uploads cause longer disruption but happen rarely. Document this as known behavior. The user can still tap hotkeys but may see 1-2 missed commands during an active upload.

## Sources

### Primary (HIGH confidence)
- [ESP-IDF WiFi Driver Guide (ESP32-S3, v5.5.2)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi.html) -- AP_STA channel coexistence, channel priority rules
- [ESP-IDF ESP-NOW API Reference](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/network/esp_now.html) -- peer.channel=0 semantics, channel matching requirement, `ESP_ERR_ESPNOW_CHAN` error
- [ESP-IDF WiFi API Reference (esp_wifi.h)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/network/esp_wifi.html) -- `esp_wifi_set_channel()` restrictions
- Existing codebase: `display/config_server.cpp`, `display/ota.cpp`, `display/espnow_link.cpp`, `bridge/espnow_link.cpp`, `display/ui.cpp`, `display/main.cpp`
- Prior research: `.planning/research/PITFALLS.md` (Pitfall 1: WiFi channel lock), `.planning/research/SUMMARY.md`

### Secondary (MEDIUM confidence)
- [ESP32 Forum: ESP-NOW & WiFi Performance and Channel](https://www.esp32.com/viewtopic.php?t=12772) -- community confirmation of channel pinning requirement
- [Arduino Forum: ESP-NOW + WiFi simultaneously](https://forum.arduino.cc/t/use-esp-now-and-wifi-simultaneously-on-esp32/1034555) -- channel pinning requirement confirmed
- [GitHub Issue #1477: Can't change WiFi channel in APSTA mode](https://github.com/espressif/arduino-esp32/issues/1477) -- documents channel override behavior in AP_STA

### Tertiary (LOW confidence)
- SoftAP inactivity timeout: No ESP-IDF API exists for application-level timeout. Must implement manually. [ESP32 Forum: softAP timeout](https://esp32.com/viewtopic.php?t=5461)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use in the project, no new dependencies
- Architecture: HIGH -- merger of two existing working modules following established patterns in the codebase
- Channel pinning: HIGH (theory) / MEDIUM (practice) -- well-documented in ESP-IDF, but hardware validation needed for re-pin-after-mode-change scenario
- Inactivity timeout: HIGH -- straightforward millis() tracking, no complex APIs needed
- Memory: MEDIUM -- theoretical budget analysis, needs hardware validation under load

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (stable domain, no fast-moving dependencies)
