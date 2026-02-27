#include "uart_input.h"
#include <Arduino.h>
#include "protocol.h"
#include "config.h"
#include "hw_input.h"
#include "ui.h"

// ============================================================
// UART Receiver for ESP32-WROOM Button Controller
// ============================================================
//
// Receives MSG_HW_BUTTON frames from the WROOM over Serial1.
// Frame format: [SOF 0xAA] [LEN] [TYPE] [PAYLOAD] [CRC8]
//
// Front buttons (0-7) map to cfg.hw_buttons[0..7]
// Back buttons (8-11) have hardcoded system actions:
//   B1 (8)  = CONFIG_MODE
//   B2 (9)  = MODE_CYCLE
//   B3 (10) = BRIGHTNESS
//   B4 (11) = PAGE_NAV (next page)

#define UART_RX_PIN 44
#define UART_TX_PIN 43

// Frame parser state machine
enum UartRxState : uint8_t {
    UART_WAIT_SOF,
    UART_READ_LEN,
    UART_READ_BODY,
};

static UartRxState rx_state = UART_WAIT_SOF;
static uint8_t rx_buf[PROTO_MAX_PAYLOAD + 4];
static uint8_t rx_pos = 0;
static uint8_t rx_len = 0;  // LEN field value (TYPE + PAYLOAD size)

// Track last valid UART frame for link detection
static uint32_t last_uart_rx_time = 0;
#define UART_LINK_TIMEOUT_MS 5000

bool uart_is_linked() {
    return last_uart_rx_time > 0 && (millis() - last_uart_rx_time) < UART_LINK_TIMEOUT_MS;
}

// Send a framed response back to the button controller over UART
static void uart_send_reply(uint8_t msg_type, const uint8_t *payload, uint8_t payload_len) {
    uint8_t frame[PROTO_MAX_PAYLOAD + 4];
    frame[0] = PROTO_SOF;
    frame[1] = 1 + payload_len;
    frame[2] = msg_type;
    if (payload_len > 0) {
        memcpy(&frame[3], payload, payload_len);
    }
    frame[3 + payload_len] = crc8_calc(&frame[1], 1 + 1 + payload_len);
    Serial1.write(frame, 4 + payload_len);
    Serial1.flush();
}

void uart_input_init() {
    Serial1.begin(115200, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
    Serial.println("[uart_input] Serial1 init: RX=44 TX=43 @ 115200");
}

void handle_hw_button(const uint8_t *payload, uint8_t payload_len) {
    if (payload_len < sizeof(HwButtonMsg)) return;

    const HwButtonMsg *msg = (const HwButtonMsg *)payload;
    uint8_t idx = msg->button_index;
    bool pressed = (msg->pressed != 0);

    // Only dispatch on press (not release)
    if (!pressed) return;

    if (idx > 11) {
        Serial.printf("[uart_input] invalid button index %d\n", idx);
        return;
    }

    Serial.printf("[uart_input] Button %d pressed\n", idx);

    // Back buttons (8-11): hardcoded system actions
    if (idx >= 8) {
        switch (idx) {
            case 8:  // B1 = Config Mode
                dispatch_action(ACTION_CONFIG_MODE, 0, 0, 0, idx);
                break;
            case 9:  // B2 = Mode Cycle
                dispatch_action(ACTION_MODE_CYCLE, 0, 0, 0, idx);
                break;
            case 10: // B3 = Brightness
                dispatch_action(ACTION_BRIGHTNESS, 0, 0, 0, idx);
                break;
            case 11: // B4 = Page Nav (next)
                dispatch_action(ACTION_PAGE_NEXT, 0, 0, 0, idx);
                break;
        }
        return;
    }

    // Front buttons (0-7): user-configurable via hw_buttons[]
    const AppConfig &cfg = get_global_config();
    const HwButtonConfig &bc = cfg.hw_buttons[idx];
    dispatch_action(bc.action_type, bc.keycode, bc.consumer_code, bc.modifiers, idx);
}

void uart_input_poll() {
    while (Serial1.available()) {
        uint8_t b = Serial1.read();

        switch (rx_state) {
            case UART_WAIT_SOF:
                if (b == PROTO_SOF) {
                    rx_state = UART_READ_LEN;
                }
                break;

            case UART_READ_LEN:
                rx_len = b;
                if (rx_len < 1 || rx_len > PROTO_MAX_PAYLOAD + 1) {
                    rx_state = UART_WAIT_SOF;
                } else {
                    rx_pos = 0;
                    rx_buf[rx_pos++] = b;  // Store LEN for CRC calculation
                    rx_state = UART_READ_BODY;
                }
                break;

            case UART_READ_BODY:
                rx_buf[rx_pos++] = b;
                // Need: LEN(1) + TYPE(1) + PAYLOAD(rx_len-1) + CRC(1) = rx_len + 2 bytes total
                if (rx_pos >= (uint8_t)(rx_len + 2)) {
                    // CRC covers LEN + TYPE + PAYLOAD = rx_buf[0..rx_len]
                    uint8_t expected_crc = rx_buf[rx_pos - 1];
                    uint8_t calc_crc = crc8_calc(rx_buf, rx_len + 1);

                    if (calc_crc == expected_crc) {
                        last_uart_rx_time = millis();
                        uint8_t msg_type = rx_buf[1];
                        uint8_t *payload = &rx_buf[2];
                        uint8_t payload_len = rx_len - 1;

                        if (msg_type == MSG_HW_BUTTON) {
                            handle_hw_button(payload, payload_len);
                        } else if (msg_type == MSG_PING) {
                            // Echo ping back so WROOM detects UART link at boot
                            uart_send_reply(MSG_PING, nullptr, 0);
                        } else {
                            Serial.printf("[uart_input] unknown msg type 0x%02X\n", msg_type);
                        }
                    } else {
                        Serial.printf("[uart_input] CRC mismatch: got 0x%02X expected 0x%02X\n",
                                      expected_crc, calc_crc);
                    }
                    rx_state = UART_WAIT_SOF;
                }
                break;
        }
    }
}
