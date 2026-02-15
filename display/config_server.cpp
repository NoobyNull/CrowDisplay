#include "config_server.h"
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include "sdcard.h"
#include "config.h"
#include "ui.h"

#define CONFIG_SSID     "CrowPanel-Config"
#define CONFIG_PASS     "crowconfig"
#define CONFIG_HOSTNAME "crowpanel-cfg"

static bool active = false;
static WebServer *web_server = nullptr;
static on_config_updated_callback_t g_callback = nullptr;

// Simple HTML upload form for configuration
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

  const statusDiv = document.getElementById('status');
  statusDiv.innerHTML = 'Uploading...';

  fetch('/api/config/upload', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      statusDiv.innerHTML = '<span style="color: #2ecc71;">✓ Configuration updated! Rebuilding UI...</span>';
      setTimeout(() => {
        statusDiv.innerHTML = '<span style="color: #3498db;">UI rebuilt. Ready to use new configuration.</span>';
      }, 2000);
    } else {
      statusDiv.innerHTML = '<span style="color: #e74c3c;">✗ Error: ' + (data.error || 'Unknown error') + '</span>';
    }
  })
  .catch(error => {
    statusDiv.innerHTML = '<span style="color: #e74c3c;">✗ Upload failed: ' + error + '</span>';
  });
}
</script>
</head>
<body>
<div class="container">
  <h2>🎛️ CrowPanel Configuration</h2>
  <div class="info">
    <strong>Upload a configuration file</strong><br>
    Select your <code>config.json</code> file to update the hotkey layout.
    The device will validate and apply the configuration without rebooting.
  </div>

  <form>
    <input type="file" id="configFile" name="config" accept=".json">
    <button type="button" onclick="uploadConfig()">Upload Configuration</button>
  </form>

  <div id="status" class="status"></div>

  <hr style="opacity: 0.2; margin: 30px 0;">
  <div class="info" style="text-align: left; font-size: 13px;">
    <strong>Configuration Format:</strong><br>
    Expected JSON structure with profiles, pages, and buttons.
    See device documentation for schema details.
  </div>
</div>
</body>
</html>)rawliteral";

// Handle GET /api/config (serves HTML form)
static void handle_config_page() {
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

        config_buffer = (uint8_t *)ps_malloc(MAX_CONFIG_SIZE);
        if (!config_buffer) {
            Serial.println("Config: malloc failed");
            return;
        }
        config_size = 0;
    }
    else if (upload.status == UPLOAD_FILE_WRITE) {
        if (config_buffer) {
            if (config_size + upload.currentSize > MAX_CONFIG_SIZE) {
                Serial.println("Config: buffer overflow");
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
        if (!config_buffer) {
            Serial.println("Config: buffer is null at EOF");
            return;
        }

        Serial.printf("Config: upload complete, %zu bytes total\n", config_size);

        // Validate JSON by attempting to parse (ArduinoJson v7)
        JsonDocument doc;
        DeserializationError error = deserializeJson(doc, config_buffer, config_size);

        if (error) {
            Serial.printf("Config: JSON parse error: %s\n", error.c_str());
            free(config_buffer);
            config_buffer = nullptr;
            return;
        }

        // Write to SD card atomically: tmp file -> validate -> rename
        if (!sdcard_write_file("/config.tmp", config_buffer, config_size)) {
            Serial.println("Config: write to /config.tmp failed");
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
            free(config_buffer);
            config_buffer = nullptr;
            return;
        }

        // Atomic rename: move tmp to config.json
        bool rename_ok = sdcard_file_rename("/config.tmp", "/config.json");
        if (!rename_ok) {
            Serial.println("Config: rename /config.tmp to /config.json failed");
            free(config_buffer);
            config_buffer = nullptr;
            return;
        }

        // Load new config into global (all LVGL widgets destroyed before rebuild in loop)
        AppConfig new_cfg = config_load();
        const ProfileConfig* profile = new_cfg.get_active_profile();
        if (!profile || profile->pages.empty()) {
            Serial.println("Config: uploaded config invalid, keeping current");
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
    bool success = true;  // Assume success if we got here (no errors in upload handler)

    if (success) {
        web_server->send(200, "application/json", "{\"success\": true}");
    } else {
        web_server->send(400, "application/json", "{\"success\": false, \"error\": \"Upload failed\"}");
    }
}

bool config_server_start() {
    if (active) return true;

    // Switch from STA to AP+STA so ESP-NOW keeps working
    WiFi.mode(WIFI_AP_STA);
    if (!WiFi.softAP(CONFIG_SSID, CONFIG_PASS)) {
        Serial.println("Config Server: SoftAP failed");
        WiFi.mode(WIFI_STA);  // revert
        return false;
    }

    Serial.printf("Config Server: SoftAP started - SSID: %s  Password: %s  IP: %s\n",
                  CONFIG_SSID, CONFIG_PASS, WiFi.softAPIP().toString().c_str());

    // Web server on port 80
    web_server = new WebServer(80);
    web_server->on("/", HTTP_GET, handle_config_page);
    web_server->on("/api/config/upload", HTTP_POST, handle_config_done, handle_config_upload);
    web_server->begin();
    Serial.println("Config Server: web server on port 80");

    active = true;
    return true;
}

void config_server_stop() {
    if (!active) return;

    if (web_server) {
        web_server->stop();
        delete web_server;
        web_server = nullptr;
    }

    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);  // back to STA-only for ESP-NOW

    active = false;
    Serial.println("Config Server: stopped");
}

void config_server_poll() {
    if (!active || !web_server) return;
    web_server->handleClient();
}

bool config_server_active() {
    return active;
}

void config_server_set_callback(on_config_updated_callback_t cb) {
    g_callback = cb;
}
