#pragma once
#include <cstdint>
#include "protocol.h"

void espnow_link_init();
bool espnow_send(MsgType type, const uint8_t *payload, uint8_t len);

// Convenience: send hotkey command to bridge
void send_hotkey_to_bridge(uint8_t modifiers, uint8_t keycode);

// Convenience: send media/consumer control key to bridge
void send_media_key_to_bridge(uint16_t consumer_code);

// Poll for incoming ACK messages (non-blocking)
// Returns true if ACK received, status in out param
bool espnow_poll_ack(uint8_t &status);

// Poll for any incoming message (non-blocking)
// Returns true if a message was received; type, payload, and len are filled in.
// payload buffer must be at least PROTO_MAX_PAYLOAD bytes.
bool espnow_poll_msg(uint8_t &type, uint8_t *payload, uint8_t &payload_len);

// Get RSSI of last received ESP-NOW packet (dBm, 0 = no packets yet)
int espnow_get_rssi();
