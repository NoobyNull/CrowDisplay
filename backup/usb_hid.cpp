/**
 * @file usb_hid.cpp
 * USB HID Keyboard + Consumer Control implementation
 */

#include "usb_hid.h"

static USBHIDKeyboard Keyboard;
static USBHIDConsumerControl ConsumerControl;

void usb_hid_init(void) {
    Keyboard.begin();
    ConsumerControl.begin();
    USB.begin();
    delay(500);  // Allow USB enumeration
    Serial.println("USB HID Keyboard + Consumer Control initialized");
}

void send_key_combo(uint8_t modifiers, uint16_t key) {
    // Press modifier keys
    if (modifiers & MOD_CTRL)  Keyboard.press(KEY_LEFT_CTRL);
    if (modifiers & MOD_SHIFT) Keyboard.press(KEY_LEFT_SHIFT);
    if (modifiers & MOD_ALT)   Keyboard.press(KEY_LEFT_ALT);
    if (modifiers & MOD_GUI)   Keyboard.press(KEY_LEFT_GUI);

    // Press and release the key
    Keyboard.press((uint8_t)key);
    delay(50);
    Keyboard.releaseAll();
}

void send_hotkey(const Hotkey &hk) {
    Serial.printf("Sending: %s (%s)\n", hk.label, hk.description);

    if (hk.modifiers & MOD_CONSUMER) {
        // Media/consumer control key
        ConsumerControl.press(hk.key);
        delay(50);
        ConsumerControl.release();
    } else {
        // Regular keyboard combo
        send_key_combo(hk.modifiers, hk.key);
    }
}
