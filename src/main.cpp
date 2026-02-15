#include <Arduino.h>
#include <Wire.h>
#include <LovyanGFX.hpp>
#include <lgfx/v1/platforms/esp32s3/Panel_RGB.hpp>
#include <lgfx/v1/platforms/esp32s3/Bus_RGB.hpp>
#include <lvgl.h>
#include <PCA9557.h>

#ifdef USE_BLE
  #include <BleKeyboard.h>
#else
  #include <USB.h>
  #include <USBHIDKeyboard.h>
#endif

// ============================================================
// LovyanGFX Display — CrowPanel 7.0" (800x480 RGB565)
// ============================================================
class LGFX : public lgfx::LGFX_Device {
public:
  lgfx::Bus_RGB   _bus_instance;
  lgfx::Panel_RGB _panel_instance;
  lgfx::Light_PWM _light_instance;

  LGFX(void) {
    {
      auto cfg = _panel_instance.config();
      cfg.memory_width  = 800;
      cfg.memory_height = 480;
      cfg.panel_width   = 800;
      cfg.panel_height  = 480;
      cfg.offset_x = 0;
      cfg.offset_y = 0;
      _panel_instance.config(cfg);
    }
    {
      auto cfg = _bus_instance.config();
      cfg.panel = &_panel_instance;
      cfg.pin_d0  = GPIO_NUM_15; cfg.pin_d1  = GPIO_NUM_7;
      cfg.pin_d2  = GPIO_NUM_6;  cfg.pin_d3  = GPIO_NUM_5;
      cfg.pin_d4  = GPIO_NUM_4;  cfg.pin_d5  = GPIO_NUM_9;
      cfg.pin_d6  = GPIO_NUM_46; cfg.pin_d7  = GPIO_NUM_3;
      cfg.pin_d8  = GPIO_NUM_8;  cfg.pin_d9  = GPIO_NUM_16;
      cfg.pin_d10 = GPIO_NUM_1;  cfg.pin_d11 = GPIO_NUM_14;
      cfg.pin_d12 = GPIO_NUM_21; cfg.pin_d13 = GPIO_NUM_47;
      cfg.pin_d14 = GPIO_NUM_48; cfg.pin_d15 = GPIO_NUM_45;
      cfg.pin_henable = GPIO_NUM_41;
      cfg.pin_vsync   = GPIO_NUM_40;
      cfg.pin_hsync   = GPIO_NUM_39;
      cfg.pin_pclk    = GPIO_NUM_0;
      cfg.freq_write  = 12000000;
      cfg.hsync_polarity    = 0; cfg.hsync_front_porch = 40;
      cfg.hsync_pulse_width = 48; cfg.hsync_back_porch = 40;
      cfg.vsync_polarity    = 0; cfg.vsync_front_porch = 1;
      cfg.vsync_pulse_width = 31; cfg.vsync_back_porch = 13;
      cfg.pclk_active_neg = 1;
      cfg.de_idle_high    = 0;
      cfg.pclk_idle_high  = 0;
      _bus_instance.config(cfg);
      _panel_instance.setBus(&_bus_instance);
    }
    {
      auto cfg = _light_instance.config();
      cfg.pin_bl = GPIO_NUM_2;
      _light_instance.config(cfg);
      _panel_instance.light(&_light_instance);
    }
    setPanel(&_panel_instance);
  }
};

static LGFX lcd;
static PCA9557 ioExpander;

#ifdef USE_BLE
  static BleKeyboard bleKbd("HotkeyPad", "Elcrow", 100);
#else
  static USBHIDKeyboard usbKbd;
#endif

// ============================================================
// GT911 Touch — direct I2C via Wire
// ============================================================
static uint8_t gt911_addr = 0;

static void gt911_discover() {
  uint8_t addrs[] = {0x5D, 0x14};
  for (int attempt = 0; attempt < 10; attempt++) {
    for (int i = 0; i < 2; i++) {
      Wire.beginTransmission(addrs[i]);
      if (Wire.endTransmission() == 0) {
        gt911_addr = addrs[i];
        Serial.printf("GT911 found at 0x%02X (attempt %d)\n", gt911_addr, attempt);
        return;
      }
    }
    delay(100);
  }
  Serial.println("GT911 not found!");
}

// ============================================================
// Hotkey Definitions
// ============================================================
#define MOD_CTRL  (1 << 0)
#define MOD_SHIFT (1 << 1)
#define MOD_ALT   (1 << 2)
#define MOD_GUI   (1 << 3)

#ifndef USE_BLE
  // USBHIDKeyboard has no KEY_PRTSC; use sentinel + pressRaw(0x46)
  #define KEY_PRTSC 0xFE
#endif

struct HotkeyDef {
  const char *label;
  uint8_t modifiers;
  uint8_t key;
};

static HotkeyDef hotkeys[12] = {
  {"Copy",       MOD_CTRL,              'c'},
  {"Paste",      MOD_CTRL,              'v'},
  {"Cut",        MOD_CTRL,              'x'},
  {"Undo",       MOD_CTRL,              'z'},
  {"Redo",       MOD_CTRL | MOD_SHIFT,  'z'},
  {"Save",       MOD_CTRL,              's'},
  {"Find",       MOD_CTRL,              'f'},
  {"Select All", MOD_CTRL,              'a'},
  {"Close Tab",  MOD_CTRL,              'w'},
  {"New Tab",    MOD_CTRL,              't'},
  {"Screenshot", 0,                     KEY_PRTSC},
  {"Lock",       MOD_GUI,               'l'},
};

// ============================================================
// LVGL Display Driver
// ============================================================
static lv_disp_draw_buf_t draw_buf;
static lv_color_t *buf1;
static lv_color_t *buf2;

static void disp_flush_cb(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *color_p) {
  uint32_t w = area->x2 - area->x1 + 1;
  uint32_t h = area->y2 - area->y1 + 1;
  lcd.startWrite();
  lcd.setAddrWindow(area->x1, area->y1, w, h);
  lcd.writePixels((lgfx::rgb565_t *)color_p, w * h);
  lcd.endWrite();
  lv_disp_flush_ready(disp);
}

// ============================================================
// LVGL Touch Driver — GT911 register reads via Wire
// ============================================================
static volatile bool     touch_down = false;
static volatile uint16_t touch_x = 0;
static volatile uint16_t touch_y = 0;

static uint32_t touch_dbg_timer = 0;

static void poll_touch() {
  if (gt911_addr == 0) return;

  Wire.beginTransmission(gt911_addr);
  Wire.write(0x81);
  Wire.write(0x4E);
  int err = Wire.endTransmission();
  if (err != 0) {
    if (millis() - touch_dbg_timer > 2000) {
      touch_dbg_timer = millis();
      Serial.printf("GT911 i2c err: %d\n", err);
    }
    touch_down = false;
    return;
  }

  delay(1);
  Wire.requestFrom(gt911_addr, (uint8_t)1);
  if (!Wire.available()) { touch_down = false; return; }

  uint8_t status = Wire.read();
  uint8_t touches = status & 0x0F;

  // Periodic status dump (every 2s)
  if (millis() - touch_dbg_timer > 2000) {
    touch_dbg_timer = millis();
    Serial.printf("GT911 status=0x%02X touches=%d td=%d xy=%d,%d\n",
      status, touches, (int)touch_down, touch_x, touch_y);
  }

  if ((status & 0x80) && touches > 0) {
    Wire.beginTransmission(gt911_addr);
    Wire.write(0x81);
    Wire.write(0x50);
    Wire.endTransmission();
    delay(1);
    Wire.requestFrom(gt911_addr, (uint8_t)4);
    if (Wire.available() >= 4) {
      touch_x = Wire.read() | (Wire.read() << 8);
      touch_y = Wire.read() | (Wire.read() << 8);
      touch_down = true;
      Serial.printf("TOUCH %d,%d\n", touch_x, touch_y);
    }
  } else {
    touch_down = false;
  }

  Wire.beginTransmission(gt911_addr);
  Wire.write(0x81);
  Wire.write(0x4E);
  Wire.write(0x00);
  Wire.endTransmission();
}

static void touch_read_cb(lv_indev_drv_t *drv, lv_indev_data_t *data) {
  data->point.x = touch_x;
  data->point.y = touch_y;
  data->state   = touch_down ? LV_INDEV_STATE_PR : LV_INDEV_STATE_REL;
}

// ============================================================
// Hotkey Button Callback
// ============================================================
static void hotkey_event_cb(lv_event_t *e) {
  HotkeyDef *hk = (HotkeyDef *)lv_event_get_user_data(e);
  if (!hk) return;

  Serial.printf("Hotkey: %s\n", hk->label);

#ifdef USE_BLE
  if (!bleKbd.isConnected()) {
    Serial.println("  BLE not connected!");
    return;
  }
  if (hk->modifiers & MOD_CTRL)  bleKbd.press(KEY_LEFT_CTRL);
  if (hk->modifiers & MOD_SHIFT) bleKbd.press(KEY_LEFT_SHIFT);
  if (hk->modifiers & MOD_ALT)   bleKbd.press(KEY_LEFT_ALT);
  if (hk->modifiers & MOD_GUI)   bleKbd.press(KEY_LEFT_GUI);
  if (hk->key) bleKbd.press(hk->key);
  delay(50);
  bleKbd.releaseAll();
#else
  if (hk->modifiers & MOD_CTRL)  usbKbd.press(KEY_LEFT_CTRL);
  if (hk->modifiers & MOD_SHIFT) usbKbd.press(KEY_LEFT_SHIFT);
  if (hk->modifiers & MOD_ALT)   usbKbd.press(KEY_LEFT_ALT);
  if (hk->modifiers & MOD_GUI)   usbKbd.press(KEY_LEFT_GUI);
  if (hk->key == KEY_PRTSC) {
    usbKbd.pressRaw(0x46);
  } else if (hk->key) {
    usbKbd.press(hk->key);
  }
  delay(50);
  usbKbd.releaseAll();
#endif
}

// ============================================================
// On-screen debug label
// ============================================================
static lv_obj_t *dbg_label = NULL;

// ============================================================
// Build 4x3 Button Grid
// ============================================================
static void build_ui() {
  lv_obj_t *scr = lv_scr_act();
  lv_obj_set_style_bg_color(scr, lv_color_hex(0x0a0a1a), 0);
  lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

  static lv_coord_t col_dsc[] = {
    LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1),
    LV_GRID_TEMPLATE_LAST
  };
  static lv_coord_t row_dsc[] = {
    LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1),
    LV_GRID_TEMPLATE_LAST
  };

  lv_obj_t *grid = lv_obj_create(scr);
  lv_obj_set_size(grid, 800, 480);
  lv_obj_set_pos(grid, 0, 0);
  lv_obj_set_layout(grid, LV_LAYOUT_GRID);
  lv_obj_set_grid_dsc_array(grid, col_dsc, row_dsc);
  lv_obj_set_style_pad_all(grid, 10, 0);
  lv_obj_set_style_pad_gap(grid, 10, 0);
  lv_obj_set_style_bg_color(grid, lv_color_hex(0x0a0a1a), 0);
  lv_obj_set_style_border_width(grid, 0, 0);
  lv_obj_clear_flag(grid, LV_OBJ_FLAG_SCROLLABLE);

  for (int i = 0; i < 12; i++) {
    int col = i % 4;
    int row = i / 4;

    lv_obj_t *btn = lv_btn_create(grid);
    lv_obj_set_grid_cell(btn,
      LV_GRID_ALIGN_STRETCH, col, 1,
      LV_GRID_ALIGN_STRETCH, row, 1);

    lv_obj_set_style_bg_color(btn, lv_color_hex(0x16213e), LV_STATE_DEFAULT);
    lv_obj_set_style_bg_opa(btn, LV_OPA_COVER, LV_STATE_DEFAULT);
    lv_obj_set_style_radius(btn, 12, LV_STATE_DEFAULT);
    lv_obj_set_style_shadow_width(btn, 6, LV_STATE_DEFAULT);
    lv_obj_set_style_shadow_color(btn, lv_color_hex(0x000000), LV_STATE_DEFAULT);
    lv_obj_set_style_shadow_opa(btn, LV_OPA_60, LV_STATE_DEFAULT);
    lv_obj_set_style_border_width(btn, 2, LV_STATE_DEFAULT);
    lv_obj_set_style_border_color(btn, lv_color_hex(0x0f3460), LV_STATE_DEFAULT);

    lv_obj_set_style_bg_color(btn, lv_color_hex(0xe94560), LV_STATE_PRESSED);
    lv_obj_set_style_border_color(btn, lv_color_hex(0xff6b6b), LV_STATE_PRESSED);

    lv_obj_t *label = lv_label_create(btn);
    lv_label_set_text(label, hotkeys[i].label);
    lv_obj_set_style_text_font(label, &lv_font_montserrat_22, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0xffffff), 0);
    lv_obj_center(label);

    lv_obj_add_event_cb(btn, hotkey_event_cb, LV_EVENT_CLICKED, &hotkeys[i]);
  }

  dbg_label = lv_label_create(scr);
  lv_obj_set_style_text_color(dbg_label, lv_color_hex(0xffff00), 0);
  lv_obj_set_style_text_font(dbg_label, &lv_font_montserrat_14, 0);
  lv_obj_set_style_bg_color(dbg_label, lv_color_hex(0x000000), 0);
  lv_obj_set_style_bg_opa(dbg_label, LV_OPA_70, 0);
  lv_obj_set_style_pad_all(dbg_label, 4, 0);
  lv_label_set_text(dbg_label, "Starting...");
  lv_obj_align(dbg_label, LV_ALIGN_BOTTOM_LEFT, 5, -5);
}

// ============================================================
// Setup
// ============================================================
void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Hotkey Pad Starting ===");

  pinMode(38, OUTPUT);
  digitalWrite(38, LOW);

  Wire.begin(19, 20);
  ioExpander.reset();
  ioExpander.setMode(IO_OUTPUT);
  ioExpander.setState(IO0, IO_LOW);
  ioExpander.setState(IO1, IO_LOW);
  delay(20);
  ioExpander.setState(IO0, IO_HIGH);
  delay(100);
  ioExpander.setMode(IO1, IO_INPUT);
  Serial.println("PCA9557 touch reset done");

  lcd.begin();
  lcd.fillScreen(TFT_BLACK);
  delay(200);
  Serial.println("Display initialized");

  // I2C bus scan (with timeout per address)
  Serial.println("I2C scan:");
  Wire.setTimeOut(50);
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission(true);
    if (err == 0) {
      Serial.printf("  0x%02X found\n", addr);
    }
    delay(2);
  }
  Serial.println("I2C scan done");

  // Pulse PCF8575 P00-P03 one at a time to identify wiring
  for (int pin = 0; pin < 4; pin++) {
    Serial.printf("PCF8575: P0%d LOW for 2s...\n", pin);
    uint8_t lo = 0xFF & ~(1 << pin);  // pull one pin LOW
    Wire.beginTransmission(0x27);
    Wire.write(lo);          // low byte
    Wire.write(0xFF);        // high byte all HIGH
    Wire.endTransmission();
    delay(2000);
  }
  // Restore all HIGH
  Serial.println("All pins HIGH — done.");
  Wire.beginTransmission(0x27);
  Wire.write(0xFF);
  Wire.write(0xFF);
  Wire.endTransmission();

  gt911_discover();

#ifdef USE_BLE
  bleKbd.begin();
  Serial.println("BLE keyboard advertising as 'HotkeyPad'");
#else
  usbKbd.begin();
  USB.productName("HotkeyPad");
  USB.manufacturerName("Elcrow");
  USB.begin();
  Serial.println("USB HID keyboard started");
#endif

  lv_init();

  buf1 = (lv_color_t *)ps_malloc(800 * 40 * sizeof(lv_color_t));
  buf2 = (lv_color_t *)ps_malloc(800 * 40 * sizeof(lv_color_t));
  lv_disp_draw_buf_init(&draw_buf, buf1, buf2, 800 * 40);

  static lv_disp_drv_t disp_drv;
  lv_disp_drv_init(&disp_drv);
  disp_drv.hor_res  = 800;
  disp_drv.ver_res  = 480;
  disp_drv.flush_cb = disp_flush_cb;
  disp_drv.draw_buf = &draw_buf;
  lv_disp_drv_register(&disp_drv);

  static lv_indev_drv_t indev_drv;
  lv_indev_drv_init(&indev_drv);
  indev_drv.type    = LV_INDEV_TYPE_POINTER;
  indev_drv.read_cb = touch_read_cb;
  lv_indev_drv_register(&indev_drv);

  build_ui();
  Serial.println("UI ready");
}

// ============================================================
// Loop
// ============================================================
static uint32_t dbg_timer = 0;
static uint32_t touch_timer = 0;

void loop() {
  if (millis() - touch_timer >= 50) {
    touch_timer = millis();
    poll_touch();
  }

  lv_timer_handler();
  delay(5);

  // Poll PCF8575 at 0x27
  static uint16_t last_pcf = 0xFFFF;
  static uint32_t pcf_timer = 0;
  if (millis() - pcf_timer > 100) {
    pcf_timer = millis();
    Wire.requestFrom((uint8_t)0x27, (uint8_t)2);
    if (Wire.available() >= 2) {
      uint16_t val = Wire.read() | (Wire.read() << 8);
      if (val != last_pcf) {
        Serial.printf("PCF8575: 0x%04X  changed: 0x%04X\n", val, val ^ last_pcf);
        last_pcf = val;
      }
    }
  }

  if (dbg_label && millis() - dbg_timer > 500) {
    dbg_timer = millis();
    static char dbg_buf[96];
#ifdef USE_BLE
    snprintf(dbg_buf, sizeof(dbg_buf),
      "BLE:%s  xy:%d,%d %s",
      bleKbd.isConnected() ? "Y" : "N",
      touch_x, touch_y,
      touch_down ? "TOUCH" : "");
#else
    snprintf(dbg_buf, sizeof(dbg_buf),
      "USB-HID  xy:%d,%d %s",
      touch_x, touch_y,
      touch_down ? "TOUCH" : "");
#endif
    lv_label_set_text(dbg_label, dbg_buf);
  }
}
