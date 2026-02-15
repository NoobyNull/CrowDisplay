#include <Arduino.h>
#include "protocol.h"
#include "usb_hid.h"
#include "uart_link.h"

void setup() {
    Serial.begin(115200);  // Debug output on UART0 (GPIO 43/44)
    Serial.println("=== Bridge Unit Starting ===");

    usb_hid_init();
    Serial.println("USB HID keyboard initialized");

    uart_link_init();
    Serial.println("UART link initialized");

    Serial.println("Bridge ready - waiting for commands");
}

void loop() {
    uint8_t msg_type;
    uint8_t payload[PROTO_MAX_PAYLOAD];
    uint8_t payload_len;

    if (uart_poll(msg_type, payload, payload_len)) {
        switch (msg_type) {
            case MSG_HOTKEY: {
                if (payload_len >= sizeof(HotkeyMsg)) {
                    HotkeyMsg *cmd = (HotkeyMsg *)payload;
                    Serial.printf("CMD: hotkey mod=0x%02X key=0x%02X\n",
                                  cmd->modifiers, cmd->keycode);
                    fire_keystroke(cmd->modifiers, cmd->keycode);

                    // Send ACK
                    HotkeyAckMsg ack = { 0 };  // status = 0 (success)
                    uart_send(MSG_HOTKEY_ACK, (uint8_t *)&ack, sizeof(ack));
                } else {
                    Serial.printf("ERR: hotkey payload too short (%d)\n", payload_len);
                    HotkeyAckMsg ack = { 1 };  // status = 1 (error)
                    uart_send(MSG_HOTKEY_ACK, (uint8_t *)&ack, sizeof(ack));
                }
                break;
            }
            default:
                Serial.printf("WARN: unknown msg type 0x%02X\n", msg_type);
                break;
        }
    }

    delay(1);  // Yield to other tasks; keep responsive
}
