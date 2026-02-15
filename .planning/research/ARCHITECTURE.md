# Architecture: SD Card Config + SoftAP Upload + Data-Driven UI

**Domain:** Configurable ESP32-S3 display firmware (SD config, HTTP upload, dynamic LVGL)
**Researched:** 2026-02-15
**Confidence:** HIGH (proven patterns in existing codebase + official ESP-IDF docs)

## Recommended Architecture

### High-Level Flow

```
BOOT SEQUENCE:
  sdcard_init() -> config_load() -> create_ui(&config) -> normal loop
                   |                                       |
                   +-- fallback to hardcoded defaults      +-- config_server available
                       if SD missing or parse fails             via header icon tap

CONFIG UPLOAD (user-initiated, not always-on):
  User taps header icon -> config_server_start()
  -> WIFI_AP_STA mode (ESP-NOW stays alive on same channel)
  -> HTTP server :80 receives JSON config
  -> Validate + write to SD card (atomic: tmp -> rename)
  -> User taps "Apply" -> reload config -> rebuild UI
  -> config_server_stop() -> WIFI_STA restored
```

### Component Map: NEW vs MODIFIED vs UNCHANGED

| Component | Status | File | Purpose |
|-----------|--------|------|---------|
| `config.cpp/.h` | **NEW** | `display/config.cpp` | JSON parse/serialize, config data model, load/save SD, defaults |
| `config_server.cpp/.h` | **NEW** | `display/config_server.cpp` | SoftAP HTTP server for config upload + OTA (absorbs ota.cpp) |
| `ui.cpp` | **MODIFIED** | `display/ui.cpp` | Refactor from hardcoded arrays to data-driven widget creation |
| `ui.h` | **MODIFIED** | `display/ui.h` | New signature: `create_ui(const AppConfig*)` + `rebuild_ui()` |
| `main.cpp` | **MODIFIED** | `display/main.cpp` | Insert config_load() before create_ui(); swap ota_poll for config_server_poll |
| `ota.cpp/.h` | **ABSORBED** | Merged into `config_server.cpp` | OTA routes become part of unified HTTP server |
| `sdcard.cpp/.h` | **UNCHANGED** | `display/sdcard.cpp` | Already has read/write/exists -- sufficient |
| `espnow_link.cpp/.h` | **UNCHANGED** | `display/espnow_link.cpp` | Channel 0 auto-detect works with WIFI_AP_STA |
| `power.cpp/.h` | **UNCHANGED** | `display/power.cpp` | No changes needed |
| `protocol.h` | **UNCHANGED** | `shared/protocol.h` | Hotkey/stats protocol untouched |

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `config` | Parse JSON from SD, validate, provide typed AppConfig struct, fallback to defaults | `sdcard` (file I/O) |
| `config_server` | Own SoftAP lifecycle, HTTP endpoints for config + OTA upload, trigger reload | `config` (save), `sdcard` (write), `ui` (signal rebuild) |
| `ui` (modified) | Create LVGL widgets from AppConfig instead of hardcoded arrays, rebuild without reboot | `config` (read AppConfig), `espnow_link` (send hotkeys on press) |
| `main` (modified) | Orchestrate boot: SD -> config -> UI. Loop: swap ota_poll for config_server_poll | All modules |

## CRITICAL: WiFi + ESP-NOW Coexistence Strategy

**Confidence: HIGH** -- Already proven in the existing codebase.

### The Pattern Already Works

The existing `ota.cpp` (line 69) already does exactly what config_server needs:

```cpp
// ota.cpp:69 -- EXISTING CODE
WiFi.mode(WIFI_AP_STA);  // Both AP and STA active
WiFi.softAP(OTA_SSID, OTA_PASS);
```

And `espnow_link.cpp` (line 72) registers the broadcast peer with `channel = 0`:

```cpp
// espnow_link.cpp:72 -- EXISTING CODE
peer.channel = 0;  // 0 = use current interface channel (auto-detect)
```

**This means:** When SoftAP starts, it picks a channel (default: 1). ESP-NOW, configured with channel 0, automatically follows. Both share the single WiFi radio via time-division. The bridge also uses broadcast with channel 0, so it matches automatically.

### Why There Is No Channel Conflict

1. Neither device connects to an external AP (no STA connection forcing a channel change)
2. SoftAP picks a channel, ESP-NOW auto-follows via channel 0
3. Bridge also uses broadcast with channel 0
4. Single radio time-shares between AP service and ESP-NOW packets

### Performance Impact During Config Upload

When SoftAP is active, ESP-NOW shares radio time with HTTP traffic. This means:
- ESP-NOW latency may increase from ~3ms to ~10-20ms during active HTTP transfer
- Hotkey presses still work but may feel slightly less responsive
- Stats updates may be delayed

**Mitigation:** Config upload is user-initiated and brief (tap icon, upload JSON, tap apply, done). SoftAP is NOT left running permanently. Default state is WIFI_STA only (ESP-NOW has full radio access).

### Consolidation: Merge OTA Into Config Server

The existing `ota.cpp` and the new config server both need the same SoftAP lifecycle. Having two SoftAP managers would create conflicts (only one can exist). Merge them:

```
config_server_start():
  WiFi.mode(WIFI_AP_STA)
  WiFi.softAP("CrowPanel", "crowpanel")
  WebServer on :80
    GET  /           -> Config upload web UI (new)
    POST /api/config -> JSON config upload (new)
    GET  /api/config -> Download current config (new)
    GET  /update     -> OTA firmware upload page (from ota.cpp)
    POST /update     -> OTA firmware upload handler (from ota.cpp)
  ArduinoOTA.begin() (from ota.cpp)

config_server_stop():
  ArduinoOTA.end()
  web_server->stop()
  WiFi.softAPdisconnect(true)
  WiFi.mode(WIFI_STA)
```

## Config Data Model

### JSON Schema (stored as `/config.json` on SD card)

```json
{
  "version": 1,
  "pages": [
    {
      "name": "Windows",
      "keys": [
        {
          "label": "WS 1",
          "desc": "Super+1",
          "mod": 8,
          "key": 49,
          "color": "3498DB",
          "icon": "home",
          "media": false,
          "cc": 0
        }
      ]
    }
  ]
}
```

**Design decisions:**
- Short key names (`mod`, `desc`, `cc`) to minimize JSON size on SD card
- Color as hex string (6 chars) -- human-readable in editor, easy to parse with `strtoul`
- Icon as name string -- mapped to LV_SYMBOL_* via lookup table in config.cpp
- `mod` uses same bitmask as protocol.h (MOD_CTRL=0x01, MOD_SHIFT=0x02, etc.)
- `key` uses same codes as protocol.h (ASCII or special key defines)
- No nesting beyond page->keys -- keeps parsing simple and memory predictable

### C++ Config Struct (fixed-size, stack-safe)

```cpp
// config.h
#define MAX_PAGES       8
#define MAX_KEYS_PER_PAGE 16
#define MAX_LABEL_LEN   16
#define MAX_DESC_LEN    24
#define MAX_ICON_LEN    16

struct HotkeyConfig {
    char     label[MAX_LABEL_LEN];
    char     desc[MAX_DESC_LEN];
    uint8_t  modifiers;
    uint8_t  keycode;
    uint32_t color;
    char     icon[MAX_ICON_LEN];   // name string -> LV_SYMBOL_* lookup
    bool     is_media;
    uint16_t consumer_code;
};
// sizeof(HotkeyConfig) ~ 64 bytes

struct PageConfig {
    char          name[MAX_LABEL_LEN];
    HotkeyConfig  keys[MAX_KEYS_PER_PAGE];
    uint8_t       key_count;
};
// sizeof(PageConfig) ~ 1040 bytes

struct AppConfig {
    uint8_t    version;
    PageConfig pages[MAX_PAGES];
    uint8_t    page_count;
    bool       from_sd;  // true if loaded from SD, false if using defaults
};
// sizeof(AppConfig) ~ 8324 bytes -- fits in internal RAM, no PSRAM needed
```

### Icon Name-to-Symbol Lookup

```cpp
// In config.cpp
struct IconEntry { const char *name; const char *symbol; };
static const IconEntry icon_map[] = {
    {"home",      LV_SYMBOL_HOME},
    {"settings",  LV_SYMBOL_SETTINGS},
    {"play",      LV_SYMBOL_PLAY},
    {"next",      LV_SYMBOL_NEXT},
    {"prev",      LV_SYMBOL_PREV},
    {"close",     LV_SYMBOL_CLOSE},
    {"left",      LV_SYMBOL_LEFT},
    {"right",     LV_SYMBOL_RIGHT},
    {"up",        LV_SYMBOL_UP},
    {"down",      LV_SYMBOL_DOWN},
    {"keyboard",  LV_SYMBOL_KEYBOARD},
    {"directory", LV_SYMBOL_DIRECTORY},
    {"list",      LV_SYMBOL_LIST},
    {"image",     LV_SYMBOL_IMAGE},
    {"eye_open",  LV_SYMBOL_EYE_OPEN},
    {"eye_close", LV_SYMBOL_EYE_CLOSE},
    {"bell",      LV_SYMBOL_BELL},
    {"warning",   LV_SYMBOL_WARNING},
    {"wifi",      LV_SYMBOL_WIFI},
    {"shuffle",   LV_SYMBOL_SHUFFLE},
    {"loop",      LV_SYMBOL_LOOP},
    {"paste",     LV_SYMBOL_PASTE},
    {"mute",      LV_SYMBOL_MUTE},
    {"volume_max",LV_SYMBOL_VOLUME_MAX},
    {"volume_mid",LV_SYMBOL_VOLUME_MID},
    {"new_line",  LV_SYMBOL_NEW_LINE},
    {"upload",    LV_SYMBOL_UPLOAD},
    {"download",  LV_SYMBOL_DOWNLOAD},
    {nullptr,     nullptr}  // sentinel
};

const char* icon_lookup(const char *name);  // returns LV_SYMBOL_* or ""
```

## Data Flow: Boot Config Loading

```
1. sdcard_init()                    [already in setup(), unchanged]
2. config_load(&app_config)         [NEW -- inserted before create_ui]
   a. sdcard_mounted()?
      NO  -> config_load_defaults(&app_config), return false
   b. sdcard_file_exists("/config.json")?
      NO  -> config_load_defaults(&app_config), return false
   c. sdcard_read_file("/config.json", buf, MAX_CONFIG_SIZE)
   d. ArduinoJson deserializeJson(doc, buf)
      FAIL -> config_load_defaults(&app_config), return false
   e. Walk JSON: populate app_config.pages[].keys[]
   f. app_config.from_sd = true, return true
3. create_ui(&app_config)           [MODIFIED -- takes config pointer]
```

**Fallback guarantee:** Device ALWAYS boots to a usable state. If SD is missing, corrupt, or JSON is malformed, the current hardcoded layout (page1/2/3_hotkeys[]) is loaded as defaults. No user action required.

## Data Flow: Config Upload via HTTP

```
1. User taps config icon in header bar
2. config_server_start()
   a. WiFi.mode(WIFI_AP_STA)
   b. WiFi.softAP("CrowPanel", "crowpanel")
   c. Start WebServer on port 80
   d. Show config-mode screen (IP address, instructions)
3. Phone/laptop connects to "CrowPanel" WiFi
4. POST /api/config with JSON body
   a. WebServer receives body (chunked via upload handler)
   b. Write to /config.tmp on SD card
   c. Read back /config.tmp, parse with ArduinoJson to validate
   d. If valid: SD.remove("/config.json"), SD.rename("/config.tmp", "/config.json")
   e. If invalid: SD.remove("/config.tmp"), return 400 with error details
   f. Return 200 OK
5. User taps "Apply & Exit" button on display
   a. config_server_stop()  -- tears down SoftAP, restores WIFI_STA
   b. config_load(&app_config)  -- re-read from SD
   c. rebuild_ui(&app_config)  -- destroy LVGL tree, recreate from new config
```

## Data Flow: Hotkey Press (Data-Driven)

```
1. LVGL button clicked -> btn_event_cb()
2. lv_event_get_user_data() returns HotkeyConfig*
   (pointer into app_config.pages[i].keys[j])
3. if (hk->is_media):
     send_media_key_to_bridge(hk->consumer_code)   [UNCHANGED]
   else:
     send_hotkey_to_bridge(hk->modifiers, hk->keycode)  [UNCHANGED]
```

**Key insight:** The protocol layer (espnow_link, protocol.h) is completely unchanged. The data-driven UI just changes WHERE the hotkey data comes from (config struct vs hardcoded array), not HOW it is sent.

## Integration Points (Specific Code Changes)

### 1. main.cpp setup() -- 3-Line Change

```cpp
// BEFORE:
sdcard_init();
create_ui();

// AFTER:
sdcard_init();
static AppConfig app_config;         // Static so pointers stay valid for LVGL callbacks
config_load(&app_config);            // NEW: load from SD or defaults
create_ui(&app_config);              // MODIFIED: pass config
```

### 2. main.cpp loop() -- Swap OTA for Config Server

```cpp
// BEFORE:
if (ota_active()) {
    ota_poll();
}

// AFTER:
if (config_server_active()) {
    config_server_poll();             // Handles HTTP + ArduinoOTA (absorbed from ota.cpp)
}
```

### 3. ui.cpp -- Button Event Handler (Minimal Change)

```cpp
// BEFORE:
const Hotkey *hk = (const Hotkey *)lv_event_get_user_data(e);

// AFTER:
const HotkeyConfig *hk = (const HotkeyConfig *)lv_event_get_user_data(e);
```

The HotkeyConfig struct has the same fields as the old Hotkey struct (label, modifiers, keycode, color, icon, is_media, consumer_code). The callback logic is identical.

### 4. ui.cpp -- create_ui() Refactor

The existing `create_ui()` function already uses a data-driven pattern internally:

```cpp
// EXISTING: iterates over pages[] array
for (uint8_t i = 0; i < NUM_PAGES; i++) {
    lv_obj_t *tab = lv_tabview_add_tab(tabview, pages[i].name);
    create_hotkey_page(tab, pages[i]);
}
```

The refactor changes the data source from static `const HotkeyPage pages[]` to `config->pages[]`:

```cpp
// NEW: iterates over config struct
void create_ui(const AppConfig *cfg) {
    // ... header creation (unchanged) ...
    for (uint8_t i = 0; i < cfg->page_count; i++) {
        lv_obj_t *tab = lv_tabview_add_tab(tabview, cfg->pages[i].name);
        create_hotkey_page(tab, cfg->pages[i]);  // Takes PageConfig instead of HotkeyPage
    }
}
```

### 5. ui.cpp -- Add Config Mode Header Icon

Next to existing brightness and OTA icons:

```cpp
lv_obj_t *cfg_btn = lv_label_create(header);
lv_label_set_text(cfg_btn, LV_SYMBOL_EDIT);
lv_obj_set_style_text_font(cfg_btn, &lv_font_montserrat_16, LV_PART_MAIN);
lv_obj_set_style_text_color(cfg_btn, lv_color_hex(CLR_CYAN), LV_PART_MAIN);
lv_obj_align(cfg_btn, LV_ALIGN_RIGHT_MID, -135, 0);  // Next to existing icons
lv_obj_add_flag(cfg_btn, LV_OBJ_FLAG_CLICKABLE);
lv_obj_add_event_cb(cfg_btn, config_btn_event_cb, LV_EVENT_CLICKED, nullptr);
```

### 6. ui.cpp -- UI Rebuild (No Reboot)

```cpp
void rebuild_ui(const AppConfig *cfg) {
    // Destroy all children of main_screen
    lv_obj_clean(main_screen);

    // Recreate everything (header, stats header, tabview, pages)
    create_ui_internal(main_screen, cfg);

    // Switch to main screen (in case we were on config screen)
    lv_scr_load(main_screen);
}
```

**LVGL v8 supports this:** `lv_obj_clean()` deletes all children and frees their memory. Safe to call outside event callbacks.

**Widget pointer lifetime:** After `lv_obj_clean()`, all `lv_obj_t*` pointers (tabview, stats_header, status_label, etc.) are dangling. The `create_ui_internal()` function must reassign all of them. This is already the pattern in the existing code -- all these are file-scope static variables that get assigned during UI creation.

## Patterns to Follow

### Pattern 1: Fallback-to-Defaults (Non-Negotiable)

The device must boot to a usable UI regardless of SD card state. The current hardcoded page1/2/3_hotkeys[] arrays become the default config:

```cpp
void config_load_defaults(AppConfig *cfg) {
    cfg->version = 1;
    cfg->page_count = 3;
    cfg->from_sd = false;
    // Copy existing static arrays into cfg->pages[0..2]
    // (One-time conversion of the hardcoded data)
}
```

### Pattern 2: Atomic Config Write

Never write directly to `/config.json`. Power loss during write corrupts the file.

```cpp
bool config_save(const uint8_t *json, size_t len) {
    if (!sdcard_write_file("/config.tmp", json, len)) return false;

    // Validate by re-reading and parsing
    AppConfig test;
    uint8_t *buf = (uint8_t *)malloc(len + 1);
    sdcard_read_file("/config.tmp", buf, len + 1);
    bool valid = config_parse(buf, len, &test);
    free(buf);

    if (!valid) { SD.remove("/config.tmp"); return false; }

    SD.remove("/config.json");
    SD.rename("/config.tmp", "/config.json");
    return true;
}
```

**Note:** FAT32 rename is not truly atomic (no journaling), but it is the best available on SD card. The fallback-to-defaults pattern covers the rare corruption case.

### Pattern 3: Use Synchronous WebServer (Not AsyncWebServer)

The existing `ota.cpp` uses the synchronous `WebServer` class with `handleClient()` in the loop. Use the same pattern for config upload.

**Why NOT AsyncWebServer:**
- Already have WebServer as a proven dependency
- Config upload is user-initiated, infrequent, not latency-critical
- AsyncWebServer adds ~100KB flash footprint
- The existing loop() pattern of calling `handleClient()` works fine
- No new library dependency

### Pattern 4: Config Struct Outlives Widgets

The `AppConfig` struct is declared `static` in `main.cpp`, giving it program lifetime. LVGL button callbacks store `HotkeyConfig*` pointers into this struct via `lv_event_get_user_data()`.

**Rebuild sequence must be:**
1. Destroy all LVGL widgets (`lv_obj_clean`)
2. Load new config into the SAME static AppConfig
3. Create new widgets pointing to the updated config data

Never allocate a new AppConfig while old widgets still reference the old one.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Parsing JSON on Every Button Press

**What:** Reading `/config.json` from SD each time a hotkey is pressed.
**Why bad:** SD SPI reads take 5-50ms. LVGL callbacks must return in <5ms or UI stutters.
**Instead:** Parse once at boot. Button callbacks reference the in-RAM struct.

### Anti-Pattern 2: Two Separate SoftAP Managers

**What:** Keeping `ota.cpp` and adding a separate `config_server.cpp` that each manage WiFi.
**Why bad:** Only one SoftAP instance can exist. Two modules calling `WiFi.mode()` and `WiFi.softAP()` create race conditions and mode conflicts.
**Instead:** Absorb OTA into config_server. Single module owns the SoftAP lifecycle.

### Anti-Pattern 3: Leaving SoftAP Running Permanently

**What:** Starting SoftAP at boot and leaving it active.
**Why bad:** WiFi AP draws ~120mA continuous. Reduces ESP-NOW throughput. Unnecessary attack surface.
**Instead:** User-activated only. Default state is WIFI_STA (ESP-NOW has full radio bandwidth).

### Anti-Pattern 4: Storing LVGL Widget Pointers in Config Struct

**What:** Keeping `lv_obj_t*` inside AppConfig.
**Why bad:** Widget pointers become dangling after `lv_obj_clean()` during rebuild.
**Instead:** Config holds data only. Widget pointers are file-scope statics in `ui.cpp` (existing pattern).

### Anti-Pattern 5: ArduinoJson DynamicJsonDocument as Long-Lived Storage

**What:** Keeping the ArduinoJson document alive as the runtime config.
**Why bad:** JsonDocument holds a memory pool with internal fragmentation. Our fixed-size AppConfig struct is smaller and has predictable memory layout.
**Instead:** Deserialize JSON into AppConfig, then discard the JsonDocument immediately.

## ArduinoJson Integration Details

**Library:** ArduinoJson v7 (latest). Add to `lib_deps` in platformio.ini.
**PSRAM:** Not needed for config parsing. The JSON document is temporary (~4-8KB for a full config) and freed after parsing into the AppConfig struct. Internal heap can handle this.

```cpp
// config.cpp -- parsing
#include <ArduinoJson.h>

bool config_parse(const uint8_t *json, size_t len, AppConfig *cfg) {
    JsonDocument doc;  // v7: auto-sizing, uses heap
    DeserializationError err = deserializeJson(doc, json, len);
    if (err) {
        Serial.printf("[config] JSON parse error: %s\n", err.c_str());
        return false;
    }

    cfg->version = doc["version"] | 1;
    JsonArray pages = doc["pages"];
    cfg->page_count = min((int)pages.size(), MAX_PAGES);

    for (int i = 0; i < cfg->page_count; i++) {
        JsonObject page = pages[i];
        strlcpy(cfg->pages[i].name, page["name"] | "Page", MAX_LABEL_LEN);

        JsonArray keys = page["keys"];
        cfg->pages[i].key_count = min((int)keys.size(), MAX_KEYS_PER_PAGE);

        for (int j = 0; j < cfg->pages[i].key_count; j++) {
            JsonObject key = keys[j];
            HotkeyConfig *hk = &cfg->pages[i].keys[j];

            strlcpy(hk->label, key["label"] | "Key", MAX_LABEL_LEN);
            strlcpy(hk->desc, key["desc"] | "", MAX_DESC_LEN);
            hk->modifiers = key["mod"] | 0;
            hk->keycode = key["key"] | 0;
            hk->color = strtoul(key["color"] | "7F8C8D", nullptr, 16);
            strlcpy(hk->icon, key["icon"] | "", MAX_ICON_LEN);
            hk->is_media = key["media"] | false;
            hk->consumer_code = key["cc"] | 0;
        }
    }
    return true;
}
// JsonDocument goes out of scope here -> memory freed
```

## Suggested Build Order

Dependencies dictate the order. Each phase is independently testable.

### Phase 1: Config Data Model + SD Loading

**New files:** `display/config.cpp`, `display/config.h`
**Modified:** `platformio.ini` (add ArduinoJson to lib_deps)
**Depends on:** `sdcard.cpp` (existing, unchanged)
**Test:** Load hardcoded JSON string -> parse into AppConfig -> Serial.print all fields. Then test with actual `/config.json` on SD card. Verify fallback when file is missing/corrupt.

### Phase 2: Data-Driven UI

**Modified:** `display/ui.cpp`, `display/ui.h`
**Depends on:** Phase 1 (AppConfig struct exists)
**Test:** Boot with defaults-loaded config -> verify UI looks IDENTICAL to current hardcoded UI. This is the critical regression test. Then boot with SD config that changes a label/color -> verify it appears.

### Phase 3: Config Server (SoftAP + HTTP + OTA Merge)

**New files:** `display/config_server.cpp`, `display/config_server.h`
**Removed:** `display/ota.cpp`, `display/ota.h` (absorbed)
**Depends on:** Phase 1 (config save), Phase 2 (UI rebuild)
**Test:** Tap header icon -> connect phone to WiFi -> POST JSON via curl -> verify SD write -> tap Apply -> verify UI rebuilds. Also verify OTA firmware upload still works via /update route.

### Phase 4: Main Loop Integration + Polish

**Modified:** `display/main.cpp`
**Depends on:** Phases 1-3
**Test:** Full end-to-end: boot from SD config -> use hotkeys -> upload new config -> rebuild -> hotkeys match new config. Also: remove SD card -> boot to defaults -> insert SD -> upload config -> reboot -> loads from SD.

## Memory Budget

| Resource | Available | Used by Config Feature | Remaining |
|----------|-----------|----------------------|-----------|
| Internal heap | ~300KB | AppConfig: ~8KB, JSON parse temp: ~8KB | ~284KB |
| PSRAM | ~4MB (8MB chip) | Not needed | ~4MB |
| Flash | 4MB total, ~1.5MB firmware | ArduinoJson lib: ~60KB | Adequate |
| SD card | User-provided, typically 1-32GB | config.json: ~2-8KB | Vast |

No PSRAM allocation needed. Everything fits in internal heap with large margins.

## Sources

- [ESP-IDF ESP-NOW Documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/network/esp_now.html) -- channel 0 auto-detect behavior, peer configuration (HIGH confidence)
- [ESP-IDF WiFi Driver: SoftAP+STA Coexistence](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi.html) -- single radio channel constraint in AP_STA mode (HIGH confidence)
- [ArduinoJson v7 PSRAM on ESP32](https://arduinojson.org/v7/how-to/use-external-ram-on-esp32/) -- allocator options (HIGH confidence)
- [ArduinoJson v7 Memory Reduction](https://arduinojson.org/v7/how-to/reduce-memory-usage/) -- strategies for embedded parsing (HIGH confidence)
- [ESP32 Forum: ESP-NOW + WiFi Coexistence](https://www.esp32.com/viewtopic.php?t=12772) -- community confirmation of AP_STA + ESP-NOW (MEDIUM confidence)
- [Arduino Forum: ESP-NOW + WiFi Simultaneously](https://forum.arduino.cc/t/use-esp-now-and-wifi-simultaneously-on-esp32/1034555) -- practical examples (MEDIUM confidence)
- Existing `display/ota.cpp` line 69: proves `WIFI_AP_STA` + ESP-NOW works on this hardware (HIGH confidence, verified in codebase)
- Existing `display/espnow_link.cpp` line 72: channel 0 broadcast peer (HIGH confidence, verified in codebase)
- Existing `display/ui.cpp`: data-driven loop pattern already present (iterates `pages[]` array) (HIGH confidence, verified in codebase)
