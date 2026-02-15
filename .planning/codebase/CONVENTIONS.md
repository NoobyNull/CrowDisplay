# Coding Conventions

**Analysis Date:** 2026-02-12

## Naming Patterns

**Files:**
- C++ source files: `.cpp` (implementation)
- Header files: `.h` (declarations)
- Pattern: `snake_case` for files (e.g., `display_driver.cpp`, `usb_hid.h`)
- Configuration files: `{library}_conf.h` (e.g., `lv_conf.h`)

**Functions:**
- Private functions (static): `snake_case_cb` for callbacks (e.g., `btn_event_cb`, `disp_flush_cb`, `touchpad_read_cb`)
- Public functions: `snake_case` (e.g., `display_init()`, `send_hotkey()`, `lvgl_tick()`)
- Callback convention: suffix with `_cb` for event handlers
- Setup functions: use standard Arduino convention (`setup()`, `loop()`)

**Variables:**
- Global static variables: `snake_case` or descriptive names (e.g., `Keyboard`, `ConsumerControl`, `tft`, `draw_buf`)
- Class member variables: start with underscore (e.g., `_bus_instance`, `_panel_instance`, `_touch_instance`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `SCREEN_WIDTH`, `SCREEN_HEIGHT`, `MOD_CTRL`, `LVGL_BUF_SIZE`)
- Color definitions: `CLR_` prefix in `SCREAMING_SNAKE_CASE` (e.g., `CLR_RED`, `CLR_BLUE`, `CLR_GREEN`)
- Media key definitions: `MEDIA_` prefix (e.g., `MEDIA_PLAY_PAUSE`, `MEDIA_VOL_UP`)
- Local variables: `snake_case` (e.g., `w`, `h`, `x`, `y`, `btn`, `label`)

**Types:**
- Structs: PascalCase (e.g., `Hotkey`, `HotkeyPage`, `LGFX`)
- Type aliases: typically not used; use direct struct names
- Fixed-width integer types: `uint8_t`, `uint16_t`, `uint32_t`, `int` for standard operations

## Code Style

**Formatting:**
- Indentation: 4 spaces (observed consistently)
- Brace style: opening brace on same line (K&R style)
- Line continuation: aligned with opening parenthesis or indented 4 spaces
- Maximum line length: approximately 100 characters (no strict enforced limit detected)

**Linting:**
- No linter configuration found (`.clang-format`, `.clang-tidy` absent)
- Code follows Arduino framework conventions
- PlatformIO project configuration in `platformio.ini`

**Style Examples:**

Static function declaration and implementation:
```cpp
static void btn_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        const Hotkey *hk = (const Hotkey *)lv_event_get_user_data(e);
        if (hk) {
            send_hotkey(*hk);
        }
    }
}
```

Class definition with initialization:
```cpp
class LGFX : public lgfx::LGFX_Device {
public:
    lgfx::Bus_RGB     _bus_instance;
    lgfx::Panel_RGB   _panel_instance;
    lgfx::Light_PWM   _light_instance;
    lgfx::Touch_GT911 _touch_instance;

    LGFX(void) {
        // Configuration setup
    }
};
```

## Import Organization

**Order:**
1. System headers: `#include <Arduino.h>`, `#include <Wire.h>`, `#include <driver/i2c.h>`
2. Third-party library headers: `#include <lvgl.h>`, `#include <LovyanGFX.hpp>`
3. Local project headers: `#include "display_driver.h"`, `#include "usb_hid.h"`

**Pattern from usb_hid.cpp:**
```cpp
#include "usb_hid.h"
#include <Arduino.h>
#include "USB.h"
#include "USBHIDKeyboard.h"
#include "USBHIDConsumerControl.h"
```

**Pattern from display_driver.cpp:**
```cpp
#include "display_driver.h"

#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include <lgfx/v1/platforms/esp32s3/Panel_RGB.hpp>
#include <lgfx/v1/platforms/esp32s3/Bus_RGB.hpp>
#include <driver/i2c.h>
#include <lvgl.h>
```

**Macro definitions:**
- Placed immediately before relevant includes or at top of file
- Example: `#define LGFX_USE_V1` placed before LovyanGFX includes to enable V1 API

## Error Handling

**Patterns:**
- Null pointer checks: `if (hk)` before dereferencing pointers
- Simple validation: check for null before use
- Example from `btn_event_cb`:
  ```cpp
  const Hotkey *hk = (const Hotkey *)lv_event_get_user_data(e);
  if (hk) {
      send_hotkey(*hk);  // Safe to dereference
  }
  ```

- Serial logging for errors and debug info: `Serial.println()`, `Serial.printf()`, `Serial0.println()`
- Hardware initialization errors: logged but no exception handling (embedded context)
- No try-catch blocks used (C++ embedded convention)

## Logging

**Framework:** Serial communication via Arduino Serial library

**Patterns:**
- Debug output: `Serial.println()`, `Serial.printf()` for standard logging
- Alternative serial: `Serial0` for diagnostic output
- Touch debug: periodic polling notification (once every 3 seconds to reduce spam)
- Example from `display_driver.cpp`:
  ```cpp
  Serial0.printf("TOUCH: x=%d y=%d\n", x, y);
  Serial0.println("touch: polling (no touch)");
  ```

- Hotkey feedback: status bar update via `lv_label_set_text_fmt()`
- Initialization logging: each major init step logged (display, LVGL, USB HID)
- Log levels: implicit (no structured levels), messages are informational or diagnostic

## Comments

**When to Comment:**
- File headers: document file purpose, hardware details
- Section headers: use decorative separators (e.g., `// ══════════════════════════════════`)
- Subsection headers: use `// ──` with description
- Configuration values: explain pin mappings, timing values
- Non-obvious logic: explain why, not what
- Hardware-specific details: annotate GPIO pins, I2C addresses

**Format:**
```cpp
/**
 * @file main.cpp
 * Hotkey Display for Elcrow 7.0" CrowPanel (ESP32-S3)
 *
 * Displays a grid of customizable hotkey buttons on the touchscreen.
 * When touched, sends the corresponding keyboard shortcut via USB HID.
 *
 * Features:
 * - 3x4 grid of touch buttons (12 hotkeys per page)
 * - Multiple pages via tab navigation
 * - Visual feedback on press
 * - USB HID keyboard output
 */
```

**JSDoc/Doxygen:**
- Not extensively used in implementation files
- Function prototypes in headers have basic documentation comments
- Struct fields documented inline with `//` comments

**Example from usb_hid.h:**
```cpp
struct Hotkey {
    const char *label;          // Display label on button
    const char *description;    // Tooltip/description
    uint8_t modifiers;          // Modifier key bitmask (MOD_CONSUMER for media keys)
    uint16_t key;               // Key code: ASCII/special for keyboard, usage ID for consumer
    uint32_t color;             // Button color (LVGL format)
    const char *icon;           // LV_SYMBOL for icon (nullable)
};
```

## Function Design

**Size:** Functions range from 2-40 lines; most are focused on single tasks
- Small functions: UI creation helpers (`create_hotkey_button`, `create_hotkey_page`)
- Medium functions: initialization and callbacks (20-30 lines)
- Larger functions acceptable for complex hardware setup (constructor in LGFX class)

**Parameters:**
- Pass by reference for objects: `const HotkeyPage &page`
- Pass by pointer for data: `lv_obj_t *parent`, `lv_event_t *e`
- Pass by value for simple types: `uint8_t count`, `uint32_t color`
- Void parameters explicitly: `void function(void)` in C context

**Return Values:**
- Object pointers: `lv_obj_t *create_hotkey_button()`
- Void for setups/callbacks: callbacks return `void`
- Simple initialization: return `void` with side effects (setup(), loop())

**Example of well-structured function:**
```cpp
static lv_obj_t *create_hotkey_button(lv_obj_t *parent, const Hotkey *hk) {
    // Button container
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_set_size(btn, 170, 90);

    // Style
    lv_obj_set_style_bg_color(btn, lv_color_hex(hk->color), LV_PART_MAIN);
    lv_obj_set_style_radius(btn, 12, LV_PART_MAIN);

    // Event callback
    lv_obj_add_event_cb(btn, btn_event_cb, LV_EVENT_CLICKED, (void *)hk);

    // Layout and children setup...
    return btn;
}
```

## Module Design

**Exports:**
- Header files declare public interface
- Implementation files (`.cpp`) contain static functions for internal use
- Public functions declared in headers with function prototypes
- Global objects are static to limit scope

**Example from display_driver.h:**
```cpp
#ifndef DISPLAY_DRIVER_H
#define DISPLAY_DRIVER_H

#include <Arduino.h>

#define SCREEN_WIDTH  800
#define SCREEN_HEIGHT 480

void display_init(void);
void lvgl_init(void);
void lvgl_tick(void);

#endif /* DISPLAY_DRIVER_H */
```

**Barrel Files:** Not used; each module has its own header

**Include Guards:**
- Pattern: `#ifndef FILENAME_H` / `#define FILENAME_H` / `#endif /* FILENAME_H */`
- Observed in all headers: `usb_hid.h`, `display_driver.h`

**Static Scope:**
- All module-level objects are `static` to prevent global namespace pollution
- Examples: `static LGFX tft;`, `static USBHIDKeyboard Keyboard;`, `static lv_obj_t *tabview;`

---

*Convention analysis: 2026-02-12*
