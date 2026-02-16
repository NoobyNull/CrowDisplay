#include <Arduino.h>
#include "protocol.h"
#include "usb_hid.h"
#include "espnow_link.h"

void setup() {
    Serial.begin(115200);  // Debug output on UART0 (GPIO 43/44)
    Serial.println("=== Bridge Unit Starting ===");

    usb_hid_init();
    Serial.println("USB HID keyboard initialized");

    espnow_link_init();
    Serial.println("ESP-NOW link initialized");

    Serial.println("Bridge ready - waiting for commands");
}

void loop() {
    // --- Poll USB Vendor HID for incoming messages from companion app ---
    // Protocol: [msg_type byte] [payload...]
    // Requires companion to send type-prefixed HID reports (MSG_STATS byte before payload)
    uint8_t vendor_buf[63];
    size_t vendor_len = 0;
    if (poll_vendor_hid(vendor_buf, vendor_len)) {
        if (vendor_len >= 1) {
            uint8_t msg_type = vendor_buf[0];
            uint8_t *payload = vendor_buf + 1;
            size_t payload_len = vendor_len - 1;

            switch (msg_type) {
                case MSG_STATS:
                    if (payload_len >= 1) {
                        espnow_send(MSG_STATS, payload, payload_len);
                        Serial.printf("STATS: relayed %zu bytes to display\n", payload_len);
                    }
                    break;
                case MSG_POWER_STATE:
                    if (payload_len >= sizeof(PowerStateMsg)) {
                        espnow_send(MSG_POWER_STATE, payload, sizeof(PowerStateMsg));
                        Serial.printf("POWER: relayed state=%d\n", payload[0]);
                    }
                    break;
                case MSG_TIME_SYNC:
                    if (payload_len >= sizeof(TimeSyncMsg)) {
                        espnow_send(MSG_TIME_SYNC, payload, sizeof(TimeSyncMsg));
                        Serial.println("TIME: relayed to display");
                    }
                    break;
                case MSG_NOTIFICATION:
                    if (payload_len >= sizeof(NotificationMsg)) {
                        espnow_send(MSG_NOTIFICATION, payload, sizeof(NotificationMsg));
                        Serial.printf("NOTIF: relayed (%d bytes)\n", (int)sizeof(NotificationMsg));
                    }
                    break;
                default:
                    Serial.printf("VENDOR: unknown type 0x%02X len=%zu\n", msg_type, vendor_len);
                    break;
            }
        }
    }

    // --- Poll ESP-NOW for incoming messages from display ---
    uint8_t msg_type;
    uint8_t payload[PROTO_MAX_PAYLOAD];
    uint8_t payload_len;

    if (espnow_poll(msg_type, payload, payload_len)) {
        switch (msg_type) {
            case MSG_HOTKEY: {
                if (payload_len >= sizeof(HotkeyMsg)) {
                    HotkeyMsg *cmd = (HotkeyMsg *)payload;
                    Serial.printf("CMD: hotkey mod=0x%02X key=0x%02X\n",
                                  cmd->modifiers, cmd->keycode);
                    fire_keystroke(cmd->modifiers, cmd->keycode);

                    // Send ACK
                    HotkeyAckMsg ack = { 0 };  // status = 0 (success)
                    espnow_send(MSG_HOTKEY_ACK, (uint8_t *)&ack, sizeof(ack));
                } else {
                    Serial.printf("ERR: hotkey payload too short (%d)\n", payload_len);
                    HotkeyAckMsg ack = { 1 };  // status = 1 (error)
                    espnow_send(MSG_HOTKEY_ACK, (uint8_t *)&ack, sizeof(ack));
                }
                break;
            }
            case MSG_MEDIA_KEY: {
                if (payload_len >= sizeof(MediaKeyMsg)) {
                    MediaKeyMsg *cmd = (MediaKeyMsg *)payload;
                    Serial.printf("CMD: media key 0x%04X\n", cmd->consumer_code);
                    fire_media_key(cmd->consumer_code);
                } else {
                    Serial.printf("ERR: media key payload too short (%d)\n", payload_len);
                }
                break;
            }
            case MSG_PING: {
                HotkeyAckMsg ack = { 0 };
                espnow_send(MSG_HOTKEY_ACK, (uint8_t *)&ack, sizeof(ack));
                break;
            }
            default:
                Serial.printf("WARN: unknown msg type 0x%02X\n", msg_type);
                break;
        }
    }

    delay(1);  // Yield to other tasks; keep responsive
}
