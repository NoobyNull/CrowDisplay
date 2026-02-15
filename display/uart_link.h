#pragma once
#include <cstdint>
#include "protocol.h"

void uart_link_init();
bool uart_send(MsgType type, const uint8_t *payload, uint8_t len);

// Convenience: send hotkey command to bridge
void send_hotkey_to_bridge(uint8_t modifiers, uint8_t keycode);

// Poll for incoming ACK messages (non-blocking)
// Returns true if ACK received, status in out param
bool uart_poll_ack(uint8_t &status);
