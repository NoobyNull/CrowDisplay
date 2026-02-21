/**
 * @file espnow_link.cpp
 * ESP-NOW wireless link for display <-> bridge communication
 *
 * Broadcasts hotkey/media key commands; receives ACKs and stats from bridge.
 * No pairing required -- bridge accepts from any peer.
 *
 * Uses a ring buffer for received messages to prevent race conditions
 * between the WiFi task receive callback and the main loop poll.
 */

#include "espnow_link.h"
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_idf_version.h>
#include <string.h>

// Broadcast address (all 0xFF)
static const uint8_t broadcast_addr[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// Ring buffer for received messages (callback -> poll)
#define RX_QUEUE_SIZE 8

struct RxMsg {
    uint8_t type;
    uint8_t payload[PROTO_MAX_PAYLOAD];
    uint8_t len;
    bool is_ack;        // true = ACK message, false = generic message
    uint8_t ack_status; // only valid when is_ack == true
};

static volatile RxMsg rx_queue[RX_QUEUE_SIZE];
static volatile int rx_head = 0;
static volatile int rx_tail = 0;

// RSSI from last received packet
static volatile int last_rssi = 0;

// ESP-NOW receive callback (runs in WiFi task context)
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
static void on_recv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    if (info->rx_ctrl) last_rssi = info->rx_ctrl->rssi;
#else
static void on_recv(const uint8_t *mac, const uint8_t *data, int len) {
#endif
    if (len < 1) return;  // need at least type byte

    int next = (rx_head + 1) % RX_QUEUE_SIZE;
    if (next == rx_tail) return;  // queue full, drop

    uint8_t msg_type = data[0];

    if (msg_type == MSG_HOTKEY_ACK && len >= 2) {
        rx_queue[rx_head].is_ack = true;
        rx_queue[rx_head].ack_status = data[1];
        rx_queue[rx_head].type = msg_type;
        rx_queue[rx_head].len = 0;
    } else {
        rx_queue[rx_head].is_ack = false;
        rx_queue[rx_head].type = msg_type;
        uint8_t plen = (len > 1) ? (uint8_t)(len - 1) : 0;
        if (plen > PROTO_MAX_PAYLOAD) plen = PROTO_MAX_PAYLOAD;
        if (plen > 0) {
            memcpy((void *)rx_queue[rx_head].payload, &data[1], plen);
        }
        rx_queue[rx_head].len = plen;
    }
    rx_head = next;  // publish only after all fields are written
}

void espnow_link_init() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    // Pin to WiFi channel 1 for deterministic coexistence with SoftAP
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW init failed!");
        return;
    }

    // Register broadcast peer
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, broadcast_addr, 6);
    peer.channel = 1;
    peer.encrypt = false;
    esp_now_add_peer(&peer);

    esp_now_register_recv_cb(on_recv);

    // Print our MAC for reference
    Serial.printf("ESP-NOW ready (MAC: %s)\n", WiFi.macAddress().c_str());
}

bool espnow_send(MsgType type, const uint8_t *payload, uint8_t len) {
    // Frame: [TYPE] [PAYLOAD...]
    uint8_t buf[1 + PROTO_MAX_PAYLOAD];
    buf[0] = (uint8_t)type;
    if (len > 0 && payload) {
        memcpy(&buf[1], payload, len);
    }

    esp_err_t result = esp_now_send(broadcast_addr, buf, 1 + len);
    return result == ESP_OK;
}

void send_hotkey_to_bridge(uint8_t modifiers, uint8_t keycode) {
    HotkeyMsg msg;
    msg.modifiers = modifiers;
    msg.keycode = keycode;
    espnow_send(MSG_HOTKEY, (uint8_t *)&msg, sizeof(msg));
    Serial.printf("ESPNOW TX: hotkey mod=0x%02X key=0x%02X\n", modifiers, keycode);
}

void send_media_key_to_bridge(uint16_t consumer_code) {
    MediaKeyMsg msg;
    msg.consumer_code = consumer_code;
    espnow_send(MSG_MEDIA_KEY, (uint8_t *)&msg, sizeof(msg));
    Serial.printf("ESPNOW TX: media key 0x%04X\n", consumer_code);
}

void send_button_press_to_bridge(uint8_t page_index, uint8_t widget_index) {
    ButtonPressMsg msg;
    msg.page_index = page_index;
    msg.widget_index = widget_index;
    espnow_send(MSG_BUTTON_PRESS, (uint8_t *)&msg, sizeof(msg));
    Serial.printf("ESPNOW TX: button press page=%d widget=%d\n", page_index, widget_index);
}

bool espnow_poll_ack(uint8_t &status) {
    // Scan ring buffer for ACK messages, skip non-ACK entries
    while (rx_tail != rx_head) {
        if (rx_queue[rx_tail].is_ack) {
            status = rx_queue[rx_tail].ack_status;
            rx_tail = (rx_tail + 1) % RX_QUEUE_SIZE;
            return true;
        }
        break;  // stop at first non-ACK; let poll_msg handle it
    }
    return false;
}

bool espnow_poll_msg(uint8_t &type, uint8_t *payload, uint8_t &payload_len) {
    while (rx_tail != rx_head) {
        if (rx_queue[rx_tail].is_ack) {
            break;  // stop at ACK; let poll_ack handle it
        }
        type = rx_queue[rx_tail].type;
        payload_len = rx_queue[rx_tail].len;
        if (payload_len > 0) {
            memcpy(payload, (const void *)rx_queue[rx_tail].payload, payload_len);
        }
        rx_tail = (rx_tail + 1) % RX_QUEUE_SIZE;
        return true;
    }
    return false;
}

int espnow_get_rssi() {
    return last_rssi;
}
