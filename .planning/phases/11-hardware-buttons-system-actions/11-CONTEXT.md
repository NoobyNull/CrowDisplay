# Phase 11: Hardware Buttons + System Actions - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Read 4 physical push buttons and 1 rotary encoder (with push) via PCF8575 I/O expander on TCA9548A I2C mux. Map hardware inputs to configurable actions using the same action system as touchscreen buttons. Add new "system" action types (page nav, mode switch, display controls) available to both hardware and touch buttons. Add editor UI for hardware button config and a dedicated settings tab for display function configuration (clock, slideshow, power, mode cycle, SD card management).

</domain>

<decisions>
## Implementation Decisions

### Hardware Pin Mapping
- PCF8575 I/O expander on TCA9548A mux channel 0
- PCF8575 I2C address: auto-detect (likely 0x20 default)
- Button 1: P1 (active low, depressed connects to ground)
- Button 2: P2 (active low)
- Button 3: P3 (active low)
- Button 4: P4 (active low)
- Encoder push/switch: P0 (active low)
- Encoder CLK: P11
- Encoder DT: P10
- All inputs are active low (pull-up, grounded when pressed)

### Button Configuration Model
- All 4 buttons are fully configurable -- same action system as touchscreen widgets
- No fixed-function buttons; user assigns any action type per button in editor
- Single press only, no long-press support
- Hardware buttons reuse the existing properties panel (action type dropdown with all action types including new system actions)

### Encoder Configuration Model
- Encoder is a single configurable input with push as its own action
- CW/CCW represent positive/negative of the assigned action (e.g., volume +/-, page next/prev, workspace slide left/right)
- One action per detent (no continuous/rapid-fire)
- "App select" encoder mode: rotation cycles through and highlights widgets on the current page, wrapping at the end; encoder push fires the highlighted widget's action

### System Action Types
- New action types available for BOTH hardware buttons AND touchscreen widgets
- Page navigation: next page, prev page, go to specific page N
- Mode switch: cycle through configurable set of display modes
- Config mode: enter SoftAP config mode
- Brightness: include if GPIO PWM works on hardware, otherwise degrade to on/off toggle -- test first
- All system actions execute locally on the display firmware (no PC/companion needed)

### Mode Cycle Configuration
- All 4 display modes available: hotkeys, clock, slideshow, standby
- User configures which modes are in the rotation and their order
- Mode switch action cycles through the configured mode list

### Editor UI -- Hardware Section
- Hardware buttons and encoder appear on the canvas BELOW the 800x480 display area, simulating their physical position on the device bezel
- Clicking a hardware button opens the same properties panel as touchscreen widgets
- Encoder shown as a single widget; properties panel shows push action + CW/CCW action assignment

### Editor UI -- Settings Tab
- Dedicated tab alongside page tabs at the top of the editor
- Clock settings: analog+digital style (keep existing Phase 9 implementation), 12/24h, color theme
- Slideshow settings: interval, transition effect; images must be in /slideshow/ root folder on SD card
- Power settings: dim timeout, sleep timeout, wake-on-touch
- Mode cycle settings: which modes are enabled and their rotation order
- SD card management: show capacity/usage, list files, delete files from companion app

### SD Card Management
- Companion editor manages SD card contents over WiFi
- HTTP endpoints on existing config server for file listing, usage stats, and file deletion

### Claude's Discretion
- Config storage approach (same config.json vs separate settings file)
- SD card HTTP API endpoint design (/api/sd/list, /api/sd/usage, /api/sd/delete or similar)
- Encoder debounce and quadrature decode implementation
- PCF8575 polling interval vs interrupt-driven approach
- Visual representation of hardware buttons below canvas (styling, layout)
- Brightness PWM GPIO pin and implementation (if available)

</decisions>

<specifics>
## Specific Ideas

- Encoder "app select" mode is a key interaction: rotate highlights widgets sequentially on the current page, push activates the highlighted one -- like keyboard focus navigation but with a physical knob
- Hardware buttons positioned below the 800x480 canvas in the editor mirrors their physical bezel position -- makes the editor a 1:1 representation of the device
- Slideshow images always in /slideshow/ root directory on SD card (fixed path)
- SD card capacity and file management visible in the settings tab -- user can see what's using space and delete files without removing the SD card

</specifics>

<deferred>
## Deferred Ideas

- None -- discussion stayed within phase scope

</deferred>

---

*Phase: 11-hardware-buttons-system-actions*
*Context gathered: 2026-02-17*
