# Phase 3: Stats Display + Companion App - Context

**Gathered:** 2026-02-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Live PC system metrics streaming to a persistent stats header on the display, plus reworked hotkey pages for Hyprland Linux. Stats flow from companion app through the bridge's existing USB HID connection (single cable) via ESP-NOW to the display. Desktop notifications are deferred.

</domain>

<decisions>
## Implementation Decisions

### Stats data path
- Single USB cable from bridge to PC (the HID cable)
- Companion app sends stats as USB HID raw/feature reports to the bridge — NO UART, NO second USB cable
- Bridge receives HID output reports, parses stats payload, relays as MSG_STATS over ESP-NOW to display
- This means the bridge must register a custom HID report descriptor that accepts data from the host (output/feature report)
- Companion app uses hidapi (or equivalent) to write raw HID reports to the bridge device

### Stats header layout
- Two-row header bar, ~90px total (2 x 45px rows)
- Row 1: CPU %, RAM %, GPU %, CPU temp, GPU temp
- Row 2: Network upload speed, Network download speed, Disk usage %, (remaining space for future: battery, link status)
- Header HIDES entirely when no stats are being received (companion not running)
- Header appears automatically when first stats frame arrives
- This maximizes hotkey button area when display is used standalone

### Hotkey page rework for Linux
- Rework all 3 pages for Hyprland / Wayland Linux workflow
- Page 1 — Window Management: Claude picks best Hyprland shortcut set (workspace switching, focus, move, layout controls, kill window, fullscreen, float toggle)
- Page 2 — System Actions: App launchers (terminal, file manager, browser, app launcher/wofi), screenshots (full screen, area selection, window capture via grim/slurp)
- Page 3 — Media + extras: Play/pause, next/prev, volume up/down/mute, plus any remaining useful shortcuts
- Keys are hardcoded for now (full configurability comes in Phase 5)
- Consumer control (media keys) requires USBHIDConsumerControl on bridge alongside existing USBHIDKeyboard

### Companion app behavior
- Dual mode: CLI daemon for dev/debug + systemd user service for production
- Auto-detect bridge by scanning USB HID devices for Espressif VID (0x303A) and product string "HotkeyBridge"
- No config file needed for basic operation
- Language: Claude's discretion (Python with hidapi or Rust with hidapi crate — choose based on what's practical)

### Claude's Discretion
- Companion app language choice (Python vs Rust)
- Exact Hyprland shortcut selection for Page 1
- HID report descriptor design for stats data channel
- Stats update rate (1-2 Hz range)
- Font sizes and icon choices for stats header
- Exact layout spacing and colors for reworked hotkey pages

</decisions>

<specifics>
## Specific Ideas

- User runs Hyprland on Arch/CachyOS — all key bindings should match Hyprland defaults (Super+1-6 for workspaces, Super+Q to kill, etc.)
- Screenshots use grim + slurp (standard Hyprland screenshot toolchain)
- App launchers should include wofi/rofi (standard Hyprland launcher)
- The bridge's UART USB-C port exists but is ONLY for programming — never used in normal operation
- Single cable philosophy: one USB-C from bridge to PC does everything (HID keyboard + stats input)

</specifics>

<deferred>
## Deferred Ideas

- Desktop notification forwarding to display — mentioned as "notifications area" concept. Would require companion to capture D-Bus notifications and relay to display. New capability, belongs in its own phase or Phase 4/5 expansion.
- Full key configurability — Phase 5 (GUI editor)

</deferred>

---

*Phase: 03-stats-display-companion-app*
*Context gathered: 2026-02-15*
