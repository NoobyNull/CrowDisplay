#pragma once
#include <cstdint>
#include "protocol.h"

// Initialize ESP-NOW receiver on bridge
void espnow_link_init();

// Poll for incoming hotkey commands (non-blocking)
// Returns true if a command was received
bool espnow_poll(uint8_t &type, uint8_t *payload, uint8_t &payload_len);

// Send a message back to display (ACK responses, uses last sender MAC)
bool espnow_send(MsgType type, const uint8_t *payload, uint8_t len);

// Send a message via broadcast (for commands like CONFIG_MODE/CONFIG_DONE)
bool espnow_send_broadcast(MsgType type, const uint8_t *payload, uint8_t len);
