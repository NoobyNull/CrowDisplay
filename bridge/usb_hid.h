#pragma once
#include <cstdint>
#include <cstddef>

void usb_hid_init();
void fire_keystroke(uint8_t modifiers, uint8_t keycode);
void fire_media_key(uint16_t consumer_code);
bool poll_vendor_hid(uint8_t *buf, size_t &len);
void send_vendor_report(uint8_t msg_type, const uint8_t *payload, uint8_t len);
