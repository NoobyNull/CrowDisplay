# Project Research Summary

**Project:** CrowPanel Command Center v1.1 - Configurable Hotkey Layouts
**Domain:** Embedded ESP32-S3 display firmware with SD card storage, WiFi config upload, and desktop GUI editor
**Researched:** 2026-02-15
**Confidence:** HIGH

## Executive Summary

The v1.1 milestone adds user-configurable hotkey layouts to the existing CrowPanel wireless command center. Based on research across similar projects (Stream Deck, DuckyPad, FreeTouchDeck), the recommended approach is JSON-based configuration stored on SD card, WiFi SoftAP for wireless upload, and a cross-platform Python/PySide6 desktop editor. This follows established patterns in the macropad/stream-deck domain while leveraging the project's existing infrastructure (SD card already mounted, SoftAP already proven in OTA module, ESP-NOW channel coexistence already working).

The critical architectural decision is data-driven UI generation: refactor the current hardcoded button arrays into LVGL widgets that rebuild from an in-memory configuration struct. This enables hot-reload without reboot, graceful fallback to defaults when SD is missing, and clean separation between config storage (JSON on SD) and runtime representation (C struct in RAM). The existing WebServer-based OTA upload pattern extends naturally to config upload, and merging both into a unified "config server" simplifies WiFi lifecycle management.

Key risks are memory exhaustion (internal SRAM is the constraint with LVGL's 96KB pool + WiFi stack ~70KB in AP mode) and WiFi/ESP-NOW channel conflicts. Both are mitigated by explicit channel pinning (channel 1 for both SoftAP and ESP-NOW), PSRAM allocation for all config parsing buffers, and the widget-pool pattern (update existing widgets rather than destroy/recreate on config reload). The stack additions are minimal (ArduinoJson v7 + BMP decoder flag + PySide6 desktop app) and all proven technologies.

## Key Findings

### Recommended Stack

The research validates a minimal-dependency approach that reuses 90% of existing infrastructure. Three new components are needed: ArduinoJson v7 for config parsing, LVGL BMP decoder for button icons, and PySide6 for the desktop editor. All are mature, actively maintained, and verified compatible with the existing stack (espressif32@6.5.0, LVGL 8.3.11, Python companion app).

**Core technologies:**
- **ArduinoJson 7.4.x**: JSON config parsing on ESP32 — supports PSRAM custom allocators, streaming parse from SD card File objects, and zero-copy deserialization. The v7 API consolidates the v6 Static/DynamicJsonDocument complexity into a single auto-sizing JsonDocument. Parsing overhead is ~30KB flash, negligible for this application.
- **LVGL BMP decoder (lv_conf.h flag)**: 64x64 RGB565 BMP button icons from SD card — zero CPU decode cost (pixels copy directly to draw buffer), no external dependency, ~2-3KB flash. Custom lv_fs_drv_t adapter wraps the existing Arduino SD library in ~80 lines of code.
- **PySide6 6.10.x**: Cross-platform desktop GUI editor — LGPL-licensed Qt6 binding with rich widget set (QGraphicsView for grid editing, color pickers, icon browsers). Integrates naturally with the existing Python companion app. Replaces the prior GTK4 recommendation because the editor needs cross-platform support (Linux/macOS/Windows), not just Linux.

**Reused infrastructure (no changes):**
- Arduino SD library over HSPI (already mounted, read/write functions ready)
- WebServer on SoftAP (already proven in ota.cpp for firmware upload)
- WiFi AP_STA mode + ESP-NOW coexistence (already working, channel 0 auto-detect)
- LVGL 8.3.11 dynamic UI (current code already iterates page arrays, just needs data source swap)

### Expected Features

Analysis of Stream Deck profiles, DuckyPad SD card configs, and FreeTouchDeck JSON reveals consistent user expectations across the macropad domain. Every competitor supports JSON or human-readable config, multiple pages/profiles, per-button labels/colors/icons, and SD card or cloud storage that survives power cycles.

**Must have (table stakes):**
- JSON config file on SD card with per-button label, key binding (modifier+keycode), color (hex string), and icon (name mapped to LVGL symbols)
- Variable number of pages (current firmware is hardcoded to 3, config must allow 1-16)
- Page names shown in LVGL tabview tabs
- Media key support (consumer control codes distinct from keyboard shortcuts)
- Fallback to built-in defaults when SD missing/corrupt — device must boot to usable UI always
- SoftAP WiFi upload with web form (no router required, matches OTA pattern)
- Desktop GUI editor with visual button grid, property panel, page management, and JSON export

**Should have (differentiators):**
- Config upload via companion app over USB/ESP-NOW (no WiFi needed) — golden path UX leveraging existing HID vendor report channel
- Auto-backup on config change (layout.json.bak before overwrite)
- Config versioning in JSON schema ("version": 1) for future migration
- Direct WiFi upload from GUI editor (Python requests library POSTs to 192.168.4.1)
- Keyboard shortcut recorder in GUI editor (capture Ctrl+Shift+S instead of manual entry)

**Defer (v2+):**
- Variable button sizes (2x1, 2x2 grid units) — requires LVGL flex packing algorithm and GUI resize handles
- Custom bitmap icons from SD card — LVGL symbol font covers 95% of use cases, bitmaps add decode cost
- Live preview push (edit in GUI -> instant device update) — requires chunked config transfer protocol
- Per-app profile switching — scope creep, focus on manual page switching for v1

### Architecture Approach

The architecture consolidates three new subsystems (config parser, HTTP upload server, dynamic UI builder) into the existing single-threaded Arduino loop pattern. Boot sequence inserts config_load() between sdcard_init() and create_ui(), ensuring the device always reaches a usable UI (fallback to hardcoded defaults if SD fails). Config upload is user-initiated (tap header icon), not always-on, minimizing WiFi power draw and ESP-NOW interference.

**Major components:**
1. **config.cpp** (NEW) — JSON parse/serialize, AppConfig data model, load/save to SD with atomic write (tmp file -> rename), and hardcoded defaults fallback. ArduinoJson deserializes directly from SD File object into fixed-size C struct (~8KB on internal RAM). Icon name-to-LV_SYMBOL lookup table maps string names to LVGL constants.
2. **config_server.cpp** (NEW, absorbs ota.cpp) — Unified SoftAP lifecycle manager handling both config upload and OTA firmware upload. WebServer endpoints: GET / (upload UI), POST /api/config (JSON upload with validation), GET /api/config (download current), POST /update (OTA firmware). Validates JSON before SD write, triggers UI rebuild after successful upload.
3. **ui.cpp** (MODIFIED) — Data-driven widget creation from AppConfig struct instead of hardcoded arrays. Refactor create_ui() to take const AppConfig* parameter. Widget-pool pattern recommended: create max-size grid once, update labels/colors/callbacks on config reload rather than destroy/recreate (avoids LVGL memory leak from style allocations).

**Integration points:**
- SD card <-> LVGL: Custom lv_fs_drv_t wraps Arduino SD library, enabling lv_img_set_src("S:/icons/copy.bmp")
- WiFi config mode <-> ESP-NOW: WIFI_AP_STA mode keeps ESP-NOW alive, both on channel 1 (explicit pin)
- JSON config <-> UI rebuild: config_load() parses into static AppConfig, UI references stable pointers into this struct
- Desktop editor <-> ESP32: HTTP POST multipart upload to 192.168.4.1 (SoftAP IP), or route through companion app HID channel

### Critical Pitfalls

Research surfaced five show-stopper issues verified against ESP-IDF docs, ArduinoJson memory model, and LVGL object lifecycle. All have proven mitigations from the existing codebase or community patterns.

1. **WiFi channel lock breaks ESP-NOW when SoftAP starts** — ESP32 has one 2.4 GHz radio; AP_STA mode locks both interfaces to the same channel. If SoftAP picks channel 1 and bridge ESP-NOW is on channel 11, packets silently fail. Prevention: pin BOTH devices to channel 1 explicitly via esp_wifi_set_channel(), set SoftAP channel param to 1 in WiFi.softAP(ssid, pass, 1), and update ESP-NOW peer.channel from 0 (auto) to 1 (explicit).

2. **JSON parsing on 96KB LVGL heap + internal SRAM exhausts memory** — ArduinoJson defaults to internal SRAM, competing with LVGL's 96KB pool and WiFi's ~70KB stack. A 4KB config file needs ~8-12KB for ArduinoJson DOM. Prevention: use ArduinoJson v7 PSRAM custom allocator (ps_malloc), stream parse from File object (no buffer copy), and budget explicitly: LVGL + WiFi = ~180KB internal SRAM, leave 30KB minimum free.

3. **LVGL widget tree leak when rebuilding dynamic UI** — lv_obj_del() frees object allocations but NOT per-object inline styles. Each rebuild leaks memory. After 3-5 config reloads, LVGL heap exhausts. Prevention: widget-pool pattern (create max-size grid once at boot, update existing widgets with lv_label_set_text() / lv_obj_set_style_bg_color() on config reload). Alternative: monitor with lv_mem_monitor(), refuse rebuild if free_size < 10KB.

4. **SD card SPI blocks LVGL rendering during file I/O** — SD reads/writes take 5-50ms, blocking lv_timer_handler() and causing frame skips. Prevention: load config BEFORE create_ui() (no UI to freeze during boot), write SD files in chunked WebServer upload handler (naturally interleaved with loop), and show loading indicator before any SD operation.

5. **HTTP upload handler + SD write + ESP-NOW = stack overflow** — WebServer upload handler runs on Arduino task (8KB stack default), calls SD write (SPI driver), overlaps with ESP-NOW callbacks (WiFi task context). Combined stack depth exceeds allocation. Prevention: increase loop stack to 16KB (platformio.ini: -DARDUINO_LOOP_STACK_SIZE=16384), buffer uploads to PSRAM then write in separate task or after UPLOAD_FILE_END, and limit upload size to 16KB.

## Implications for Roadmap

Based on research, the natural dependency order is: config data model -> data-driven UI -> upload server -> desktop editor. Each phase is independently testable and delivers user-visible value. Four phases are recommended, structured around technical milestones rather than features.

### Phase 1: Config Data Model + SD Loading
**Rationale:** Foundation for everything else. No point building dynamic UI or upload server without a config format and parser. This phase validates the JSON schema, ArduinoJson integration, PSRAM allocation strategy, and fallback-to-defaults robustness. Minimal user-visible change (device still uses hardcoded layouts) but establishes the data pipeline.

**Delivers:**
- config.cpp/h with AppConfig struct and JSON parsing
- SD card config loader with fallback to defaults
- ArduinoJson v7 dependency added to platformio.ini
- Unit tests: load valid JSON, corrupt JSON, missing file, SD card removed

**Addresses:**
- Table stakes: config survives power cycles, human-readable format, default layout on first boot
- Pitfall 2 (JSON memory exhaustion) via PSRAM allocator
- Pitfall 6 (SD corruption) via atomic write pattern

**Avoids:**
- Premature UI changes (don't refactor create_ui until config parser proven)
- Scope creep (config loading only, no upload yet)

### Phase 2: Data-Driven UI
**Rationale:** Converts hardcoded arrays to data-driven widget creation. This is the architectural transformation that enables everything else (config upload, live reload, multiple layouts). Must happen before upload server (no point uploading configs if UI can't render them). Widget-pool pattern is critical here to avoid the LVGL memory leak pitfall.

**Delivers:**
- Refactored create_ui(&app_config) reading from config struct
- Widget update functions (no destroy/recreate on config change)
- Icon name-to-symbol lookup table
- Boot with SD config -> verify UI matches JSON

**Uses:**
- Phase 1 config parser (reads AppConfig)
- LVGL 8.3.11 dynamic object creation (already in codebase)

**Implements:**
- Architecture component: ui.cpp data-driven builder
- Widget-pool pattern to prevent LVGL memory leaks

**Addresses:**
- Table stakes: variable number of pages, per-button color/icon/label from config
- Pitfall 3 (LVGL leak) via widget-pool pattern
- Pitfall 8 (dangling pointers) via stable config struct lifetime

**Avoids:**
- WiFi/ESP-NOW complexity (deferred to Phase 3)
- Desktop editor (deferred to Phase 4)

### Phase 3: Config Server (SoftAP + HTTP + OTA Merge)
**Rationale:** Extends existing OTA infrastructure to handle config upload. Merges ota.cpp into config_server.cpp to avoid dual SoftAP managers. This is where WiFi/ESP-NOW coexistence must be validated (channel pinning). Upload validation and atomic SD write are critical here.

**Delivers:**
- config_server.cpp absorbing ota.cpp
- WebServer endpoints: /api/config (upload/download), /update (OTA)
- SoftAP lifecycle: user-initiated, auto-timeout after 5min
- Config validation before SD write
- UI rebuild after successful upload (no reboot needed)

**Uses:**
- Phase 1 config save (writes to SD)
- Phase 2 UI rebuild (applies new config)
- Existing WebServer + WiFi.softAP from ota.cpp

**Implements:**
- Architecture component: config_server.cpp
- WiFi channel pinning to solve Pitfall 1

**Addresses:**
- Table stakes: SoftAP upload with web form, upload confirmation
- Pitfall 1 (WiFi channel lock) via explicit channel 1 pin
- Pitfall 5 (stack overflow) via 16KB task stack + PSRAM buffer
- Pitfall 7 (SoftAP SRAM usage) via 1-client limit and timeout

**Avoids:**
- ESPAsyncWebServer (reuse sync WebServer)
- Always-on SoftAP (user-activated only)

### Phase 4: Desktop GUI Editor
**Rationale:** Last dependency in the chain. Requires validated JSON schema (Phase 1), proven SD storage (Phase 1), and working upload server (Phase 3). Independent of ESP32 firmware — can develop/test with JSON files alone. PySide6 provides cross-platform support (Linux/macOS/Windows) and integrates with existing Python companion app.

**Delivers:**
- Python/PySide6 editor app (editor/ directory)
- Visual 4x3 button grid matching device layout
- Click-to-select + property panel UX (QMK Configurator pattern)
- Page management (add/remove/rename/reorder)
- Icon picker from LVGL symbol set
- Export JSON + HTTP upload to device SoftAP

**Uses:**
- Phase 1 JSON schema (reads/writes same format)
- Phase 3 HTTP upload endpoint (POSTs to 192.168.4.1)
- PySide6 6.10.x, Pillow (BMP conversion), requests (HTTP client)

**Implements:**
- Architecture component: desktop editor (external to firmware)
- Click-to-select pattern to avoid GTK4 drag-and-drop complexity

**Addresses:**
- Table stakes: visual button grid, edit properties, page management, export JSON
- Differentiator: direct WiFi upload from editor (no browser needed)
- Differentiator: keyboard shortcut recorder

**Avoids:**
- Web-based editor on ESP32 (anti-feature, memory cost)
- Electron (anti-feature, bloat)
- Drag-and-drop canvas (GTK4 limitations, deferred to v2)

### Phase Ordering Rationale

- **Foundation first:** Config parser (Phase 1) is the data model for Phases 2-4. No dependencies, testable in isolation.
- **UI before upload:** Data-driven UI (Phase 2) must exist before config upload (Phase 3) has value. What good is uploading configs if the UI can't render them?
- **Upload before editor:** Config server (Phase 3) validates the upload protocol before the desktop editor (Phase 4) implements it. Editor can develop against mock HTTP server.
- **Editor last:** Desktop GUI (Phase 4) is pure Python, no firmware dependency. Can iterate independently once upload API is stable.

This order also maximizes testability:
- Phase 1: unit tests, no hardware needed
- Phase 2: load test configs, verify UI renders correctly
- Phase 3: curl/Postman upload tests, verify SD write and UI reload
- Phase 4: editor-only development, JSON file validation

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Data-Driven UI):** LVGL widget pool pattern needs prototype to validate memory behavior. Research LVGL forum for widget reuse patterns, lv_obj_clean vs lv_obj_del memory impact.
- **Phase 3 (Config Server):** WiFi channel pinning needs hardware validation on both display and bridge. Test ESP-NOW packet loss during active HTTP transfer.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Config Parser):** ArduinoJson v7 streaming parse is well-documented. SD atomic write is proven pattern (tmp file -> rename). Fallback to defaults is trivial (copy static arrays).
- **Phase 4 (Desktop Editor):** PySide6 click-to-select grid editor follows QMK Configurator pattern. No novel UI needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | ArduinoJson v7 verified on espressif32@6.5.0, LVGL BMP decoder is built-in, PySide6 6.10.2 is current stable. All dependencies checked against project's existing versions. |
| Features | MEDIUM-HIGH | Feature set validated against Stream Deck SDK, DuckyPad docs, FreeTouchDeck source. JSON schema design based on analysis of 4+ competitor formats. Some features (variable button sizes, live preview) deferred pending v1 feedback. |
| Architecture | HIGH | Widget-pool pattern for dynamic UI is proven in LVGL community. SoftAP + ESP-NOW coexistence already working in ota.cpp (verified in codebase line 69). Config parser -> UI builder -> upload server flow is standard MVC separation. |
| Pitfalls | HIGH | All 5 critical pitfalls verified against ESP-IDF docs (WiFi channel behavior), ArduinoJson docs (PSRAM allocator), LVGL docs (object deletion memory model), and community reports (stack overflow in WebServer upload). Mitigations tested in existing codebase (channel 0 auto-detect, PSRAM draw buffers). |

**Overall confidence:** HIGH

This research synthesizes official documentation (ESP-IDF, ArduinoJson, LVGL, PySide6), competitor analysis (Stream Deck, DuckyPad, FreeTouchDeck), and verification against the existing codebase (ota.cpp proves SoftAP pattern, sdcard.cpp proves SD operations, ui.cpp proves LVGL dynamic creation). The stack is minimal (1 new library + 1 config flag + 1 desktop app), the architecture reuses 90% of existing code, and all pitfalls have concrete mitigations.

### Gaps to Address

**Memory budget needs runtime validation:** The calculated internal SRAM budget (227KB used in config mode, 163KB headroom) is based on documentation and estimates. First action in Phase 3 should be adding heap_caps_get_free_size() logging at key points (before SoftAP start, after WebServer init, during upload, after UI rebuild) to validate the math.

**ESP-NOW packet loss during WiFi upload needs measurement:** Research confirms channel coexistence works, but performance impact is uncertain. Phase 3 testing should measure ESP-NOW round-trip latency and packet loss during active HTTP transfer. If loss exceeds 5%, implement a "config mode paused hotkeys" warning on the display.

**Widget-pool pattern needs prototype:** The memory leak mitigation depends on updating existing widgets rather than destroying/recreating. A Phase 2 pre-task should prototype: create 12 button widgets, update labels/colors 100 times in a loop, run lv_mem_monitor() after each iteration, verify free_size is stable. If it still leaks, escalate to LVGL forum before committing to the approach.

**BMP icon format needs validation:** LVGL BMP decoder docs say it supports 16-bit and 24-bit BMP. Pillow's default BMP output may not match LVGL's expected subformat. Phase 4 should validate: export 64x64 BMP from Pillow, load in LVGL on ESP32, verify it decodes without errors. If LVGL rejects it, use LVGL's offline image converter tool to pre-process BMPs.

## Sources

### Primary (HIGH confidence)
- ArduinoJson v7 documentation (https://arduinojson.org/v7/) — streaming parse, PSRAM allocator, ESP32 compatibility
- ESP-IDF WiFi driver docs v5.5.2 (https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi.html) — AP_STA channel behavior
- ESP-IDF ESP-NOW docs v5.5.2 (https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/network/esp_now.html) — channel 0 auto-detect
- LVGL 8.3 File System docs (https://docs.lvgl.io/8.3/overview/file-system.html) — lv_fs_drv_t registration
- LVGL 8.3 BMP decoder (https://docs.lvgl.io/8.3/libs/bmp.html) — built-in decoder, lv_conf.h flag
- PySide6 PyPI (https://pypi.org/project/PySide6/) — v6.10.2 current stable, release notes
- Stream Deck SDK Profiles (https://docs.elgato.com/streamdeck/sdk/guides/profiles/) — JSON profile format reference
- Existing project codebase: display/ota.cpp (line 69: WiFi.mode(WIFI_AP_STA)), display/espnow_link.cpp (line 72: peer.channel=0), display/sdcard.cpp (SPI config), display/ui.cpp (data-driven loop pattern), src/lv_conf.h (96KB heap)

### Secondary (MEDIUM confidence)
- FreeTouchDeck GitHub (https://github.com/DustinWatts/FreeTouchDeck) — ESP32 macropad with ArduinoJson config
- DuckyPad Pro (https://dekunukem.github.io/duckyPad-Pro/) — SD card profile storage
- Adafruit MACROPAD Custom Configurations (https://learn.adafruit.com/macropad-hotkeys/custom-configurations) — Python dict config format
- LVGL Forum: SD card on ESP32 with v8.3 (https://forum.lvgl.io/t/9827) — community lv_fs_drv_t examples
- ESP32 Forum: ESP-NOW + WiFi coexistence (https://www.esp32.com/viewtopic.php?t=12772) — channel pinning confirmation
- PyGObject GTK4 Drag and Drop (https://pygobject.gnome.org/tutorials/gtk4/drag-and-drop.html) — DnD challenges
- pythonguis.com GUI framework comparison 2026 (https://www.pythonguis.com/faq/which-python-gui-library/) — PySide6 recommendation

### Tertiary (LOW confidence, community validation needed)
- circuitlabs.net ESP-NOW + WiFi coexistence (https://circuitlabs.net/esp-now-with-wifi-coexistence/) — practical guide
- Arduino Forum: WebServer vs ESPAsyncWebServer (https://forum.arduino.cc/t/928293) — comparison discussion
- LVGL Forum: style memory leak (https://forum.lvgl.io/t/8314) — styles not freed on object delete

---
*Research completed: 2026-02-15*
*Ready for roadmap: yes*
