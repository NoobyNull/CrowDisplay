#pragma once
#include <cstdint>

void usb_hid_init();
void fire_keystroke(uint8_t modifiers, uint8_t keycode);
