# Stack Research: v1.1 Configurable Hotkey Layouts

**Domain:** SD card config storage, SoftAP HTTP file upload, desktop GUI layout editor
**Researched:** 2026-02-15
**Confidence:** HIGH (all three areas verified against official docs and existing codebase)

## Existing Stack (DO NOT CHANGE)

Already validated and production-ready. This research covers only NEW additions.

| Technology | Version | Status |
|------------|---------|--------|
| PlatformIO + espressif32@6.5.0 | Arduino 2.x / ESP-IDF 4.4 | Locked |
| LovyanGFX | 1.1.8 | Locked |
| LVGL | 8.3.11 | Locked |
| ESP-NOW | built-in | Locked, production |
| Arduino SD library | built-in | Already integrated (display/sdcard.cpp) |
| Arduino WebServer | built-in | Already used (display/ota.cpp) |
| WiFi.h SoftAP | built-in | Already used in OTA mode (WIFI_AP_STA) |
| Python companion app | psutil, hidapi, pynvml | Locked |

---

## Area 1: SD Card JSON Config + Image Assets

### What Already Exists

The project already has a working SD card module (`display/sdcard.cpp`) using the Arduino `SD` library over SPI (HSPI bus):
- Pins: CS=10, MOSI=11, CLK=12, MISO=13
- SPI clock: 4 MHz
- Functions: `sdcard_init()`, `sdcard_read_file()`, `sdcard_write_file()`, `sdcard_file_exists()`
- Called at boot in `display/main.cpp` as non-fatal init

### NEW: ArduinoJson for Config Parsing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ArduinoJson | 7.4.x | Parse/serialize hotkey layout JSON from SD card | The only serious JSON library for embedded C++. v7 has streaming parser, reduced memory footprint vs v6, and zero-copy deserialization. ~30KB flash overhead is acceptable for config parsing (not real-time protocol). |

**Confidence:** HIGH -- ArduinoJson 7.4.2 is current stable (released 2025-07-01). Compatible with ESP-IDF 4.4 / Arduino 2.x.

**Why ArduinoJson and not raw struct files:**
- Hotkey layouts are user-editable configuration, not a fixed wire protocol. JSON is the right format because:
  - Human-readable on the SD card (debugging without special tools)
  - The desktop GUI editor naturally produces JSON
  - Schema can evolve (add fields) without binary format versioning headaches
  - ArduinoJson's `JsonDocument` with PSRAM allocation handles layouts easily within memory

**Why ArduinoJson v7 specifically:**
- v7 replaced `StaticJsonDocument`/`DynamicJsonDocument` with a single `JsonDocument` that auto-sizes
- `JsonDocument` can allocate from PSRAM via custom allocator -- critical on ESP32-S3 where internal RAM is precious
- Streaming `deserializeJson(doc, file)` reads directly from SD `File` object -- no need to buffer entire file in RAM
- v6 is in maintenance mode; v7 is actively developed

**Installation:**
```ini
; platformio.ini [env:display] lib_deps addition
lib_deps =
    ${env.lib_deps}
    bblanchon/ArduinoJson@^7.4.0
```

**Usage pattern (parse from SD):**
```cpp
#include <ArduinoJson.h>
#include <SD.h>

bool load_layout(const char *path) {
    File f = SD.open(path, FILE_READ);
    if (!f) return false;

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, f);
    f.close();
    if (err) {
        Serial.printf("JSON parse error: %s\n", err.c_str());
        return false;
    }
    // Extract hotkey definitions from doc...
    return true;
}
```

Sources:
- [ArduinoJson v7 release notes](https://arduinojson.org/v7/revisions/) -- v7.4.2 current stable
- [ArduinoJson v7 docs](https://arduinojson.org/v7/) -- streaming deserialization, custom allocators
- [ArduinoJson GitHub](https://github.com/bblanchon/ArduinoJson) -- ESP32 compatibility confirmed

### NEW: LVGL File System Driver for Button Icons

The existing `lv_conf.h` has image loading disabled:
```c
#define LV_USE_FS_STDIO 0
#define LV_USE_FS_POSIX 0
#define LV_USE_FS_FATFS 0
#define LV_USE_PNG 0
#define LV_USE_BMP 0
#define LV_USE_SJPG 0
```

**Recommendation: Use LVGL's custom file system driver (`lv_fs_drv_t`) wrapping Arduino SD, plus enable `LV_USE_BMP` for button icon images.**

| Change | Value | Why |
|--------|-------|-----|
| Custom `lv_fs_drv_t` | Register with letter 'S' | LVGL v8.3 requires a registered FS driver to load images from files. The built-in `LV_USE_FS_FATFS` expects raw FatFs, not Arduino's SD wrapper. A custom driver wrapping `SD.open()`/`File.read()`/etc. is ~80 lines of code and is the standard approach for Arduino+LVGL. |
| `LV_USE_BMP 1` | in lv_conf.h | BMP is the simplest format -- no decompression CPU cost, no extra library. 16-bit RGB565 BMP files match the display's native color depth exactly. |
| `LV_USE_IMG 1` | Already enabled | No change needed. `lv_img_set_src(img, "S:/icons/copy.bmp")` loads from SD. |

**Why BMP and not PNG:**
- PNG decoding on ESP32 is CPU-intensive (zlib decompression). Each button icon decode adds latency to UI load.
- BMP at RGB565 is zero-decode -- LVGL copies pixels directly to the draw buffer.
- Button icons at 64x64 RGB565 = 8KB each. With 36 buttons max, that is 288KB of SD reads, which is trivial at 4MHz SPI.
- The desktop GUI editor will export BMP files -- PNG-to-BMP conversion happens on the PC, not the ESP32.

**Why not LVGL's built-in `LV_USE_FS_FATFS`:**
- That macro expects the raw ESP-IDF FatFs API (`ff.h`), not Arduino's `SD.h` wrapper.
- The Arduino SD library is already working and tested. Writing a thin `lv_fs_drv_t` adapter is simpler and safer than switching to raw FatFs.

**Flash impact:** Enabling `LV_USE_BMP` adds ~2-3KB to firmware. Negligible.

**lv_conf.h changes needed:**
```c
#define LV_USE_BMP 1       // Enable BMP decoder
// Optionally, for future PNG support:
// #define LV_USE_PNG 1    // ~10KB flash, requires lodepng
```

Sources:
- [LVGL 8.3 File System docs](https://docs.lvgl.io/8.3/overview/file-system.html) -- lv_fs_drv_t registration
- [LVGL forum: SD card on ESP32 with v8.3](https://forum.lvgl.io/t/how-do-i-correctly-make-the-sd-card-work-for-image-widgets-on-an-esp32-dev-kit-with-lvgl-v-8-3/9827) -- community examples
- [LVGL BMP decoder](https://docs.lvgl.io/8.3/libs/bmp.html) -- built-in, enable via lv_conf.h

### SD Card File Layout

```
/config/
  layout.json          <- Hotkey definitions (all pages)
  settings.json        <- Device settings (brightness, idle timeout, etc.)
/icons/
  copy.bmp             <- 64x64 RGB565 BMP button icons
  paste.bmp
  terminal.bmp
  ...
/backup/
  layout.json.bak      <- Auto-backup before overwrite
```

### What NOT to Add for SD Card

| Avoid | Why |
|-------|-----|
| SdFat library | Adds external dependency. Arduino SD is already working and sufficient. SdFat's advantages (long filenames, exFAT) are not needed -- config files have short names. |
| SD_MMC | Uses SDMMC peripheral (4-bit/8-bit bus), different pins. The CrowPanel TF card slot is wired for SPI. SD_MMC would require hardware changes. |
| LittleFS on flash | 4MB flash is tight with firmware. SD card provides effectively unlimited config storage. LittleFS is appropriate for devices without SD slots. |
| SPIFFS | Deprecated in favor of LittleFS. Same flash space concerns. |
| cJSON | Lower-level C library. ArduinoJson is the idiomatic choice for Arduino framework and has better memory management (custom allocators, PSRAM support). |
| MessagePack on SD | Config files should be human-readable for debugging. JSON wins here. |

---

## Area 2: SoftAP HTTP Server for File Upload

### What Already Exists

The project already has a complete SoftAP + WebServer implementation in `display/ota.cpp`:
- `WiFi.mode(WIFI_AP_STA)` -- AP+STA mode so ESP-NOW keeps working
- `WiFi.softAP("CrowPanel-OTA", "crowpanel")` -- SoftAP with password
- `WebServer` on port 80 -- handles multipart file upload via `HTTPUpload`
- Teardown: `WiFi.softAPdisconnect(true)` then back to `WIFI_STA`

**This infrastructure is directly reusable for config file upload.** The OTA module proves the pattern works, including WiFi + ESP-NOW coexistence.

### Recommended Approach: Extend Existing WebServer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Arduino WebServer | built-in | HTTP server for file upload | Already working in OTA module. Synchronous model is fine for single-client config upload. No new dependency needed. |

**Why NOT ESPAsyncWebServer:**
- The sync `WebServer` is already proven in this codebase (OTA upload works).
- ESPAsyncWebServer would add an external dependency (`me-no-dev/ESPAsyncWebServer` + `me-no-dev/AsyncTCP`).
- Config upload is a single-client operation (one desktop app uploading files). No concurrent connection handling needed.
- The async library has historical stability issues and is maintained by a single developer.
- Adding async introduces task/callback complexity that conflicts with the existing synchronous main loop pattern.

**Implementation approach:**

Add new endpoints to the same `WebServer` instance, activated alongside OTA or as a separate "config mode":

```
POST /api/config/upload     <- Multipart form: layout.json
POST /api/icons/upload      <- Multipart form: icon BMP file(s)
GET  /api/config/download   <- Download current layout.json
GET  /api/status            <- Device info (SD card size, firmware version, current layout)
DELETE /api/icons/{name}    <- Remove an icon file
```

**WiFi + ESP-NOW Coexistence:**

This is already solved in the codebase. Key constraints (verified from ESP-IDF docs and existing OTA code):

1. Use `WIFI_AP_STA` mode (not `WIFI_AP` alone) -- ESP-NOW requires the station interface
2. ESP-NOW and SoftAP must operate on the same WiFi channel. SoftAP defaults to channel 1, and ESP-NOW peers must be configured for channel 0 (auto = current channel) or explicitly channel 1
3. Both the display and bridge are already using channel 0 / auto in the current ESP-NOW init, so this works out of the box when SoftAP is active
4. Performance: expect slight ESP-NOW latency increase (~1-5ms) when WiFi is actively handling HTTP traffic. This is acceptable since config upload is not time-critical

**SoftAP Configuration (reuse OTA pattern):**
```cpp
WiFi.mode(WIFI_AP_STA);
WiFi.softAP("CrowPanel-Config", "crowpanel");
// WebServer setup...
// When done:
WiFi.softAPdisconnect(true);
WiFi.mode(WIFI_STA);
```

**File upload handler (SD card write):**
```cpp
static File upload_file;

void handle_config_upload() {
    HTTPUpload &upload = server.upload();
    if (upload.status == UPLOAD_FILE_START) {
        // Backup existing config
        if (SD.exists("/config/layout.json")) {
            // Copy to /backup/layout.json.bak
        }
        upload_file = SD.open("/config/layout.json", FILE_WRITE);
    } else if (upload.status == UPLOAD_FILE_WRITE) {
        upload_file.write(upload.buf, upload.currentSize);
    } else if (upload.status == UPLOAD_FILE_END) {
        upload_file.close();
        // Validate JSON before accepting
        // Reload layout from SD card
    }
}
```

### What NOT to Add for HTTP Server

| Avoid | Why |
|-------|-----|
| ESPAsyncWebServer | External dependency, async complexity, single-client use case. Sync WebServer already proven. |
| WebSocket | Overkill for file upload. Standard HTTP multipart POST is sufficient. |
| mDNS | Nice-to-have but not essential. The SoftAP always has IP 192.168.4.1. Desktop app can hardcode this. |
| HTTPS/TLS | Local AP-only connection. No internet exposure. TLS would consume ~40KB RAM and add latency. |
| REST framework (e.g., aREST) | Adds dependency for trivial routing. WebServer's `on()` method handles the 5 endpoints needed. |

Sources:
- [ESP-IDF WiFi coexistence docs (v5.5.2)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi.html) -- AP_STA + ESP-NOW channel behavior
- [ESP-IDF ESP-NOW docs](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/network/esp_now.html) -- channel 0 = current channel
- [circuitlabs.net ESP-NOW + WiFi coexistence](https://circuitlabs.net/esp-now-with-wifi-coexistence/) -- practical guide
- [Arduino Forum: WebServer vs ESPAsyncWebServer](https://forum.arduino.cc/t/webserver-vs-espasyncwebserver/928293) -- comparison discussion

---

## Area 3: Python Desktop GUI for Hotkey Layout Editor

### Technology Selection: PySide6

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PySide6 | 6.10.x | GUI framework for layout editor | See detailed rationale below |
| Pillow | 11.x | Image processing (resize, convert icons to BMP RGB565) | Standard Python imaging library. Needed to prepare button icons for the ESP32 display. |
| requests | 2.32.x | HTTP client to upload config/icons to ESP32 SoftAP | Lightweight, standard HTTP library. Handles multipart file upload. |

**Why PySide6 over GTK4 (reversing prior research recommendation):**

The prior STACK.md recommended GTK4 + PyGObject for the companion daemon's config panel. For the dedicated layout editor GUI, PySide6 is the better choice:

1. **Cross-platform:** PySide6 runs on Linux, macOS, and Windows. GTK4 is Linux-only in practice (macOS/Windows GTK is painful). A hotkey editor should work wherever the user's desktop PC is.

2. **Richer widget set for visual editors:** Qt provides `QGraphicsView`/`QGraphicsScene` for the drag-and-drop grid layout editor, `QColorDialog` for button color picking, `QFileDialog` for icon selection, and `QTreeView` for page/hotkey hierarchy. GTK4 has equivalents but they are less polished for editor-style applications.

3. **LGPL license:** PySide6 is LGPL-licensed (official Qt for Python binding). No commercial license needed for distribution. PyQt6 requires GPL or commercial license.

4. **Companion app synergy:** The existing companion app (`companion/hotkey_companion.py`) is pure Python. PySide6 integrates naturally as another Python module in the same project.

5. **Active development:** PySide6 6.10.2 released February 2026. Regular releases tracking Qt6.

**Why NOT the alternatives:**

| Alternative | Why Not |
|-------------|---------|
| GTK4 + PyGObject | Linux-only in practice. Editor app benefits from cross-platform. GTK4 lacks QGraphicsView equivalent for visual grid editing. |
| PyQt6 | Same Qt6 API as PySide6 but GPL-licensed. Would require commercial license for distribution. |
| Dear PyGui | Immediate-mode rendering. Great for data visualization, wrong paradigm for a form-based config editor with drag-and-drop. |
| Tkinter | Primitive widget set. No modern styling. Would look and feel outdated. |
| Electron/web | 200MB+ RAM overhead for a config panel. Absurd. |
| Kivy | Touch-focused framework. Desktop editor needs standard desktop widgets (menus, dialogs, tree views). |

**Confidence:** HIGH -- PySide6 is the official Qt for Python binding, actively maintained by the Qt Company, and 6.10.x is current stable.

Sources:
- [PySide6 on PyPI](https://pypi.org/project/PySide6/) -- v6.10.2, released Feb 2026
- [PySide6 release notes](https://doc.qt.io/qtforpython-6/release_notes/pyside6_release_notes.html) -- full changelog
- [PyQt6 vs PySide6 comparison](https://www.pythonguis.com/faq/pyqt6-vs-pyside6/) -- licensing is the key difference
- [pythonguis.com 2026 GUI comparison](https://www.pythonguis.com/faq/which-python-gui-library/) -- PySide6 recommended for professional apps
- [Medium: PySide6 vs PyQt vs Dear PyGui 2025 review](https://medium.com/@areejkam01/i-compared-pyside6-pyqt-kivy-flet-and-dearpygui-my-honest-2025-review-8c037118a777) -- practical comparison

### GUI Editor Architecture

```
editor/
  main.py                <- Entry point, QApplication
  editor_window.py       <- Main window with toolbar, page tabs
  grid_editor.py         <- QGraphicsView-based 4x3 button grid editor
  hotkey_dialog.py       <- Dialog for editing individual hotkey properties
  icon_manager.py        <- Icon browser, BMP conversion via Pillow
  device_connection.py   <- HTTP client for ESP32 SoftAP upload/download
  models.py              <- Layout data model (pages, hotkeys) with JSON serialization
```

### Image Processing Pipeline (Pillow)

Button icons need to be converted from any format (PNG, JPEG, SVG) to 64x64 RGB565 BMP for the ESP32 display:

```python
from PIL import Image
import struct

def convert_to_rgb565_bmp(input_path: str, output_path: str, size: int = 64):
    img = Image.open(input_path).convert("RGB").resize((size, size))
    # Save as 16-bit BMP (RGB565)
    # LVGL's BMP decoder expects standard BMP with 16-bit color depth
    img.save(output_path, format="BMP")
```

Note: LVGL's BMP decoder supports 16-bit and 24-bit BMP. For simplicity, 24-bit BMP works fine (LVGL converts internally). For optimal performance, pre-convert to RGB565 format using LVGL's offline image converter tool.

### Installation

```bash
# Desktop GUI editor
pip install PySide6>=6.10.0 Pillow>=11.0.0 requests>=2.32.0

# Or with requirements.txt
# editor/requirements.txt:
# PySide6>=6.10.0
# Pillow>=11.0.0
# requests>=2.32.0
```

---

## Combined Stack Summary

### ESP32 Display Firmware Additions

| Library | Version | platformio.ini | Purpose |
|---------|---------|----------------|---------|
| ArduinoJson | ^7.4.0 | `lib_deps` addition | Parse layout JSON from SD card |

**lv_conf.h changes:**
| Define | New Value | Purpose |
|--------|-----------|---------|
| `LV_USE_BMP` | `1` | Decode BMP button icons from SD |

**No new libraries needed for HTTP upload** -- reuses existing WebServer + WiFi SoftAP from OTA module.

### Desktop Editor (New Python Package)

| Package | Version | Purpose |
|---------|---------|---------|
| PySide6 | >=6.10.0 | GUI framework |
| Pillow | >=11.0.0 | Image conversion (any format -> BMP for ESP32) |
| requests | >=2.32.0 | HTTP upload to ESP32 SoftAP |

### Total New Dependencies

**Firmware:** 1 library (ArduinoJson) + 1 lv_conf.h flag change.
**Desktop:** 3 pip packages (PySide6, Pillow, requests).

This is deliberately minimal. The heaviest existing infrastructure (SD card, SoftAP, WebServer, ESP-NOW) is already built and proven.

---

## Version Compatibility Matrix

| Component | Compatible With | Verified |
|-----------|-----------------|----------|
| ArduinoJson 7.4.x | espressif32@6.5.0 / Arduino 2.x | YES -- ESP Component Registry confirms compatibility |
| ArduinoJson 7.4.x | PSRAM allocation | YES -- supports custom allocators |
| WebServer (built-in) | WiFi.mode(WIFI_AP_STA) + ESP-NOW | YES -- proven in display/ota.cpp |
| LV_USE_BMP | LVGL 8.3.11 | YES -- built-in decoder, lv_conf.h flag |
| lv_fs_drv_t | Arduino SD library | YES -- standard adapter pattern, community-proven |
| PySide6 6.10.x | Python 3.11+ | YES -- PyPI confirms |
| Pillow 11.x | Python 3.11+ | YES -- standard compatibility |
| requests 2.32.x | Python 3.11+ | YES -- standard compatibility |

---

## Integration Points with Existing Stack

### SD Card <-> LVGL Integration
The existing `sdcard.cpp` module uses `SD.h` with HSPI. The LVGL FS driver will also use `SD.h`, calling `SD.open()` / `File.read()` etc. Since both use the same `SD` singleton, they share the mounted filesystem. No SPI bus conflict because it is the same bus instance.

### WiFi Config Mode <-> ESP-NOW
The existing `ota.cpp` already sets `WIFI_AP_STA` which keeps ESP-NOW alive. The config upload server will use the identical pattern. ESP-NOW messages (hotkey commands, stats) continue to flow during config upload. The only constraint: both display and bridge must be on the same WiFi channel (channel 1, the SoftAP default).

### JSON Config <-> UI Rebuild
When a new `layout.json` is uploaded via HTTP, the firmware must:
1. Parse with ArduinoJson
2. Destroy existing LVGL tabview and button objects
3. Rebuild UI from new config
4. This is safe because LVGL is single-threaded and the rebuild happens in the main loop

### Desktop Editor <-> ESP32 Upload
The editor generates `layout.json` and BMP icon files, then uploads via HTTP POST to `192.168.4.1` (SoftAP IP). The ESP32's WebServer receives multipart uploads and writes to SD card. Standard HTTP -- no custom protocol needed.

---

## Sources

- [ArduinoJson v7 documentation](https://arduinojson.org/v7/) -- HIGH confidence
- [ArduinoJson v7 release notes](https://arduinojson.org/v7/revisions/) -- v7.4.2 current, HIGH confidence
- [ArduinoJson GitHub](https://github.com/bblanchon/ArduinoJson) -- HIGH confidence
- [LVGL 8.3 File System docs](https://docs.lvgl.io/8.3/overview/file-system.html) -- HIGH confidence
- [LVGL 8.3 BMP decoder](https://docs.lvgl.io/8.3/libs/bmp.html) -- HIGH confidence
- [LVGL Forum: SD card with LVGL v8.3 on ESP32](https://forum.lvgl.io/t/how-do-i-correctly-make-the-sd-card-work-for-image-widgets-on-an-esp32-dev-kit-with-lvgl-v-8-3/9827) -- MEDIUM confidence
- [ESP-IDF WiFi driver docs (v5.5.2)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi.html) -- HIGH confidence
- [ESP-IDF ESP-NOW docs (v5.5.2)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/network/esp_now.html) -- HIGH confidence
- [circuitlabs.net ESP-NOW + WiFi coexistence](https://circuitlabs.net/esp-now-with-wifi-coexistence/) -- MEDIUM confidence
- [Arduino Forum: WebServer vs ESPAsyncWebServer](https://forum.arduino.cc/t/webserver-vs-espasyncwebserver/928293) -- MEDIUM confidence
- [PySide6 on PyPI](https://pypi.org/project/PySide6/) -- v6.10.2, HIGH confidence
- [PySide6 release notes](https://doc.qt.io/qtforpython-6/release_notes/pyside6_release_notes.html) -- HIGH confidence
- [pythonguis.com GUI framework comparison 2026](https://www.pythonguis.com/faq/which-python-gui-library/) -- MEDIUM confidence
- [PyQt6 vs PySide6](https://www.pythonguis.com/faq/pyqt6-vs-pyside6/) -- MEDIUM confidence

---
*Stack research for: v1.1 Configurable Hotkey Layouts (SD card + SoftAP upload + GUI editor)*
*Researched: 2026-02-15*
