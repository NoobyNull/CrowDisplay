# Feature Landscape: Configurable Hotkey Layouts

**Domain:** Configurable hotkey display with SD card storage, WiFi upload, and desktop GUI editor
**Researched:** 2026-02-15
**Confidence:** MEDIUM-HIGH
**Scope:** NEW features only -- config format, WiFi upload UX, GUI editor. Existing features (grid UI, stats header, power states, ESP-NOW transport) are already built.

## Table Stakes

Features users expect from a configurable macropad. Missing any of these means the config system feels incomplete or broken.

### Config File Format

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-button label text | Every macropad shows what each button does. DuckyPad, FreeTouchDeck, Stream Deck all have labels. | LOW | Already in Hotkey struct as `label` field. Must be in config. Max ~20 chars for readability on 170x90px buttons. |
| Per-button key binding (modifier + keycode) | The entire point of a macropad. Every competitor supports modifier+key combos. | LOW | Already in Hotkey struct: `modifiers` bitmask + `keycode`. Config must store both. |
| Per-button color | Current firmware already has per-button colors. Removing this in config = regression. Stream Deck has per-button icon colors. | LOW | Store as 24-bit hex (e.g. `"color": "3498DB"`). Already 16 colors defined in palette. |
| Per-button icon (from built-in set) | Current firmware already shows LVGL symbols on each button. Must persist across config changes. | LOW | Store as string name mapping to LV_SYMBOL constants. Finite set (~40 LVGL symbols). |
| Media key support | Current firmware supports consumer control codes (play, volume, mute). Config must distinguish keyboard vs media keys. | LOW | Add `type` field: `"keyboard"` or `"media"`. Media keys store `consumer_code` instead of modifier+keycode. |
| Per-button description/subtitle | Current firmware shows shortcut description below label (e.g. "Ctrl+C"). Useful for learning. | LOW | Optional field. If omitted, auto-generate from modifier+keycode. |
| Variable number of pages | Every competitor supports multiple pages/profiles. Current firmware has 3 hardcoded. Config must allow 1-N pages. | LOW | Top-level array of page objects. DuckyPad supports 64 profiles. Reasonable limit: 16 pages (memory). |
| Page names/labels | Tab bar shows page names. Stream Deck shows profile names. Essential for navigation. | LOW | String field per page, shown in LVGL tabview tab buttons. |
| Config survives power cycles | Nobody reconfigures on every boot. DuckyPad stores on SD. Stream Deck stores in desktop app database. FreeTouchDeck stores in SPIFFS. | MEDIUM | SD card is the right choice here -- already mounted, large capacity, removable for backup. JSON file at `/config/layout.json`. Fallback to built-in default if file missing/corrupt. |
| Human-readable config format | DuckyPad uses plain text. Adafruit Macropad uses Python dicts. Stream Deck profiles are JSON. Users expect to be able to hand-edit. | LOW | JSON. Not binary, not MessagePack, not CBOR. ArduinoJson v7 handles parsing on ESP32 with PSRAM. Human-editable as backup to GUI editor. |
| Default layout on first boot | Device must work out of box with no SD card or empty SD card. Current 3-page Hyprland layout becomes the built-in default. | LOW | Compile current hotkey arrays as fallback. If SD config missing, use defaults. Write defaults to SD on first boot so user has a starting template. |

### WiFi Config Upload

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| SoftAP mode (no router needed) | OTA module already uses this pattern. Device creates its own WiFi network. No home network config required. FreeTouchDeck uses same approach. | LOW | Already implemented in `ota.cpp` -- `WiFi.softAP("CrowPanel-OTA", "crowpanel")`. Reuse this infrastructure. |
| Web page with file upload form | OTA already has multipart upload form at `http://192.168.4.1`. Same pattern for config. Users expect browser-based upload. | LOW | Add `/config` endpoint to existing WebServer. Multipart form with file input accepting `.json`. |
| Upload confirmation/validation | User needs to know if upload succeeded. FreeTouchDeck web configurator shows save confirmation. | MEDIUM | Validate JSON on receive before writing to SD. Return success/error HTTP response with human-readable message. Show result on display too. |
| Display shows WiFi SSID and IP | OTA screen already does this. User needs to know what WiFi to connect to. | LOW | Already built -- `show_ota_screen()` displays SSID, password, IP. Extend to show config upload URL too. |

### Desktop GUI Editor

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Visual button grid matching device layout | Stream Deck app shows exact grid layout. User sees what they are designing. Essential for spatial awareness. | MEDIUM | GTK4 grid widget or drawing area. Show 4xN button grid per page with accurate proportions matching 800x480 screen (minus header/tabs). |
| Edit button properties (label, shortcut, color) | Click a button in the editor, edit its properties in a sidebar panel. Stream Deck, Macro Deck, FreeTouchDeck all do this. | MEDIUM | Properties panel: text entry for label, dropdown/entry for key combo, color picker. Standard form layout. |
| Page management (add/remove/rename/reorder) | Stream Deck has page navigation. DuckyPad has up to 64 profiles. Users need to organize their layouts. | MEDIUM | Tab bar or list view of pages with add/remove buttons. Drag to reorder (or up/down arrows as simpler alternative). |
| Export to JSON file | Users need to get the config file to upload via WiFi. Stream Deck exports .streamDeckProfile files. | LOW | "Save As" dialog, writes JSON to local filesystem. User then uploads via browser to device. |
| Import/load existing config | Users need to edit what is already on the device. Stream Deck app reads current device config. | LOW | "Open" dialog, loads JSON file into editor. Requirements COMP-06 specifies reading config from device too. |
| Icon picker from available set | Users should not memorize LVGL symbol names. Show a visual picker grid of available icons. | MEDIUM | Grid of ~40 LVGL symbols with names. Click to select. Similar to emoji pickers. |

## Differentiators

Features that elevate this beyond "yet another macropad config tool." Not expected but genuinely valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Live preview push (edit -> instant update on device) | Stream Deck's killer UX: edit a button, see it change on device in real time. No export/upload/reboot cycle. Most DIY alternatives require file transfer + reboot. | HIGH | Requires companion app integration: GUI editor saves JSON -> companion pushes via HID vendor reports -> bridge relays to display -> display hot-reloads UI. The chunked config transfer protocol (CONF-04) enables this. Eliminates WiFi upload step entirely for users with bridge connected. |
| Config upload via companion app (no WiFi needed) | Companion app already has USB HID path to bridge. Why make user connect to WiFi AP when the wire is already there? WiFi upload becomes a fallback, not primary path. | MEDIUM | Route JSON config through existing HID vendor report channel: companion -> bridge (USB) -> display (ESP-NOW/UART). Chunked transfer handles size. This is the "golden path" UX. |
| Configurable button sizes (1x1, 2x1, 2x2) | 7" screen (800x480) has enough real estate for variable-size buttons. A large "MUTE" button for video calls, a 2x1 "Terminal" button. No DIY macropad does this well. | HIGH | Each button gets `width` and `height` in grid units. LVGL flex layout handles variable sizing. Grid packing algorithm needed. GUI editor needs drag-to-resize or size dropdown. Config schema: `"size": [2, 1]` for 2-wide, 1-tall. |
| Color picker with palette presets | Current firmware has 16 named colors. Let users pick from palette OR enter custom hex. Most competitors only offer preset colors. | LOW | Color picker widget in GTK4 (GtkColorChooserDialog). Save as hex string. Offer palette presets matching firmware defaults. |
| Auto-backup on config change | DuckyPad creates local backup every save. SD card configs should be backed up before overwriting. | LOW | Before writing new config, copy `layout.json` to `layout.json.bak`. Simple insurance against corrupted uploads. |
| Config versioning in schema | Future config format changes need graceful migration. Stream Deck profiles have a Version field. | LOW | Add `"version": 1` to config root. Parser checks version, migrates or rejects incompatible configs. Cheap insurance. |
| Freeform button placement (pixel-level) | Instead of grid snap, allow buttons anywhere on screen. No competitor does this for macropads. Ultimate flexibility. | VERY HIGH | Requires abandoning grid layout for absolute positioning. LVGL supports it but massively complicates overlap detection, touch hit areas, and GUI editor UX. Only pursue if grid-snapped variable sizes prove insufficient. |
| Direct WiFi upload from GUI editor | GUI editor has a "Deploy to Device" button that connects to CrowPanel SoftAP and HTTP POSTs the config. No browser needed. | MEDIUM | Python `requests` library or `urllib`. Auto-detect device IP (always 192.168.4.1 for SoftAP). Button in GUI toolbar. Requires device to be in config upload mode. |
| Keyboard shortcut recorder in GUI editor | Instead of manually entering "Ctrl+Shift+S", press the key combo and the editor captures it. Stream Deck app does this. | MEDIUM | Platform-specific key capture. On Linux/X11: `python-xlib`. On Wayland: more complex (may need portal). GTK4 key event handlers work for basic combos. Worth doing for keyboard shortcuts, skip for media keys. |

## Anti-Features

Features that seem useful but should be explicitly avoided. Each has a concrete reason and a better alternative.

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Web-based config editor on ESP32 | FreeTouchDeck does this. No app install needed. | ESP32 web editor is severely limited: tiny screen for editing, JavaScript + HTML eat flash, WiFi conflicts with ESP-NOW, poor UX compared to desktop app. CrowPanel already has memory pressure with LVGL + 800x480 display buffers. FreeTouchDeck's web editor is universally criticized as clunky. | Desktop GUI editor (Python/GTK4). Richer UI, no ESP32 resource cost. Web upload form is only for file transfer, not editing. |
| YAML config format | "More human-readable than JSON." | No YAML parser for ESP32/Arduino. ArduinoJson supports JSON natively with streaming parser. YAML adds a dependency with no embedded ecosystem support. | JSON. ArduinoJson v7 is battle-tested on ESP32, supports PSRAM allocation, streaming parse from SD card. |
| TOML config format | "Better than JSON for config files." | Same problem as YAML -- no maintained ESP32 parser. ArduinoJson is the standard. | JSON with ArduinoJson. |
| Binary config format (MessagePack/CBOR) | "Smaller, faster parsing." | Not human-editable. Config files should be inspectable and hand-editable as a debugging escape hatch. Binary complicates the GUI editor (needs serializer/deserializer). ArduinoJson streaming parse is fast enough for a config file loaded once at boot. | JSON. The config file is ~2-10 KB. Parsing speed is irrelevant for a one-time boot load. |
| DuckyScript macro language | DuckyPad supports it. Powerful scripting with loops and variables. | Requires implementing a script interpreter on ESP32. Massive scope creep. Our device sends single keystrokes, not automation sequences. DuckyScript is for penetration testing tools, not desktop macropads. | Single key binding per button (modifier + keycode OR consumer code). Companion app on PC handles complex automation if needed. |
| Per-button custom bitmap images | "I want my app logo on each button." | 36 buttons x custom BMP = significant PSRAM/flash usage. Image decoding is slow on ESP32. SD card I/O for 36 images adds boot time. Image management in GUI editor adds complexity. LVGL image widget needs decoded bitmap in RAM. | LVGL built-in symbol font (~40 icons). These are vector-rendered, resolution-independent, zero decode time. Custom bitmaps can be a v2 feature stored on SD card with strict size limits (32x32 indexed color). |
| Electron-based GUI editor | "Cross-platform, web tech." | 200+ MB download for a config editor. Massive dependency. Overkill for a form-based editor. The user base is Linux power users who already have GTK. | Python + GTK4 (PyGObject). ~5 MB total. Native look and feel on Linux. Already used in companion app stack. |
| Config sync via cloud | "Sync layouts across devices." | No cloud infra to maintain. Privacy concerns. Unnecessary complexity for a single-device macropad. | JSON file on disk. User can manually copy/backup. Version control (git) works perfectly for JSON config files. |
| Real-time drag-and-drop grid editor with physics | "Drag buttons around freely like a design tool." | GTK4 drag-and-drop for widget reordering is poorly documented and fragile (per PyGObject community issues). Massive implementation effort for minimal UX gain over click-to-select + property panel. | Click button in grid -> edit in property panel. Reorder via move up/down buttons or cut/paste. This is how most hardware config tools work (QMK Configurator, VIA). |

## Feature Dependencies

```
[SD Card Driver] (exists: sdcard.cpp)
    |
    v
[JSON Config Schema Definition]
    |-- feeds --> [Config Parser on ESP32] (ArduinoJson, reads from SD)
    |-- feeds --> [GUI Editor JSON export]
    |-- feeds --> [Default Config Generator] (writes factory defaults to SD)
    |
    v
[Config Parser on ESP32]
    |-- feeds --> [Dynamic UI Builder] (replaces hardcoded Hotkey arrays)
    |                |
    |                v
    |           [LVGL Tabview + Button Grid] (exists, needs refactor)
    |
    v
[SoftAP WiFi Upload] (extends existing ota.cpp infrastructure)
    |-- requires --> [WebServer with /config endpoint]
    |-- requires --> [JSON validation before SD write]
    |-- requires --> [UI reload after config change]
    |
    v
[Desktop GUI Editor] (Python/GTK4)
    |-- reads/writes --> [JSON config files]
    |-- optionally --> [Direct HTTP upload to device SoftAP]
    |
    v
[Companion App Integration] (future differentiator)
    |-- pushes config --> [HID vendor report channel] (exists)
    |-- enables --> [Live preview without WiFi]
```

### Key Dependency Notes

- **SD card driver already exists** (`sdcard.cpp`): read/write/exists functions are ready. No new hardware work needed.
- **SoftAP + WebServer already exists** (`ota.cpp`): reuse `WiFi.softAP()` and `WebServer` infrastructure. Add config upload endpoints alongside OTA.
- **ESP-NOW coexistence is solved**: OTA already uses `WIFI_AP_STA` mode to keep ESP-NOW alive during SoftAP. Config upload inherits this.
- **Config parser must run before UI creation**: `create_ui()` currently reads hardcoded arrays. Must refactor to read from parsed config struct.
- **GUI editor is independent of firmware**: Can develop and test with JSON files alone, no device needed.

## Config Schema Design

Based on analysis of Stream Deck profiles (JSON with per-button objects keyed by position), DuckyPad (plain text scripts per profile on SD), Adafruit Macropad (Python dicts with tuples), and FreeTouchDeck (JSON via ArduinoJson), the recommended schema:

```json
{
  "version": 1,
  "pages": [
    {
      "name": "Windows",
      "buttons": [
        {
          "label": "WS 1",
          "description": "Super+1",
          "type": "keyboard",
          "modifiers": ["gui"],
          "keycode": "1",
          "color": "3498DB",
          "icon": "home"
        },
        {
          "label": "Play",
          "description": "Play/Pause",
          "type": "media",
          "consumer_code": "0x00CD",
          "color": "7B1FA2",
          "icon": "play"
        }
      ]
    }
  ]
}
```

### Schema Design Rationale

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| Modifiers as string array `["ctrl", "shift"]` | Human-readable, no bitmask math for hand-editors | Bitmask integer `0x03` -- harder to hand-edit |
| Keycode as string `"1"` or `"left_arrow"` | Readable. Parser maps to USB HID codes. | Raw HID code `0x1E` -- opaque |
| Color as 6-char hex string `"3498DB"` | Standard web color format. Easy for GUI color picker. | Named colors -- limits palette |
| Icon as string name `"home"` | Maps to `LV_SYMBOL_HOME`. Finite known set. | Unicode codepoint -- harder to validate |
| Consumer code as hex string `"0x00CD"` | Standard USB HID usage table format | Decimal integer -- less recognizable |
| Fixed 4-column grid (v1) | Matches current 170px button width on 800px screen. Simplifies layout math. | Variable columns per page -- deferred to v2 |
| Max 12 buttons per page (v1) | Current 4x3 grid with stats header visible. Well-tested layout. | Variable count -- deferred to variable sizes feature |

### Essential Config Fields (v1)

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `version` | integer | YES | 1 |
| `pages[].name` | string | YES | -- |
| `pages[].buttons[].label` | string | YES | -- |
| `pages[].buttons[].type` | string | YES | `"keyboard"` |
| `pages[].buttons[].modifiers` | string[] | NO | `[]` |
| `pages[].buttons[].keycode` | string | conditional | -- (required if type=keyboard) |
| `pages[].buttons[].consumer_code` | string | conditional | -- (required if type=media) |
| `pages[].buttons[].color` | string | NO | `"3498DB"` |
| `pages[].buttons[].icon` | string | NO | `"keyboard"` |
| `pages[].buttons[].description` | string | NO | auto-generated from binding |

### Nice-to-Have Config Fields (v2)

| Field | Type | Purpose |
|-------|------|---------|
| `pages[].buttons[].size` | `[w, h]` | Variable button sizes in grid units (e.g. `[2, 1]`) |
| `pages[].buttons[].row`, `col` | integer | Explicit grid position instead of sequential |
| `pages[].columns` | integer | Variable column count per page |
| `pages[].buttons[].image` | string | SD card path to custom bitmap |
| `global.brightness_default` | integer | Startup brightness level |
| `global.idle_timeout_ms` | integer | Custom dim timeout |

## GUI Editor UX Patterns

Analysis of existing macropad editors reveals two dominant patterns:

### Pattern A: Click-to-Select + Property Panel (RECOMMENDED)

Used by: QMK Configurator, VIA, Stream Deck app, Macro Deck

- Grid of buttons displayed on left/center
- Click a button to select it (highlight border)
- Right panel shows editable properties (label, shortcut, color, icon)
- Changes reflected immediately in the grid preview
- Page tabs along the top with add/remove buttons

**Why this pattern:** Simplest to implement. GTK4 has all needed widgets (Grid, Entry, ColorButton, FlowBox for icon picker). No drag-and-drop complexity. Proven UX from QMK/VIA which target the exact same user base (keyboard enthusiasts).

### Pattern B: Drag-and-Drop Canvas (NOT recommended for v1)

Used by: ssebs Macro Pad editor (Go/Fyne), some game UI editors

- Buttons are draggable on a canvas
- Freeform placement or snap-to-grid
- Resize handles on buttons

**Why not for v1:** GTK4 widget drag-and-drop is poorly supported and documented (community GitHub issues confirm this). Implementation effort is 5-10x vs click-to-select. Minimal UX benefit for a fixed-grid layout. Revisit only if variable button sizes are implemented.

### Recommended Editor Layout

```
+------------------------------------------+
| [File] [Deploy]              CrowPanel   |
+------------------------------------------+
| Pages:    |                    |  Props:  |
| [+ Add]   |   +---------+     | Label:   |
| > Windows |   | WS 1    |     | [______] |
|   System  |   | Super+1 |     |          |
|   Media   |   +---------+     | Shortcut:|
|           |   | WS 2    |...  | [______] |
|           |   | Super+2 |     |          |
|           |   +---------+     | Color:   |
|           |   | ...     |     | [picker] |
|           |                    |          |
|           |   4x3 grid         | Icon:    |
|           |   preview          | [picker] |
+------------------------------------------+
```

## MVP Recommendation

### Build First (Minimum Viable Config)

1. **JSON config schema** with version, pages, buttons (essential fields only)
2. **SD card config parser** on ESP32 using ArduinoJson v7 -- load at boot, fall back to compiled defaults
3. **Dynamic UI builder** refactoring `create_ui()` to read from parsed config instead of hardcoded arrays
4. **SoftAP config upload** extending existing OTA web server with `/config` endpoint for JSON file upload
5. **Basic GUI editor** in Python/GTK4 with click-to-select grid, property panel, page management, save/load JSON

### Build Second (Polish)

6. **Config validation** on both ESP32 (reject malformed JSON) and GUI editor (schema validation before save)
7. **Icon picker** popup in GUI editor
8. **Keyboard shortcut recorder** in GUI editor
9. **Direct deploy** from GUI editor to device via HTTP POST to SoftAP

### Defer (v2)

10. **Variable button sizes** (requires grid packing algorithm, GUI resize handles)
11. **Custom bitmap icons** from SD card
12. **Live preview push** via companion app HID channel
13. **Per-app profile switching**

## Estimated Config File Size

| Layout | Pages | Buttons | Approx JSON Size |
|--------|-------|---------|-------------------|
| Minimal (1 page, 6 buttons) | 1 | 6 | ~800 bytes |
| Current default (3 pages, 36 buttons) | 3 | 36 | ~5 KB |
| Power user (8 pages, 96 buttons) | 8 | 96 | ~13 KB |
| Maximum reasonable (16 pages, 192 buttons) | 16 | 192 | ~26 KB |

All sizes well within ESP32 PSRAM capacity (~8 MB) and SD card capacity. ArduinoJson streaming parse can handle 26 KB trivially. No chunking needed for SD card reads.

Note: chunked transfer (CONF-04) is only needed for the ESP-NOW/UART config push path (250-byte payload limit), not for SD card loading. WiFi HTTP upload handles arbitrary file sizes natively.

## Sources

- [Stream Deck SDK Profiles](https://docs.elgato.com/streamdeck/sdk/guides/profiles/) -- Profile/layout format reference
- [Stream Deck SDK Manifest](https://docs.elgato.com/streamdeck/sdk/references/manifest/) -- JSON manifest structure
- [streamdeck-config profile breakdown](https://github.com/jameswhite/streamdeck-config/blob/main/doc/breaking-down-profiles.md) -- Detailed JSON structure analysis
- [Elgato Stream Deck Schemas](https://github.com/elgatosf/schemas) -- Official JSON schemas
- [FreeTouchDeck (GitHub)](https://github.com/DustinWatts/FreeTouchDeck) -- ESP32 macropad with web configurator, ArduinoJson config
- [FreeTouchDeck (Hackaday.io)](https://hackaday.io/project/175827-freetouchdeck) -- Project overview and configurator details
- [DuckyPad Pro](https://dekunukem.github.io/duckyPad-Pro/) -- SD card profile storage, duckyScript config
- [DuckyPad Getting Started](https://github.com/dekuNukem/duckyPad/blob/master/getting_started.md) -- SD card file structure
- [Adafruit MACROPAD Custom Configurations](https://learn.adafruit.com/macropad-hotkeys/custom-configurations) -- Python dict config format with tuples
- [InfiniteDeck (Electromaker)](https://www.electromaker.io/project/view/streamdeck-alternative-infinitedeck) -- SD card macro storage
- [ssebs Macro Pad GUI Editor](https://ssebs.com/blog/mmpguieditor/) -- Drag-and-drop config editor implementation
- [ArduinoJson Memory Usage](https://arduinojson.org/v7/how-to/reduce-memory-usage/) -- Streaming parse, PSRAM allocation
- [ArduinoJson PSRAM on ESP32](https://arduinojson.org/v6/how-to/use-external-ram-on-esp32/) -- External RAM usage
- [ESP32 SoftAP Tutorial (Espressif)](https://developer.espressif.com/blog/2025/04/soft-ap-tutorial/) -- Official SoftAP guide
- [ESP32 Access Point Web Server](https://randomnerdtutorials.com/esp32-access-point-ap-web-server/) -- SoftAP + HTTP upload pattern
- [PyGObject GTK4 Drag and Drop](https://pygobject.gnome.org/tutorials/gtk4/drag-and-drop.html) -- DnD challenges in GTK4
- [PyGObject GTK4 Layout Containers](https://pygobject.gnome.org/tutorials/gtk4/layout-widgets.html) -- Grid and box layouts
- [Macro Deck](https://macro-deck.app/) -- Open source macro board with profile/button config
- [streamdeckd (Go)](https://pkg.go.dev/github.com/unix-streamdeck/streamdeckd) -- Open source Stream Deck JSON config

---
*Feature research for: Configurable hotkey layouts (SD card + WiFi upload + GUI editor)*
*Researched: 2026-02-15*
