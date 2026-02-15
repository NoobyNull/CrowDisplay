/**
 * @file espnow_link.cpp
 * ESP-NOW wireless link for display -> bridge communication
 *
 * Broadcasts hotkey commands; receives ACKs from bridge.
 * No pairing required -- bridge accepts from any peer.
 */

#include "espnow_link.h"
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <string.h>

// Broadcast address (all 0xFF)
static const uint8_t broadcast_addr[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ACK receive buffer (callback -> poll)
static volatile bool ack_ready = false;
static volatile uint8_t ack_status_buf = 0;

// ESP-NOW receive callback (runs in WiFi task context)
static void on_recv(const uint8_t *mac, const uint8_t *data, int len) {
    if (len < 2) return;  // need at least type + 1 byte payload

    uint8_t msg_type = data[0];
    if (msg_type == MSG_HOTKEY_ACK && len >= 2) {
        ack_status_buf = data[1];
        ack_ready = true;
    }
}

void espnow_link_init() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW init failed!");
        return;
    }

    // Register broadcast peer
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, broadcast_addr, 6);
    peer.channel = 0;
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

bool espnow_poll_ack(uint8_t &status) {
    if (ack_ready) {
        ack_ready = false;
        status = ack_status_buf;
        return true;
    }
    return false;
}
