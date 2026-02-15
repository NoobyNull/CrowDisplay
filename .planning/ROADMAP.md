# Roadmap: CrowPanel Command Center

## Milestones

- [x] **v1.0 MVP** - Phases 1-4 (shipped 2026-02-15)
- [ ] **v1.1 System Control** - Phases 5-8 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>v1.0 MVP (Phases 1-4) - SHIPPED 2026-02-15</summary>

### Phase 1: Wired Command Foundation
**Goal**: User taps a button on the display, the correct keyboard shortcut fires on the PC over a wired UART link
**Plans**: 4 plans (complete)

Plans:
- [x] 01-01-PLAN.md -- Project restructure: dual-firmware architecture, shared protocol header, display hardware skeleton with I2C mutex
- [x] 01-02-PLAN.md -- Bridge firmware: USB HID keyboard, UART receive with SOF parser, hotkey command dispatch
- [x] 01-03-PLAN.md -- Display firmware: multi-page hotkey UI with tabview, icons, colors, press feedback, UART transmit
- [x] 01-04-PLAN.md -- End-to-end verification checkpoint: human tests full hotkey pipeline

### Phase 2: Wireless Link + Dual Transport
**Goal**: Display and bridge communicate wirelessly over ESP-NOW with automatic failover between wired and wireless links
**Plans**: N/A (merged into Phase 1)

### Phase 3: Stats Display + Companion App
**Goal**: Live PC system metrics stream from a desktop companion app through the bridge to a persistent stats header on the display
**Plans**: 4 plans (complete)

Plans:
- [x] 03-01-PLAN.md -- Protocol extension + bridge composite USB HID (Keyboard + ConsumerControl + Vendor) with stats relay
- [x] 03-02-PLAN.md -- Display firmware: Hyprland hotkey pages rework, stats header bar, media key + stats message handling
- [x] 03-03-PLAN.md -- Python companion app: stats collection via psutil/pynvml, HID output reports via hidapi, systemd service
- [x] 03-04-PLAN.md -- End-to-end verification checkpoint: stats pipeline, media keys, Hyprland hotkeys

### Phase 4: Battery Management + Power States
**Goal**: Display operates untethered on battery power with intelligent power states and clock mode when the PC is off
**Plans**: 4 plans (complete)

Plans:
- [x] 04-01-PLAN.md -- Protocol extension + battery module + power state machine + brightness wrappers
- [x] 04-02-PLAN.md -- Companion app D-Bus shutdown listener + time sync + type-prefixed HID protocol
- [x] 04-03-PLAN.md -- Display UI (device status header + clock screen) + main loop integration + bridge relay

</details>

## v1.1 System Control (In Progress)

**Milestone Goal:** Make the display fully configurable -- all hotkey layouts, button properties, and visual assets defined by config files on SD card, editable via a Linux GUI app and pushed over WiFi.

- [x] **Phase 5: Config Data Model + SD Loading** - JSON config schema, parser, SD card persistence with fallback defaults
- [ ] **Phase 6: Data-Driven Display UI** - Display renders pages and buttons dynamically from parsed config struct
- [ ] **Phase 7: Config Server (SoftAP + HTTP)** - WiFi upload of config files with validation, OTA merge, ESP-NOW coexistence
- [ ] **Phase 8: Desktop GUI Editor** - PySide6 visual layout editor with direct WiFi deploy to device

## Phase Details

### Phase 5: Config Data Model + SD Loading
**Goal**: Hotkey layouts are defined in a human-readable JSON file on SD card, parsed at boot into an in-memory config struct, with robust fallback to built-in defaults
**Depends on**: Phase 4 (v1.0 shipped)
**Requirements**: CFG-01, CFG-02, CFG-03, CFG-04, CFG-05, CFG-06, CFG-07, CFG-08
**Success Criteria** (what must be TRUE):
  1. Device boots and loads hotkey layout from a JSON config file on SD card -- pages, buttons, labels, key bindings, colors, icons, and media key consumer codes all read from the file
  2. Device boots to a usable default hotkey layout when the SD card is missing, the config file is absent, or the JSON is malformed
  3. Config file includes a version field, and the device can distinguish config format versions
  4. When a new config is saved, the previous config.json is automatically backed up to config.json.bak, and writes use atomic temp-file-then-rename to prevent corruption on power loss
**Plans**: 1 plan

Plans:
- [x] 05-01-PLAN.md -- ArduinoJson v7 migration, version field, backup + atomic save, page validation

### Phase 6: Data-Driven Display UI
**Goal**: Display UI renders pages and buttons entirely from the in-memory config struct, enabling hot-reload of layouts without device reboot
**Depends on**: Phase 5
**Requirements**: DRVUI-01, DRVUI-02, DRVUI-03, DRVUI-04, DRVUI-05
**Success Criteria** (what must be TRUE):
  1. Display shows the exact number of pages and buttons defined in the config file, with each button displaying its configured label, color, icon symbol, and keystroke description
  2. User can edit the JSON config on SD card (manually or via upload), and the display renders the updated layout after a config reload -- without rebooting the device
  3. Repeated config reloads do not degrade performance or exhaust LVGL memory (widget-pool pattern prevents leaks across at least 10 consecutive reloads)
**Plans**: 2 plans

Plans:
- [ ] 06-01-PLAN.md -- Fix config lifetime bugs, eliminate Hotkey struct, single config-driven render path
- [ ] 06-02-PLAN.md -- Full-screen rebuild with lv_obj_clean, deferred rebuild flag, LVGL memory monitoring

### Phase 7: Config Server (SoftAP + HTTP)
**Goal**: User can wirelessly upload new hotkey configs to the display via a WiFi access point and HTTP server, with validation and seamless ESP-NOW coexistence
**Depends on**: Phase 6
**Requirements**: WIFI-01, WIFI-02, WIFI-03, WIFI-04, WIFI-05, WIFI-06, WIFI-07
**Success Criteria** (what must be TRUE):
  1. User taps a config icon in the stats header and the display enters SoftAP config mode, showing the WiFi SSID, password, and IP address on screen
  2. User can POST a JSON config file to the HTTP server from any HTTP client (browser, curl, editor app), and the display validates the JSON, writes it to SD, and rebuilds the UI -- all without rebooting
  3. SoftAP auto-stops after 5 minutes of inactivity, or immediately when the user taps "Apply and Exit"
  4. Hotkey commands continue to reach the PC over ESP-NOW while config mode is active (WiFi channel pinned to avoid ESP-NOW disruption)
  5. OTA firmware upload is available on the same HTTP server alongside config upload
**Plans**: 2 plans

Plans:
- [ ] 07-01-PLAN.md -- Merge OTA into unified config_server, WiFi channel pinning, inactivity timeout, error propagation fix
- [ ] 07-02-PLAN.md -- Config mode UI screen with header icon, SSID/password/IP display, Apply & Exit button

### Phase 8: Desktop GUI Editor
**Goal**: User designs hotkey layouts visually in a desktop app and deploys them directly to the device over WiFi
**Depends on**: Phase 7
**Requirements**: EDIT-01, EDIT-02, EDIT-03, EDIT-04, EDIT-05, EDIT-06, EDIT-07
**Success Criteria** (what must be TRUE):
  1. User opens the PySide6 editor app and sees a visual button grid matching the device layout, with buttons showing their configured labels, colors, and icons
  2. User clicks any button in the grid to edit its properties (label, keyboard shortcut, color, icon) in a side panel, and can add, remove, rename, and reorder pages
  3. User can save the layout to a local JSON file and load existing JSON files for editing
  4. User can capture keyboard shortcuts by pressing key combos (recorder mode) instead of typing modifier names manually
  5. User clicks "Deploy" and the config is pushed to the device over WiFi HTTP -- the device validates, saves, and rebuilds the UI without reboot
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 -> 6 -> 7 -> 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Wired Command Foundation | v1.0 | 4/4 | Complete | 2026-02-15 |
| 2. Wireless Link (merged) | v1.0 | N/A | Complete | 2026-02-15 |
| 3. Stats Display + Companion | v1.0 | 4/4 | Complete | 2026-02-15 |
| 4. Battery + Power States | v1.0 | 3/3 | Complete | 2026-02-15 |
| 5. Config Data Model + SD Loading | v1.1 | 1/1 | Complete | 2026-02-15 |
| 6. Data-Driven Display UI | v1.1 | 0/2 | Planned | - |
| 7. Config Server (SoftAP + HTTP) | v1.1 | 0/TBD | Not started | - |
| 8. Desktop GUI Editor | v1.1 | 0/TBD | Not started | - |
