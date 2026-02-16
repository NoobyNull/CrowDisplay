#include "config_server.h"
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoOTA.h>
#include <Update.h>
#include <esp_wifi.h>
#include <ArduinoJson.h>
#include "sdcard.h"
#include "config.h"
#include "ui.h"

#define CONFIG_SSID     "CrowPanel-Config"
#define CONFIG_PASS     "crowconfig"
#define CONFIG_HOSTNAME "crowpanel"
#define CONFIG_CHANNEL  1
#define INACTIVITY_TIMEOUT_MS (5 * 60 * 1000)

static bool active = false;
static WebServer *web_server = nullptr;
static on_config_updated_callback_t g_callback = nullptr;

// Inactivity tracking
static uint32_t last_activity_time = 0;

// Inactivity timeout latch (cleared on read)
static bool g_timed_out = false;

// Upload error propagation state
static bool g_upload_success = false;
static String g_upload_error = "";

// Simple HTML upload form for configuration + OTA
static const char config_html[] PROGMEM = R"rawliteral(
<!DOCTYPE html><html><head><title>CrowPanel Config</title>
<style>
body {
  font-family: sans-serif;
  max-width: 600px;
  margin: 40px auto;
  padding: 20px;
  text-align: center;
  background: #1a1a2e;
  color: #eee;
}
h2 { color: #3498db; }
.container { background: #16213e; padding: 30px; border-radius: 8px; }
input[type=file] { margin: 20px 0; display: block; }
button {
  padding: 12px 40px;
  font-size: 16px;
  background: #2ecc71;
  border: none;
  color: #fff;
  border-radius: 8px;
  cursor: pointer;
  margin: 10px;
}
button:hover { background: #27ae60; }
.info {
  margin: 20px 0;
  padding: 15px;
  background: #0f3460;
  border-left: 4px solid #3498db;
  text-align: left;
  border-radius: 4px;
}
.status { margin: 15px 0; font-size: 14px; color: #bdc3c7; }
code { background: #0f3460; padding: 2px 6px; border-radius: 3px; font-family: monospace; }
hr { opacity: 0.2; margin: 30px 0; }
</style>
<script>
function uploadConfig() {
  const fileInput = document.getElementById('configFile');
  if (!fileInput.files.length) {
    alert('Please select a config.json file');
    return;
  }

  const formData = new FormData();
  formData.append('config', fileInput.files[0]);

  const statusDiv = document.getElementById('configStatus');
  statusDiv.innerHTML = 'Uploading...';

  fetch('/api/config/upload', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      statusDiv.innerHTML = '<span style="color: #2ecc71;">&#10003; Configuration updated! Rebuilding UI...</span>';
      setTimeout(() => {
        statusDiv.innerHTML = '<span style="color: #3498db;">UI rebuilt. Ready to use new configuration.</span>';
      }, 2000);
    } else {
      statusDiv.innerHTML = '<span style="color: #e74c3c;">&#10007; Error: ' + (data.error || 'Unknown error') + '</span>';
    }
  })
  .catch(error => {
    statusDiv.innerHTML = '<span style="color: #e74c3c;">&#10007; Upload failed: ' + error + '</span>';
  });
}

function uploadFirmware() {
  const fileInput = document.getElementById('firmwareFile');
  if (!fileInput.files.length) {
    alert('Please select a .bin firmware file');
    return;
  }

  const formData = new FormData();
  formData.append('firmware', fileInput.files[0]);

  const statusDiv = document.getElementById('otaStatus');
  statusDiv.innerHTML = 'Uploading firmware...';

  fetch('/update', {
    method: 'POST',
    body: formData
  })
  .then(response => response.text())
  .then(data => {
    if (data.indexOf('OK') >= 0) {
      statusDiv.innerHTML = '<span style="color: #2ecc71;">&#10003; Firmware updated! Rebooting...</span>';
    } else {
      statusDiv.innerHTML = '<span style="color: #e74c3c;">&#10007; Firmware update failed</span>';
    }
  })
  .catch(error => {
    statusDiv.innerHTML = '<span style="color: #e74c3c;">&#10007; Upload failed: ' + error + '</span>';
  });
}
</script>
</head>
<body>
<div class="container">
  <h2>CrowPanel Configuration</h2>

  <div class="info">
    <strong>Upload a configuration file</strong><br>
    Select your <code>config.json</code> file to update the hotkey layout.
    The device will validate and apply the configuration without rebooting.
  </div>

  <form>
    <input type="file" id="configFile" name="config" accept=".json">
    <button type="button" onclick="uploadConfig()">Upload Configuration</button>
  </form>

  <div id="configStatus" class="status"></div>

  <hr>

  <div class="info">
    <strong>Firmware Update (OTA)</strong><br>
    Select a <code>.bin</code> firmware file to update the device.
    The device will reboot after a successful update.
  </div>

  <form>
    <input type="file" id="firmwareFile" name="firmware" accept=".bin">
    <button type="button" onclick="uploadFirmware()">Upload Firmware</button>
  </form>

  <div id="otaStatus" class="status"></div>

  <hr>
  <div class="info" style="text-align: left; font-size: 13px;">
    <strong>PlatformIO OTA:</strong><br>
    <code>pio run -t upload --upload-port &lt;IP&gt;</code>
  </div>
</div>
</body>
</html>)rawliteral";

// Handle GET /api/health (lightweight probe)
static void handle_health() {
    last_activity_time = millis();
    web_server->send(200, "application/json", "{\"status\":\"ok\"}");
}

// Handle GET / (serves HTML form)
static void handle_config_page() {
    last_activity_time = millis();
    web_server->send_P(200, "text/html", config_html);
}

// Handle POST /api/config/upload (multipart form data)
static void handle_config_upload() {
    HTTPUpload &upload = web_server->upload();
    static uint8_t *config_buffer = nullptr;
    static size_t config_size = 0;
    static const size_t MAX_CONFIG_SIZE = 65536;  // 64KB max config

    if (upload.status == UPLOAD_FILE_START) {
        Serial.printf("Config: receiving %s\n", upload.filename.c_str());
        last_activity_time = millis();

        // Reset error state
        g_upload_success = false;
        g_upload_error = "";

        config_buffer = (uint8_t *)ps_malloc(MAX_CONFIG_SIZE);
        if (!config_buffer) {
            Serial.println("Config: malloc failed");
            g_upload_error = "Memory allocation failed";
            return;
        }
        config_size = 0;
    }
    else if (upload.status == UPLOAD_FILE_WRITE) {
        last_activity_time = millis();
        if (config_buffer) {
            if (config_size + upload.currentSize > MAX_CONFIG_SIZE) {
                Serial.println("Config: buffer overflow");
                g_upload_error = "Config file too large (max 64KB)";
                free(config_buffer);
                config_buffer = nullptr;
                config_size = 0;
                return;
            }
            memcpy(config_buffer + config_size, upload.buf, upload.currentSize);
            config_size += upload.currentSize;
            Serial.printf("Config: received %zu bytes so far\n", config_size);
        }
    }
    else if (upload.status == UPLOAD_FILE_END) {
        last_activity_time = millis();
        if (!config_buffer) {
            Serial.println("Config: buffer is null at EOF");
            if (g_upload_error.isEmpty()) g_upload_error = "Upload buffer lost";
            return;
        }

        Serial.printf("Config: upload complete, %zu bytes total\n", config_size);

        // Validate JSON by attempting to parse (ArduinoJson v7)
        JsonDocument doc;
        DeserializationError error = deserializeJson(doc, config_buffer, config_size);

        if (error) {
            Serial.printf("Config: JSON parse error: %s\n", error.c_str());
            g_upload_error = String("JSON parse error: ") + error.c_str();
            free(config_buffer);
            config_buffer = nullptr;
            return;
        }

        // Write to SD card atomically: tmp file -> validate -> rename
        if (!sdcard_write_file("/config.tmp", config_buffer, config_size)) {
            Serial.println("Config: write to /config.tmp failed");
            g_upload_error = "SD card write failed";
            free(config_buffer);
            config_buffer = nullptr;
            return;
        }

        Serial.println("Config: wrote /config.tmp, validating...");

        // Re-parse from buffer already in memory to validate schema
        JsonDocument validate_doc;
        DeserializationError validate_error = deserializeJson(validate_doc, config_buffer, config_size);
        if (validate_error) {
            Serial.printf("Config: validation parse error: %s\n", validate_error.c_str());
            g_upload_error = String("Validation error: ") + validate_error.c_str();
            free(config_buffer);
            config_buffer = nullptr;
            return;
        }

        // Atomic rename: move tmp to config.json
        bool rename_ok = sdcard_file_rename("/config.tmp", "/config.json");
        if (!rename_ok) {
            Serial.println("Config: rename /config.tmp to /config.json failed");
            g_upload_error = "SD card rename failed";
            free(config_buffer);
            config_buffer = nullptr;
            return;
        }

        // Load new config into global (all LVGL widgets destroyed before rebuild in loop)
        AppConfig new_cfg = config_load();
        const ProfileConfig* profile = new_cfg.get_active_profile();
        if (!profile || profile->pages.empty()) {
            Serial.println("Config: uploaded config invalid, keeping current");
            g_upload_error = "Config loaded but has no valid pages";
            free(config_buffer);
            config_buffer = nullptr;
            return;
        }

        // Update global config (ButtonConfig* pointers invalidated on rebuild)
        get_global_config() = new_cfg;
        Serial.printf("Config: loaded updated config, profile: %s, %zu pages\n",
                      new_cfg.active_profile_name.c_str(), profile->pages.size());

        // Request deferred rebuild (will execute from loop context)
        request_ui_rebuild();
        Serial.println("Config: rebuild requested");

        // Mark upload as successful
        g_upload_success = true;

        // Call user callback if registered
        if (g_callback) {
            g_callback();
        }

        free(config_buffer);
        config_buffer = nullptr;
    }
}

// Handle POST /api/config/upload completion (returns JSON response)
static void handle_config_done() {
    if (g_upload_success) {
        web_server->send(200, "application/json", "{\"success\": true}");
    } else {
        String response = "{\"success\": false, \"error\": \"" + g_upload_error + "\"}";
        web_server->send(400, "application/json", response);
    }
}

// Handle POST /update (OTA firmware upload)
static void handle_ota_upload() {
    HTTPUpload &upload = web_server->upload();
    last_activity_time = millis();

    if (upload.status == UPLOAD_FILE_START) {
        Serial.printf("OTA: receiving %s\n", upload.filename.c_str());
        if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
            Update.printError(Serial);
        }
    } else if (upload.status == UPLOAD_FILE_WRITE) {
        if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
            Update.printError(Serial);
        }
    } else if (upload.status == UPLOAD_FILE_END) {
        if (Update.end(true)) {
            Serial.printf("OTA: success, %u bytes\n", upload.totalSize);
        } else {
            Update.printError(Serial);
        }
    }
}

static void handle_ota_done() {
    bool ok = !Update.hasError();
    web_server->send(200, "text/html",
        ok ? "<h2>Update OK! Rebooting...</h2>"
           : "<h2>Update FAILED</h2>");
    if (ok) {
        delay(500);
        ESP.restart();
    }
}

// ============================================================
// Image Upload Endpoint: POST /api/image/upload
// ============================================================
static uint8_t *g_image_buffer = nullptr;
static size_t g_image_size = 0;
static String g_image_filename = "";
static bool g_image_upload_success = false;
static String g_image_upload_error = "";
static const size_t MAX_IMAGE_SIZE = 102400;  // 100KB max

static void handle_image_upload() {
    HTTPUpload &upload = web_server->upload();

    if (upload.status == UPLOAD_FILE_START) {
        Serial.printf("Image: receiving %s\n", upload.filename.c_str());
        last_activity_time = millis();

        g_image_upload_success = false;
        g_image_upload_error = "";
        g_image_filename = upload.filename;

        g_image_buffer = (uint8_t *)ps_malloc(MAX_IMAGE_SIZE);
        if (!g_image_buffer) {
            g_image_upload_error = "Memory allocation failed";
            return;
        }
        g_image_size = 0;
    }
    else if (upload.status == UPLOAD_FILE_WRITE) {
        last_activity_time = millis();
        if (g_image_buffer) {
            if (g_image_size + upload.currentSize > MAX_IMAGE_SIZE) {
                g_image_upload_error = "Image too large (max 100KB)";
                free(g_image_buffer);
                g_image_buffer = nullptr;
                g_image_size = 0;
                return;
            }
            memcpy(g_image_buffer + g_image_size, upload.buf, upload.currentSize);
            g_image_size += upload.currentSize;
        }
    }
    else if (upload.status == UPLOAD_FILE_END) {
        last_activity_time = millis();
        if (!g_image_buffer) {
            if (g_image_upload_error.isEmpty()) g_image_upload_error = "Upload buffer lost";
            return;
        }

        // Ensure /icons directory exists
        sdcard_mkdir("/icons");

        // Build destination path
        String dest_path = "/icons/" + g_image_filename;

        if (!sdcard_write_file(dest_path.c_str(), g_image_buffer, g_image_size)) {
            g_image_upload_error = "SD card write failed";
            free(g_image_buffer);
            g_image_buffer = nullptr;
            return;
        }

        Serial.printf("Image: saved %s (%zu bytes)\n", dest_path.c_str(), g_image_size);
        g_image_upload_success = true;

        free(g_image_buffer);
        g_image_buffer = nullptr;
    }
}

static void handle_image_done() {
    if (g_image_upload_success) {
        String path = "/icons/" + g_image_filename;
        String response = "{\"success\":true,\"path\":\"" + path + "\"}";
        web_server->send(200, "application/json", response);
    } else {
        String response = "{\"success\":false,\"error\":\"" + g_image_upload_error + "\"}";
        web_server->send(400, "application/json", response);
    }
}

bool config_server_start() {
    if (active) return true;

    // Switch from STA to AP+STA so ESP-NOW keeps working
    WiFi.mode(WIFI_AP_STA);
    if (!WiFi.softAP(CONFIG_SSID, CONFIG_PASS, CONFIG_CHANNEL)) {
        Serial.println("Config Server: SoftAP failed");
        WiFi.mode(WIFI_STA);  // revert
        return false;
    }

    // Re-pin channel after softAP start
    esp_wifi_set_channel(CONFIG_CHANNEL, WIFI_SECOND_CHAN_NONE);

    Serial.printf("Config Server: SoftAP started - SSID: %s  Password: %s  IP: %s  Channel: %d\n",
                  CONFIG_SSID, CONFIG_PASS, WiFi.softAPIP().toString().c_str(), CONFIG_CHANNEL);

    // ArduinoOTA (for PlatformIO upload)
    ArduinoOTA.setHostname(CONFIG_HOSTNAME);
    ArduinoOTA.onStart([]() { Serial.println("OTA: start"); });
    ArduinoOTA.onEnd([]()   { Serial.println("OTA: done, rebooting"); });
    ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
        Serial.printf("OTA: %u%%\r", progress * 100 / total);
    });
    ArduinoOTA.onError([](ota_error_t error) {
        Serial.printf("OTA: error %u\n", error);
    });
    ArduinoOTA.begin();

    // Web server on port 80
    web_server = new WebServer(80);
    web_server->on("/", HTTP_GET, handle_config_page);
    web_server->on("/api/health", HTTP_GET, handle_health);
    web_server->on("/api/config/upload", HTTP_POST, handle_config_done, handle_config_upload);
    web_server->on("/api/image/upload", HTTP_POST, handle_image_done, handle_image_upload);
    web_server->on("/update", HTTP_POST, handle_ota_done, handle_ota_upload);
    web_server->begin();
    Serial.println("Config Server: web server on port 80");

    last_activity_time = millis();
    active = true;
    return true;
}

void config_server_stop() {
    if (!active) return;

    ArduinoOTA.end();

    if (web_server) {
        web_server->stop();
        delete web_server;
        web_server = nullptr;
    }

    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);  // back to STA-only for ESP-NOW

    // Re-pin ESP-NOW channel after WiFi mode transition
    esp_wifi_set_channel(CONFIG_CHANNEL, WIFI_SECOND_CHAN_NONE);

    active = false;
    Serial.println("Config Server: stopped");
}

void config_server_poll() {
    if (!active || !web_server) return;

    ArduinoOTA.handle();
    web_server->handleClient();

    // Track client connections as activity
    if (WiFi.softAPgetStationNum() > 0) {
        last_activity_time = millis();
    }

    // Inactivity timeout: auto-stop after 5 minutes
    if (millis() - last_activity_time > INACTIVITY_TIMEOUT_MS) {
        Serial.println("Config Server: inactivity timeout, auto-stopping");
        config_server_stop();
        g_timed_out = true;
    }
}

bool config_server_active() {
    return active;
}

bool config_server_timed_out() {
    if (g_timed_out) {
        g_timed_out = false;
        return true;
    }
    return false;
}

void config_server_set_callback(on_config_updated_callback_t cb) {
    g_callback = cb;
}
