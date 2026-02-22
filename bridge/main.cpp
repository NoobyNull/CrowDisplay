#include <Arduino.h>
#include "protocol.h"
#include "usb_hid.h"
#include "espnow_link.h"
#include "status_led.h"

static uint32_t last_espnow_rx_ms = 0;
static bool in_config_mode = false;
static bool pc_asleep = false;

// Notification fragment reassembly buffer
static uint8_t notif_buf[256];  // >= sizeof(NotificationMsg)
static uint8_t notif_frags_expected = 0;
static uint8_t notif_frags_received = 0;
static uint32_t notif_start_ms = 0;
static const uint32_t NOTIF_TIMEOUT_MS = 500;  // discard stale fragments

void setup() {
    status_led_init();  // Yellow during init

    Serial.begin(115200);  // Debug output on UART0 (GPIO 43/44)
    Serial.println("=== Bridge Unit Starting ===");

    usb_hid_init();
    Serial.println("USB HID keyboard initialized");

    espnow_link_init();
    Serial.println("ESP-NOW link initialized");

    Serial.println("Bridge ready - waiting for commands");
    status_led_set_state(LED_DISCONNECTED);  // Red until ESP-NOW traffic arrives
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
                        pc_asleep = (payload[0] != POWER_WAKE);
                        if (pc_asleep) {
                            status_led_set_state(LED_SLEEP);
                        }
                        Serial.printf("POWER: relayed state=%d\n", payload[0]);
                    }
                    break;
                case MSG_TIME_SYNC:
                    if (payload_len >= sizeof(TimeSyncMsg)) {
                        espnow_send(MSG_TIME_SYNC, payload, sizeof(TimeSyncMsg));
                        Serial.println("TIME: relayed to display");
                    }
                    break;
                case MSG_NOTIFICATION: {
                    // Fragmented: payload[0] = frag header (seq<<4 | total), payload[1..] = data
                    if (payload_len < 2) break;
                    uint8_t frag_header = payload[0];
                    uint8_t seq = frag_header >> 4;
                    uint8_t total = frag_header & 0x0F;
                    uint8_t *frag_data = payload + 1;
                    size_t frag_len = payload_len - 1;

                    // Reset if new sequence or timeout
                    if (seq == 0 || total != notif_frags_expected ||
                        (millis() - notif_start_ms > NOTIF_TIMEOUT_MS && notif_frags_received > 0)) {
                        memset(notif_buf, 0, sizeof(notif_buf));
                        notif_frags_expected = total;
                        notif_frags_received = 0;
                        notif_start_ms = millis();
                    }

                    // Copy fragment data into reassembly buffer
                    size_t offset = (size_t)seq * 61;  // 61 bytes per fragment
                    if (offset + frag_len <= sizeof(notif_buf)) {
                        memcpy(notif_buf + offset, frag_data, frag_len);
                    }
                    notif_frags_received++;

                    if (notif_frags_received >= notif_frags_expected) {
                        // All fragments received — relay complete notification
                        espnow_send(MSG_NOTIFICATION, notif_buf, sizeof(NotificationMsg));
                        Serial.printf("NOTIF: reassembled %d frags, relayed %d bytes\n",
                                      notif_frags_expected, (int)sizeof(NotificationMsg));
                        notif_frags_expected = 0;
                        notif_frags_received = 0;
                    } else {
                        Serial.printf("NOTIF: frag %d/%d\n", seq + 1, total);
                    }
                    break;
                }
                case MSG_CONFIG_MODE:
                    espnow_send(MSG_CONFIG_MODE, nullptr, 0);
                    in_config_mode = true;
                    status_led_set_state(LED_CONFIG_MODE);
                    Serial.println("CONFIG_MODE: relayed to display");
                    break;
                case MSG_CONFIG_DONE:
                    espnow_send(MSG_CONFIG_DONE, nullptr, 0);
                    in_config_mode = false;
                    Serial.println("CONFIG_DONE: relayed to display");
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
        last_espnow_rx_ms = millis();

        switch (msg_type) {
            case MSG_HOTKEY: {
                if (payload_len >= sizeof(HotkeyMsg)) {
                    HotkeyMsg *cmd = (HotkeyMsg *)payload;
                    Serial.printf("CMD: hotkey mod=0x%02X key=0x%02X\n",
                                  cmd->modifiers, cmd->keycode);
                    fire_keystroke(cmd->modifiers, cmd->keycode);
                    status_led_flash();

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
                    status_led_flash();
                } else {
                    Serial.printf("ERR: media key payload too short (%d)\n", payload_len);
                }
                break;
            }
            case MSG_BUTTON_PRESS: {
                if (payload_len >= sizeof(ButtonPressMsg)) {
                    // Immediately ACK display (fast visual feedback)
                    HotkeyAckMsg ack = { 0 };
                    espnow_send(MSG_HOTKEY_ACK, (uint8_t *)&ack, sizeof(ack));

                    // Relay to companion via vendor HID INPUT report
                    send_vendor_report(MSG_BUTTON_PRESS, payload, sizeof(ButtonPressMsg));
                    Serial.printf("BTN: page=%d widget=%d -> companion\n",
                                  payload[0], payload[1]);
                }
                break;
            }
            case MSG_DDC_CMD: {
                if (payload_len >= sizeof(DdcCmdMsg)) {
                    // Relay DDC command to companion via vendor HID
                    send_vendor_report(MSG_DDC_CMD, payload, sizeof(DdcCmdMsg));
                    Serial.println("DDC: relayed to companion");
                    status_led_flash();
                } else {
                    Serial.printf("ERR: DDC payload too short (%d)\n", payload_len);
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

    // Update LED state: sleep overrides everything, then config mode, then connection
    if (pc_asleep) {
        status_led_set_state(LED_SLEEP);
    } else if (!in_config_mode) {
        if (last_espnow_rx_ms > 0 && millis() - last_espnow_rx_ms < 5000) {
            status_led_set_state(LED_CONNECTED);
        } else {
            status_led_set_state(LED_DISCONNECTED);
        }
    }

    status_led_update();
    delay(1);  // Yield to other tasks; keep responsive
}
