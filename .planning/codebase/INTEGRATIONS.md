# External Integrations

**Analysis Date:** 2026-02-12

## Hardware Interfaces

**Display Panel:**
- Elcrow CrowPanel 7.0" (WZ8048C070)
  - Type: 800x480 RGB TFT parallel interface
  - Driver: LovyanGFX LGFX class in `src/display_driver.cpp`
  - GPIO pins: 16 data lines (D0-D15: pins 15,7,6,5,4,9,46,3,8,16,1,14,21,47,48,45)
  - Control: HSYNC (39), VSYNC (40), ENABLE (41), PCLK (0)
  - Pixel clock: 12MHz
  - Backlight: PWM on GPIO2

**Touch Controller:**
- GT911 Capacitive Touch IC
  - Communication: I2C bus (400kHz)
  - I2C address: 0x14
  - SDA pin: GPIO19
  - SCL pin: GPIO20
  - Reset pin: GPIO38
  - Interrupt: Not used (polling mode)
  - Calibration: X (0-799), Y (0-479)
  - Driver: LovyanGFX Touch_GT911 class in `src/display_driver.cpp` lines 99-116

## USB Interfaces

**USB HID Keyboard:**
- Device: ESP32-S3 native USB controller (OTG device mode)
- Protocol: USB HID Keyboard (standard HID report)
- Implementation: `src/usb_hid.cpp` using Arduino USBHIDKeyboard library
- Supported keys: All standard ASCII + special keys (F1-F12, arrow keys, etc.)
- Modifier support: Ctrl, Shift, Alt, GUI (Windows/Command)
- Initialization: USB.begin() after keyboard and consumer control setup (line 14)

**USB HID Consumer Control:**
- Device: ESP32-S3 native USB controller (same port)
- Protocol: USB HID Consumer Control (media keys)
- Implementation: `src/usb_hid.cpp` using Arduino USBHIDConsumerControl library
- Supported controls: Play/Pause, Next, Previous, Volume Up/Down, Mute
- Usage IDs: MEDIA_PLAY_PAUSE (0xCD), MEDIA_NEXT (0xB5), MEDIA_PREV (0xB6), MEDIA_VOL_UP (0xE9), MEDIA_VOL_DOWN (0xEA), MEDIA_MUTE (0xE2)

**USB Serial Debug (CDC):**
- Type: USB Communications Device Class (CDC)
- Enabled: Yes, via `-DARDUINO_USB_CDC_ON_BOOT=1` flag
- Purpose: Serial debug output on Serial0
- Speed: 115200 baud (configured in platformio.ini line 29)
- Output: Uses Serial0.print() for debug logging (e.g., line 237 main.cpp)

## Data Storage

**Databases:**
- None - All configuration is compile-time in `src/main.cpp`

**File Storage:**
- None - No filesystem or persistent storage used

**Caching:**
- None - No caching layer

**Hotkey Configuration Storage:**
- Compile-time static arrays in `src/main.cpp`:
  - Page 1: General shortcuts (Copy, Paste, Cut, etc.) - 12 hotkeys, lines 38-51
  - Page 2: Window management (Desktop, Task View, Lock, etc.) - 12 hotkeys, lines 54-67
  - Page 3: Media & Development (Play/Pause, Terminal, Debug, etc.) - 12 hotkeys, lines 70-83
- No runtime modification or persistence

## Authentication & Identity

**Auth Provider:**
- None - Device is locally controlled only

**Security Model:**
- Physical touchscreen access only
- No network connectivity
- No user authentication required
- USB HID operates as unprivileged input device on host OS

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service

**Logs:**
- Serial output via Serial (USB CDC) at 115200 baud
- Debug levels:
  - Touch events: Logged to Serial0 on each touch (line 151 display_driver.cpp)
  - Hotkey sends: Logged with label and description (line 33 usb_hid.cpp)
  - Initialization steps: Serial.println() messages during setup (lines 237-265 main.cpp)
  - I2C device scan: Scan results printed to Serial0 (lines 256-264 main.cpp)

**Performance Monitoring:**
- LVGL_DISP_DEF_REFR_PERIOD: 16ms refresh (lv_conf.h line 22)
- LVGL_INDEV_DEF_READ_PERIOD: 30ms touch polling (lv_conf.h line 23)
- No profiling or metrics collection

## CI/CD & Deployment

**Hosting:**
- Target: Elcrow CrowPanel 7.0" (ESP32-S3 hardare)
- Deployment: Direct firmware flash via PlatformIO

**CI Pipeline:**
- None - No automated CI configured

**Build Process:**
- Tool: PlatformIO
- Command: `platformio run -e elcrow_7inch` (builds and links firmware)
- Upload: `platformio run -e elcrow_7inch --target upload` (programs ESP32-S3 via USB)

## Webhooks & Callbacks

**Incoming:**
- None - No network connectivity

**Outgoing:**
- USB HID keyboard reports sent to host OS on button click
  - Triggered by LVGL LV_EVENT_CLICKED in `src/main.cpp` line 109
  - Handler: `btn_event_cb()` calls `send_hotkey()` (lines 107-119)
  - Delivery: USB HID keyboard or consumer control report within 50ms

**LVGL Callbacks:**
- Display flush callback: `disp_flush_cb()` in `src/display_driver.cpp` lines 130-140
  - Triggered: LVGL timer at 16ms intervals
  - Action: Writes pixel data to TFT via LovyanGFX
- Touch read callback: `touchpad_read_cb()` in `src/display_driver.cpp` lines 145-160
  - Triggered: LVGL input device handler at 30ms intervals
  - Action: Polls GT911 via I2C for touch coordinates, updates LVGL input state

## Network Connectivity

**Network:**
- None - Device is standalone

**Wireless:**
- None - No WiFi or Bluetooth

**Internet Access:**
- None - No external API calls

---

*Integration audit: 2026-02-12*
