#pragma once
#include <stdint.h>
#include <string.h>

// ============================================================
// SOF-Framed Binary Protocol for Display <-> Bridge UART
// ============================================================
//
// Frame format:
//   [SOF 0xAA] [LENGTH] [TYPE] [PAYLOAD 0-250 bytes] [CRC8]
//
// CRC8 is computed over LENGTH + TYPE + PAYLOAD bytes.

#define PROTO_SOF         0xAA
#define PROTO_MAX_PAYLOAD 250

// --- Message Types ---------------------------------------------------

enum MsgType : uint8_t {
    MSG_HOTKEY      = 0x01,  // Display -> Bridge: fire keystroke
    MSG_HOTKEY_ACK  = 0x02,  // Bridge -> Display: keystroke delivered
    MSG_STATS       = 0x03,  // Bridge -> Display: system stats payload
    MSG_MEDIA_KEY   = 0x04,  // Display -> Bridge: consumer control key
    MSG_POWER_STATE = 0x05,  // Bridge -> Display: PC power state change
    MSG_TIME_SYNC   = 0x06,  // Bridge -> Display: epoch time from companion
    MSG_PING         = 0x07,  // Display -> Bridge: heartbeat (bridge replies with ACK)
    MSG_NOTIFICATION = 0x08,  // Bridge -> Display: desktop notification
    MSG_CONFIG_MODE  = 0x09,  // Bridge -> Display: enter SoftAP config mode
    MSG_CONFIG_DONE  = 0x0A,  // Bridge -> Display: reload config, exit AP mode
    MSG_BUTTON_PRESS = 0x0B,  // Display -> Bridge: button identity (page + widget index)
};

// --- Stat Type Enum (for TLV stats protocol) ------------------------

enum StatType : uint8_t {
    STAT_CPU_PERCENT    = 0x01,
    STAT_RAM_PERCENT    = 0x02,
    STAT_GPU_PERCENT    = 0x03,
    STAT_CPU_TEMP       = 0x04,
    STAT_GPU_TEMP       = 0x05,
    STAT_DISK_PERCENT   = 0x06,
    STAT_NET_UP         = 0x07,  // KB/s, uint16
    STAT_NET_DOWN       = 0x08,  // KB/s, uint16
    STAT_CPU_FREQ       = 0x09,  // MHz, uint16
    STAT_GPU_FREQ       = 0x0A,  // MHz, uint16
    STAT_SWAP_PERCENT   = 0x0B,
    STAT_UPTIME_HOURS   = 0x0C,  // Hours, uint16
    STAT_BATTERY_PCT    = 0x0D,  // For laptops
    STAT_FAN_RPM        = 0x0E,  // uint16
    STAT_LOAD_AVG       = 0x0F,  // Load average x 100, uint16
    STAT_PROC_COUNT     = 0x10,  // Process count, uint16
    STAT_GPU_MEM_PCT    = 0x11,  // GPU memory percent
    STAT_GPU_POWER_W    = 0x12,  // GPU power in watts
    STAT_DISK_READ_KBS  = 0x13,  // Disk read KB/s, uint16
    STAT_DISK_WRITE_KBS = 0x14,  // Disk write KB/s, uint16
    STAT_DISPLAY_UPTIME = 0x15,  // Display uptime hours (local, no companion data)
    STAT_PROC_USER      = 0x16,  // User process count, uint16
    STAT_PROC_SYSTEM    = 0x17,  // System/root process count, uint16
};

#define STAT_TYPE_MAX 0x17

// --- TLV Stats Decoding Helper ---------------------------------------
//
// TLV format: [count] [type1][len1][val1...] [type2][len2][val2...] ...
// Each value is 1 byte (uint8) or 2 bytes (uint16 LE).
// Heuristic: if data[0] <= STAT_TYPE_MAX, it's TLV (count); if > STAT_TYPE_MAX, legacy.

inline bool tlv_decode_stats(const uint8_t *data, uint8_t len,
                              void (*callback)(uint8_t type, uint16_t value)) {
    if (len < 1) return false;
    uint8_t count = data[0];
    uint8_t pos = 1;
    for (uint8_t i = 0; i < count && pos + 1 < len; i++) {
        uint8_t type = data[pos++];
        uint8_t vlen = data[pos++];
        if (pos + vlen > len) return false;
        uint16_t value = 0;
        if (vlen == 1) value = data[pos];
        else if (vlen == 2) value = data[pos] | (data[pos+1] << 8);
        else return false;
        callback(type, value);
        pos += vlen;
    }
    return true;
}

// --- Payload Structs -------------------------------------------------

// NOTE: StatsPayload is the legacy fixed-format struct (v0.9.0).
// New stats use TLV encoding via tlv_decode_stats() above.

struct __attribute__((packed)) HotkeyMsg {
    uint8_t modifiers;  // Bitfield: MOD_CTRL | MOD_SHIFT | MOD_ALT | MOD_GUI
    uint8_t keycode;    // ASCII key or special key code
};

struct __attribute__((packed)) HotkeyAckMsg {
    uint8_t status;  // 0 = success, 1 = error
};

struct __attribute__((packed)) StatsPayload {
    uint8_t  cpu_percent;     // 0-100
    uint8_t  ram_percent;     // 0-100
    uint8_t  gpu_percent;     // 0-100, 0xFF = unavailable
    uint8_t  cpu_temp;        // Celsius, 0xFF = unavailable
    uint8_t  gpu_temp;        // Celsius, 0xFF = unavailable
    uint8_t  disk_percent;    // 0-100
    uint16_t net_up_kbps;     // KB/s, little-endian
    uint16_t net_down_kbps;   // KB/s, little-endian
};

struct __attribute__((packed)) MediaKeyMsg {
    uint16_t consumer_code;   // USB HID consumer control usage code (e.g. 0x00CD = play/pause)
};

#define POWER_SHUTDOWN 0
#define POWER_WAKE     1
#define POWER_LOCKED   2

struct __attribute__((packed)) PowerStateMsg {
    uint8_t state;            // POWER_SHUTDOWN (0) or POWER_WAKE (1)
};

struct __attribute__((packed)) TimeSyncMsg {
    uint32_t epoch_seconds;   // Unix timestamp from companion (little-endian)
    int16_t  tz_offset_min;   // Local timezone offset from UTC in minutes (e.g., -300 for EST)
};

struct __attribute__((packed)) ButtonPressMsg {
    uint8_t page_index;       // Which page the button is on
    uint8_t widget_index;     // Widget index within the page
};

struct __attribute__((packed)) NotificationMsg {
    char app_name[32];   // Source app (null-terminated, truncated)
    char summary[100];   // Notification title
    char body[116];      // Notification body (truncated to fit)
};
// Total: 248 bytes, fits within 250-byte ESP-NOW limit
static_assert(sizeof(NotificationMsg) == 248, "NotificationMsg must be 248 bytes");

// --- Modifier Masks --------------------------------------------------

#define MOD_NONE  0x00
#define MOD_CTRL  0x01
#define MOD_SHIFT 0x02
#define MOD_ALT   0x04
#define MOD_GUI   0x08

// --- CRC8/CCITT (polynomial 0x07, init 0x00) ------------------------

static const uint8_t crc8_table[256] = {
    0x00, 0x07, 0x0E, 0x09, 0x1C, 0x1B, 0x12, 0x15,
    0x38, 0x3F, 0x36, 0x31, 0x24, 0x23, 0x2A, 0x2D,
    0x70, 0x77, 0x7E, 0x79, 0x6C, 0x6B, 0x62, 0x65,
    0x48, 0x4F, 0x46, 0x41, 0x54, 0x53, 0x5A, 0x5D,
    0xE0, 0xE7, 0xEE, 0xE9, 0xFC, 0xFB, 0xF2, 0xF5,
    0xD8, 0xDF, 0xD6, 0xD1, 0xC4, 0xC3, 0xCA, 0xCD,
    0x90, 0x97, 0x9E, 0x99, 0x8C, 0x8B, 0x82, 0x85,
    0xA8, 0xAF, 0xA6, 0xA1, 0xB4, 0xB3, 0xBA, 0xBD,
    0xC7, 0xC0, 0xC9, 0xCE, 0xDB, 0xDC, 0xD5, 0xD2,
    0xFF, 0xF8, 0xF1, 0xF6, 0xE3, 0xE4, 0xED, 0xEA,
    0xB7, 0xB0, 0xB9, 0xBE, 0xAB, 0xAC, 0xA5, 0xA2,
    0x8F, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9D, 0x9A,
    0x27, 0x20, 0x29, 0x2E, 0x3B, 0x3C, 0x35, 0x32,
    0x1F, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0D, 0x0A,
    0x57, 0x50, 0x59, 0x5E, 0x4B, 0x4C, 0x45, 0x42,
    0x6F, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7D, 0x7A,
    0x89, 0x8E, 0x87, 0x80, 0x95, 0x92, 0x9B, 0x9C,
    0xB1, 0xB6, 0xBF, 0xB8, 0xAD, 0xAA, 0xA3, 0xA4,
    0xF9, 0xFE, 0xF7, 0xF0, 0xE5, 0xE2, 0xEB, 0xEC,
    0xC1, 0xC6, 0xCF, 0xC8, 0xDD, 0xDA, 0xD3, 0xD4,
    0x69, 0x6E, 0x67, 0x60, 0x75, 0x72, 0x7B, 0x7C,
    0x51, 0x56, 0x5F, 0x58, 0x4D, 0x4A, 0x43, 0x44,
    0x19, 0x1E, 0x17, 0x10, 0x05, 0x02, 0x0B, 0x0C,
    0x21, 0x26, 0x2F, 0x28, 0x3D, 0x3A, 0x33, 0x34,
    0x4E, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5C, 0x5B,
    0x76, 0x71, 0x78, 0x7F, 0x6A, 0x6D, 0x64, 0x63,
    0x3E, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2C, 0x2B,
    0x06, 0x01, 0x08, 0x0F, 0x1A, 0x1D, 0x14, 0x13,
    0xAE, 0xA9, 0xA0, 0xA7, 0xB2, 0xB5, 0xBC, 0xBB,
    0x96, 0x91, 0x98, 0x9F, 0x8A, 0x8D, 0x84, 0x83,
    0xDE, 0xD9, 0xD0, 0xD7, 0xC2, 0xC5, 0xCC, 0xCB,
    0xE6, 0xE1, 0xE8, 0xEF, 0xFA, 0xFD, 0xF4, 0xF3
};

inline uint8_t crc8_calc(const uint8_t* data, size_t len) {
    uint8_t crc = 0x00;
    for (size_t i = 0; i < len; i++) {
        crc = crc8_table[crc ^ data[i]];
    }
    return crc;
}
