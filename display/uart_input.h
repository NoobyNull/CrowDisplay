#pragma once
#include <stdint.h>

// Initialize UART1 receiver for button controller (RX=GPIO44, TX=GPIO43)
void uart_input_init();

// Poll UART1 for incoming MSG_HW_BUTTON frames. Call every 10ms from loop().
void uart_input_poll();

// Handle a HwButtonMsg payload from any transport (UART or ESP-NOW).
// payload must point to a HwButtonMsg struct, payload_len must be >= 2.
void handle_hw_button(const uint8_t *payload, uint8_t payload_len);

// Returns true if a valid UART frame was received within the last 5 seconds.
bool uart_is_linked();
