#include <lvgl.h>
#include <Arduino.h>
#include <ctime>
#include <cmath>
#include <vector>
#include <SD.h>
#include "protocol.h"
#include "config.h"
#include "display_hw.h"
#include "espnow_link.h"
#include "power.h"
#include "config_server.h"
#include <WiFi.h>

// ============================================================
//  Color Palette
// ============================================================
#define CLR_RED     0xE74C3C
#define CLR_BLUE    0x3498DB
#define CLR_GREEN   0x2ECC71
#define CLR_ORANGE  0xE67E22
#define CLR_PURPLE  0x9B59B6
#define CLR_TEAL    0x1ABC9C
#define CLR_PINK    0xE91E63
#define CLR_YELLOW  0xF1C40F
#define CLR_GREY    0x7F8C8D
#define CLR_DARK    0x2C3E50
#define CLR_CYAN    0x00BCD4
#define CLR_INDIGO  0x3F51B5
#define CLR_LIME    0x8BC34A
#define CLR_AMBER   0xFFC107
#define CLR_DPURPLE 0x7B1FA2
#define CLR_MAGENTA 0xAD1457

// ============================================================
//  UI State
// ============================================================
static lv_obj_t *tabview = nullptr;
static lv_obj_t *status_label = nullptr;
static lv_obj_t *stats_header = nullptr;
static bool stats_visible = false;

// Device status header labels
static lv_obj_t *rssi_label = nullptr;
static lv_obj_t *bright_btn = nullptr;

// Global config reference (set by create_ui)
static const AppConfig *g_active_config = nullptr;

// Clock mode screen
static lv_obj_t *main_screen = nullptr;
static lv_obj_t *clock_screen = nullptr;
static lv_obj_t *clock_time_label = nullptr;
static lv_obj_t *clock_rssi_label = nullptr;

// Config mode screen (replaces OTA screen)
static lv_obj_t *config_screen = nullptr;
static lv_obj_t *config_info_label = nullptr;

// Stats header labels (row 1: cpu%, ram%, gpu%, cpu_temp, gpu_temp; row 2: net_up, net_down, disk%)
static lv_obj_t *stat_labels[8] = {};

// Picture frame mode state
static lv_obj_t *picture_frame_screen = nullptr;
static lv_obj_t *slideshow_img = nullptr;
static lv_obj_t *slideshow_fallback_label = nullptr;
static std::vector<String> slideshow_files;
static size_t slideshow_index = 0;
static lv_timer_t *slideshow_timer = nullptr;

// Standby mode state
static lv_obj_t *standby_screen = nullptr;
static lv_obj_t *standby_time_label = nullptr;
static lv_obj_t *standby_stats_label = nullptr;

// Analog clock widgets (on clock_screen)
static lv_obj_t *analog_clock_face = nullptr;
static lv_obj_t *analog_hour_hand = nullptr;
static lv_obj_t *analog_min_hand = nullptr;
static lv_point_t hour_points[2];
static lv_point_t min_points[2];

// LVGL SD card filesystem driver state
static bool sd_fs_registered = false;

// Forward declarations
void update_clock_time();
void show_config_screen();
void hide_config_screen();
static void init_picture_frame_mode();
static void cleanup_picture_frame_mode();
static void init_standby_mode();
static void load_next_slideshow_image();
static void slideshow_timer_cb(lv_timer_t *timer);
static void lvgl_register_sd_driver();

// ============================================================
//  Brightness Button Callback
// ============================================================
static void brightness_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        power_cycle_brightness();
    }
}

// ============================================================
//  Button Event Handler
// ============================================================
static void btn_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        const ButtonConfig *btn = (const ButtonConfig *)lv_event_get_user_data(e);
        if (!btn) return;
        if (btn->action_type == ACTION_MEDIA_KEY) {
            send_media_key_to_bridge(btn->consumer_code);
        } else {
            send_hotkey_to_bridge(btn->modifiers, btn->keycode);
        }

        // Update status bar
        if (status_label) {
            lv_label_set_text_fmt(status_label, LV_SYMBOL_OK " Sent: %s (%s)",
                                  btn->label.c_str(), btn->description.c_str());
        }

        Serial.printf("Hotkey: %s (%s) mod=0x%02X key=0x%02X media=%d\n",
                      btn->label.c_str(), btn->description.c_str(),
                      btn->modifiers, btn->keycode, btn->action_type == ACTION_MEDIA_KEY);
    }
}

// ============================================================
//  Button Creation
// ============================================================
static lv_obj_t *create_hotkey_button(lv_obj_t *parent, const ButtonConfig *btn_cfg) {
    lv_obj_t *btn = lv_btn_create(parent);
    // Grid layout auto-sizes based on cell dimensions (no fixed size)
    lv_obj_add_flag(btn, LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_obj_add_event_cb(btn, btn_event_cb, LV_EVENT_CLICKED, (void *)btn_cfg);

    // Normal style
    lv_obj_set_style_bg_color(btn, lv_color_hex(btn_cfg->color), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(btn, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(btn, 12, LV_PART_MAIN);
    lv_obj_set_style_shadow_width(btn, 8, LV_PART_MAIN);
    lv_obj_set_style_shadow_ofs_y(btn, 4, LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(btn, LV_OPA_30, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn, 0, LV_PART_MAIN);

    // Pressed style: configurable color + shrink for visual feedback (DISP-03)
    lv_color_t pressed_clr;
    if (btn_cfg->pressed_color == 0x000000) {
        // Auto-darken if not explicitly set
        pressed_clr = lv_color_darken(lv_color_hex(btn_cfg->color), LV_OPA_30);
    } else {
        // Use explicit pressed color
        pressed_clr = lv_color_hex(btn_cfg->pressed_color);
    }
    lv_obj_set_style_bg_color(btn, pressed_clr, LV_STATE_PRESSED);
    lv_obj_set_style_transform_width(btn, -3, LV_STATE_PRESSED);
    lv_obj_set_style_transform_height(btn, -3, LV_STATE_PRESSED);

    // Column flex layout: icon -> label -> description
    lv_obj_set_flex_flow(btn, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(btn, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_all(btn, 8, LV_PART_MAIN);

    // Icon
    if (!btn_cfg->icon.empty()) {
        lv_obj_t *icon = lv_label_create(btn);
        lv_label_set_text(icon, btn_cfg->icon.c_str());
        lv_obj_set_style_text_font(icon, &lv_font_montserrat_22, LV_PART_MAIN);
        lv_obj_set_style_text_color(icon, lv_color_white(), LV_PART_MAIN);
    }

    // Label
    lv_obj_t *label = lv_label_create(btn);
    lv_label_set_text(label, btn_cfg->label.c_str());
    lv_obj_set_style_text_font(label, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_style_text_color(label, lv_color_white(), LV_PART_MAIN);

    // Description sublabel
    lv_obj_t *sub = lv_label_create(btn);
    lv_label_set_text(sub, btn_cfg->description.c_str());
    lv_obj_set_style_text_font(sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_style_text_color(sub, lv_color_make(200, 200, 200), LV_PART_MAIN);

    return btn;
}

// ============================================================
//  Stats Header: helper to create a stat label with color
// ============================================================
static lv_obj_t *create_stat_label(lv_obj_t *parent, const char *text, uint32_t color) {
    lv_obj_t *lbl = lv_label_create(parent);
    lv_label_set_text(lbl, text);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl, lv_color_hex(color), LV_PART_MAIN);
    return lbl;
}

// ============================================================
//  Stats Header: create the two-row header container
// ============================================================
static void create_stats_header(lv_obj_t *parent) {
    stats_header = lv_obj_create(parent);
    lv_obj_set_size(stats_header, SCREEN_WIDTH, 90);
    lv_obj_align(stats_header, LV_ALIGN_TOP_MID, 0, 45);
    lv_obj_set_style_bg_color(stats_header, lv_color_hex(0x0d1b2a), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(stats_header, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_width(stats_header, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(stats_header, 0, LV_PART_MAIN);
    lv_obj_clear_flag(stats_header, LV_OBJ_FLAG_SCROLLABLE);

    // Start hidden
    lv_obj_add_flag(stats_header, LV_OBJ_FLAG_HIDDEN);

    // Row 1 container (top 45px): CPU%, RAM%, GPU%, CPU temp, GPU temp
    lv_obj_t *row1 = lv_obj_create(stats_header);
    lv_obj_set_size(row1, SCREEN_WIDTH - 20, 40);
    lv_obj_align(row1, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_bg_opa(row1, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(row1, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(row1, 0, LV_PART_MAIN);
    lv_obj_clear_flag(row1, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(row1, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(row1, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    // Colors: CPU blue, RAM green, GPU orange, CPU temp red, GPU temp yellow
    stat_labels[0] = create_stat_label(row1, "CPU --%",  0x3498DB);  // cpu_percent
    stat_labels[1] = create_stat_label(row1, "RAM --%",  0x2ECC71);  // ram_percent
    stat_labels[2] = create_stat_label(row1, "GPU --%",  0xE67E22);  // gpu_percent
    stat_labels[3] = create_stat_label(row1, "CPU --\xC2\xB0""C", 0xE74C3C);  // cpu_temp
    stat_labels[4] = create_stat_label(row1, "GPU --\xC2\xB0""C", 0xF1C40F);  // gpu_temp

    // Row 2 container (bottom 45px): Net up, Net down, Disk%
    lv_obj_t *row2 = lv_obj_create(stats_header);
    lv_obj_set_size(row2, SCREEN_WIDTH - 20, 40);
    lv_obj_align(row2, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_opa(row2, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(row2, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(row2, 0, LV_PART_MAIN);
    lv_obj_clear_flag(row2, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(row2, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(row2, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    // Colors: network teal, disk grey
    stat_labels[5] = create_stat_label(row2, LV_SYMBOL_UPLOAD " -- KB/s",   0x1ABC9C);  // net_up
    stat_labels[6] = create_stat_label(row2, LV_SYMBOL_DOWNLOAD " -- KB/s", 0x1ABC9C);  // net_down
    stat_labels[7] = create_stat_label(row2, "Disk --%",                     0x7F8C8D);  // disk_percent
}

// ============================================================
//  Public: update_stats() -- Update stats header with new data
// ============================================================
void update_stats(const StatsPayload *stats) {
    if (!stats_header || !stats) return;

    // Show header if hidden
    if (!stats_visible) {
        lv_obj_clear_flag(stats_header, LV_OBJ_FLAG_HIDDEN);
        stats_visible = true;
        // Resize tabview to make room for stats header
        lv_obj_set_size(tabview, SCREEN_WIDTH, SCREEN_HEIGHT - 45 - 90);
        lv_obj_align(tabview, LV_ALIGN_BOTTOM_MID, 0, 0);
    }

    // Helper lambda for unavailable values
    auto fmt_pct = [](lv_obj_t *lbl, const char *prefix, uint8_t val) {
        if (val == 0xFF)
            lv_label_set_text_fmt(lbl, "%s N/A", prefix);
        else
            lv_label_set_text_fmt(lbl, "%s %d%%", prefix, val);
    };

    auto fmt_temp = [](lv_obj_t *lbl, const char *prefix, uint8_t val) {
        if (val == 0xFF)
            lv_label_set_text_fmt(lbl, "%s N/A", prefix);
        else
            lv_label_set_text_fmt(lbl, "%s %d\xC2\xB0""C", prefix, val);
    };

    // Row 1
    fmt_pct(stat_labels[0], "CPU", stats->cpu_percent);
    fmt_pct(stat_labels[1], "RAM", stats->ram_percent);
    fmt_pct(stat_labels[2], "GPU", stats->gpu_percent);
    fmt_temp(stat_labels[3], "CPU", stats->cpu_temp);
    fmt_temp(stat_labels[4], "GPU", stats->gpu_temp);

    // Row 2 - network
    if (stats->net_up_kbps >= 1024)
        lv_label_set_text_fmt(stat_labels[5], LV_SYMBOL_UPLOAD " %.1f MB/s", stats->net_up_kbps / 1024.0f);
    else
        lv_label_set_text_fmt(stat_labels[5], LV_SYMBOL_UPLOAD " %d KB/s", stats->net_up_kbps);

    if (stats->net_down_kbps >= 1024)
        lv_label_set_text_fmt(stat_labels[6], LV_SYMBOL_DOWNLOAD " %.1f MB/s", stats->net_down_kbps / 1024.0f);
    else
        lv_label_set_text_fmt(stat_labels[6], LV_SYMBOL_DOWNLOAD " %d KB/s", stats->net_down_kbps);

    fmt_pct(stat_labels[7], "Disk", stats->disk_percent);
}

// ============================================================
//  Public: hide_stats_header() -- Hide stats header on timeout
// ============================================================
void hide_stats_header() {
    if (!stats_header || !stats_visible) return;

    lv_obj_add_flag(stats_header, LV_OBJ_FLAG_HIDDEN);
    stats_visible = false;

    // Restore tabview to full size
    lv_obj_set_size(tabview, SCREEN_WIDTH, SCREEN_HEIGHT - 45);
    lv_obj_align(tabview, LV_ALIGN_BOTTOM_MID, 0, 0);
}

// ============================================================
//  Public: update_device_status() -- Update header indicators
// ============================================================
void update_device_status(int rssi_dbm, bool espnow_linked, uint8_t brightness_level) {
    // WiFi signal icon -- color reflects signal strength
    if (rssi_label) {
        if (rssi_dbm == 0 || !espnow_linked) {
            lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
        } else if (rssi_dbm > -50) {
            lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_GREEN), LV_PART_MAIN);
        } else if (rssi_dbm > -70) {
            lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_YELLOW), LV_PART_MAIN);
        } else {
            lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_RED), LV_PART_MAIN);
        }
    }

    (void)brightness_level;
}

// ============================================================
//  Public: show_clock_mode() -- Switch to clock screen
// ============================================================
void show_clock_mode() {
    if (clock_screen) {
        update_clock_time();
        lv_scr_load(clock_screen);
    }
}

// ============================================================
//  Public: show_hotkey_view() -- Switch back to main screen
// ============================================================
void show_hotkey_view() {
    if (main_screen) {
        lv_scr_load(main_screen);
    }
}

// ============================================================
//  Public: update_clock_time() -- Refresh clock display
// ============================================================
void update_clock_time() {
    if (!clock_time_label || !clock_rssi_label) return;

    time_t now = time(nullptr);
    struct tm *tm_info = localtime(&now);
    if (!tm_info) return;

    bool use_analog = g_active_config ? g_active_config->clock_analog : false;

    if (use_analog && analog_clock_face) {
        // Hide digital, show analog
        lv_obj_add_flag(clock_time_label, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(analog_clock_face, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(analog_hour_hand, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(analog_min_hand, LV_OBJ_FLAG_HIDDEN);

        // Calculate hand angles (0 deg = 12 o'clock, clockwise)
        float hour_angle = (tm_info->tm_hour % 12) * 30.0f + tm_info->tm_min * 0.5f;
        float min_angle = tm_info->tm_min * 6.0f;

        int cx = SCREEN_WIDTH / 2;
        int cy = SCREEN_HEIGHT / 2;
        float hour_rad = (hour_angle - 90.0f) * M_PI / 180.0f;
        float min_rad = (min_angle - 90.0f) * M_PI / 180.0f;

        hour_points[0] = {(lv_coord_t)cx, (lv_coord_t)cy};
        hour_points[1] = {
            (lv_coord_t)(cx + 80 * cosf(hour_rad)),
            (lv_coord_t)(cy + 80 * sinf(hour_rad))
        };
        lv_line_set_points(analog_hour_hand, hour_points, 2);

        min_points[0] = {(lv_coord_t)cx, (lv_coord_t)cy};
        min_points[1] = {
            (lv_coord_t)(cx + 120 * cosf(min_rad)),
            (lv_coord_t)(cy + 120 * sinf(min_rad))
        };
        lv_line_set_points(analog_min_hand, min_points, 2);
    } else {
        // Show digital, hide analog
        lv_obj_clear_flag(clock_time_label, LV_OBJ_FLAG_HIDDEN);
        lv_label_set_text_fmt(clock_time_label, "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
        if (analog_clock_face) lv_obj_add_flag(analog_clock_face, LV_OBJ_FLAG_HIDDEN);
        if (analog_hour_hand) lv_obj_add_flag(analog_hour_hand, LV_OBJ_FLAG_HIDDEN);
        if (analog_min_hand) lv_obj_add_flag(analog_min_hand, LV_OBJ_FLAG_HIDDEN);
    }

    // Update RSSI indicator (same for both modes)
    int rssi = espnow_get_rssi();
    if (rssi != 0 && rssi > -50)
        lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_GREEN), LV_PART_MAIN);
    else if (rssi != 0 && rssi > -70)
        lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_YELLOW), LV_PART_MAIN);
    else if (rssi != 0)
        lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_RED), LV_PART_MAIN);
    else
        lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
}

// ============================================================
//  Config Server Button Callback
// ============================================================
static void config_btn_event_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        if (!config_server_active()) {
            if (config_server_start()) {
                show_config_screen();
            }
        } else {
            config_server_stop();
            hide_config_screen();
        }
    }
}

// ============================================================
//  Public: show_config_screen() -- Enter config mode screen
// ============================================================
void show_config_screen() {
    if (!config_screen) return;
    if (config_info_label) {
        IPAddress ip = WiFi.softAPIP();
        lv_label_set_text_fmt(config_info_label,
            "Connect to WiFi:\n"
            "  SSID: CrowPanel-Config\n"
            "  Password: crowconfig\n\n"
            "Config upload:\n"
            "  http://%s\n\n"
            "OTA firmware upload:\n"
            "  http://%s/update\n\n"
            "PlatformIO:\n"
            "  pio run -t upload --upload-port %s",
            ip.toString().c_str(), ip.toString().c_str(), ip.toString().c_str());
    }
    lv_scr_load(config_screen);
}

// ============================================================
//  Public: hide_config_screen() -- Return to main hotkey view
// ============================================================
void hide_config_screen() {
    if (main_screen) {
        lv_scr_load(main_screen);
    }
}

// ============================================================
//  LVGL SD Card Filesystem Driver
// ============================================================
static void lvgl_register_sd_driver() {
    if (sd_fs_registered) return;

    static lv_fs_drv_t drv;
    lv_fs_drv_init(&drv);
    drv.letter = 'S';
    drv.open_cb = [](lv_fs_drv_t *, const char *path, lv_fs_mode_t) -> void* {
        File *file = new File();
        *file = SD.open(path, FILE_READ);
        if (!*file) {
            delete file;
            return nullptr;
        }
        return file;
    };
    drv.close_cb = [](lv_fs_drv_t *, void *file_p) -> lv_fs_res_t {
        File *file = (File*)file_p;
        file->close();
        delete file;
        return LV_FS_RES_OK;
    };
    drv.read_cb = [](lv_fs_drv_t *, void *file_p, void *buf, uint32_t btr, uint32_t *br) -> lv_fs_res_t {
        File *file = (File*)file_p;
        *br = file->read((uint8_t*)buf, btr);
        return LV_FS_RES_OK;
    };
    drv.seek_cb = [](lv_fs_drv_t *, void *file_p, uint32_t pos, lv_fs_whence_t whence) -> lv_fs_res_t {
        File *file = (File*)file_p;
        if (whence == LV_FS_SEEK_SET)
            file->seek(pos);
        else if (whence == LV_FS_SEEK_CUR)
            file->seek(file->position() + pos);
        else if (whence == LV_FS_SEEK_END)
            file->seek(file->size() - pos);
        return LV_FS_RES_OK;
    };
    drv.tell_cb = [](lv_fs_drv_t *, void *file_p, uint32_t *pos_p) -> lv_fs_res_t {
        File *file = (File*)file_p;
        *pos_p = file->position();
        return LV_FS_RES_OK;
    };
    lv_fs_drv_register(&drv);
    sd_fs_registered = true;
    Serial.println("[ui] LVGL SD filesystem driver registered (S:)");
}

// ============================================================
//  Picture Frame Mode
// ============================================================
static void load_next_slideshow_image() {
    if (slideshow_files.empty() || !slideshow_img) return;

    String path = "S:" + slideshow_files[slideshow_index];
    Serial.printf("[ui] Loading image: %s\n", path.c_str());
    lv_img_set_src(slideshow_img, path.c_str());

    slideshow_index = (slideshow_index + 1) % slideshow_files.size();
}

static void slideshow_timer_cb(lv_timer_t *timer) {
    (void)timer;
    load_next_slideshow_image();
}

static void init_picture_frame_mode() {
    lvgl_register_sd_driver();

    if (!picture_frame_screen) {
        picture_frame_screen = lv_obj_create(NULL);
        lv_obj_set_style_bg_color(picture_frame_screen, lv_color_black(), LV_PART_MAIN);
        lv_obj_set_style_bg_opa(picture_frame_screen, LV_OPA_COVER, LV_PART_MAIN);
    } else {
        lv_obj_clean(picture_frame_screen);
    }
    slideshow_img = nullptr;
    slideshow_fallback_label = nullptr;

    // Scan SD card /pictures directory for images
    slideshow_files.clear();
    File dir = SD.open("/pictures");
    if (dir && dir.isDirectory()) {
        File entry;
        while ((entry = dir.openNextFile())) {
            if (!entry.isDirectory()) {
                String name = String(entry.name());
                String lower = name;
                lower.toLowerCase();
                if (lower.endsWith(".jpg") || lower.endsWith(".jpeg") ||
                    lower.endsWith(".sjpg") || lower.endsWith(".bmp")) {
                    if (!name.startsWith("/")) {
                        slideshow_files.push_back("/pictures/" + name);
                    } else {
                        slideshow_files.push_back(name);
                    }
                }
            }
            entry.close();
        }
        dir.close();
    }

    if (slideshow_files.empty()) {
        Serial.println("[ui] WARN: No images found in /pictures");
        slideshow_fallback_label = lv_label_create(picture_frame_screen);
        lv_label_set_text(slideshow_fallback_label,
            "No images in /pictures\n\nUpload JPG/BMP files to SD card");
        lv_obj_center(slideshow_fallback_label);
        lv_obj_set_style_text_color(slideshow_fallback_label, lv_color_white(), LV_PART_MAIN);
        lv_obj_set_style_text_font(slideshow_fallback_label, &lv_font_montserrat_20, LV_PART_MAIN);
        lv_obj_set_style_text_align(slideshow_fallback_label, LV_TEXT_ALIGN_CENTER, LV_PART_MAIN);
        return;
    }

    Serial.printf("[ui] Found %zu images in /pictures\n", slideshow_files.size());

    slideshow_img = lv_img_create(picture_frame_screen);
    lv_obj_set_size(slideshow_img, SCREEN_WIDTH, SCREEN_HEIGHT);
    lv_obj_align(slideshow_img, LV_ALIGN_CENTER, 0, 0);

    slideshow_index = 0;
    load_next_slideshow_image();

    uint32_t interval_ms = g_active_config ? g_active_config->slideshow_interval_sec * 1000 : 30000;
    if (interval_ms < 5000) interval_ms = 5000;
    slideshow_timer = lv_timer_create(slideshow_timer_cb, interval_ms, nullptr);
}

static void cleanup_picture_frame_mode() {
    if (slideshow_timer) {
        lv_timer_del(slideshow_timer);
        slideshow_timer = nullptr;
    }
}

// ============================================================
//  Standby Mode
// ============================================================
static void init_standby_mode() {
    if (!standby_screen) {
        standby_screen = lv_obj_create(NULL);
        lv_obj_set_style_bg_color(standby_screen, lv_color_hex(0x0f0f23), LV_PART_MAIN);
        lv_obj_set_style_bg_opa(standby_screen, LV_OPA_COVER, LV_PART_MAIN);

        standby_time_label = lv_label_create(standby_screen);
        lv_label_set_text(standby_time_label, "00:00");
        lv_obj_set_style_text_font(standby_time_label, &lv_font_montserrat_40, LV_PART_MAIN);
        lv_obj_set_style_text_color(standby_time_label, lv_color_white(), LV_PART_MAIN);
        lv_obj_align(standby_time_label, LV_ALIGN_CENTER, 0, -50);

        standby_stats_label = lv_label_create(standby_screen);
        lv_label_set_text(standby_stats_label, "CPU --% | RAM --% | GPU --%");
        lv_obj_set_style_text_font(standby_stats_label, &lv_font_montserrat_16, LV_PART_MAIN);
        lv_obj_set_style_text_color(standby_stats_label, lv_color_hex(0x888888), LV_PART_MAIN);
        lv_obj_align(standby_stats_label, LV_ALIGN_CENTER, 0, 20);
    }

    time_t now = time(nullptr);
    struct tm *tm_info = localtime(&now);
    if (standby_time_label && tm_info) {
        lv_label_set_text_fmt(standby_time_label, "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
    }
}

void update_standby_time() {
    if (!standby_time_label) return;
    time_t now = time(nullptr);
    struct tm *tm_info = localtime(&now);
    if (tm_info) {
        lv_label_set_text_fmt(standby_time_label, "%02d:%02d", tm_info->tm_hour, tm_info->tm_min);
    }
}

void update_standby_stats(const StatsPayload *stats) {
    if (!standby_stats_label || !stats) return;
    auto pct_str = [](uint8_t val) -> String {
        if (val == 0xFF) return "N/A";
        return String(val) + "%";
    };
    String line = "CPU " + pct_str(stats->cpu_percent) +
                  " | RAM " + pct_str(stats->ram_percent) +
                  " | GPU " + pct_str(stats->gpu_percent);
    lv_label_set_text(standby_stats_label, line.c_str());
}

// ============================================================
//  Analog Clock Widgets (created on clock_screen)
// ============================================================
static void create_analog_clock_widgets(lv_obj_t *parent) {
    analog_clock_face = lv_arc_create(parent);
    lv_obj_set_size(analog_clock_face, 300, 300);
    lv_obj_center(analog_clock_face);
    lv_arc_set_bg_angles(analog_clock_face, 0, 360);
    lv_arc_set_value(analog_clock_face, 0);
    lv_obj_remove_style(analog_clock_face, NULL, LV_PART_KNOB);
    lv_obj_remove_style(analog_clock_face, NULL, LV_PART_INDICATOR);
    lv_obj_set_style_arc_width(analog_clock_face, 4, LV_PART_MAIN);
    lv_obj_set_style_arc_color(analog_clock_face, lv_color_hex(0x888888), LV_PART_MAIN);

    hour_points[0] = {(lv_coord_t)(SCREEN_WIDTH / 2), (lv_coord_t)(SCREEN_HEIGHT / 2)};
    hour_points[1] = {(lv_coord_t)(SCREEN_WIDTH / 2), (lv_coord_t)(SCREEN_HEIGHT / 2 - 80)};
    analog_hour_hand = lv_line_create(parent);
    lv_line_set_points(analog_hour_hand, hour_points, 2);
    lv_obj_set_style_line_width(analog_hour_hand, 6, LV_PART_MAIN);
    lv_obj_set_style_line_color(analog_hour_hand, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_line_rounded(analog_hour_hand, true, LV_PART_MAIN);

    min_points[0] = {(lv_coord_t)(SCREEN_WIDTH / 2), (lv_coord_t)(SCREEN_HEIGHT / 2)};
    min_points[1] = {(lv_coord_t)(SCREEN_WIDTH / 2), (lv_coord_t)(SCREEN_HEIGHT / 2 - 120)};
    analog_min_hand = lv_line_create(parent);
    lv_line_set_points(analog_min_hand, min_points, 2);
    lv_obj_set_style_line_width(analog_min_hand, 4, LV_PART_MAIN);
    lv_obj_set_style_line_color(analog_min_hand, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_line_rounded(analog_min_hand, true, LV_PART_MAIN);

    lv_obj_add_flag(analog_clock_face, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(analog_hour_hand, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(analog_min_hand, LV_OBJ_FLAG_HIDDEN);
}

// ============================================================
//  Mode Transition Handler (called by display_set_mode in power.cpp)
// ============================================================
void ui_transition_mode(DisplayMode from, DisplayMode to) {
    switch (from) {
        case MODE_HOTKEYS: break;
        case MODE_CLOCK: break;
        case MODE_PICTURE_FRAME: cleanup_picture_frame_mode(); break;
        case MODE_STANDBY: break;
    }

    switch (to) {
        case MODE_HOTKEYS:
            show_hotkey_view();
            break;
        case MODE_CLOCK:
            show_clock_mode();
            break;
        case MODE_PICTURE_FRAME:
            init_picture_frame_mode();
            if (picture_frame_screen) lv_scr_load(picture_frame_screen);
            break;
        case MODE_STANDBY:
            init_standby_mode();
            if (standby_screen) lv_scr_load(standby_screen);
            break;
    }
    Serial.printf("[ui] Mode transition: %d -> %d complete\n", from, to);
}

// ============================================================
//  Brightness Long-Press: Cycle Display Modes
// ============================================================
static void brightness_long_press_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_LONG_PRESSED) {
        DisplayMode current = display_get_mode();
        DisplayMode next = (DisplayMode)((current + 1) % 4);
        display_set_mode(next);
    }
}

// ============================================================
//  Static helper: create all main screen widgets (header, stats, tabview)
//  Called by both create_ui() and rebuild_ui()
// ============================================================
static void create_ui_widgets(lv_obj_t *screen, const AppConfig *cfg) {
    // Header bar (45px)
    lv_obj_t *header = lv_obj_create(screen);
    lv_obj_set_size(header, SCREEN_WIDTH, 45);
    lv_obj_align(header, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_bg_color(header, lv_color_hex(0x16213e), LV_PART_MAIN);
    lv_obj_set_style_border_width(header, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(header, 0, LV_PART_MAIN);
    lv_obj_clear_flag(header, LV_OBJ_FLAG_SCROLLABLE);

    // Title on the left
    lv_obj_t *title = lv_label_create(header);
    lv_label_set_text(title, LV_SYMBOL_KEYBOARD "  Hotkeys");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_set_style_text_color(title, lv_color_hex(0xE0E0E0), LV_PART_MAIN);
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 15, 0);

    // Status label (center-ish)
    status_label = lv_label_create(header);
    lv_label_set_text(status_label, LV_SYMBOL_USB " Ready");
    lv_obj_set_style_text_font(status_label, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_style_text_color(status_label, lv_color_hex(0x2ECC71), LV_PART_MAIN);
    lv_obj_align(status_label, LV_ALIGN_CENTER, 0, 0);

    // Device status indicators on the right side of header
    rssi_label = lv_label_create(header);
    lv_label_set_text(rssi_label, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_font(rssi_label, &lv_font_montserrat_18, LV_PART_MAIN);
    lv_obj_set_style_text_color(rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
    lv_obj_align(rssi_label, LV_ALIGN_RIGHT_MID, -15, 0);

    // Config button (gear icon, tappable)
    lv_obj_t *cfg_btn = lv_label_create(header);
    lv_label_set_text(cfg_btn, LV_SYMBOL_SETTINGS);
    lv_obj_set_style_text_font(cfg_btn, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_style_text_color(cfg_btn, lv_color_hex(CLR_TEAL), LV_PART_MAIN);
    lv_obj_align(cfg_btn, LV_ALIGN_RIGHT_MID, -55, 0);
    lv_obj_add_flag(cfg_btn, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(cfg_btn, config_btn_event_cb, LV_EVENT_CLICKED, nullptr);

    // Brightness button (tappable)
    bright_btn = lv_label_create(header);
    lv_label_set_text(bright_btn, LV_SYMBOL_IMAGE);
    lv_obj_set_style_text_font(bright_btn, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_style_text_color(bright_btn, lv_color_hex(CLR_YELLOW), LV_PART_MAIN);
    lv_obj_align(bright_btn, LV_ALIGN_RIGHT_MID, -95, 0);
    lv_obj_add_flag(bright_btn, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(bright_btn, brightness_event_cb, LV_EVENT_CLICKED, nullptr);
    lv_obj_add_event_cb(bright_btn, brightness_long_press_cb, LV_EVENT_LONG_PRESSED, nullptr);

    // Stats header (hidden by default, shown on first MSG_STATS)
    create_stats_header(screen);

    // Tabview with bottom tabs (45px tab bar)
    tabview = lv_tabview_create(screen, LV_DIR_BOTTOM, 45);
    lv_obj_set_size(tabview, SCREEN_WIDTH, SCREEN_HEIGHT - 45);
    lv_obj_align(tabview, LV_ALIGN_BOTTOM_MID, 0, 0);

    // Style the tab buttons
    lv_obj_t *tab_btns = lv_tabview_get_tab_btns(tabview);
    lv_obj_set_style_bg_color(tab_btns, lv_color_hex(0x16213e), LV_PART_MAIN);
    lv_obj_set_style_text_color(tab_btns, lv_color_hex(0xBBBBBB), LV_PART_MAIN);
    lv_obj_set_style_text_color(tab_btns, lv_color_hex(0x3498DB), LV_PART_ITEMS | LV_STATE_CHECKED);
    lv_obj_set_style_border_color(tab_btns, lv_color_hex(0x3498DB), LV_PART_ITEMS | LV_STATE_CHECKED);
    lv_obj_set_style_text_font(tab_btns, &lv_font_montserrat_16, LV_PART_MAIN);

    // Grid descriptors: 4 columns x 3 rows with equal fractional units
    static lv_coord_t col_dsc[] = {LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_TEMPLATE_LAST};
    static lv_coord_t row_dsc[] = {LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_FR(1), LV_GRID_TEMPLATE_LAST};

    // Create pages from config (single config-driven path)
    const ProfileConfig* active_profile = cfg->get_active_profile();
    if (active_profile) {
        for (size_t i = 0; i < active_profile->pages.size(); i++) {
            const PageConfig& page = active_profile->pages[i];
            lv_obj_t *tab = lv_tabview_add_tab(tabview, page.name.c_str());

            // Grid layout: 4 columns x 3 rows
            lv_obj_set_layout(tab, LV_LAYOUT_GRID);
            lv_obj_set_grid_dsc_array(tab, col_dsc, row_dsc);
            lv_obj_set_style_pad_all(tab, 6, LV_PART_MAIN);
            lv_obj_set_style_pad_row(tab, 6, LV_PART_MAIN);
            lv_obj_set_style_pad_column(tab, 6, LV_PART_MAIN);
            lv_obj_set_style_bg_color(tab, lv_color_hex(0x1a1a2e), LV_PART_MAIN);

            // Track auto-flow position for buttons without explicit grid placement
            int auto_row = 0, auto_col = 0;

            for (size_t j = 0; j < page.buttons.size(); j++) {
                const ButtonConfig& btn_cfg = page.buttons[j];
                lv_obj_t *btn = create_hotkey_button(tab, &btn_cfg);

                if (btn_cfg.grid_row >= 0 && btn_cfg.grid_col >= 0) {
                    // Explicit positioning
                    lv_obj_set_grid_cell(btn,
                        LV_GRID_ALIGN_STRETCH, btn_cfg.grid_col, 1,
                        LV_GRID_ALIGN_STRETCH, btn_cfg.grid_row, 1);
                } else {
                    // Auto-flow: place in next available cell
                    lv_obj_set_grid_cell(btn,
                        LV_GRID_ALIGN_STRETCH, auto_col, 1,
                        LV_GRID_ALIGN_STRETCH, auto_row, 1);
                    auto_col++;
                    if (auto_col >= GRID_COLS) {
                        auto_col = 0;
                        auto_row++;
                    }
                }
            }
        }
    } else {
        Serial.println("UI: No active profile found in config");
    }
}

// ============================================================
//  Public: create_ui() -- Build the complete hotkey tabview UI
// ============================================================
void create_ui(const AppConfig* cfg) {
    if (!cfg) {
        Serial.println("create_ui: nullptr config, cannot create UI");
        return;
    }
    g_active_config = cfg;

    // Save reference to the main screen before adding widgets
    main_screen = lv_scr_act();

    // Dark background
    lv_obj_set_style_bg_color(main_screen, lv_color_hex(0x0f0f23), LV_PART_MAIN);

    // --- Clock mode screen (created once, persists across rebuilds) ---
    clock_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(clock_screen, lv_color_hex(0x0f0f23), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(clock_screen, LV_OPA_COVER, LV_PART_MAIN);

    clock_time_label = lv_label_create(clock_screen);
    lv_label_set_text(clock_time_label, "00:00");
    lv_obj_set_style_text_font(clock_time_label, &lv_font_montserrat_40, LV_PART_MAIN);
    lv_obj_set_style_text_color(clock_time_label, lv_color_white(), LV_PART_MAIN);
    lv_obj_align(clock_time_label, LV_ALIGN_CENTER, 0, -30);

    clock_rssi_label = lv_label_create(clock_screen);
    lv_label_set_text(clock_rssi_label, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_font(clock_rssi_label, &lv_font_montserrat_28, LV_PART_MAIN);
    lv_obj_set_style_text_color(clock_rssi_label, lv_color_hex(CLR_GREY), LV_PART_MAIN);
    lv_obj_align(clock_rssi_label, LV_ALIGN_CENTER, 0, 30);

    // Analog clock widgets on clock_screen (hidden by default)
    create_analog_clock_widgets(clock_screen);

    // --- Config mode screen (created once, persists across rebuilds) ---
    config_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(config_screen, lv_color_hex(0x0d1b2a), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(config_screen, LV_OPA_COVER, LV_PART_MAIN);

    lv_obj_t *cfg_title = lv_label_create(config_screen);
    lv_label_set_text(cfg_title, LV_SYMBOL_SETTINGS "  Config Upload Mode");
    lv_obj_set_style_text_font(cfg_title, &lv_font_montserrat_28, LV_PART_MAIN);
    lv_obj_set_style_text_color(cfg_title, lv_color_hex(CLR_TEAL), LV_PART_MAIN);
    lv_obj_align(cfg_title, LV_ALIGN_TOP_MID, 0, 40);

    config_info_label = lv_label_create(config_screen);
    lv_label_set_text(config_info_label, "Starting...");
    lv_obj_set_style_text_font(config_info_label, &lv_font_montserrat_18, LV_PART_MAIN);
    lv_obj_set_style_text_color(config_info_label, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_text_align(config_info_label, LV_TEXT_ALIGN_LEFT, LV_PART_MAIN);
    lv_obj_align(config_info_label, LV_ALIGN_CENTER, 0, 10);

    // "Apply & Exit" button
    lv_obj_t *cfg_exit = lv_btn_create(config_screen);
    lv_obj_set_size(cfg_exit, 250, 50);
    lv_obj_align(cfg_exit, LV_ALIGN_BOTTOM_MID, 0, -40);
    lv_obj_set_style_bg_color(cfg_exit, lv_color_hex(CLR_GREEN), LV_PART_MAIN);
    lv_obj_add_event_cb(cfg_exit, config_btn_event_cb, LV_EVENT_CLICKED, nullptr);
    lv_obj_t *exit_lbl = lv_label_create(cfg_exit);
    lv_label_set_text(exit_lbl, "Apply & Exit");
    lv_obj_center(exit_lbl);

    // Create main screen widgets (header, stats header, tabview with pages)
    create_ui_widgets(main_screen, cfg);

    Serial.printf("UI initialized: %zu page(s), stats header, clock screen ready\n",
                  cfg->get_active_profile() ? cfg->get_active_profile()->pages.size() : 0);
}

// ============================================================
//  Public: rebuild_ui() -- Full-screen rebuild from AppConfig
// ============================================================
void rebuild_ui(const AppConfig* cfg) {
    if (!cfg || !main_screen) {
        Serial.println("rebuild_ui: invalid args");
        return;
    }

    // Memory before rebuild
    lv_mem_monitor_t mon_pre;
    lv_mem_monitor(&mon_pre);

    // Step 1: Destroy ALL children of main screen
    lv_obj_clean(main_screen);

    // Step 2: Null all widget pointers (now dangling after clean)
    tabview = nullptr;
    status_label = nullptr;
    stats_header = nullptr;
    stats_visible = false;
    rssi_label = nullptr;
    bright_btn = nullptr;
    memset(stat_labels, 0, sizeof(stat_labels));

    // Step 3: Update active config pointer
    g_active_config = cfg;

    // Step 4: Recreate all widgets on main screen
    create_ui_widgets(main_screen, cfg);

    // Step 5: Memory after rebuild
    lv_mem_monitor_t mon_post;
    lv_mem_monitor(&mon_post);

    uint32_t used_pre = mon_pre.total_size - mon_pre.free_size;
    uint32_t used_post = mon_post.total_size - mon_post.free_size;
    Serial.printf("UI rebuild: LVGL mem used=%u->%u (delta=%d), free=%u, frag=%u, biggest=%u\n",
                  used_pre, used_post, (int32_t)(used_post - used_pre),
                  mon_post.free_size, mon_post.free_cnt, mon_post.free_biggest_size);
}
