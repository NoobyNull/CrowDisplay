#pragma once
#include <cstdint>
#include "protocol.h"

void espnow_link_init();
bool espnow_send(MsgType type, const uint8_t *payload, uint8_t len);

// Convenience: send hotkey command to bridge
void send_hotkey_to_bridge(uint8_t modifiers, uint8_t keycode);

// Poll for incoming ACK messages (non-blocking)
// Returns true if ACK received, status in out param
bool espnow_poll_ack(uint8_t &status);
