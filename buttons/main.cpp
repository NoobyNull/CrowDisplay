#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include "protocol.h"

// ============================================================
// ESP32-WROOM Button Controller Firmware
// ============================================================
//
// 12 physical buttons (8 front user-programmable, 4 back system)
// connected to GPIO with internal pullups, active LOW.
//
// Transport selection at boot:
//   1. Send MSG_PING over UART, wait 200ms for echo
//   2. If echo received → UART mode (wired to CrowPanel)
//   3. If no response  → ESP-NOW broadcast mode (wireless)
//
// Pin assignments: see docs/esp32d-button-controller-pinout.md

// --- Pin Assignments ---
static const uint8_t FRONT_PINS[] = {4, 5, 18, 19, 21, 22, 23, 25};  // F1-F8
static const uint8_t BACK_PINS[]  = {26, 27, 14, 13};                  // B1-B4

#define NUM_FRONT  8
#define NUM_BACK   4
#define NUM_BUTTONS (NUM_FRONT + NUM_BACK)

// --- Debounce ---
#define DEBOUNCE_MS 50

static bool     prev_pressed[NUM_BUTTONS] = {false};
static uint32_t debounce_time[NUM_BUTTONS] = {0};

// --- Transport selection (set once at boot) ---
static bool use_uart = false;

// ESP-NOW broadcast address
static const uint8_t broadcast_addr[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ============================================================
// Transport: UART framed protocol
// ============================================================

static void uart_send_frame(uint8_t msg_type, const uint8_t *payload, uint8_t payload_len) {
    uint8_t frame[PROTO_MAX_PAYLOAD + 4];
    frame[0] = PROTO_SOF;
    frame[1] = 1 + payload_len;  // LEN = type + payload
    frame[2] = msg_type;
    if (payload_len > 0) {
        memcpy(&frame[3], payload, payload_len);
    }
    // CRC8 over LEN + TYPE + PAYLOAD
    frame[3 + payload_len] = crc8_calc(&frame[1], 1 + 1 + payload_len);

    Serial2.write(frame, 4 + payload_len);
    Serial2.flush();
}

// ============================================================
// Transport: ESP-NOW
// ============================================================

static void espnow_init_transport() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

    if (esp_now_init() != ESP_OK) {
        Serial.println("[transport] ESP-NOW init FAILED");
        return;
    }

    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, broadcast_addr, 6);
    peer.channel = 1;
    peer.encrypt = false;
    esp_now_add_peer(&peer);

    Serial.printf("[transport] ESP-NOW ready (MAC: %s)\n", WiFi.macAddress().c_str());
}

static void espnow_send_msg(uint8_t msg_type, const uint8_t *payload, uint8_t payload_len) {
    // ESP-NOW frame: [TYPE] [PAYLOAD...]
    uint8_t buf[1 + PROTO_MAX_PAYLOAD];
    buf[0] = msg_type;
    if (payload_len > 0 && payload) {
        memcpy(&buf[1], payload, payload_len);
    }
    esp_now_send(broadcast_addr, buf, 1 + payload_len);
}

// ============================================================
// Unified send (uses whichever transport was selected at boot)
// ============================================================

static void send_hw_button(uint8_t button_index, uint8_t pressed) {
    HwButtonMsg msg;
    msg.button_index = button_index;
    msg.pressed = pressed;

    if (use_uart) {
        uart_send_frame(MSG_HW_BUTTON, (const uint8_t *)&msg, sizeof(msg));
    } else {
        espnow_send_msg(MSG_HW_BUTTON, (const uint8_t *)&msg, sizeof(msg));
    }
}

// ============================================================
// UART probe: send MSG_PING, wait for any valid SOF response
// ============================================================

static bool uart_probe() {
    // Drain any stale bytes
    while (Serial2.available()) Serial2.read();

    // Send a MSG_PING (no payload)
    uart_send_frame(MSG_PING, nullptr, 0);

    // Wait up to 200ms for a valid SOF-framed response
    uint32_t start = millis();
    while (millis() - start < 200) {
        if (Serial2.available()) {
            uint8_t b = Serial2.read();
            if (b == PROTO_SOF) {
                // Got a framed response — UART link is live
                // Drain rest of the response frame
                delay(10);
                while (Serial2.available()) Serial2.read();
                return true;
            }
        }
        delay(1);
    }
    return false;
}

// ============================================================
// UART Receiver (future: LED feedback commands from CrowPanel)
// ============================================================

static uint8_t rx_buf[PROTO_MAX_PAYLOAD + 4];
static uint8_t rx_pos = 0;

enum RxState { WAIT_SOF, READ_LEN, READ_BODY };
static RxState rx_state = WAIT_SOF;
static uint8_t rx_len = 0;

static void uart_rx_poll() {
    while (Serial2.available()) {
        uint8_t b = Serial2.read();

        switch (rx_state) {
            case WAIT_SOF:
                if (b == PROTO_SOF) {
                    rx_state = READ_LEN;
                }
                break;
            case READ_LEN:
                rx_len = b;
                if (rx_len < 1 || rx_len > PROTO_MAX_PAYLOAD + 1) {
                    rx_state = WAIT_SOF;
                } else {
                    rx_pos = 0;
                    rx_buf[rx_pos++] = b;
                    rx_state = READ_BODY;
                }
                break;
            case READ_BODY:
                rx_buf[rx_pos++] = b;
                if (rx_pos >= (uint8_t)(rx_len + 2)) {
                    uint8_t expected_crc = rx_buf[rx_pos - 1];
                    uint8_t calc_crc = crc8_calc(rx_buf, rx_len + 1);
                    if (calc_crc == expected_crc) {
                        uint8_t msg_type = rx_buf[1];
                        Serial.printf("[btn_rx] msg type=0x%02X len=%d\n", msg_type, rx_len);
                    }
                    rx_state = WAIT_SOF;
                }
                break;
        }
    }
}

// --- Pin reading helper ---

static inline uint8_t get_pin(uint8_t button_index) {
    if (button_index < NUM_FRONT) return FRONT_PINS[button_index];
    return BACK_PINS[button_index - NUM_FRONT];
}

// ============================================================
// Arduino setup/loop
// ============================================================

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== Button Controller Starting ===");

    // Configure all button pins as INPUT_PULLUP (active LOW)
    for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
        pinMode(get_pin(i), INPUT_PULLUP);
    }

    // UART to CrowPanel: TX=GPIO17, RX=GPIO16
    Serial2.begin(115200, SERIAL_8N1, /*RX=*/16, /*TX=*/17);

    // Probe UART — if CrowPanel responds to ping, use wired transport
    Serial.println("[transport] Probing UART...");
    use_uart = uart_probe();

    if (use_uart) {
        Serial.println("[transport] UART detected — using wired transport");
    } else {
        Serial.println("[transport] No UART response — using ESP-NOW broadcast");
        espnow_init_transport();
    }

    Serial.printf("Configured %d buttons (%d front + %d back)\n",
                  NUM_BUTTONS, NUM_FRONT, NUM_BACK);
    Serial.println("Button controller ready");
}

void loop() {
    static uint32_t poll_timer = 0;

    // Poll buttons at 100Hz (10ms)
    if (millis() - poll_timer >= 10) {
        poll_timer = millis();
        uint32_t now = millis();

        for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
            bool pressed = (digitalRead(get_pin(i)) == LOW);

            if (pressed != prev_pressed[i]) {
                if (now - debounce_time[i] >= DEBOUNCE_MS) {
                    debounce_time[i] = now;
                    prev_pressed[i] = pressed;

                    if (pressed) {
                        Serial.printf("[btn] Button %d pressed (GPIO %d)\n",
                                      i, get_pin(i));
                        send_hw_button(i, 1);
                    } else {
                        send_hw_button(i, 0);
                    }
                }
            }
        }
    }

    // Check for incoming UART commands (only if wired)
    if (use_uart) {
        uart_rx_poll();
    }

    delay(1);
}
