/**
 * @file espnow_link.cpp
 * ESP-NOW wireless link for bridge (receiver side)
 *
 * Receives hotkey commands from display; sends ACKs back.
 * Accepts from any peer (no pairing required).
 */

#include "espnow_link.h"
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <string.h>

// Ring buffer for received messages (callback -> poll)
#define RX_QUEUE_SIZE 8

struct RxMsg {
    uint8_t type;
    uint8_t payload[PROTO_MAX_PAYLOAD];
    uint8_t len;
};

static volatile RxMsg rx_queue[RX_QUEUE_SIZE];
static volatile int rx_head = 0;
static volatile int rx_tail = 0;

// Store last sender MAC for ACK replies
static uint8_t last_sender_mac[6] = {};

static void on_recv(const uint8_t *mac, const uint8_t *data, int len) {
    if (len < 1) return;

    // Save sender MAC for ACK
    memcpy(last_sender_mac, mac, 6);

    int next = (rx_head + 1) % RX_QUEUE_SIZE;
    if (next == rx_tail) return;  // queue full, drop

    rx_queue[rx_head].type = data[0];
    uint8_t payload_len = (len > 1) ? len - 1 : 0;
    if (payload_len > PROTO_MAX_PAYLOAD) payload_len = PROTO_MAX_PAYLOAD;
    if (payload_len > 0) {
        memcpy((void *)rx_queue[rx_head].payload, &data[1], payload_len);
    }
    rx_queue[rx_head].len = payload_len;
    rx_head = next;
}

void espnow_link_init() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW init failed!");
        return;
    }

    esp_now_register_recv_cb(on_recv);

    Serial.printf("ESP-NOW ready (MAC: %s)\n", WiFi.macAddress().c_str());
}

bool espnow_poll(uint8_t &type, uint8_t *payload, uint8_t &payload_len) {
    if (rx_tail == rx_head) return false;  // empty

    type = rx_queue[rx_tail].type;
    payload_len = rx_queue[rx_tail].len;
    memcpy(payload, (const void *)rx_queue[rx_tail].payload, payload_len);
    rx_tail = (rx_tail + 1) % RX_QUEUE_SIZE;
    return true;
}

bool espnow_send(MsgType type, const uint8_t *payload, uint8_t len) {
    // Ensure last sender is registered as peer
    if (!esp_now_is_peer_exist(last_sender_mac)) {
        esp_now_peer_info_t peer = {};
        memcpy(peer.peer_addr, last_sender_mac, 6);
        peer.channel = 0;
        peer.encrypt = false;
        esp_now_add_peer(&peer);
    }

    uint8_t buf[1 + PROTO_MAX_PAYLOAD];
    buf[0] = (uint8_t)type;
    if (len > 0 && payload) {
        memcpy(&buf[1], payload, len);
    }

    esp_err_t result = esp_now_send(last_sender_mac, buf, 1 + len);
    return result == ESP_OK;
}
