/**
 * @file usb_hid.cpp
 * Composite USB HID implementation for bridge ESP32-S3
 *
 * Three HID interfaces:
 *   - Keyboard: fires hotkey keystrokes
 *   - ConsumerControl: fires media keys (play/pause, volume, etc.)
 *   - Vendor (63-byte reports): receives stats data from companion app
 *
 * Requires build flags: ARDUINO_USB_MODE=0, ARDUINO_USB_CDC_ON_BOOT=0
 */

#include "usb_hid.h"
#include "protocol.h"

#include <Arduino.h>
#include <USB.h>
#include <USBHIDKeyboard.h>
#include <USBHIDConsumerControl.h>
#include <USBHIDVendor.h>

static USBHIDKeyboard Keyboard;
static USBHIDConsumerControl ConsumerControl;
static USBHIDVendor Vendor(63, false);  // 63-byte reports, no size prepend

void usb_hid_init() {
    // Force USB D+/D- low to trigger host disconnect before switching
    // from JTAG controller to USB-OTG/TinyUSB PHY
    pinMode(19, OUTPUT);  // USB_D-
    pinMode(20, OUTPUT);  // USB_D+
    digitalWrite(19, LOW);
    digitalWrite(20, LOW);
    delay(100);

    // Register all HID devices before USB.begin()
    Keyboard.begin();
    ConsumerControl.begin();
    Vendor.begin();

    USB.productName("HotkeyBridge");
    USB.manufacturerName("CrowPanel");
    USB.begin();
    delay(1000);  // Allow USB enumeration after PHY switch
    Serial.println("USB HID composite initialized (Keyboard + ConsumerControl + Vendor)");
}

void fire_keystroke(uint8_t modifiers, uint8_t keycode) {
    // Press modifier keys based on protocol.h modifier masks
    if (modifiers & MOD_CTRL)  Keyboard.press(KEY_LEFT_CTRL);
    if (modifiers & MOD_SHIFT) Keyboard.press(KEY_LEFT_SHIFT);
    if (modifiers & MOD_ALT)   Keyboard.press(KEY_LEFT_ALT);
    if (modifiers & MOD_GUI)   Keyboard.press(KEY_LEFT_GUI);

    // Press the key itself
    Keyboard.press(keycode);
    delay(20);  // Minimum hold time for host to register
    Keyboard.releaseAll();

    Serial.printf("HID: mod=0x%02X key=0x%02X\n", modifiers, keycode);
}

void fire_media_key(uint16_t consumer_code) {
    ConsumerControl.press(consumer_code);
    delay(20);
    ConsumerControl.release();
    Serial.printf("HID: media key 0x%04X\n", consumer_code);
}

bool poll_vendor_hid(uint8_t *buf, size_t &len) {
    if (Vendor.available()) {
        int n = Vendor.read(buf, 63);
        if (n > 0) {
            len = (size_t)n;
            return true;
        }
    }
    return false;
}

void send_vendor_report(uint8_t msg_type, const uint8_t *payload, uint8_t len) {
    uint8_t buf[63];
    memset(buf, 0, sizeof(buf));
    buf[0] = msg_type;
    if (len > 0 && payload) memcpy(&buf[1], payload, min((int)len, 62));
    Vendor.write(buf, 1 + len);
}
