# Elcrow Display Hotkeys

A complete wireless display control system combining a 7" RGB TFT panel with a bridge device for bidirectional HID communication. Control your PC from the display with custom hotkey buttons, media controls, and app launchers—all configured through an intuitive desktop editor.

## Overview

**Elcrow Display Hotkeys** is a modular system consisting of:

- **Display Firmware** (CrowPanel 7.0" ESP32-S3) - Configurable UI with widgets and display modes
- **Bridge Firmware** (ESP32-S3 DevKitC-1) - USB HID gateway and WiFi relay
- **Desktop Companion** (Qt6 Python) - Configuration editor and deployment tool
- **Protocol** (Binary SOF-framed) - Device-to-device communication over ESP-NOW

### Key Features

✓ **Custom Widgets** - Buttons, text labels, icon displays, stat monitors, analog clocks
✓ **Multiple Display Modes** - Page tabs, clock mode, picture frame slideshow, standby
✓ **Rich Actions** - Hotkeys, media keys, app launch, shell commands, URL open, DDC monitor control
✓ **Wireless Sync** - ESP-NOW link between display and bridge with automatic reconnection
✓ **Secure Config** - Ephemeral WiFi passwords exchanged via trusted USB HID channel
✓ **Live Stats** - CPU, GPU, memory, network, process stats (companion plugin)
✓ **Persistent Storage** - SD card for config, images, fonts

## Hardware

### Display Unit

| Component | Model | Specs |
|-----------|-------|-------|
| **Board** | CrowPanel 7.0" | ESP32-S3, 4MB Flash, 8MB PSRAM |
| **Display** | ILI9488 TFT | 800×480, RGB TFT, 65k colors |
| **Touch** | GT911 | Capacitive, I2C interface |
| **Power** | USB-C (5V) | ~800mA typical |
| **Storage** | SD Card Slot | FAT32 support via SPI |
| **Expansion** | I2C Bus | PCF8575 GPIO expander |

### Bridge Unit (Optional)

| Component | Model | Specs |
|-----------|-------|-------|
| **Board** | ESP32-S3 DevKitC-1 | ESP32-S3, 8MB Flash |
| **USB** | Native USB-OTG | Acts as HID device/composite |
| **Indicator** | NeoPixel LED | Status indication |
| **Power** | USB-C (5V) | ~200mA typical |

### Host PC Requirements

- **OS** - Linux (with systemd+NetworkManager) or macOS
- **USB** - Available USB port (HID device endpoint)
- **Python** - 3.8+ with Qt6 (PySide6)
- **Tools** - `nmcli` (NetworkManager), `ydotool`/`xdotool` (X11/Wayland)

### Bill of Materials (BOM)

**Display Kit**

| Qty | Part | Reference | Cost |
|-----|------|-----------|------|
| 1 | CrowPanel 7" Display | Elcrow | $80-120 |
| 1 | USB-C Cable (data) | - | $5 |
| 1 | Micro SD Card (32GB+) | Kingston/Sandisk | $15 |
| 1 | USB Power Adapter | 5V/2A | $15 |
| **Total** | | | **$115-155** |

**Bridge Kit (Optional)**

| Qty | Part | Reference | Cost |
|-----|------|-----------|------|
| 1 | ESP32-S3 DevKitC-1 | Espressif | $25 |
| 1 | USB-C Cable (data) | - | $5 |
| 1 | USB Power Adapter | 5V/1A | $10 |
| **Total** | | | **$40** |

**Complete System (Display + Bridge + Companion)**

- **Total Hardware Cost**: $155-195
- **Companion Software**: Free (open source)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Host PC (Linux/macOS)                                   │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────┐          ┌──────────────────┐     │
│  │ Companion Editor │          │ Hotkey Companion │     │
│  │   (Qt6 Python)   │          │   (Daemon)       │     │
│  └────────┬─────────┘          └────────┬─────────┘     │
│           │                             │               │
│           │ (Deploy config)    (USB HID reports)        │
│           │                             │               │
│           └─────────────┬───────────────┘               │
│                         │ USB                           │
└─────────────────────────┼───────────────────────────────┘
                          │
                    ┌─────▼────┐
                    │  Bridge   │
                    │ (ESP32-S3)│
                    └─────┬────┘
                          │ ESP-NOW (2.4GHz)
                    ┌─────▼────────┐
                    │   Display    │
                    │ (CrowPanel)  │
                    │  ESP32-S3    │
                    └──────────────┘
                    ┌────────────────┐
                    │  Touch + TFT   │
                    │  GT911 + ILI48 │
                    └────────────────┘
```

### Module Organization

```
├── display/              # CrowPanel firmware (ESP32-S3)
│   ├── main.cpp          # Entry point, initialization
│   ├── ui.cpp            # LVGL UI rendering (widgets, pages, modes)
│   ├── touch.cpp         # GT911 capacitive touch
│   ├── hw_input.cpp      # Rotary encoder, physical buttons
│   ├── espnow_link.cpp   # ESP-NOW wireless communication
│   ├── config_server.cpp # SoftAP WiFi config mode
│   └── ui.h              # UI state and functions
│
├── bridge/               # USB HID bridge firmware (ESP32-S3 DevKit)
│   ├── main.cpp          # USB HID + ESP-NOW relay
│   ├── usb_hid.cpp       # USB endpoint handling
│   └── vendor_report.cpp # Vendor HID report parsing
│
├── companion/            # Host companion application (Python)
│   ├── crowpanel_editor.py      # Qt6 configuration editor
│   ├── hotkey_companion.py       # Daemon for action dispatch
│   ├── config_manager.py         # Configuration state & I/O
│   ├── action_executor.py        # Action execution (hotkey/app/shell)
│   ├── wifi_manager.py           # NetworkManager integration
│   ├── keycode_map.py            # Qt ↔ Arduino keycode translation
│   ├── bridge_device.py          # USB HID device discovery
│   ├── ui/                       # Qt6 UI components
│   │   ├── editor_main.py        # Editor main window
│   │   ├── deploy_dialog.py      # Deployment wizard
│   │   └── (extracted UI modules)
│   └── tests/                    # Test suite (98 tests)
│       ├── test_config.py        # Config round-trip validation
│       ├── test_keycode_map.py   # Keycode mapping tests
│       ├── test_action_executor.py # Action dispatch tests
│       └── README.md             # Test documentation
│
├── shared/               # Shared protocol definitions
│   ├── protocol.h        # Message types, structures, CRC8
│   └── keycodes.h        # Arduino USB HID keycode definitions
│
└── scripts/              # Build and deployment helpers
    └── (helper scripts)
```

### Communication Flows

**Configuration Deployment**

1. User edits config in desktop editor (JSON)
2. Editor validates and builds binary widget layouts
3. Companion connects to display via USB
4. Sends `MSG_CONFIG_MODE` to display
5. Display generates ephemeral 12-char base62 WiFi password
6. Password sent to bridge via ESP-NOW, relayed to companion via USB
7. Companion connects to WiFi AP using relayed password
8. Sends config via HTTP to display
9. Display saves to SD card and reloads

**Button Press to Action**

1. User presses widget button on display
2. Display sends `MSG_BUTTON_PRESS` via ESP-NOW to bridge
3. Bridge relays via USB HID vendor report to companion
4. Companion looks up action in config
5. Executes action (hotkey via ydotool, app launch, etc.)

**Stats/Feedback**

1. Display sends `MSG_STATS_QUERY` to bridge
2. Bridge responds with `MSG_STATS_RESPONSE` containing uptime, RSSI
3. Display renders stats in status bar or stat monitor widgets

## Building

### Prerequisites

- **ESP32 Tools**:
  - PlatformIO CLI: `pip install platformio`
  - esp-idf: Installed by PlatformIO
  - Board support: ESP32-S3 (installed by PlatformIO)

- **Python** (for companion):
  - Python 3.8+
  - PySide6: `pip install PySide6`
  - pyusb: `pip install pyusb`

- **System** (Linux):
  - `ydotool` or `xdotool`: Keyboard/mouse simulation
  - `nmcli`: NetworkManager CLI
  - libusb: USB device access

### Building Display Firmware

```bash
# One-time setup
pio run -e display --target menuconfig  # Optional: configure advanced options

# Build and upload to CrowPanel
pio run -e display                       # Build
pio run -e display --target upload       # Upload via /dev/ttyUSB0
pio run -e display --target monitor      # Open serial monitor (Ctrl-C to exit)
```

### Building Bridge Firmware (Optional)

```bash
# Build and upload to ESP32-S3 DevKit
pio run -e bridge                        # Build
pio run -e bridge --target upload        # Upload via /dev/ttyACM0
pio run -e bridge --target monitor       # Monitor
```

### Installing Companion

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt  # Or manually:
# pip install PySide6 pyusb dbus-next pynvml_utils

# Run editor
python3 -m companion.crowpanel_editor

# Run hotkey daemon (in separate terminal)
python3 -m companion.hotkey_companion
```

### Build Troubleshooting

**Flash size exceeded**
- Disable debugging: Remove `-DCORE_DEBUG_LEVEL=3`
- Check partition scheme: `partitions_4MB_app.csv` reserves 52% for app

**USB upload fails**
- Verify port: `ls /dev/ttyUSB* /dev/ttyACM*`
- Check upload port in `platformio.ini`
- Press BOOT + EN button during upload if stuck

**Missing dependencies**
- Display: `pio lib install` (manages automatically)
- Companion: `pip install -r requirements.txt`

## Usage

### First-Time Setup

1. **Flash Display Firmware**
   ```bash
   pio run -e display --target upload
   ```

2. **Configure Network**
   - Press CONFIG button on display
   - Or action `ACTION_CONFIG_MODE` (e.g., rotary press)
   - Display enters SoftAP mode (blue LED)
   - Creates "crowpanel-XX" WiFi network

3. **Deploy Configuration**
   - Run companion editor: `python3 -m companion.crowpanel_editor`
   - Connect display via USB
   - Click Deploy
   - Enter WiFi network credentials when prompted
   - Configuration uploads automatically

### Creating Custom Layouts

1. **Editor Basics**
   - Drag-and-drop widgets to canvas
   - Right-click for properties (label, action, colors)
   - Use grid for alignment
   - Preview in real-time (if display connected)

2. **Action Types**
   - **Hotkey**: Keyboard shortcut (Ctrl+C, Alt+Tab, etc.)
   - **Media Key**: Play/Pause, Volume, etc.
   - **Launch App**: Firefox, Blender, custom app
   - **Shell Command**: `xdotool type "text"`
   - **Open URL**: Default browser
   - **DDC Control**: Monitor brightness/contrast
   - **Display Actions**: Page nav, clock mode, brightness

3. **Widget Types**
   - **Button**: Clickable action trigger
   - **Label**: Static text display
   - **Value**: Dynamic stat display (CPU, network, etc.)
   - **Clock**: Analog or digital time
   - **Icon**: Image display from SD card

### Configuration File Format

Config is stored as JSON in `config.json` on display SD card:

```json
{
  "version": 2,
  "pages": [
    {
      "name": "Page 1",
      "widgets": [
        {
          "id": "btn_firefox",
          "type": "button",
          "x": 10, "y": 10, "width": 100, "height": 50,
          "label": "Firefox",
          "action": {
            "type": 2,
            "app": "firefox"
          },
          "color": 16711680
        },
        {
          "id": "btn_mute",
          "type": "button",
          "x": 120, "y": 10, "width": 100, "height": 50,
          "label": "Mute",
          "action": {
            "type": 1,
            "code": 226
          }
        }
      ]
    }
  ]
}
```

## Testing

Comprehensive test suite with 98 tests covering configuration, keycode mapping, and action dispatch:

```bash
# Setup test environment
python3 -m venv test_venv
source test_venv/bin/activate
pip install pytest

# Run all tests
pytest companion/tests/ -v

# Run specific suite
pytest companion/tests/test_config.py -v

# Run single test
pytest companion/tests/test_config.py::TestConfigRoundTrip::test_json_serialization -v
```

See `companion/tests/README.md` for detailed test documentation.

## Protocol Reference

### Message Types

| Type | Value | Direction | Purpose |
|------|-------|-----------|---------|
| `MSG_HOTKEY` | 0x01 | Display → Bridge | Keyboard shortcut |
| `MSG_MEDIA_KEY` | 0x02 | Display → Bridge | Media key (play/volume) |
| `MSG_BUTTON_PRESS` | 0x03 | Display → Bridge | Widget button action |
| `MSG_HOTKEY_ACK` | 0x04 | Bridge → Display | Command acknowledgment |
| `MSG_STATS_RESPONSE` | 0x05 | Bridge → Display | System stats reply |
| `MSG_CONFIG_MODE` | 0x06 | Host → Display | Enter config WiFi mode |
| `MSG_CONFIG_CREDENTIALS` | 0x0D | Display → Bridge | Ephemeral WiFi password |

### Message Structure

```
Frame: [SOF:0xAA] [TYPE] [PAYLOAD...] [CRC8]
Length: 1 + 1 + 0-248 + 1 bytes

SOF:     0xAA (frame sync)
TYPE:    Message type (0x01-0x0F)
PAYLOAD: Type-specific data (0-248 bytes)
CRC8:    Polynomial 0x07 over [TYPE + PAYLOAD]
```

### CRC8 Calculation

```cpp
uint8_t crc8(const uint8_t *data, int len) {
    uint8_t crc = 0;
    for (int i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            crc = (crc << 1) ^ (crc & 0x80 ? 0x07 : 0);
        }
    }
    return crc;
}
```

## Pin Configuration

### Display (CrowPanel)

| Pin | Function | Type | Notes |
|-----|----------|------|-------|
| GPIO 3-6 | SPI (TFT) | Output | Display data bus |
| GPIO 8-13 | SPI (Touch/SD) | Bidir | I2C + SPI |
| GPIO 0 | Touch interrupt | Input | GT911 |
| GPIO 46 | User button | Input | Optional physical button |
| GPIO 1,2 | Rotary encoder | Input | Optional rotary |

### Bridge (ESP32-S3 DevKit)

| Pin | Function | Type | Notes |
|-----|----------|------|-------|
| GPIO 19,20 | USB D+/D- | Bidir | Native USB-OTG |
| GPIO 3 | NeoPixel | Output | Status LED (optional) |

## Troubleshooting

### Display won't respond to button presses

1. Check bridge connection: `pio run -e bridge --target monitor`
2. Verify ESP-NOW pairing in logs
3. Restart both devices

### WiFi config AP not appearing

1. Check display logs: `pio run -e display --target monitor`
2. Verify `config_server.cpp` is initialized
3. Look for "ESP-NOW ready" message in bridge log

### Companion can't find display

1. Verify USB cable is data-capable (not charge-only)
2. Check device: `lsusb | grep ESP32`
3. Verify permissions: `sudo usermod -aG dialout,uucp $USER`
4. Restart companion after adding groups

### Actions not executing on host

1. Ensure hotkey companion is running: `ps aux | grep hotkey_companion`
2. Check for permission errors in logs
3. Verify `ydotool` is installed and working: `echo "test" | ydotool type --file -`

## Performance

### Memory Usage

| Component | RAM | Flash | Notes |
|-----------|-----|-------|-------|
| Display Firmware | 66KB / 320KB | 1.6MB / 3.1MB | Includes LVGL + config |
| Bridge Firmware | 45KB / 320KB | 1.0MB / 3.1MB | Minimal USB HID relay |
| Config JSON | ~5-50KB | ~5-50KB | Depends on widget count |

### Response Times

- Button press → PC hotkey: ~50-200ms (ESP-NOW + USB round-trip)
- Config deployment: ~5-10s (including WiFi negotiation)
- Page navigation: <100ms (local display)
- LVGL render: 60 FPS (display refresh rate limited)

## Known Limitations

- **WiFi**: Only tested on 2.4GHz networks (ESP-NOW limitation)
- **Companion**: Linux/macOS only (no Windows due to ydotool)
- **Config UI**: Qt6-based, requires X11 or Wayland display
- **Stats**: Linux host only (uses /proc filesystem)
- **USB**: Single device per host (no multiple displays per PC)

## Future Enhancements

- [ ] Bluetooth mesh for multi-display sync
- [ ] Custom fonts and theme engine
- [ ] Gesture recognition (swipe, long-press)
- [ ] Voice command integration
- [ ] Cloud config sync
- [ ] Raspberry Pi support for bridge
- [ ] Windows companion application

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Submit a pull request

## Support

- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Join GitHub Discussions for questions
- **Documentation**: See `companion/tests/README.md` for testing
- **Protocol**: See `shared/protocol.h` for message definitions

## Credits

- **Display**: CrowPanel 7" by Elcrow Electronics
- **UI Framework**: LVGL v8.3.11
- **Graphics**: LovyanGFX by lovyan03
- **Companion**: Qt6 (PySide6) by Qt Company

## Changelog

### v1.0 (Current)

- Initial release with display + bridge firmware
- Qt6-based companion editor and hotkey daemon
- 98 test suite covering config, keycodes, and actions
- Ephemeral WiFi password security for config mode
- Full stat monitoring integration (CPU, GPU, network, memory)
- Multi-page layouts with drag-and-drop editor
- 17 action types including hotkeys, app launch, DDC control

---

**Last Updated**: 2026-02-21
**Status**: Production Ready
**Maintainers**: Elcrow Display Hotkeys Team
