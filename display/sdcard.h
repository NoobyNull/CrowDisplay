#pragma once
#include <stdint.h>
#include <stddef.h>

// Initialize SD card on CrowPanel 7.0" TF Card slot (SPI: CS=10, MOSI=11, CLK=12, MISO=13)
// Returns true if card mounted successfully.
bool sdcard_init();

// Check if SD card is mounted and accessible.
bool sdcard_mounted();

// Get card size in MB.
uint32_t sdcard_size_mb();

// Read entire file into caller-provided buffer. Returns bytes read, or -1 on error.
// buf must be at least max_len bytes.
int sdcard_read_file(const char *path, uint8_t *buf, size_t max_len);

// Write buffer to file (creates or overwrites). Returns true on success.
bool sdcard_write_file(const char *path, const uint8_t *data, size_t len);

// Check if a file exists.
bool sdcard_file_exists(const char *path);

// Remove a file from SD card. Returns true on success.
bool sdcard_file_remove(const char *path);

// Rename a file on SD card (atomic). Returns true on success.
// Used for atomic writes: write to tmp file, then rename to final name.
bool sdcard_file_rename(const char *old_path, const char *new_path);

// Create a directory on SD card (recursive). Returns true on success or if already exists.
bool sdcard_mkdir(const char *path);
