# Domain Pitfalls: SD Card Config + SoftAP Upload + Dynamic LVGL UI

**Domain:** Adding configurable hotkey layouts to existing ESP32-S3 wireless command center
**Researched:** 2026-02-15
**Confidence:** HIGH (pitfalls verified against actual codebase, ESP-IDF docs, and community reports)

---

## Critical Pitfalls

These cause hard-to-diagnose failures, data loss, or require architectural rework.

---

### Pitfall 1: WiFi Channel Lock Breaks ESP-NOW When SoftAP Starts

**What goes wrong:**
When `WiFi.mode(WIFI_AP_STA)` starts the SoftAP for config upload, the ESP32's single radio locks to the SoftAP's channel. If the bridge ESP32 was communicating on a different channel (e.g., channel 1 from `esp_wifi_set_channel()`), all ESP-NOW packets silently fail. The existing OTA code in `ota.cpp` already does `WiFi.mode(WIFI_AP_STA)` but does NOT pin the channel -- the SoftAP defaults to channel 1, which may or may not match the bridge's channel.

**Why it happens:**
ESP32 has ONE 2.4 GHz radio. In AP_STA mode, both interfaces share the same physical channel. The SoftAP picks a channel (default 1), and ESP-NOW MUST operate on that same channel. The bridge ESP32 (running in STA mode on some other channel) cannot hear packets on a different channel. The current `espnow_link.cpp` sets `peer.channel = 0` (auto), which works in pure STA mode but becomes ambiguous in AP_STA mode.

**Consequences:**
- Hotkey commands stop reaching the bridge while config upload is active
- ESP-NOW send callback reports success (MAC-layer ACK fails silently when peer is on wrong channel)
- User thinks the device crashed because buttons stop working

**Prevention:**
1. Pin BOTH devices to the same channel explicitly at boot: `esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE)` on both display and bridge
2. When starting SoftAP, specify the channel: `WiFi.softAP(ssid, pass, 1)` -- third param is channel, must match the ESP-NOW channel
3. Update the ESP-NOW peer registration to use the explicit channel (not 0): `peer.channel = 1`
4. After stopping SoftAP, call `WiFi.mode(WIFI_STA)` then re-pin channel with `esp_wifi_set_channel()`
5. Add a pre-flight check: before entering config mode, send a MSG_PING to bridge and verify ACK, then send a "entering config mode" message so bridge knows to expect a pause

**Detection:**
- `espnow_get_rssi()` drops to 0 after SoftAP starts
- Bridge stops receiving heartbeat pings
- `esp_now_send()` returns ESP_OK but send callback never fires with success

**Phase to address:** Config Upload milestone, first task -- WiFi mode transition must be the first thing tested.

---

### Pitfall 2: JSON Parsing on 96KB LVGL Heap + Internal SRAM Exhausts Memory

**What goes wrong:**
ArduinoJson's `JsonDocument` allocates from the heap. On ESP32-S3, the default heap is internal SRAM (~300KB total, shared with LVGL's 96KB pool, WiFi stack ~50KB, FreeRTOS tasks, etc.). Parsing a layout config file (say 3 pages x 12 buttons x ~100 bytes each = ~4KB JSON) requires ArduinoJson to allocate roughly 2-3x the file size for its DOM. This hits internal SRAM directly, competing with LVGL's memory pool and the WiFi stack buffers.

**Why it happens:**
- `LV_MEM_CUSTOM 0` in `lv_conf.h` means LVGL uses its own 96KB allocator from internal SRAM
- ArduinoJson `JsonDocument` defaults to heap_caps_malloc(MALLOC_CAP_DEFAULT) which is internal SRAM
- WiFi + SoftAP + HTTP server consume ~50-70KB of internal SRAM when active
- Reading the entire JSON file into a buffer before parsing doubles the memory cost

**Consequences:**
- `malloc()` returns NULL during JSON parsing, causing crash or silent data corruption
- LVGL allocations fail during/after JSON parsing, widgets not created
- HTTP upload + JSON parse + SD write happening simultaneously = memory cliff

**Prevention:**
1. Use ArduinoJson v7 with a PSRAM-backed custom allocator:
   ```cpp
   struct PsramAllocator {
       void* allocate(size_t size) { return ps_malloc(size); }
       void deallocate(void* ptr) { free(ptr); }
       void* reallocate(void* ptr, size_t new_size) { return ps_realloc(ptr, new_size); }
   };
   using PsramJsonDocument = BasicJsonDocument<PsramAllocator>;
   ```
2. Use streaming JSON parser (ArduinoJson `deserializeJson()` directly from File object) instead of reading entire file into buffer first
3. Parse config BEFORE starting the HTTP server, not during an upload handler
4. Budget memory explicitly:
   - LVGL heap: 96KB (internal SRAM)
   - WiFi + SoftAP stack: ~60KB (internal SRAM)
   - JSON parsing: PSRAM only
   - SD card read buffer: PSRAM only
   - HTTP upload buffer: 1460 bytes per chunk (handled by WebServer internally)
   - Available internal SRAM after LVGL + WiFi: ~120-150KB -- leave 50KB headroom minimum

**Detection:**
- Call `ESP.getFreeHeap()` before and after JSON parsing -- drop > 10KB is a warning
- Enable `LV_USE_ASSERT_MALLOC 1` (already enabled) to catch LVGL allocation failures
- Serial print: `heap_caps_get_free_size(MALLOC_CAP_INTERNAL)` at key points

**Phase to address:** SD Card Config milestone -- JSON format and parsing approach must be decided before writing any parser code.

---

### Pitfall 3: LVGL Widget Tree Leak When Rebuilding Dynamic UI

**What goes wrong:**
When the user uploads a new layout config, the UI must be rebuilt -- old buttons destroyed, new buttons created from the config. If you call `lv_obj_del()` on the tab content but LVGL styles were initialized with `lv_style_init()`, those style allocations are NOT freed. Each rebuild leaks memory. After 3-5 config reloads, LVGL heap is exhausted and the device must be rebooted.

**Why it happens:**
LVGL v8.3 does NOT garbage-collect styles. `lv_obj_del()` recursively deletes an object and its children, freeing their base allocations. But if you created local `lv_style_t` variables and applied them with `lv_obj_add_style()`, the style's internal data (allocated by `lv_style_init()`) is NOT freed by `lv_obj_del()`. The current `ui.cpp` uses inline style setters (`lv_obj_set_style_*`) which allocate from LVGL heap per-object.

**Consequences:**
- Memory usage grows with each layout reload
- After 3-5 reloads: widgets fail to create, display goes blank or shows partial UI
- No error message -- LVGL silently returns NULL from `lv_*_create()`

**Prevention:**
1. Do NOT destroy and recreate widgets for config changes. Instead, create the maximum widget tree once at boot (e.g., 4 pages x 12 buttons = 48 button slots), then UPDATE their labels, colors, and callbacks when config changes:
   ```cpp
   // At boot: create all slots
   lv_obj_t* btn_slots[MAX_PAGES][MAX_BUTTONS_PER_PAGE];

   // On config reload: update existing widgets
   lv_label_set_text(btn_label, new_config.label);
   lv_obj_set_style_bg_color(btn, lv_color_hex(new_config.color), 0);
   ```
2. If dynamic creation is unavoidable: call `lv_obj_clean()` on the parent (deletes all children) rather than individual `lv_obj_del()` calls -- this is slightly more memory-efficient
3. Use `lv_obj_set_style_*()` functions (which the current code already does) instead of separate `lv_style_t` objects -- the per-object inline styles ARE freed when the object is deleted
4. After any UI rebuild, call `lv_mem_monitor()` and log the result:
   ```cpp
   lv_mem_monitor_t mon;
   lv_mem_monitor(&mon);
   Serial.printf("LVGL: used=%d free=%d frag=%d%%\n",
       mon.total_size - mon.free_size, mon.free_size, mon.frag_pct);
   ```
5. Set a hard limit: if `mon.free_size < 10240`, refuse to rebuild and show error message

**Detection:**
- `lv_mem_monitor()` shows decreasing free memory after each reload
- Widgets stop appearing after multiple config uploads
- LVGL assert fires (if `LV_USE_ASSERT_MALLOC 1` is enabled)

**Phase to address:** Dynamic UI milestone -- widget pool pattern must be designed before building any dynamic layout code.

---

### Pitfall 4: SD Card SPI Blocks LVGL Rendering During File I/O

**What goes wrong:**
The SD card uses SPI (HSPI on GPIO 10-13, separate from display's RGB parallel bus). SD card reads/writes take 5-50ms depending on card speed and file size. During this time, the main loop is blocked -- `lv_timer_handler()` doesn't run, touch polling stops, and the display appears frozen. On a 7" 800x480 display at 60Hz refresh, even a 30ms stall is visually noticeable as a frame skip.

**Why it happens:**
The current architecture runs everything in a single-threaded `loop()`. SD file operations (`SD.open()`, `f.read()`, `f.write()`) are synchronous and blocking. The SPI bus is separate from the display bus (display uses RGB parallel, SD uses HSPI), so there is no electrical bus contention -- the problem is purely CPU time.

**Consequences:**
- UI freezes briefly when loading config from SD at boot
- During HTTP file upload to SD, the touch stops responding and display flickers
- If upload writes large files (icons, multiple configs), the freeze can last seconds

**Prevention:**
1. Move SD card I/O to a dedicated FreeRTOS task on Core 0 (LVGL runs on Core 1 by default in Arduino):
   ```cpp
   // SD task on Core 0
   xTaskCreatePinnedToCore(sd_task, "sd_io", 4096, NULL, 1, &sd_task_handle, 0);

   // Communication via queue
   xQueueSend(sd_request_queue, &request, portMAX_DELAY);
   ```
2. For config loading at boot: load and parse BEFORE creating the LVGL UI. The display shows nothing useful during boot anyway
3. For HTTP upload: write file chunks in the WebServer upload handler (already chunked at ~1460 bytes), which interleaves naturally with `loop()` calls since WebServer is polled, not async
4. Keep individual SD operations under 5ms: read/write in small chunks (512-1024 bytes), yield between chunks with `vTaskDelay(1)`
5. Show a loading indicator on screen BEFORE starting any SD operation, so the user knows the device is busy

**Detection:**
- Touch input feels "laggy" after adding SD reads to loop
- LVGL timer handler warnings if `LV_USE_PERF_MONITOR` is enabled
- Serial timestamps show >10ms gaps in loop iteration timing

**Phase to address:** SD Card Config milestone -- file I/O strategy must account for LVGL rendering requirements.

---

### Pitfall 5: HTTP Upload Handler + SD Write + ESP-NOW = Stack Overflow

**What goes wrong:**
The ESP32 WebServer upload handler runs in the WiFi task's context (or the main loop, depending on how `handleClient()` is called). The upload handler writes to SD card (SPI transaction). Meanwhile, ESP-NOW receive callbacks fire from the WiFi task. If the upload handler is running when an ESP-NOW packet arrives, the callback fires on the same stack. The combined stack depth (WebServer parsing + multipart decode + SD write + ESP-NOW callback) can exceed the task's stack allocation, causing a silent crash or watchdog reset.

**Why it happens:**
- WebServer `handleClient()` is called from `loop()`, which runs on the Arduino main task (default 8KB stack)
- SD file write involves SPI driver internals, adding stack frames
- ESP-NOW callbacks fire in WiFi task context -- but if `handleClient()` is handling an upload, the callback is deferred, and when it fires, the combined context is deep
- The real danger is the HTTP upload handler calling SD write, which triggers SPI interrupt handling, overlapping with WiFi interrupt handling

**Consequences:**
- Guru Meditation Error (stack overflow) during file upload
- Device reboots mid-upload, leaving corrupt file on SD card
- Intermittent: depends on exact timing of ESP-NOW packets arriving during upload

**Prevention:**
1. Increase Arduino loop task stack size in `platformio.ini`:
   ```ini
   build_flags = ... -DARDUINO_LOOP_STACK_SIZE=16384
   ```
2. Separate concerns: HTTP upload handler writes to a PSRAM buffer, then a separate task writes to SD card:
   ```cpp
   static void handle_config_upload() {
       HTTPUpload &upload = web_server->upload();
       if (upload.status == UPLOAD_FILE_WRITE) {
           // Copy to PSRAM buffer -- fast, no SPI
           memcpy(psram_buf + offset, upload.buf, upload.currentSize);
           offset += upload.currentSize;
       } else if (upload.status == UPLOAD_FILE_END) {
           // Signal SD task to write the complete buffer
           xTaskNotifyGive(sd_task_handle);
       }
   }
   ```
3. Limit upload file size (config files should be <16KB; reject anything larger in the upload handler)
4. During active HTTP upload, temporarily pause ESP-NOW sending (not receiving -- we cannot stop callbacks, but we can avoid adding our own send operations that compete for WiFi task time)

**Detection:**
- `Guru Meditation Error: Core 0 panic'd (Unhandled debug exception)` in serial output
- `Stack canary watchpoint triggered (loopTask)` message
- Upload succeeds sometimes but crashes other times (timing-dependent)

**Phase to address:** Config Upload milestone -- upload handler design must avoid blocking SD writes on the HTTP task.

---

## Moderate Pitfalls

These cause bugs or performance issues but have straightforward fixes.

---

### Pitfall 6: Config File Corruption From Power Loss During SD Write

**What goes wrong:**
If the device loses power or resets during `sdcard_write_file()`, the config file is left in a corrupt or truncated state. On next boot, JSON parsing fails on the corrupt file, and the device has no valid layout configuration. The current `sdcard_write_file()` opens with `FILE_WRITE` (overwrite mode) -- if it crashes mid-write, the old config is already destroyed.

**Prevention:**
1. Write to a temp file first, then rename atomically:
   ```cpp
   bool sdcard_write_config(const char *path, const uint8_t *data, size_t len) {
       const char *tmp = "/config/.tmp";
       if (!sdcard_write_file(tmp, data, len)) return false;
       SD.remove(path);           // Remove old config
       return SD.rename(tmp, path); // Atomic rename
   }
   ```
   Note: FAT32 rename is not truly atomic, but it is much safer than overwriting in place. The temp file approach means either the old config or new config is always intact.
2. Keep a backup: before writing new config, copy current config to `.bak`:
   ```
   /config/layout.json      <- active config
   /config/layout.json.bak  <- previous config (fallback)
   ```
3. On boot, if `layout.json` fails to parse, try `layout.json.bak`. If both fail, use hardcoded defaults (the current static hotkey arrays)
4. Validate JSON BEFORE writing to SD: parse the uploaded data in PSRAM first, verify it produces a valid layout, then write

**Detection:**
- Device boots with no layout after power cycle during upload
- JSON parser reports syntax error on a file that was "just uploaded"

**Phase to address:** SD Card Config milestone -- file write safety must be implemented from the start.

---

### Pitfall 7: SoftAP Mode Consumes 60-70KB Internal SRAM

**What goes wrong:**
Starting WiFi SoftAP allocates significant internal SRAM for the WiFi stack, DHCP server, and TCP/IP buffers. Combined with LVGL's 96KB pool and existing allocations, free internal heap drops to dangerously low levels. Creating the WebServer object (`new WebServer(80)`) adds another ~2-3KB. Each connected client adds ~4KB for TCP buffers. If two browser tabs connect simultaneously, that is another 8KB gone.

**Why it happens:**
The ESP32's WiFi stack requires internal SRAM (not PSRAM) for DMA-capable buffers. SoftAP needs more memory than STA-only mode because it must manage client associations, beacon generation, and DHCP.

Current memory budget (estimated from codebase):
- LVGL internal heap: 96KB
- LVGL draw buffers: 128KB (PSRAM -- does not count)
- WiFi STA-only: ~40KB
- WiFi AP_STA: ~70KB (additional ~30KB over STA-only)
- FreeRTOS + Arduino core: ~40KB
- Remaining free internal SRAM: ~50-80KB
- WebServer + ArduinoOTA: ~10KB
- **Safety margin: 40-70KB** -- tight but workable

**Prevention:**
1. Limit SoftAP to 1 simultaneous client: `WiFi.softAP(ssid, pass, channel, 0, 1)` -- last param is max_connections
2. Use the existing OTA pattern: SoftAP is temporary, not always-on. Start only when user taps config button, stop when upload is complete or after timeout
3. Do NOT run SoftAP + HTTP server at the same time as any other memory-intensive operation (JSON parsing, large SD reads)
4. Monitor internal heap during SoftAP mode:
   ```cpp
   Serial.printf("Internal free: %d\n", heap_caps_get_free_size(MALLOC_CAP_INTERNAL));
   ```
5. Set a hard minimum: if `heap_caps_get_free_size(MALLOC_CAP_INTERNAL) < 30000` after starting SoftAP, abort and show error

**Detection:**
- Random crashes when SoftAP is active + user interacts with LVGL UI
- `heap_caps_get_free_size(MALLOC_CAP_INTERNAL)` drops below 30KB
- WiFi stack prints "E (xxx) wifi:alloc pbuf fail" to serial

**Phase to address:** Config Upload milestone -- SoftAP start/stop lifecycle must include memory checks.

---

### Pitfall 8: Dynamic Hotkey Callbacks With Dangling Pointers

**What goes wrong:**
The current `btn_event_cb` receives a `const Hotkey*` pointer via `lv_event_get_user_data()`. These pointers reference static const arrays (`page1_hotkeys[]`, etc.) which live forever. When switching to dynamic configs loaded from SD card, the hotkey data is allocated on the heap or in a buffer. If the config buffer is freed or overwritten (e.g., loading a new config), all button callbacks now hold dangling pointers. Pressing any button crashes the device.

**Prevention:**
1. Maintain a stable config buffer that persists for the lifetime of the UI:
   ```cpp
   // Global config storage -- allocated once, updated in place
   static Hotkey dynamic_hotkeys[MAX_PAGES][MAX_BUTTONS_PER_PAGE];

   // Button callback always points into this stable array
   lv_obj_add_event_cb(btn, btn_event_cb, LV_EVENT_CLICKED,
                        &dynamic_hotkeys[page][button_idx]);
   ```
2. Never `free()` the old config until the new config is fully installed AND all button callbacks are updated
3. Use a double-buffer pattern: two config slots, toggle between them. The inactive slot gets the new config, then swap the "active" pointer atomically
4. Alternative: use button index as user_data (cast int to void*), and look up the hotkey from the active config array:
   ```cpp
   static void btn_event_cb(lv_event_t *e) {
       int idx = (int)(intptr_t)lv_event_get_user_data(e);
       const Hotkey *hk = &active_config->pages[current_page].hotkeys[idx];
       // ...
   }
   ```

**Detection:**
- Crash (Guru Meditation) when pressing a button after config reload
- Buttons send wrong keys (reading freed/overwritten memory)
- Works perfectly on first config, crashes on second load

**Phase to address:** Dynamic UI milestone -- callback data lifetime must be part of the design.

---

### Pitfall 9: SD Card Not Detected After WiFi/SoftAP Operations

**What goes wrong:**
Some ESP32-S3 GPIO configurations cause SD card SPI communication to fail after WiFi mode changes. The WiFi radio initialization can affect GPIO multiplexing, especially if any SD card pins overlap with WiFi-related internal routing. On the CrowPanel, SD uses GPIO 10-13 (HSPI), which do not overlap with WiFi's pins -- BUT the SPI bus state can be corrupted if the SD card was in the middle of a transaction when WiFi mode changed, or if the SD library's internal state machine gets confused.

**Prevention:**
1. Always complete any SD transaction before changing WiFi mode:
   ```cpp
   // BAD: WiFi mode change while SD might be mid-operation
   WiFi.mode(WIFI_AP_STA);

   // GOOD: ensure SD is idle first
   // (no SD operations in progress -- check by design, not by mutex)
   WiFi.mode(WIFI_AP_STA);
   ```
2. After returning from SoftAP mode to STA mode, verify SD card is still accessible:
   ```cpp
   if (!SD.exists("/")) {
       Serial.println("SD lost after WiFi change, re-mounting");
       SD.end();
       SD.begin(SD_CS, sd_spi, 4000000);
   }
   ```
3. Do NOT run SD card operations and WiFi mode transitions concurrently

**Detection:**
- SD reads return -1 after SoftAP start/stop cycle
- "SD: mount failed" in serial output despite card being present
- Config upload succeeds (file received via HTTP) but write to SD fails

**Phase to address:** Config Upload milestone -- WiFi/SD interaction must be tested as integration scenario.

---

### Pitfall 10: Config Upload via HTTP Has No Authentication

**What goes wrong:**
The SoftAP network ("CrowPanel-OTA" with password "crowpanel") is the only protection. Anyone within WiFi range who knows the SSID/password can upload arbitrary config files. A malicious config could define hotkeys that execute dangerous keyboard shortcuts (Ctrl+Alt+Del, format commands, etc.). The existing OTA code has the same issue for firmware uploads -- but config uploads are a lower bar for attack.

**Prevention:**
1. Use a unique per-device password displayed on screen when config mode starts (not a hardcoded default)
2. Add a confirmation step: after upload, show the new config on screen and require a physical tap to "Apply" -- this prevents silent remote config changes
3. Validate config contents strictly: reject any keycodes outside an allowed set, limit label lengths, sanitize all string fields
4. Add rate limiting: reject more than 3 upload attempts per config session
5. Consider: require physical button press on the device to enable config upload mode (already the pattern with the OTA button in the UI header)

**Detection:**
- Unexpected config changes without user action
- Hotkeys sending different keys than displayed labels

**Phase to address:** Config Upload milestone -- authentication should be part of the upload flow design.

---

## Minor Pitfalls

These are easy to avoid if you know about them.

---

### Pitfall 11: FAT32 Filename Limitations on SD Card

**What goes wrong:**
SD cards formatted as FAT32 have filename restrictions. While long filenames (LFN) are supported, some cheap SD card libraries have bugs with paths > 255 characters or filenames with special characters. More importantly, FAT32 is case-insensitive -- `/config/Layout.json` and `/config/layout.json` are the SAME file.

**Prevention:**
- Use lowercase filenames only
- Keep paths short: `/cfg/layout.json` not `/configuration/hotkey-layouts/default-layout.json`
- Use the `.json` extension consistently
- Create directories explicitly before writing files (`SD.mkdir("/cfg")`)

---

### Pitfall 12: WebServer Blocks Main Loop During Large Responses

**What goes wrong:**
The ESP32 `WebServer` library is synchronous. When serving the config editor HTML page (which could be 10-20KB with embedded CSS/JS for the editor UI), the `server.send()` call blocks until the entire response is sent. At WiFi SoftAP speeds (~1-2 MB/s), a 20KB page takes ~15ms -- but if the client connection is slow or dropping packets, it could block for seconds.

**Prevention:**
1. Keep served HTML pages small (< 5KB). Use minified CSS/JS
2. Serve large assets from SD card using chunked transfer with yield between chunks
3. Use `server.sendContent()` for chunked responses that yield back to loop
4. Set a client timeout: `web_server->setTimeout(5)` -- 5 seconds max per request
5. Consider: serve only a minimal bootstrap HTML that loads a richer UI from a JS file on SD card

---

### Pitfall 13: ArduinoJson StaticJsonDocument Stack Overflow

**What goes wrong:**
Using `StaticJsonDocument<N>` allocates N bytes on the stack. For a config file that produces a 4KB+ JSON DOM, `StaticJsonDocument<4096>` puts 4KB on the stack. Combined with the ESP32's 8KB default task stack, this leaves very little room and can overflow. ArduinoJson v7 removed StaticJsonDocument entirely for this reason.

**Prevention:**
- Use ArduinoJson v7 with `JsonDocument` (heap-allocated) and PSRAM custom allocator
- Never use `StaticJsonDocument` for anything larger than 512 bytes on ESP32
- If stuck on ArduinoJson v6, use `DynamicJsonDocument` with explicit capacity

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| SD Card file format design | JSON too large for memory | Keep config compact: IDs not full strings, max 4 pages x 12 buttons, cap at 8KB |
| SD Card read at boot | Blocks LVGL init, black screen for 200ms+ | Load config before `create_ui()`, show splash only after config loaded |
| SoftAP start for config upload | ESP-NOW stops working | Pin channel explicitly, warn user "hotkeys paused during upload" |
| HTTP upload handler | Stack overflow from SD write in handler | Buffer to PSRAM, write to SD in separate task or after upload complete |
| Dynamic UI rebuild | LVGL memory leak from style allocations | Use widget pool pattern (create once, update labels/colors) |
| Config validation | Corrupt JSON crashes device on boot | Validate before writing, keep fallback config, hardcoded defaults as last resort |
| Desktop config editor | Over-complex JSON schema | Keep it flat: array of pages, each page is array of button objects. No nesting beyond 2 levels |
| Multiple config files | User confusion, filename collisions | One active config, clearly named `/cfg/active.json`. Additional configs numbered `/cfg/1.json`, `/cfg/2.json` |

## Memory Budget Analysis

This is the critical constraint. All numbers are approximate for ESP32-S3 with 8MB OPI PSRAM and 512KB internal SRAM.

### Internal SRAM Budget (512KB total, ~390KB usable)

| Consumer | Allocation | Notes |
|----------|-----------|-------|
| FreeRTOS + Arduino core | ~40KB | Task stacks, kernel objects |
| WiFi STA mode | ~40KB | Baseline when WiFi initialized |
| WiFi AP_STA overhead | +30KB | Additional when SoftAP active |
| LVGL internal heap | 96KB | `LV_MEM_SIZE` in lv_conf.h |
| ESP-NOW buffers | ~5KB | Peer table, TX/RX queues |
| Serial buffers | ~4KB | TX + RX ring buffers |
| WebServer (when active) | ~8KB | Server object + client buffers |
| ArduinoOTA (when active) | ~4KB | mDNS + update state |
| **Total when idle (STA only)** | **~185KB** | |
| **Total when config mode (AP_STA + HTTP)** | **~227KB** | |
| **Remaining headroom (idle)** | **~205KB** | Comfortable |
| **Remaining headroom (config mode)** | **~163KB** | Workable but watch it |
| **Minimum safe threshold** | **30KB** | Below this = random crashes |

### PSRAM Budget (8MB, ~7.5MB usable)

| Consumer | Allocation | Notes |
|----------|-----------|-------|
| LVGL draw buffers | 128KB | 800x40x2 bytes x 2 buffers |
| JSON parse buffer | ~16KB | Config file + ArduinoJson DOM |
| HTTP upload temp buffer | ~16KB | Max config file size |
| SD read/write buffer | ~4KB | Chunk buffer for file I/O |
| **Total PSRAM used** | **~164KB** | |
| **Remaining** | **~7.3MB** | Massive headroom |

**Key insight:** Internal SRAM is the constraint, not PSRAM. Every allocation that CAN go to PSRAM SHOULD go to PSRAM. Use `ps_malloc()` for all buffers, ArduinoJson custom allocator for JSON, and keep LVGL on internal SRAM for performance.

## Integration Gotchas Specific to This Milestone

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| WiFi mode transition (STA -> AP_STA -> STA) | Not re-pinning ESP-NOW channel after mode change | Always call `esp_wifi_set_channel()` after `WiFi.mode()` changes |
| HTTP upload + SD write | Writing file in upload handler (same task as WebServer) | Buffer to PSRAM in handler, flush to SD after UPLOAD_FILE_END |
| Config reload -> UI update | Destroying and recreating LVGL widgets | Update existing widgets in place (labels, colors, callbacks) |
| Boot with no SD card | Crash or blank screen | Graceful fallback to hardcoded defaults, show "Insert SD card" message |
| Boot with corrupt config | JSON parse fails, no UI | Try backup file, then hardcoded defaults. Never leave UI unbuilt |
| SoftAP timeout | SoftAP left running forever, draining battery and blocking ESP-NOW | Auto-stop SoftAP after 5 minutes of inactivity or after successful upload |
| Multiple rapid config uploads | Memory not freed between uploads, PSRAM buffers accumulate | Reuse single upload buffer, free after each complete upload |
| Desktop editor sends oversized config | ESP32 runs out of memory parsing huge JSON | Reject uploads > 16KB at HTTP level with 413 response |

## Recovery Strategies

| Failure | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Corrupt config file on SD | LOW | Fall back to `.bak` file, then hardcoded defaults. Boot always succeeds |
| SD card removed during operation | LOW | Detect via `SD.exists("/")` check, show warning, continue with in-memory config |
| WiFi SoftAP fails to start | LOW | Show error on screen, return to normal operation (ESP-NOW still works) |
| LVGL heap exhausted after config reload | MEDIUM | Reboot device (soft reset). Widget pool pattern prevents this in production |
| Stack overflow during HTTP upload | MEDIUM | Watchdog triggers reboot. Fix by increasing stack size or moving SD writes off HTTP task |
| ESP-NOW stops after WiFi mode change | LOW | Re-initialize ESP-NOW: `esp_now_deinit(); esp_now_init(); esp_now_add_peer(...)` |

## Sources

- [ESP-IDF WiFi Driver -- Channel coexistence in AP+STA mode](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/wifi.html) -- SoftAP and STA must share same channel
- [ESP-NOW + WiFi coexistence -- Arduino Forum](https://forum.arduino.cc/t/use-esp-now-and-wifi-simultaneously-on-esp32/1034555) -- channel pinning requirement confirmed
- [ESP-NOW + WiFi performance and channel -- ESP32 Forum](https://www.esp32.com/viewtopic.php?t=12772) -- packet loss when WiFi active
- [ESP-NOW WiFi channel in APSTA mode -- ESP32 Forum](https://www.esp32.com/viewtopic.php?t=14542) -- channel 0 ambiguity in AP_STA
- [ArduinoJson v7 PSRAM allocator](https://arduinojson.org/v7/how-to/use-external-ram-on-esp32/) -- custom allocator for ESP32 PSRAM
- [ArduinoJson v6 PSRAM](https://arduinojson.org/v6/how-to/use-external-ram-on-esp32/) -- CONFIG_SPIRAM_USE_MALLOC approach
- [LVGL v8.3 Object deletion](https://docs.lvgl.io/8.3/overview/object.html) -- lv_obj_del behavior
- [LVGL style memory leak -- LVGL Forum](https://forum.lvgl.io/t/out-of-memory-even-though-using-style-reset-and-object-delete/8314) -- styles not freed on object delete
- [LVGL animation memory leak -- GitHub #2978](https://github.com/lvgl/lvgl/issues/2978) -- lv_obj_del memory issues
- [ESP32 SD card WebServer example -- arduino-esp32](https://github.com/espressif/arduino-esp32/blob/master/libraries/WebServer/examples/SDWebServer/SDWebServer.ino) -- reference implementation
- [ESP32 WebServer upload buffer](https://avantmaker.com/references/esp32-arduino-core-index/esp32-webserver-library/esp32-webserver-library-upload/) -- 1460 byte chunk size
- [ESPAsyncWebServer large file issues -- ESP32 Forum](https://www.esp32.com/viewtopic.php?t=9740) -- memory exhaustion with concurrent clients
- Existing project codebase: `display/ota.cpp` (current SoftAP + WebServer pattern), `display/espnow_link.cpp` (channel=0 peer config), `display/sdcard.cpp` (SPI pin config), `display/ui.cpp` (current static widget creation), `src/lv_conf.h` (96KB LVGL heap), `partitions_4MB_app.csv` (960KB SPIFFS partition)

---
*Pitfalls research for: SD Card Config + SoftAP Upload + Dynamic LVGL UI milestone*
*Project: CrowPanel Command Center (Elcrow Display Hotkeys)*
*Researched: 2026-02-15*
