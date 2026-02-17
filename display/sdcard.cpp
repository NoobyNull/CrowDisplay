#include "sdcard.h"
#include <Arduino.h>
#include <SPI.h>
#include <SD.h>

// CrowPanel 7.0" TF Card slot SPI pins
#define SD_CS   10
#define SD_MOSI 11
#define SD_CLK  12
#define SD_MISO 13

static SPIClass sd_spi(HSPI);
static bool mounted = false;

bool sdcard_init() {
    sd_spi.begin(SD_CLK, SD_MISO, SD_MOSI, SD_CS);

    if (!SD.begin(SD_CS, sd_spi, 4000000)) {  // 4 MHz SPI clock
        Serial.println("SD: mount failed");
        mounted = false;
        return false;
    }

    uint8_t cardType = SD.cardType();
    if (cardType == CARD_NONE) {
        Serial.println("SD: no card detected");
        mounted = false;
        return false;
    }

    const char *typeStr = "UNKNOWN";
    if (cardType == CARD_MMC)       typeStr = "MMC";
    else if (cardType == CARD_SD)   typeStr = "SD";
    else if (cardType == CARD_SDHC) typeStr = "SDHC";

    uint64_t cardSize = SD.cardSize() / (1024 * 1024);
    Serial.printf("SD: %s card, %llu MB\n", typeStr, cardSize);
    mounted = true;
    return true;
}

bool sdcard_mounted() {
    return mounted;
}

uint32_t sdcard_size_mb() {
    if (!mounted) return 0;
    return (uint32_t)(SD.cardSize() / (1024 * 1024));
}

int sdcard_read_file(const char *path, uint8_t *buf, size_t max_len) {
    if (!mounted) return -1;

    File f = SD.open(path, FILE_READ);
    if (!f) {
        Serial.printf("SD: open failed: %s\n", path);
        return -1;
    }

    size_t fileSize = f.size();
    size_t toRead = (fileSize < max_len) ? fileSize : max_len;
    int bytesRead = f.read(buf, toRead);
    f.close();
    return bytesRead;
}

bool sdcard_write_file(const char *path, const uint8_t *data, size_t len) {
    if (!mounted) return false;

    File f = SD.open(path, FILE_WRITE);
    if (!f) {
        Serial.printf("SD: create failed: %s\n", path);
        return false;
    }

    size_t written = f.write(data, len);
    f.close();

    if (written != len) {
        Serial.printf("SD: write incomplete: %zu/%zu\n", written, len);
        return false;
    }
    return true;
}

bool sdcard_file_exists(const char *path) {
    if (!mounted) return false;
    return SD.exists(path);
}

bool sdcard_file_remove(const char *path) {
    if (!mounted) return false;
    if (!SD.exists(path)) return true;  // Already gone
    if (!SD.remove(path)) {
        Serial.printf("SD: remove failed: %s\n", path);
        return false;
    }
    return true;
}

bool sdcard_file_rename(const char *old_path, const char *new_path) {
    if (!mounted) return false;

    if (!SD.exists(old_path)) {
        Serial.printf("SD: rename source not found: %s\n", old_path);
        return false;
    }

    // SD.rename() fails if destination exists — remove it first
    if (SD.exists(new_path)) {
        SD.remove(new_path);
    }
    if (!SD.rename(old_path, new_path)) {
        Serial.printf("SD: rename failed: %s -> %s\n", old_path, new_path);
        return false;
    }

    Serial.printf("SD: renamed %s -> %s\n", old_path, new_path);
    return true;
}

bool sdcard_mkdir(const char *path) {
    if (!mounted) return false;
    if (SD.exists(path)) return true;  // Already exists

    if (!SD.mkdir(path)) {
        Serial.printf("SD: mkdir failed: %s\n", path);
        return false;
    }
    Serial.printf("SD: created directory %s\n", path);
    return true;
}

int sdcard_list_dir(const char* path, sdcard_dir_callback_t cb, void* user_data) {
    if (!mounted) return -1;
    File dir = SD.open(path);
    if (!dir || !dir.isDirectory()) return -1;
    int count = 0;
    File entry;
    while ((entry = dir.openNextFile())) {
        if (cb) cb(entry.name(), entry.size(), entry.isDirectory(), user_data);
        count++;
        entry.close();
    }
    dir.close();
    return count;
}

bool sdcard_get_usage(uint64_t* total_bytes, uint64_t* used_bytes) {
    if (!mounted) return false;
    *total_bytes = SD.totalBytes();
    *used_bytes = SD.usedBytes();
    return true;
}
