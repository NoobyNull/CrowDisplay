#pragma once
#include <cstdint>
#include "protocol.h"

// Initialize UART1 for bridge-side communication
// Bridge UART pins: RX from display TX, TX to display RX
// GPIO 18 (RX) and GPIO 17 (TX) on ESP32-S3 DevKitC-1
void uart_link_init();

// Poll UART for incoming data, feed to parser
// Returns true if a complete valid frame was received
// On return true, type/payload/payload_len are populated
bool uart_poll(uint8_t &type, uint8_t *payload, uint8_t &payload_len);

// Send a framed message over UART (for ACK responses)
bool uart_send(MsgType type, const uint8_t *payload, uint8_t len);
