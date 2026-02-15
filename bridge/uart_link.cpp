/**
 * @file uart_link.cpp
 * UART receive with SOF-framed state machine parser for bridge ESP32-S3
 *
 * Receives frames from display unit over UART1, validates CRC8,
 * and provides parsed message type + payload to caller.
 */

#include "uart_link.h"
#include "protocol.h"

#include <HardwareSerial.h>

// UART1 for display communication (UART0 is debug serial)
static HardwareSerial DisplaySerial(1);

// Bridge UART pin assignments (ESP32-S3 DevKitC-1 free GPIOs)
#define BRIDGE_UART_RX   18
#define BRIDGE_UART_TX   17
#define BRIDGE_UART_BAUD 115200

// Maximum bytes to process per uart_poll() call to avoid blocking
#define MAX_BYTES_PER_POLL 64

// --- Frame Parser State Machine ---

enum ParserState : uint8_t {
    WAIT_SOF,
    READ_LEN,
    READ_TYPE,
    READ_PAYLOAD,
    READ_CRC
};

struct FrameParser {
    ParserState state;
    uint8_t payload[PROTO_MAX_PAYLOAD];
    uint8_t payload_len;
    uint8_t payload_idx;
    uint8_t msg_type;

    void reset() {
        state = WAIT_SOF;
        payload_len = 0;
        payload_idx = 0;
        msg_type = 0;
    }

    // Feed a byte into the parser. Returns true when a valid frame is complete.
    bool feed(uint8_t byte) {
        switch (state) {
            case WAIT_SOF:
                if (byte == PROTO_SOF) {
                    state = READ_LEN;
                }
                return false;

            case READ_LEN:
                if (byte > PROTO_MAX_PAYLOAD) {
                    Serial.printf("UART: frame len %d exceeds max %d, discarding\n",
                                  byte, PROTO_MAX_PAYLOAD);
                    reset();
                    return false;
                }
                payload_len = byte;
                payload_idx = 0;
                state = READ_TYPE;
                return false;

            case READ_TYPE:
                msg_type = byte;
                if (payload_len == 0) {
                    state = READ_CRC;
                } else {
                    state = READ_PAYLOAD;
                }
                return false;

            case READ_PAYLOAD:
                payload[payload_idx++] = byte;
                if (payload_idx >= payload_len) {
                    state = READ_CRC;
                }
                return false;

            case READ_CRC: {
                // Build CRC input: LEN + TYPE + PAYLOAD
                uint8_t crc_buf[2 + PROTO_MAX_PAYLOAD];
                crc_buf[0] = payload_len;
                crc_buf[1] = msg_type;
                memcpy(&crc_buf[2], payload, payload_len);

                uint8_t expected = crc8_calc(crc_buf, 2 + payload_len);
                if (byte != expected) {
                    Serial.printf("UART: CRC error (got 0x%02X, expected 0x%02X), discarding\n",
                                  byte, expected);
                    reset();
                    return false;
                }

                // Valid frame received
                state = WAIT_SOF;
                return true;
            }

            default:
                reset();
                return false;
        }
    }
};

static FrameParser parser;

void uart_link_init() {
    DisplaySerial.begin(BRIDGE_UART_BAUD, SERIAL_8N1, BRIDGE_UART_RX, BRIDGE_UART_TX);
    parser.reset();
    Serial.printf("UART link initialized (RX=%d, TX=%d, baud=%d)\n",
                  BRIDGE_UART_RX, BRIDGE_UART_TX, BRIDGE_UART_BAUD);
}

bool uart_poll(uint8_t &type, uint8_t *payload, uint8_t &payload_len) {
    int bytes_processed = 0;

    while (DisplaySerial.available() && bytes_processed < MAX_BYTES_PER_POLL) {
        uint8_t byte = DisplaySerial.read();
        bytes_processed++;

        if (parser.feed(byte)) {
            // Valid frame received -- copy results
            type = parser.msg_type;
            payload_len = parser.payload_len;
            memcpy(payload, parser.payload, parser.payload_len);
            parser.reset();
            return true;
        }
    }

    return false;
}

bool uart_send(MsgType type, const uint8_t *payload, uint8_t len) {
    // Build frame: SOF + LEN + TYPE + PAYLOAD + CRC8
    uint8_t frame[4 + len];
    frame[0] = PROTO_SOF;
    frame[1] = len;
    frame[2] = (uint8_t)type;

    if (len > 0 && payload != nullptr) {
        memcpy(&frame[3], payload, len);
    }

    // CRC over LEN + TYPE + PAYLOAD
    frame[3 + len] = crc8_calc(&frame[1], 2 + len);

    size_t written = DisplaySerial.write(frame, 4 + len);
    return (written == (size_t)(4 + len));
}
