#include "battery.h"
#include "touch.h"   // i2c_take() / i2c_give()

#include <Arduino.h>
#include <SparkFun_MAX1704x_Fuel_Gauge_Arduino_Library.h>

static SFE_MAX1704X lipo(MAX1704X_MAX17048);
static bool fuel_gauge_present = false;

// ============================================================
// battery_init() -- probe MAX17048 on shared I2C bus
// ============================================================
bool battery_init() {
    if (!i2c_take(50)) {
        Serial.println("[battery] Failed to acquire I2C mutex for init");
        return false;
    }

    fuel_gauge_present = lipo.begin();

    i2c_give();

    if (fuel_gauge_present) {
        Serial.println("[battery] MAX17048 fuel gauge detected");
    } else {
        Serial.println("[battery] No fuel gauge found -- battery unavailable");
    }

    return fuel_gauge_present;
}

// ============================================================
// battery_read() -- read SOC + voltage (mutex-protected)
// ============================================================
BatteryState battery_read() {
    if (!fuel_gauge_present) {
        return {0xFF, 0.0f, false};
    }

    if (!i2c_take(50)) {
        // Could not acquire bus -- return stale unavailable rather than block
        return {0xFF, 0.0f, false};
    }

    float voltage = lipo.getVoltage();
    float soc     = lipo.getSOC();

    i2c_give();

    uint8_t percent = constrain((int)soc, 0, 100);
    return {percent, voltage, true};
}
