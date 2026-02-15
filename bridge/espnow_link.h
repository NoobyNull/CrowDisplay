#pragma once
#include <cstdint>
#include "protocol.h"

// Initialize ESP-NOW receiver on bridge
void espnow_link_init();

// Poll for incoming hotkey commands (non-blocking)
// Returns true if a command was received
bool espnow_poll(uint8_t &type, uint8_t *payload, uint8_t &payload_len);

// Send a message back to display (ACK responses)
bool espnow_send(MsgType type, const uint8_t *payload, uint8_t len);
