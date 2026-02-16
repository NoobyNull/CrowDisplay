# Phase 10: Companion Action Execution - Context

**Gathered:** 2026-02-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Companion service intercepts button presses from the bridge via vendor HID and executes configured actions (launch apps, open URLs, run commands) instead of relying on blind keyboard shortcuts. The display sends button index (page + widget), the bridge relays to companion, companion looks up and executes the action.

</domain>

<decisions>
## Implementation Decisions

### Action types
- Four action types supported: Launch App (.desktop), Run Shell Command, Open URL, Keyboard Shortcut (legacy)
- Launch App: supports focus-or-launch behavior (if app running, focus its window; if not, launch it) — configurable per-button in settings
- Shell commands: fire and forget, no sudo allowed, output/errors logged to companion log only
- Open URL: opens in default browser
- Keyboard shortcut: legacy fallback — Claude decides whether bridge fires USB HID keystroke or companion simulates via xdotool/ydotool

### Button-to-action mapping
- Display sends page number + widget index (NOT modifier+keycode) to identify which button was pressed
- Companion looks up the action from the config by page + widget index
- Companion auto-reloads config when the file changes (file watcher)
- If companion isn't running, button presses fail silently — no fallback

### Bridge behavior change
- Bridge keeps USB HID keyboard interface registered but does NOT fire keystrokes for hotkey actions
- Bridge relays button presses to companion via vendor HID input reports — Claude decides the HID report format
- Media key commands (play/pause, volume, etc.) also route through companion — no direct USB consumer control
- ACK flow: Claude decides whether bridge ACKs immediately or waits for companion confirmation

### Editor UX for actions
- App picker auto-fills launch command; dropdown + text field for other action types (Shell Command, Open URL, Keyboard Shortcut)
- Action type dropdown selects which input is shown: app picker for Launch App, free text for Shell/URL, key recorder for Keyboard Shortcut
- Existing keyboard shortcut recorder stays — shown only when action type is Keyboard Shortcut
- Default app launch behavior: focus-or-launch (smart), user can change per-button
- "Test" button in editor fires the action immediately on the PC without going through display/bridge
- Window opens maximized/expanded (not full screen, but expanded to fill available space)
- Fix scroll wheel bug: prevent mouse scroll over dropdown widgets from changing their value unexpectedly

### Claude's Discretion
- Keyboard shortcut execution method (bridge USB HID vs companion xdotool/ydotool)
- Config storage approach (same config.json vs separate actions file)
- Vendor HID input report format for bridge → companion communication
- ACK flow timing (instant bridge ACK vs wait for companion)
- Media key simulation method on companion side

</decisions>

<specifics>
## Specific Ideas

- App picker already resolves .desktop files — just need to store the Exec command and use it
- Scroll wheel hijacking dropdowns is a known Qt issue — needs eventFilter or setFocusPolicy fix
- The companion already runs as a systemd service and talks to the bridge over vendor HID (report ID 6)

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-companion-action-execution*
*Context gathered: 2026-02-16*
