#include <Arduino.h>
#include "protocol.h"

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== Bridge Unit Starting ===");
    // Placeholder: USB HID and UART will be added in Plan 02
}

void loop() {
    delay(10);
}
