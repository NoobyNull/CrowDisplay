#include <Arduino.h>
#include <Wire.h>
#include <lvgl.h>
#include <sys/time.h>
#include "display_hw.h"
#include "touch.h"
#include "ui.h"
#include "espnow_link.h"
#include "protocol.h"
#include "battery.h"
#include "power.h"

static uint32_t touch_timer = 0;
static uint32_t last_stats_time = 0;
static bool stats_active = false;

// Power/battery timing
static uint32_t battery_timer = 0;
static uint32_t device_status_timer = 0;
static uint32_t clock_update_timer = 0;
static uint32_t last_bridge_msg_time = 0;
static const uint32_t BRIDGE_LINK_TIMEOUT_MS = 10000;  // 10s to consider link stale

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== Display Unit Starting ===");

    Wire.begin(19, 20);  // I2C SDA=19, SCL=20

    touch_init();      // Create I2C mutex
    display_init();    // PCA9557 touch reset + LCD init
    gt911_discover();  // Discover GT911 (after PCA9557 reset)
    lvgl_init();       // LVGL buffers + drivers

    espnow_link_init();  // ESP-NOW to bridge
    battery_init();      // Try to find MAX17048 (non-fatal if absent)

    create_ui();       // Build hotkey tabview UI

    power_init();      // Set initial power state to ACTIVE

    Serial.println("Display setup complete");
}

void loop() {
    // Poll touch at ~20Hz
    if (millis() - touch_timer >= 50) {
        touch_timer = millis();
        touch_poll();
        // Touch activity resets idle timer (cheap millis() assignment)
        power_activity();
    }

    // Drive LVGL
    lvgl_tick();

    // Power state machine update (checks idle timeout)
    power_update();

    // Check for ACK from bridge (non-blocking)
    uint8_t ack_status;
    if (espnow_poll_ack(ack_status)) {
        Serial.printf("ACK: status=%d\n", ack_status);
        last_bridge_msg_time = millis();
        power_activity();
    }

    // Poll for incoming messages (MSG_STATS, MSG_POWER_STATE, MSG_TIME_SYNC, etc.)
    uint8_t msg_type;
    uint8_t msg_payload[PROTO_MAX_PAYLOAD];
    uint8_t msg_len;
    if (espnow_poll_msg(msg_type, msg_payload, msg_len)) {
        last_bridge_msg_time = millis();
        power_activity();

        // Wake detection: if in CLOCK mode and a non-shutdown message arrives, wake up
        if (power_get_state() == POWER_CLOCK && msg_type != MSG_POWER_STATE) {
            power_wake_detected();
            show_hotkey_view();
        }

        if (msg_type == MSG_STATS && msg_len >= sizeof(StatsPayload)) {
            update_stats((const StatsPayload *)msg_payload);
            last_stats_time = millis();
            stats_active = true;
        }
        else if (msg_type == MSG_POWER_STATE && msg_len >= sizeof(PowerStateMsg)) {
            PowerStateMsg *ps = (PowerStateMsg *)msg_payload;
            if (ps->state == POWER_SHUTDOWN) {
                power_shutdown_received();
                show_clock_mode();
            }
            // POWER_WAKE is handled implicitly (any bridge message = wake, handled above)
        }
        else if (msg_type == MSG_TIME_SYNC && msg_len >= sizeof(TimeSyncMsg)) {
            TimeSyncMsg *ts = (TimeSyncMsg *)msg_payload;
            struct timeval tv = { .tv_sec = (time_t)ts->epoch_seconds, .tv_usec = 0 };
            settimeofday(&tv, nullptr);
            Serial.printf("Time synced: %lu\n", (unsigned long)ts->epoch_seconds);
        }
    }

    // Stats timeout: hide header if no stats received for 5 seconds
    if (stats_active && (millis() - last_stats_time > 5000)) {
        hide_stats_header();
        stats_active = false;
        Serial.println("Stats timeout -- header hidden");
    }

    // Device status update (every 5 seconds)
    if (millis() - device_status_timer >= 5000) {
        device_status_timer = millis();
        BatteryState bat = battery_read();
        bool link_ok = (millis() - last_bridge_msg_time) < BRIDGE_LINK_TIMEOUT_MS;
        update_device_status(bat.percent, link_ok, get_backlight());
    }

    // Clock mode: update time display every 30 seconds
    if (power_get_state() == POWER_CLOCK && (millis() - clock_update_timer >= 30000)) {
        clock_update_timer = millis();
        update_clock_time();
    }

    delay(5);
}
