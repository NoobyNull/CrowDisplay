/**
 * @file usb_hid.h
 * USB HID Keyboard + Consumer Control interface
 * Uses ESP32-S3 native USB
 */

#ifndef USB_HID_H
#define USB_HID_H

#include <Arduino.h>
#include "USB.h"
#include "USBHIDKeyboard.h"
#include "USBHIDConsumerControl.h"

// ── Modifier Key Masks ──
#define MOD_NONE     0x00
#define MOD_CTRL     0x01
#define MOD_SHIFT    0x02
#define MOD_ALT      0x04
#define MOD_GUI      0x08  // Windows/Command key
#define MOD_CONSUMER 0x80  // Flag: send as consumer control (media keys)

// ── Consumer Control Usage IDs ──
#define MEDIA_PLAY_PAUSE  0xCD
#define MEDIA_NEXT        0xB5
#define MEDIA_PREV        0xB6
#define MEDIA_STOP        0xB7
#define MEDIA_VOL_UP      0xE9
#define MEDIA_VOL_DOWN    0xEA
#define MEDIA_MUTE        0xE2

// ── Hotkey Definition ──
struct Hotkey {
    const char *label;          // Display label on button
    const char *description;    // Tooltip/description
    uint8_t modifiers;          // Modifier key bitmask (MOD_CONSUMER for media keys)
    uint16_t key;               // Key code: ASCII/special for keyboard, usage ID for consumer
    uint32_t color;             // Button color (LVGL format)
    const char *icon;           // LV_SYMBOL for icon (nullable)
};

// ── Function Prototypes ──
void usb_hid_init(void);
void send_hotkey(const Hotkey &hk);
void send_key_combo(uint8_t modifiers, uint16_t key);

#endif /* USB_HID_H */
