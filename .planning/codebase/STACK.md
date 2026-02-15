# Technology Stack

**Analysis Date:** 2026-02-12

## Languages

**Primary:**
- C/C++ - Embedded firmware for ESP32-S3, all source code in `src/`

## Runtime

**Environment:**
- ESP32-S3 Dual-core MCU (Xtensa instruction set)
- Arduino Framework with ESP-IDF integration

**Package Manager:**
- PlatformIO - Dependency and build management
- Lockfile: `.pio/` (local dependencies cache)

## Frameworks

**Core:**
- Arduino Framework (Arduino-compatible API) - MCU initialization, Serial I/O, Wire protocol
- LVGL 8.3.11 - GUI library for touchscreen UI, instantiated in `src/display_driver.cpp`
- LovyanGFX 1.1.8 - Display and touch abstraction layer for RGB panel driver

**USB/HID:**
- ESP32-S3 Native USB Stack (Arduino USBHIDKeyboard, USBHIDConsumerControl)
  - USBHIDKeyboard - Keyboard emulation for hotkey transmission in `src/usb_hid.cpp`
  - USBHIDConsumerControl - Media control (play, volume, mute) in `src/usb_hid.cpp`

**Display/Touch:**
- LovyanGFX Bus_RGB - RGB parallel interface driver for 800x480 TFT panel
- LovyanGFX Touch_GT911 - Capacitive touch controller (GT911 I2C device at 0x14)
- I2C driver (ESP-IDF `driver/i2c.h`) - Touch polling on pins GPIO19 (SDA), GPIO20 (SCL)

## Key Dependencies

**Critical:**
- lovyan03/LovyanGFX@^1.1.8 - Display rendering and touch input
  - Provides RGB565 color depth graphics pipeline
  - Touch coordinate mapping for capacitive touch
  - I2C polling interface to GT911 controller
- lvgl/lvgl.git#v8.3.11 - GUI framework
  - Widget system (buttons, tabs, labels)
  - Event handling (button clicks, state changes)
  - Font rendering (Montserrat 12-28pt)
  - Display flush and input callbacks

**Infrastructure:**
- espressif32@6.5.0 - ESP32-S3 platform SDK
  - Dual PSRAM support (OPI mode)
  - USB CDC and HID support
  - GPIO/I2C peripheral drivers

## Configuration

**Environment:**
- `platformio.ini` - Build and deployment configuration
  - Board: `esp32-s3-devkitc-1`
  - USB mode: OTG (device mode, not host)
  - USB CDC on boot for Serial debugging
  - PSRAM: OPI mode enabled

**Build Settings:**
- Compiler: Xtensa-based GCC (via ESP-IDF)
- Memory layout:
  - USB mode disabled by default (flag: `-DARDUINO_USB_MODE=1`)
  - USB mode enabled for this project (flag: `-DARDUINO_USB_MODE=0`)
  - CDC Serial enabled (flag: `-DARDUINO_USB_CDC_ON_BOOT=1`)
  - PSRAM support (flag: `-DBOARD_HAS_PSRAM`)
  - LVGL simple config mode (flag: `-DLV_CONF_INCLUDE_SIMPLE`)
  - Core debug level minimal (flag: `-DCORE_DEBUG_LEVEL=1`)

**Memory Configuration:**
- PSRAM: 8MB OPI mode (for LVGL double buffers)
- Flash: 4MB QIO mode
- Partition: Default ESP32-S3 partition table
- LVGL memory: 96 KB internal RAM (lv_conf.h, line 17)
- LVGL draw buffers: Dual-buffered, allocated in PSRAM (40px strip height per line 127)

## Flash & Upload

**Serial/Debug:**
- Monitor speed: 115200 baud
- Upload speed: 921600 baud
- CDC Serial: Both Serial (GPIO43-44) and Serial0 (USB-CDC) available

**Memory Map:**
```
Flash (4MB):
  - Bootloader + partitions
  - App firmware
  - Sketch data
  - LittleFS/SPIFFS if used (not present in this build)

PSRAM (8MB):
  - LVGL draw buffer 1: ~64KB (800*40 RGB565)
  - LVGL draw buffer 2: ~64KB (800*40 RGB565)
  - Remaining available for runtime allocations
```

## Platform Requirements

**Development:**
- PlatformIO CLI or VS Code PlatformIO extension
- ESP32-S3 DevKit board or compatible Elcrow CrowPanel 7.0"
- USB-C cable for programming and Serial debugging
- No external dependencies beyond platformio.ini lib_deps

**Production:**
- Elcrow CrowPanel 7.0" (ESP32-S3 SoM)
- 800x480 RGB TFT panel (integrated)
- GT911 capacitive touch controller (integrated, I2C 0x14)
- USB power or external 5V supply
- Deployment target: Direct flash to ESP32-S3 via PlatformIO

---

*Stack analysis: 2026-02-12*
