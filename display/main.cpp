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
#include "sdcard.h"
#include "config.h"
#include "config_server.h"
#include "hw_input.h"

static uint32_t touch_timer = 0;
static uint32_t last_stats_time = 0;
static bool stats_active = false;

// Power/battery timing
static uint32_t battery_timer = 0;
static uint32_t device_status_timer = 0;
static uint32_t clock_update_timer = 0;
static uint32_t last_bridge_msg_time = 0;
static const uint32_t BRIDGE_LINK_TIMEOUT_MS = 10000;  // 10s to consider link stale

// Hardware input (PCF8575 buttons + encoder) polling timer
static uint32_t encoder_timer = 0;

// Global config with program lifetime (ButtonConfig* in LVGL events point into this)
static AppConfig g_app_config;

// Deferred UI rebuild flag (set by config_server, consumed by loop)
static volatile bool g_rebuild_pending = false;

// Public accessor for global config (used by config_server to update config)
AppConfig& get_global_config() { return g_app_config; }

// Public function to request deferred UI rebuild from loop() context
void request_ui_rebuild() { g_rebuild_pending = true; }

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== Display Unit Starting ===");
    Serial.printf("PSRAM: %d bytes (free %d)\n", ESP.getPsramSize(), ESP.getFreePsram());
    Serial.printf("Heap: %d bytes (free %d)\n", ESP.getHeapSize(), ESP.getFreeHeap());

    Wire.begin(19, 20);  // I2C SDA=19, SCL=20

    touch_init();      // Create I2C mutex (must be before hw_input_init)
    display_init();    // PCA9557 touch reset + LCD init
    gt911_discover();  // Discover GT911 (after PCA9557 reset)
    bool hw_ok = hw_input_init();
    Serial.printf("[main] hw_input_init: %s\n", hw_ok ? "PCF8575 FOUND" : "NOT FOUND (hw buttons disabled)");
    lvgl_init();       // LVGL buffers + drivers

    espnow_link_init();  // ESP-NOW to bridge
    battery_init();      // Try to find MAX17048 (non-fatal if absent)
    sdcard_init();       // Mount TF Card if present (non-fatal if absent)

    // Load configuration from SD card (or use defaults)
    g_app_config = config_load();
    Serial.printf("Config: loaded profile '%s' with %zu page(s)\n",
                  g_app_config.active_profile_name.c_str(),
                  g_app_config.profiles.empty() ? 0 : g_app_config.get_active_profile()->pages.size());

    create_ui(&g_app_config);  // Build hotkey tabview UI with loaded config

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

    // Deferred UI rebuild (triggered by config upload)
    if (g_rebuild_pending) {
        g_rebuild_pending = false;
        rebuild_ui(&g_app_config);
    }

    // Config server polling (WiFi SoftAP + config upload + OTA + ArduinoOTA)
    if (config_server_active()) {
        config_server_poll();
    }

    // Handle config server inactivity timeout (auto-stopped, return to main view)
    if (config_server_timed_out()) {
        Serial.println("Config server: timed out, returning to main view");
        hide_config_screen();
    }

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

        if (msg_type == MSG_STATS && msg_len >= 1) {
            update_stats(msg_payload, msg_len);
            last_stats_time = millis();
            stats_active = true;
        }
        else if (msg_type == MSG_POWER_STATE && msg_len >= sizeof(PowerStateMsg)) {
            PowerStateMsg *ps = (PowerStateMsg *)msg_payload;
            if (ps->state == POWER_SHUTDOWN || ps->state == POWER_LOCKED) {
                power_shutdown_received();
                show_clock_mode();
            } else if (ps->state == POWER_WAKE) {
                if (power_get_state() == POWER_CLOCK) {
                    power_wake_detected();
                    show_hotkey_view();
                }
            }
        }
        else if (msg_type == MSG_TIME_SYNC && msg_len >= 4) {
            TimeSyncMsg *ts = (TimeSyncMsg *)msg_payload;
            struct timeval tv = { .tv_sec = (time_t)ts->epoch_seconds, .tv_usec = 0 };
            settimeofday(&tv, nullptr);
            // Set timezone if offset provided (msg_len >= 6 means new format with tz_offset)
            if (msg_len >= sizeof(TimeSyncMsg)) {
                int16_t offset_min = ts->tz_offset_min;
                // POSIX TZ uses inverted sign: UTC+5 = "UTC-5"
                int hours = -(offset_min / 60);
                int mins = abs(offset_min % 60);
                char tz_buf[16];
                snprintf(tz_buf, sizeof(tz_buf), "UTC%+d:%02d", hours, mins);
                setenv("TZ", tz_buf, 1);
                tzset();
            }
            Serial.printf("Time synced: %lu\n", (unsigned long)ts->epoch_seconds);
        }
        else if (msg_type == MSG_NOTIFICATION && msg_len >= sizeof(NotificationMsg)) {
            NotificationMsg *notif = (NotificationMsg *)msg_payload;
            // Safety: force null-terminate all strings
            notif->app_name[31] = '\0';
            notif->summary[99] = '\0';
            notif->body[115] = '\0';
            show_notification_toast(notif->app_name, notif->summary, notif->body);
        }
        else if (msg_type == MSG_CONFIG_MODE) {
            if (!config_server_active()) {
                Serial.println("CONFIG_MODE: starting SoftAP config server");
                config_server_start();
                show_config_screen();
            }
        }
        else if (msg_type == MSG_CONFIG_DONE) {
            if (config_server_active()) {
                Serial.println("CONFIG_DONE: stopping config server");
                config_server_stop();
                hide_config_screen();
            }
        }
    }

    // Stats timeout: mark stats as inactive if no data for 5 seconds
    if (stats_active && (millis() - last_stats_time > 5000)) {
        stats_active = false;
        Serial.println("Stats timeout -- no data");
    }

    // Hardware input polling (~20Hz, same rate as touch)
    // Reads PCF8575 via TCA9548A mux for buttons + encoder
    if (millis() - encoder_timer >= 50) {
        encoder_timer = millis();
        hw_input_poll();
    }

    // Device status + ping (every 5 seconds)
    if (millis() - device_status_timer >= 5000) {
        device_status_timer = millis();
        espnow_send(MSG_PING, nullptr, 0);  // Heartbeat to get fresh RSSI
        bool link_ok = (millis() - last_bridge_msg_time) < BRIDGE_LINK_TIMEOUT_MS;
        update_device_status(espnow_get_rssi(), link_ok, get_backlight(), stats_active);
    }

    // Clock updates every 30 seconds (clock mode screen + page clock widgets + display uptime)
    if (millis() - clock_update_timer >= 30000) {
        clock_update_timer = millis();
        if (power_get_state() == POWER_CLOCK) {
            update_clock_time();
        }
        update_page_clocks();
        update_display_uptime();
    }

    delay(5);
}
