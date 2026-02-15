#include "uart_link.h"
#include <HardwareSerial.h>
#include <Arduino.h>
#include <string.h>

// ============================================================
//  UART1 Configuration (Display -> Bridge)
// ============================================================
#define DISPLAY_UART_TX   10
#define DISPLAY_UART_RX   11
#define DISPLAY_UART_BAUD 115200

static HardwareSerial BridgeSerial(1);

// ============================================================
//  Frame Parser State (for receiving ACKs)
// ============================================================
enum ParseState : uint8_t {
    PARSE_WAIT_SOF,
    PARSE_WAIT_LEN,
    PARSE_WAIT_TYPE,
    PARSE_WAIT_PAYLOAD,
    PARSE_WAIT_CRC,
};

static struct {
    ParseState state;
    uint8_t len;
    uint8_t type;
    uint8_t payload[PROTO_MAX_PAYLOAD];
    uint8_t payload_idx;
    uint8_t expected_crc_len;  // 2 + len (TYPE + LEN + PAYLOAD for CRC)
} parser;

// ============================================================
//  Init
// ============================================================
void uart_link_init() {
    BridgeSerial.begin(DISPLAY_UART_BAUD, SERIAL_8N1, DISPLAY_UART_RX, DISPLAY_UART_TX);
    parser.state = PARSE_WAIT_SOF;
    Serial.printf("UART link ready (TX=GPIO%d, RX=GPIO%d)\n", DISPLAY_UART_TX, DISPLAY_UART_RX);
}

// ============================================================
//  Send a framed message
//  Frame: [SOF 0xAA] [LENGTH] [TYPE] [PAYLOAD...] [CRC8]
//  CRC8 is over LENGTH + TYPE + PAYLOAD
// ============================================================
bool uart_send(MsgType type, const uint8_t *payload, uint8_t len) {
    if (len > PROTO_MAX_PAYLOAD) return false;

    uint8_t frame[4 + PROTO_MAX_PAYLOAD];
    frame[0] = PROTO_SOF;
    frame[1] = len;
    frame[2] = (uint8_t)type;
    if (len > 0 && payload) {
        memcpy(&frame[3], payload, len);
    }
    frame[3 + len] = crc8_calc(&frame[1], 2 + len);

    size_t total = 4 + len;
    return BridgeSerial.write(frame, total) == total;
}

// ============================================================
//  Convenience: Send hotkey to bridge
// ============================================================
void send_hotkey_to_bridge(uint8_t modifiers, uint8_t keycode) {
    HotkeyMsg msg;
    msg.modifiers = modifiers;
    msg.keycode = keycode;
    uart_send(MSG_HOTKEY, (uint8_t *)&msg, sizeof(msg));
    Serial.printf("UART TX: hotkey mod=0x%02X key=0x%02X\n", modifiers, keycode);
}

// ============================================================
//  Poll for ACK frames (non-blocking)
// ============================================================
bool uart_poll_ack(uint8_t &status) {
    while (BridgeSerial.available()) {
        uint8_t b = BridgeSerial.read();

        switch (parser.state) {
        case PARSE_WAIT_SOF:
            if (b == PROTO_SOF) {
                parser.state = PARSE_WAIT_LEN;
            }
            break;

        case PARSE_WAIT_LEN:
            parser.len = b;
            if (parser.len > PROTO_MAX_PAYLOAD) {
                parser.state = PARSE_WAIT_SOF;  // Invalid, reset
            } else {
                parser.state = PARSE_WAIT_TYPE;
            }
            break;

        case PARSE_WAIT_TYPE:
            parser.type = b;
            parser.payload_idx = 0;
            if (parser.len == 0) {
                parser.state = PARSE_WAIT_CRC;
            } else {
                parser.state = PARSE_WAIT_PAYLOAD;
            }
            break;

        case PARSE_WAIT_PAYLOAD:
            parser.payload[parser.payload_idx++] = b;
            if (parser.payload_idx >= parser.len) {
                parser.state = PARSE_WAIT_CRC;
            }
            break;

        case PARSE_WAIT_CRC: {
            // Verify CRC: compute over LEN + TYPE + PAYLOAD
            uint8_t crc_buf[2 + PROTO_MAX_PAYLOAD];
            crc_buf[0] = parser.len;
            crc_buf[1] = parser.type;
            if (parser.len > 0) {
                memcpy(&crc_buf[2], parser.payload, parser.len);
            }
            uint8_t computed = crc8_calc(crc_buf, 2 + parser.len);

            parser.state = PARSE_WAIT_SOF;  // Reset for next frame

            if (b == computed && parser.type == (uint8_t)MSG_HOTKEY_ACK && parser.len >= 1) {
                status = parser.payload[0];
                return true;
            }
            // CRC mismatch or wrong type -- discard
            break;
        }
        }
    }
    return false;
}
