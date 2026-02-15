#pragma once
#include <cstdint>

struct BatteryState {
    uint8_t percent;    // 0-100, or 0xFF if unavailable
    float   voltage;    // Volts (e.g., 3.85), 0.0 if unavailable
    bool    available;  // false if no fuel gauge detected
};

bool battery_init();            // Init MAX17048 on I2C bus (mutex-protected). Returns true if found.
BatteryState battery_read();    // Read current state (mutex-protected). Call every 10-30s, not every loop.
