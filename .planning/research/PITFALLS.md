# Pitfalls Research

**Domain:** Dual-ESP32 wireless command center (ESP-NOW, USB HID bridging, battery management, desktop companion app)
**Researched:** 2026-02-14
**Confidence:** MEDIUM-HIGH (most pitfalls verified across multiple sources + confirmed by existing codebase patterns)

## Critical Pitfalls

### Pitfall 1: ESP-NOW + WiFi Radio Contention Destroys Reliability

**What goes wrong:**
ESP-NOW and WiFi share the same 2.4 GHz radio on the ESP32-S3. When WiFi Station mode is connected to a router, ESP-NOW packet loss jumps to 80%+. The ESP32 uses time-division multiplexing between protocols, and WiFi power-save mode (MODEM_SLEEP) actively starves ESP-NOW of radio time.

**Why it happens:**
Developers assume ESP-NOW and WiFi are independent subsystems. They are not -- they share a single radio. When WiFi is associated with an AP, the radio spends most of its time listening to the AP's beacon interval and handling WiFi traffic. ESP-NOW packets get dropped silently.

**How to avoid:**
- On the CrowPanel (display unit): do NOT connect to WiFi. Use ESP-NOW only. If WiFi is needed for OTA or config, disconnect WiFi before resuming ESP-NOW communication.
- On the USB-bridge ESP32: same rule -- ESP-NOW only, no concurrent WiFi STA connection.
- Both peers MUST be on the same WiFi channel. Pin both to channel 1 (or whichever you choose) using `esp_wifi_set_channel()`.
- Call `esp_wifi_set_ps(WIFI_PS_NONE)` to disable power save on both units. This is mandatory for reliable ESP-NOW.
- Use `WIFI_MODE_STA` (not `WIFI_MODE_AP` or `WIFI_MODE_APSTA`) on both devices -- ESP-NOW works best in STA mode without an active AP connection.

**Warning signs:**
- Intermittent command delivery (hotkeys sometimes don't fire)
- Packet loss increases when WiFi scan runs
- ESP-NOW send callback reports failures sporadically
- Latency spikes above 50ms on what should be sub-5ms delivery

**Phase to address:**
Phase 1 (ESP-NOW communication foundation). Must be resolved before any higher-level protocol work begins.

---

### Pitfall 2: USB HID + CDC Composite Device Stalls on ESP32-S3

**What goes wrong:**
Running USB HID (keyboard) and USB CDC (serial for desktop companion app communication) simultaneously on the ESP32-S3 causes the USB stack to stall after extended use. Espressif has acknowledged this issue (arduino-esp32 #10307) and marked the fix as "Won't Do." The HID report queue fills up, CDC blocks waiting for the host to read, and the entire USB stack deadlocks.

**Why it happens:**
The ESP32-S3 has one USB OTG peripheral with TinyUSB handling the stack. Composite devices (HID + CDC) share the same USB endpoint resources. When the host (PC) is slow to read CDC data or the HID report rate is high, internal semaphores timeout and the device stops responding to USB entirely.

**How to avoid:**
- Do NOT run HID and CDC on the same ESP32. This is the architecture-level fix: the USB-bridge ESP32 does HID-only to the PC. Communication from the desktop companion app goes over a separate channel (dedicated serial/UART over USB-to-serial adapter, or a second USB CDC on a separate MCU).
- If composite is absolutely required: implement watchdog monitoring of USB stack health. When stall is detected, force USB re-enumeration via `tinyusb_driver_uninstall()` / `tinyusb_driver_install()`.
- Rate-limit CDC writes. Never write CDC data faster than the host reads it. Use non-blocking writes with overflow detection.

**Warning signs:**
- USB device disappears from host after 10-60 minutes of use
- "Report wait failed" errors in serial debug output
- Windows Device Manager shows "USB Device Not Recognized" after extended operation
- HID keypresses stop working but serial debug (if separate) still shows the ESP32 is running

**Phase to address:**
Phase 1 (Architecture decision). The two-ESP32 architecture must separate HID and serial concerns from the start.

---

### Pitfall 3: I2C Bus Contention Breaks Touch After Adding New Peripherals

**What goes wrong:**
The GT911 touch controller, PCA9557 I/O expander, and PCF8575 all share I2C on pins 19/20. Adding ESP-NOW communication handlers or battery monitoring via I2C (fuel gauges like MAX17048) creates timing conflicts. The GT911 requires periodic polling with specific register read sequences (write register address, delay, read data, write clear flag). If another I2C device transaction interrupts this sequence -- especially from an ISR or FreeRTOS task -- the GT911 goes into an undefined state and stops responding.

**Why it happens:**
The current code runs everything in a single `loop()` with no I2C bus locking. This works today because the polling is sequential. The moment ESP-NOW callbacks or battery monitoring tasks run on Core 0 while touch polling runs on Core 1, or when a FreeRTOS timer fires during a GT911 multi-step I2C transaction, bus corruption occurs.

**How to avoid:**
- Wrap ALL I2C access in a FreeRTOS mutex. Create a global `SemaphoreHandle_t i2c_mutex` and take/give it around every Wire transaction sequence (not individual calls -- the entire read-modify-write sequence for GT911 must be atomic).
- Move GT911 polling to a dedicated FreeRTOS task with guaranteed timing. The current `delay(1)` between I2C write and read is fragile; use `vTaskDelay(pdMS_TO_TICKS(2))` inside a task instead.
- Never call `Wire.begin()` after initial setup. The existing code already does this correctly, but any new library that calls `Wire.begin()` internally will reset the bus and break the GT911.
- If adding a battery fuel gauge, either: (a) put it on a separate I2C bus using the ESP32-S3's second I2C peripheral (Wire1 on different pins), or (b) ensure its polling frequency is low (every 10s) and uses the same mutex.

**Warning signs:**
- Touch stops responding after adding a new I2C device or task
- I2C errors (endTransmission returns non-zero) that appear intermittently
- GT911 needs re-discovery after being active for minutes/hours
- PCF8575 reads return 0xFFFF when they shouldn't

**Phase to address:**
Phase 1 (communication infrastructure). I2C mutex must be the first thing implemented before any new peripheral or task is added.

---

### Pitfall 4: LVGL 96KB Memory Pool Exhaustion With Multi-Page UI

**What goes wrong:**
The current `LV_MEM_SIZE` is 96KB. The existing single-page 4x3 grid with buttons and labels uses a modest amount. But adding statistics pages, settings screens, connection status overlays, animations, or charts will exhaust LVGL's internal heap. When LVGL runs out of memory, it silently fails to create widgets, returns NULL pointers, and eventually crashes when NULL objects are used.

**Why it happens:**
LVGL's internal memory allocator (TLSF) fragments over time, especially when screens are created and destroyed. Each `lv_obj_create()`, `lv_label_create()`, style allocation, and animation uses LVGL heap. A 96KB pool is tight for a 7" 800x480 display with multiple pages. The draw buffers are in PSRAM (good), but LVGL's widget heap is in internal SRAM (limited).

**How to avoid:**
- Increase `LV_MEM_SIZE` to at least 128KB, preferably 192KB. The ESP32-S3 with OPI PSRAM has ~8MB external RAM. While LVGL's internal allocator should ideally use internal SRAM for speed, 96KB is too conservative for multi-page UI.
- Alternatively, switch to `LV_MEM_CUSTOM 1` and use a custom allocator that uses PSRAM via `ps_malloc()`. This gives effectively unlimited LVGL heap but with a small performance penalty for widget operations (not display rendering, which already uses PSRAM buffers).
- Do NOT create/destroy screens dynamically. Instead, create all screens at startup and use `lv_scr_load()` / `lv_scr_load_anim()` to switch. This avoids fragmentation.
- Enable `LV_USE_ASSERT_MALLOC 1` (already enabled) and also enable `LV_USE_LOG 1` during development to catch allocation failures early.
- Monitor free LVGL memory periodically: `lv_mem_monitor_t mon; lv_mem_monitor(&mon); Serial.printf("LVGL free: %d%%\n", mon.free_biggest_size);`

**Warning signs:**
- Widgets don't appear on screen after creation (NULL return from `lv_*_create`)
- Random crashes when navigating between screens
- UI works initially but degrades after screen switches
- `lv_mem_monitor()` shows fragmentation above 50% or free memory below 10KB

**Phase to address:**
Phase 2 (UI expansion). Must be addressed before building multi-page interfaces.

---

### Pitfall 5: ESP-NOW Message Framing and Reliability Without ACK Protocol

**What goes wrong:**
Developers send raw hotkey commands over ESP-NOW and assume delivery. ESP-NOW has built-in ACK at the MAC layer (the send callback tells you if the peer acknowledged), but this only confirms the frame reached the other radio -- NOT that the application processed it. If the receiving ESP32 is busy (handling a USB HID report, doing I2C, or in a critical section), the ESP-NOW receive callback may fire but the data gets dropped before the application acts on it.

**Why it happens:**
ESP-NOW's 250-byte packet limit and low-level ACK give a false sense of reliability. The MAC-layer ACK means "radio received it," not "application handled it." There's no built-in retry at the application layer, no sequence numbers, and no way to know if a hotkey actually fired on the PC.

**How to avoid:**
- Implement a simple application-layer ACK protocol: sender sends command with sequence number, receiver processes and sends ACK with same sequence number. Sender retries 2-3 times with 20ms timeout if no ACK received.
- Use a small ring buffer on the receiver to queue incoming commands. Process them in the main loop, not in the ESP-NOW receive callback (callbacks run in WiFi task context and must return quickly).
- Include a message type byte in every packet: `CMD_HOTKEY`, `CMD_ACK`, `CMD_STATS_REQUEST`, `CMD_STATS_RESPONSE`, `CMD_HEARTBEAT`. This prevents protocol confusion as features are added.
- Keep ESP-NOW receive callback minimal: copy data to queue, return immediately. Do NOT call Wire, USB, or any blocking function from the callback.

**Warning signs:**
- Hotkeys "sometimes don't work" with no error messages
- Works perfectly in testing, fails under real use (because testing is low-frequency)
- Adding console.log/Serial.print in receive callback "fixes" timing issues (masks the real problem)

**Phase to address:**
Phase 1 (ESP-NOW protocol design). The message format and ACK protocol must be defined before implementing any commands.

---

### Pitfall 6: CrowPanel USB-C Port Cannot Serve Both Programming and HID

**What goes wrong:**
The CrowPanel 7.0" routes its USB-C through a CH340 or similar USB-to-serial bridge for programming. This is NOT the ESP32-S3's native USB OTG port. The native USB pins (GPIO 19/20) are already used for I2C (GT911 touch + I/O expanders). This means the CrowPanel physically cannot act as a USB HID device through its USB-C port -- the USB data lines are connected to a UART bridge, not to the ESP32-S3's USB peripheral.

**Why it happens:**
The CrowPanel was designed as a display/HMI device, not as a USB peripheral. The ESP32-S3 has native USB on GPIO 19/20, but CrowPanel uses those pins for I2C. The USB-C port provides power and serial programming only.

**How to avoid:**
- Accept this hardware constraint: the CrowPanel will NEVER be a USB HID device directly. This is why the two-ESP32 architecture exists.
- The second ESP32 (USB bridge unit) provides USB HID to the PC. It receives commands from the CrowPanel via ESP-NOW (wireless) or UART (wired backup).
- For the desktop companion app communication: use the CrowPanel's existing serial-over-USB (CH340) for debug/config, and the bridge ESP32's connection for runtime data.
- Do NOT attempt to remap I2C to free up GPIO 19/20 for USB -- the touch controller and I/O expanders are hardwired on the CrowPanel PCB.

**Warning signs:**
- Spending time trying to get USB HID working on the CrowPanel itself
- USB HID examples compile but "device not recognized" on host (because data goes through CH340, not USB OTG)
- Confusion about which USB port does what

**Phase to address:**
Architecture (pre-Phase 1). This constraint must be understood and accepted before any design work.

---

### Pitfall 7: Battery Power Management Without Hardware Protection

**What goes wrong:**
Adding a LiPo battery to the CrowPanel without proper under-voltage protection discharges the cell below 2.9V, permanently damaging it. The ESP32-S3 with WiFi radio draws current spikes of 300-500mA during transmission. A LiPo at 3.5V nominal can brownout the voltage regulator during these spikes, causing random resets. If the CrowPanel uses a linear regulator (like AMS1117-3.3), the dropout voltage means the battery must stay above ~4.4V, which a LiPo reaches only when nearly full.

**Why it happens:**
Developers add a battery and charging circuit without understanding the full current profile. The 7" display backlight alone draws significant current. ESP-NOW transmissions add burst current. The 470x480 RGB display interface continuously refreshes, consuming steady power. Without a proper BMS (Battery Management System), there's no cutoff when voltage drops.

**How to avoid:**
- Use a battery with built-in protection PCB (most quality LiPo cells include one). Never use bare cells.
- Add a 470uF+ capacitor on the 3.3V rail to buffer current spikes during radio transmission.
- Use a buck-boost or LDO with dropout voltage under 200mV (NOT AMS1117). Candidates: HT7333 (4uA quiescent), ME6211 (low dropout), or RT9080 (ultra-low quiescent for sleep).
- Monitor battery voltage via ADC. Enter deep sleep or disable non-essential features (WiFi, backlight reduction) when voltage drops below 3.4V. Hard shutdown at 3.2V.
- If the CrowPanel has an onboard regulator already, characterize its dropout voltage before adding battery power. The regulator may be suitable or may need bypassing.

**Warning signs:**
- ESP32 randomly resets under battery power but works fine on USB
- Battery swells or gets warm during discharge (over-discharge damage)
- Brownout detector triggers (visible in serial output as "Brownout detector was triggered")
- Battery life is much shorter than calculated (regulator dropout eating usable voltage range)

**Phase to address:**
Phase 4 (Battery management). Requires hardware characterization of the CrowPanel's power circuit first.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `delay()` in touch polling | Simple timing | Blocks entire loop, prevents concurrent work | Never in final code -- replace with FreeRTOS task + vTaskDelay |
| Single `loop()` architecture | Easy to understand | Cannot handle ESP-NOW callbacks + touch + UI + serial simultaneously | Only in initial proof of concept |
| Raw byte arrays for ESP-NOW messages | Quick to implement | No versioning, no way to add fields without breaking protocol | Never -- use a struct with version byte from day one |
| Polling PCF8575 in main loop | Works for testing | Wastes I2C bandwidth, adds bus contention | Replace with interrupt-driven reads via INT pin |
| Hardcoded hotkey definitions | Fast to build | Cannot update without reflashing | Acceptable for MVP, but add config storage by Phase 3 |
| `delay(50)` after HID keypress | Ensures host registers keypress | Blocks everything for 50ms per keypress | Replace with non-blocking timer or FreeRTOS task |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ESP-NOW send callback | Blocking on send result in callback context | Copy result to flag variable, check in main loop. Callbacks run in WiFi task -- must return in <1ms |
| ESP-NOW receive callback | Processing message (I2C, USB, Serial) inside callback | Copy to FreeRTOS queue (xQueueSendFromISR), process in application task |
| USB HID on bridge ESP32 | Sending keypresses faster than host can process | Rate-limit to one keypress event per 20ms minimum. USB HID poll interval is typically 10ms |
| Desktop companion app serial | Assuming serial port stays connected | Implement reconnection logic with device enumeration. USB CDC devices disappear during ESP32 reset or sleep |
| LVGL from multiple tasks | Calling lv_* functions from ESP-NOW callback or timer ISR | All LVGL calls must happen from one task only. Use a message queue to trigger UI updates from other contexts |
| UART between two ESP32s | Assuming UART is reliable without framing | Implement packet framing (start byte, length, CRC, end byte). UART has no built-in message boundaries -- bytes arrive as a stream |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Touch polling with `delay(1)` in main loop | UI feels sluggish, LVGL refresh rate drops | Move touch to dedicated task on Core 0, UI on Core 1 | Immediately noticeable at >2 I2C devices |
| Logging Serial.printf in every touch event | Touch latency increases, LVGL timer handler starved | Use ring buffer logger, print only on debug timer | When touch events fire 30+ times/sec |
| ESP-NOW broadcast instead of unicast | All nearby ESP32s receive and process every packet | Use peer-to-peer with MAC address. Register specific peer | When other ESP32 devices exist nearby |
| LVGL full-screen redraw on every stats update | Display flickers, frame rate drops below 30fps | Use `lv_label_set_text()` on existing labels, not screen recreation | When stats update frequency exceeds 2Hz |
| Polling battery ADC every loop iteration | ADC noise, wasted CPU, I2C bus contention if using fuel gauge | Poll every 10-30 seconds. Battery voltage changes slowly | Immediately -- adds unnecessary load |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| No ESP-NOW encryption | Anyone nearby can inject fake hotkey commands (keystroke injection attack) | Enable ESP-NOW encryption with PMK/LMK. Use `esp_now_set_pmk()` and set LMK per peer |
| No pairing/authentication between ESP32 pair | Rogue device can impersonate either unit | Implement a pairing protocol: first-time setup exchanges keys, stored in NVS. Reject unknown MACs |
| Desktop companion app trusts all serial data | Malicious USB device could send crafted serial data to companion app | Validate all incoming serial data. Use message authentication (HMAC) if companion app has elevated privileges |
| HID keyboard with no physical safety | Accidental touch sends keystrokes to wrong application | Implement a "lock" mode on the touchscreen. Require deliberate gesture to unlock sending |
| OTA updates over WiFi without verification | Man-in-the-middle could push malicious firmware | Use signed OTA with ESP-IDF's secure boot, or at minimum verify firmware hash before applying |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No visual feedback for connection state | User presses hotkeys not knowing bridge is disconnected | Persistent status indicator (LED color or screen icon) showing ESP-NOW link state |
| Keypresses sent with no confirmation | User unsure if keypress was received by PC | Brief visual feedback on button (color flash or animation) confirming delivery + ACK |
| Battery dies without warning | Device stops working unexpectedly | Progressive warnings: screen notification at 20%, reduced brightness at 10%, graceful shutdown at 5% |
| Settings require reflashing | Users cannot customize hotkeys | Add settings screen accessible via long-press or dedicated button |
| Desktop app shows stale data after reconnect | Statistics appear current but are from before disconnect | Clear all stats on reconnection, display "reconnecting..." state, timestamp all data |
| Touch debounce issues cause double-presses | Single tap sends hotkey twice | Implement proper debounce in LVGL (LV_INDEV_DEF_READ_PERIOD at 30ms is good) and in hotkey callback (ignore repeat within 200ms) |

## "Looks Done But Isn't" Checklist

- [ ] **ESP-NOW pairing:** Works in testing but fails after power cycle -- verify MAC addresses are stored in NVS, not hardcoded
- [ ] **USB HID:** Works for basic keys but fails for media keys or multi-key combos -- verify HID report descriptor includes all needed usage pages
- [ ] **Battery level display:** Shows percentage but never updates -- verify ADC calibration and that monitoring task is actually running
- [ ] **Desktop companion app connection:** Shows "connected" but data is stale -- verify heartbeat/keepalive mechanism, not just port-open detection
- [ ] **Multi-page UI:** Pages render correctly but memory grows on each switch -- verify screens are reused not recreated, check lv_mem_monitor()
- [ ] **ESP-NOW range:** Works on desk but fails across room -- verify both units use external antenna (if available) and are on same channel with no WiFi interference
- [ ] **Deep sleep wake:** Device wakes from sleep but ESP-NOW is broken -- verify WiFi is re-initialized and ESP-NOW peers are re-registered after wake
- [ ] **UART fallback:** UART communication works but no framing -- verify CRC checking prevents corrupted commands from firing hotkeys

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| I2C bus lockup (GT911 hangs) | LOW | Toggle GT911 reset pin via PCA9557, re-run gt911_discover(). Already have reset circuit in hardware |
| USB HID stall on bridge ESP32 | MEDIUM | Implement USB watchdog: if no successful HID report in 5s, force USB stack reinit. May cause brief host-side disconnect |
| ESP-NOW channel mismatch after WiFi use | LOW | Store channel in NVS. On boot, set channel from NVS before calling esp_now_init(). Never let WiFi auto-channel selection override |
| LVGL memory exhaustion | HIGH | Requires code refactor. Cannot recover at runtime -- if LVGL heap is exhausted, widgets are corrupted. Must redesign screens for lower memory or increase pool |
| Battery over-discharge | HIGH (hardware) | Cannot recover damaged LiPo cell. Prevention only: hardware BMS + software monitoring. If cell is swollen, replace immediately |
| ESP-NOW + WiFi radio conflict | LOW | Call esp_wifi_disconnect(), wait 100ms, resume ESP-NOW. Can be automated with a "WiFi window" pattern for OTA |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| ESP-NOW/WiFi radio contention | Phase 1: ESP-NOW foundation | Packet loss test: send 1000 messages, verify >99% delivery |
| USB HID+CDC composite stall | Phase 1: Architecture decision | Confirmed by design: HID-only on bridge ESP32, no CDC composite |
| I2C bus contention | Phase 1: Communication infra | Add I2C mutex, stress test with simultaneous touch + PCF8575 + new device |
| LVGL memory exhaustion | Phase 2: UI expansion | Run lv_mem_monitor() on every screen, verify >30% free after all screens created |
| ESP-NOW message reliability | Phase 1: Protocol design | Implement ACK protocol, verify with packet loss simulation (drop every 10th packet) |
| CrowPanel USB-C limitation | Pre-Phase 1: Architecture | Document in architecture doc, no verification needed -- hardware constraint |
| Battery power management | Phase 4: Battery integration | Measure voltage under load (WiFi TX), verify regulator dropout, test brownout detection |
| Touch debounce / double-press | Phase 2: UI refinement | Tap each button 100 times rapidly, verify exactly 100 events fired |
| ESP-NOW security / encryption | Phase 3: Hardening | Attempt to send commands from unauthorized device, verify rejection |
| Desktop app reconnection | Phase 3: Companion app | Kill and restart companion app, verify automatic reconnection within 5s |

## Sources

- [ESP-NOW + WiFi coexistence -- ESP32 Forum](https://www.esp32.com/viewtopic.php?t=12772) -- 80%+ packet loss when WiFi STA connected
- [ESP-NOW + WiFi simultaneously -- Arduino Forum](https://forum.arduino.cc/t/use-esp-now-and-wifi-simultaneously-on-esp32/1034555) -- channel pinning requirement
- [ESP32-S3 HID+CDC stall -- arduino-esp32 #10307](https://github.com/espressif/arduino-esp32/issues/10307) -- confirmed simultaneous CDC+HID stalls
- [ESP32-S3 HID+CDC "Won't Do" -- esp-idf #13240](https://github.com/espressif/esp-idf/issues/13240) -- Espressif declined to fix
- [UART buffer overflow -- esp-idf #9682](https://github.com/espressif/esp-idf/issues/9682) -- 128-byte hardcoded UART buffer
- [UART locks and stops receiving -- arduino-esp32 #6326](https://github.com/espressif/arduino-esp32/issues/6326) -- RX stops when buffer full
- [LVGL memory and ESP32 -- LVGL Forum](https://forum.lvgl.io/t/memory-and-esp32/4050) -- memory management strategies
- [ESP32 battery low voltage issues -- espboards.dev](https://www.espboards.dev/troubleshooting/issues/power/esp32-battery-low-voltage/) -- under-voltage protection
- [ESP32 deep sleep power drain -- Home Assistant Community](https://community.home-assistant.io/t/esp32-deep-sleep-and-massive-power-drain/813330) -- radio not shut down before sleep
- [RF Coexistence -- ESP-IDF official docs](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/coexist.html) -- time-division multiplexing documentation
- [CrowPanel 7" I2C port + touch -- Elecrow Forum](https://forum.elecrow.com/discussion/4618/esp32-5-hmi-i2c-port-with-touch) -- I2C shared bus design
- [GT911 I2C address configuration -- Arduino Forum](https://forum.arduino.cc/t/gt911-i2c-touch-connects-to-esp32s3-screen/1330774) -- dual address behavior
- [ESP32-S3 USB CDC not working on every computer -- arduino-esp32 #9580](https://github.com/espressif/arduino-esp32/issues/9580) -- CDC reliability issues
- Existing project codebase analysis: `/data/Elcrow-Display-hotkeys/src/main.cpp`, `platformio.ini`, `lv_conf.h`

---
*Pitfalls research for: Dual-ESP32 wireless command center (Elcrow Display Hotkeys)*
*Researched: 2026-02-14*
