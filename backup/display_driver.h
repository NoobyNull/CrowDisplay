/**
 * @file display_driver.h
 * Display driver for Elcrow 7.0" CrowPanel (ESP32-S3)
 * 800x480 RGB TFT with GT911 capacitive touch
 * Uses LovyanGFX for RGB panel + integrated touch
 */

#ifndef DISPLAY_DRIVER_H
#define DISPLAY_DRIVER_H

#include <Arduino.h>

// ── Display Dimensions ──
#define SCREEN_WIDTH  800
#define SCREEN_HEIGHT 480

// ── LVGL Integration Functions ──
void display_init(void);
void lvgl_init(void);
void lvgl_tick(void);

#endif /* DISPLAY_DRIVER_H */
