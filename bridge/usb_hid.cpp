/**
 * @file usb_hid.cpp
 * USB HID Keyboard implementation for bridge ESP32-S3
 *
 * Keyboard only -- no consumer control (media keys deferred to Phase 3 per BRDG-04).
 * Requires build flags: ARDUINO_USB_MODE=0, ARDUINO_USB_CDC_ON_BOOT=0
 */

#include "usb_hid.h"
#include "protocol.h"

#include <Arduino.h>
#include <USB.h>
#include <USBHIDKeyboard.h>

static USBHIDKeyboard Keyboard;

void usb_hid_init() {
    // Force USB D+/D- low to trigger host disconnect before switching
    // from JTAG controller to USB-OTG/TinyUSB PHY
    pinMode(19, OUTPUT);  // USB_D-
    pinMode(20, OUTPUT);  // USB_D+
    digitalWrite(19, LOW);
    digitalWrite(20, LOW);
    delay(100);

    Keyboard.begin();
    USB.productName("HotkeyBridge");
    USB.manufacturerName("CrowPanel");
    USB.begin();
    delay(1000);  // Allow USB enumeration after PHY switch
    Serial.println("USB HID keyboard initialized");
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
