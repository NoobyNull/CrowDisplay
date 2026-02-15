# Roadmap: CrowPanel Command Center

## Overview

This roadmap delivers a wireless desktop command center in five phases, building from a proven wired hotkey pipeline through wireless transport, live system monitoring, battery-powered operation, and user-configurable layouts. Each phase delivers a complete, testable capability: wired hotkeys first (removing wireless uncertainty), then ESP-NOW dual-link transport, then PC stats streaming, then untethered battery operation, and finally persistent user-customizable hotkey layouts via a desktop GUI editor.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Wired Command Foundation** - End-to-end hotkey delivery over UART with multi-page touch UI
- [ ] **Phase 2: Wireless Link + Dual Transport** - ESP-NOW wireless link with transport abstraction and automatic failover
- [x] **Phase 3: Stats Display + Companion App** - Live PC metrics streaming to persistent stats header on display
- [ ] **Phase 4: Battery Management + Power States** - Untethered battery operation with power state machine and clock mode
- [ ] **Phase 5: Configuration + GUI Editor** - Persistent user-customizable hotkey layouts via desktop GUI editor

## Phase Details

### Phase 1: Wired Command Foundation
**Goal**: User taps a button on the display, the correct keyboard shortcut fires on the PC over a wired UART link
**Depends on**: Nothing (first phase)
**Requirements**: COMM-01, COMM-03, BRDG-01, BRDG-02, BRDG-03, DISP-01, DISP-02, DISP-03, DISP-04, DISP-05, DISP-12
**Success Criteria** (what must be TRUE):
  1. User taps a hotkey button on the display and the corresponding keyboard shortcut (including modifier+key combos like Ctrl+C, Alt+Tab) fires on the PC within 50ms
  2. User can swipe between at least 3 pages of 12 hotkey buttons each, with buttons showing icons, labels, and category-based color coding
  3. Buttons show visible press feedback (color darken + shrink) on tap, confirming the touch registered
  4. Bridge ESP32-S3 appears as a standard USB HID keyboard on the PC with no driver installation required
  5. Touch input remains stable with no I2C bus corruption during sustained use (mutex-protected bus access)
**Plans**: 4 plans

Plans:
- [ ] 01-01-PLAN.md — Project restructure: dual-firmware architecture, shared protocol header, display hardware skeleton with I2C mutex
- [ ] 01-02-PLAN.md — Bridge firmware: USB HID keyboard, UART receive with SOF parser, hotkey command dispatch
- [ ] 01-03-PLAN.md — Display firmware: multi-page hotkey UI with tabview, icons, colors, press feedback, UART transmit
- [ ] 01-04-PLAN.md — End-to-end verification checkpoint: human tests full hotkey pipeline

### Phase 2: Wireless Link + Dual Transport
**Goal**: Display and bridge communicate wirelessly over ESP-NOW with automatic failover between wired and wireless links
**Depends on**: Phase 1
**Requirements**: COMM-02, COMM-04, COMM-05, COMM-06, COMM-07, COMM-08
**Success Criteria** (what must be TRUE):
  1. User can unplug the UART cable and hotkey commands continue to fire on the PC over ESP-NOW with no manual intervention
  2. User can reconnect the UART cable and traffic automatically routes back to the wired link (preferred when available)
  3. Hotkey commands are reliably delivered even under wireless packet loss (application-layer ACK with retries confirms receipt)
  4. Display UI shows ESP-NOW connection status so user knows whether the wireless link is active
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Stats Display + Companion App
**Goal**: Live PC system metrics stream from a desktop companion app through the bridge to a persistent stats header on the display
**Depends on**: Phase 2
**Requirements**: BRDG-04, BRDG-05, DISP-06, DISP-07, COMP-01, COMP-02
**Success Criteria** (what must be TRUE):
  1. Display shows a persistent stats header bar at the top of the screen with CPU, RAM, GPU, network, and disk usage updating at 1-2 Hz
  2. Stats header remains visible while user navigates between hotkey pages
  3. Bridge relays media key commands (play/pause, volume, next/prev, mute) from display to PC as USB consumer control reports
  4. Companion app launches on Linux PC and begins streaming stats with no manual configuration
**Plans**: 4 plans

Plans:
- [ ] 03-01-PLAN.md — Protocol extension + bridge composite USB HID (Keyboard + ConsumerControl + Vendor) with stats relay
- [ ] 03-02-PLAN.md — Display firmware: Hyprland hotkey pages rework, stats header bar, media key + stats message handling
- [ ] 03-03-PLAN.md — Python companion app: stats collection via psutil/pynvml, HID output reports via hidapi, systemd service
- [ ] 03-04-PLAN.md — End-to-end verification checkpoint: stats pipeline, media keys, Hyprland hotkeys

### Phase 4: Battery Management + Power States
**Goal**: Display operates untethered on battery power with intelligent power states and clock mode when the PC is off
**Depends on**: Phase 3
**Requirements**: BRDG-07, DISP-08, DISP-09, DISP-10, DISP-11, PWR-01, PWR-02, PWR-03, PWR-04, PWR-05, COMP-03
**Success Criteria** (what must be TRUE):
  1. Display runs on LiPo battery with battery percentage shown in the stats header bar
  2. Stats header shows device status indicators: battery level, ESP-NOW link state, and brightness control
  3. Display dims after idle timeout, then enters clock mode (showing time and battery) when companion app sends shutdown signal before PC powers off
  4. Display wakes from clock mode automatically when the bridge comes back online (PC turns on)
  5. User can adjust display brightness from the stats header without leaving the hotkey view
**Plans**: 4 plans

Plans:
- [ ] 04-01-PLAN.md — Protocol extension + battery module + power state machine + brightness wrappers
- [ ] 04-02-PLAN.md — Companion app D-Bus shutdown listener + time sync + type-prefixed HID protocol
- [ ] 04-03-PLAN.md — Display UI (device status header + clock screen) + main loop integration + bridge relay
- [ ] 04-04-PLAN.md — End-to-end verification checkpoint: power states, battery, clock mode, brightness

### Phase 5: Configuration + GUI Editor
**Goal**: Users design and deploy custom hotkey layouts from a desktop GUI editor, with configurations persisting across power cycles
**Depends on**: Phase 4
**Requirements**: BRDG-06, COMP-04, COMP-05, COMP-06, CONF-01, CONF-02, CONF-03, CONF-04
**Success Criteria** (what must be TRUE):
  1. User opens desktop GUI editor, designs a multi-page hotkey layout with custom labels, icons, shortcuts, and button colors, and pushes it to the display
  2. Hotkey layout survives power cycles (stored persistently on display in NVS or LittleFS)
  3. User can read the current layout from the display into the GUI editor for modification
  4. Configs larger than 250 bytes transfer reliably via chunked protocol over ESP-NOW or UART
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Wired Command Foundation | 4/4 | Complete | 2026-02-15 |
| 2. Wireless Link + Dual Transport | N/A | Complete (merged into Phase 1) | 2026-02-15 |
| 3. Stats Display + Companion App | 4/4 | Complete | 2026-02-15 |
| 4. Battery Management + Power States | 0/TBD | Not started | - |
| 5. Configuration + GUI Editor | 0/TBD | Not started | - |
