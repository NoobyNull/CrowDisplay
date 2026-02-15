# Phase 6: Data-Driven Display UI - Research

**Researched:** 2026-02-15
**Domain:** Dynamic LVGL 8.3 widget lifecycle, config-driven UI rendering, memory-safe hot-reload on ESP32-S3
**Confidence:** HIGH

## Summary

Phase 6 transforms the display UI from dual-mode (hardcoded arrays vs. config struct) into a single config-driven rendering path with safe hot-reload capability. The existing codebase already has most of the plumbing: `create_ui()` accepts an `AppConfig*`, `rebuild_ui()` deletes and recreates the tabview, and the config server calls `rebuild_ui()` after upload. However, the current implementation has **three critical bugs** that must be fixed before the phase can be considered complete, plus the widget-pool memory safety requirement (DRVUI-05) that is entirely unaddressed.

**Critical Bug 1 -- Dangling Hotkey Pointers:** `create_hotkey_button()` receives `&hk` where `hk` is a stack-local `Hotkey` struct created inside a for-loop body. When the loop iteration ends, `hk` is destroyed, but LVGL's event system still holds the dangling pointer via `lv_event_get_user_data()`. Every button tap dereferences freed stack memory. This exists in both `create_ui()` (line 655) and `rebuild_ui()` (line 718).

**Critical Bug 2 -- Dangling Config Pointer:** `AppConfig app_config` is declared as a local variable in `setup()` at `display/main.cpp:46`. It goes out of scope when `setup()` returns, but `g_active_config` in `ui.cpp` retains a pointer to it. Similarly, `rebuild_ui()` in `config_server.cpp:206` passes a local `AppConfig` that goes out of scope immediately after the function returns.

**Critical Bug 3 -- No Widget-Pool / Memory Safety on Reload:** `rebuild_ui()` calls `lv_obj_del(tabview)` then recreates it, but does not re-apply tab button styles, does not account for stats header visibility state, and does not verify memory stability after deletion. LVGL 8.3's `lv_obj_del()` frees widget memory and event descriptors but does NOT free locally-initialized styles (by design -- styles are independent of objects in LVGL's architecture). The current code uses inline `lv_obj_set_style_*()` calls (local styles) which ARE freed on deletion, so style leaks are not an issue here. The real memory risk is fragmentation in LVGL's 96KB internal heap from repeated alloc/free cycles.

**Primary recommendation:** Fix the three dangling-pointer bugs by making `AppConfig` a file-scope static (or global) with program lifetime, and storing `ButtonConfig*` pointers (into the long-lived config) as event user_data instead of temporary `Hotkey` stack copies. Implement `lv_mem_monitor()` verification to prove memory stability across reloads.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| LVGL | 8.3.11 | Widget toolkit for ESP32 display | Already in use, pinned in platformio.ini |
| ArduinoJson | 7.4.0+ | Config JSON parse/serialize | Already in use from Phase 5 |
| LovyanGFX | 1.1.8+ | Display driver (RGB565) | Already in use, unchanged |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ESP32 PSRAM API | ESP-IDF built-in | ps_malloc() for large buffers | Buffers >4KB per Phase 5 convention |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LVGL built-in allocator (96KB pool) | Custom PSRAM allocator via LV_MEM_CUSTOM=1 | Would eliminate fragmentation concern but requires changing lv_conf.h and testing all existing widgets; current 96KB pool is adequate for 3 pages x 12 buttons |
| Inline styles (lv_obj_set_style_*) | Shared style objects (lv_style_t) | Shared styles reduce per-widget memory but add complexity; inline styles are freed on lv_obj_del |

## Architecture Patterns

### Recommended Approach

```
display/
  config.h          # AppConfig struct (unchanged from Phase 5)
  config.cpp        # JSON I/O (unchanged from Phase 5)
  ui.h              # create_ui(), rebuild_ui() (signatures may change)
  ui.cpp            # MODIFIED: single config-driven render path, fixed lifetimes
  main.cpp          # MODIFIED: static AppConfig with program lifetime
  config_server.cpp # MODIFIED: reload uses global config, not local
```

### Pattern 1: Long-Lived Config Struct
**What:** Make `AppConfig` a file-scope static or global so all pointers into it (from LVGL event user_data) remain valid for the program's lifetime.
**When to use:** Any time LVGL event callbacks store pointers to application data.
**Example:**
```cpp
// main.cpp -- config with program lifetime
static AppConfig g_app_config;

void setup() {
    // ...
    g_app_config = config_load();
    create_ui(&g_app_config);
}
```

### Pattern 2: Direct ButtonConfig* as Event User Data
**What:** Pass `&page.buttons[j]` (pointer into the long-lived `AppConfig`) directly to `lv_obj_add_event_cb()` instead of creating temporary `Hotkey` copies.
**When to use:** Replaces the current broken `button_config_to_hotkey()` + stack pointer pattern.
**Example:**
```cpp
// ui.cpp -- safe event user_data
static void btn_event_cb(lv_event_t *e) {
    const ButtonConfig *btn = (const ButtonConfig *)lv_event_get_user_data(e);
    if (!btn) return;
    if (btn->action_type == ACTION_MEDIA_KEY) {
        send_media_key_to_bridge(btn->consumer_code);
    } else {
        send_hotkey_to_bridge(btn->modifiers, btn->keycode);
    }
}

// In page creation loop:
for (size_t j = 0; j < page.buttons.size(); j++) {
    const ButtonConfig *btn_ptr = &page.buttons[j];
    lv_obj_t *btn = create_hotkey_button(tab, btn_ptr);
    // btn_ptr points into g_app_config which has program lifetime
}
```

### Pattern 3: Full Screen Rebuild via lv_obj_clean()
**What:** Instead of deleting only the tabview, use `lv_obj_clean(main_screen)` to remove ALL children of the main screen, then recreate everything (header, stats header, tabview). This ensures no orphaned widgets and resets all file-scope widget pointers.
**When to use:** On config reload (hot-reload).
**Why:** The current `rebuild_ui()` only deletes/recreates the tabview but leaves the header, stats header, and other widgets untouched. This creates inconsistency -- the stats_header may reference the old tabview size, tab button styles are not re-applied, etc. A full rebuild is simpler and more robust.
**Example:**
```cpp
void rebuild_ui(const AppConfig* cfg) {
    if (!cfg || !main_screen) return;

    // Log memory before
    lv_mem_monitor_t mon_before;
    lv_mem_monitor(&mon_before);

    // Clean all children of main screen
    lv_obj_clean(main_screen);

    // Reset all widget pointers (they are now dangling)
    tabview = nullptr;
    status_label = nullptr;
    stats_header = nullptr;
    stats_visible = false;
    // ... etc

    // Recreate everything
    create_ui_on_screen(main_screen, cfg);

    // Log memory after
    lv_mem_monitor_t mon_after;
    lv_mem_monitor(&mon_after);
    Serial.printf("LVGL mem: before=%u used, after=%u used, delta=%d\n",
                  mon_before.total_size - mon_before.free_size,
                  mon_after.total_size - mon_after.free_size,
                  (int)(mon_after.total_size - mon_after.free_size) -
                  (int)(mon_before.total_size - mon_before.free_size));
}
```

### Pattern 4: Memory Monitoring for Leak Detection
**What:** Use `lv_mem_monitor()` to track LVGL heap usage before and after each rebuild cycle.
**When to use:** During development/testing to validate DRVUI-05 (no memory leaks on repeated reloads). Can also be left as a serial diagnostic.
**Key fields:**
```cpp
lv_mem_monitor_t mon;
lv_mem_monitor(&mon);
// mon.total_size    -- total LVGL heap (96KB as configured)
// mon.free_size     -- available bytes
// mon.free_cnt      -- number of free fragments (high = fragmented)
// mon.used_pct      -- percentage used (0-100)
// mon.max_used      -- high-water mark
// mon.free_biggest_size -- largest contiguous free block
```
**Note:** `lv_mem_monitor()` only works when `LV_MEM_CUSTOM == 0` (using LVGL's built-in allocator). The current `lv_conf.h` has `LV_MEM_CUSTOM 0`, so this API is available.

### Pattern 5: Reload Sequence (Config Server Integration)
**What:** The correct reload sequence when a new config is uploaded:
```
1. Parse new JSON into temporary AppConfig
2. Validate (pages > 0, active profile exists)
3. Copy validated config into global g_app_config
4. Call rebuild_ui(&g_app_config)
5. rebuild_ui: lv_obj_clean(main_screen) -> recreate all widgets
6. New widgets' event user_data points into updated g_app_config
```
**Critical:** Step 3 must copy INTO the existing global, not create a new one. All button event pointers must point into the same long-lived struct.

### Anti-Patterns to Avoid
- **Stack-local Hotkey as event user_data:** The current code creates `Hotkey hk` on the stack inside a for loop and passes `&hk` to `lv_obj_add_event_cb()`. The pointer is invalid before the next LVGL tick. MUST be fixed.
- **Local AppConfig in setup():** The current `AppConfig app_config` in `setup()` goes out of scope. Must be `static` or global.
- **Partial rebuild (tabview-only):** The current `rebuild_ui()` only replaces the tabview. This leaves stats_header, tab button styles, and header in potentially inconsistent state. Use full `lv_obj_clean()` instead.
- **Dual rendering paths:** The current `create_ui()` has an if/else branch: one path for config, another for hardcoded arrays. Phase 6 should eliminate the hardcoded path -- `config_create_defaults()` already provides an `AppConfig` with the same data as the hardcoded arrays.
- **Styles initialized per-rebuild with `lv_style_init()`:** LVGL does NOT free styles initialized with `lv_style_init()` when objects are deleted. The current code uses inline styles (`lv_obj_set_style_*()`) which ARE freed, so this is not currently a problem. Do NOT introduce `lv_style_init()` patterns unless styles are initialized once and reused across rebuilds.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LVGL memory monitoring | Custom heap tracking | `lv_mem_monitor()` API | Built into LVGL 8.3 when LV_MEM_CUSTOM=0; provides used/free/fragmentation stats |
| Config defaults | Second set of hardcoded arrays | `config_create_defaults()` | Already exists from Phase 5; returns an AppConfig identical to the hardcoded UI |
| JSON parsing | Manual string parsing | ArduinoJson v7 `deserializeJson()` | Already in use from Phase 5 |
| Atomic SD writes | Direct file overwrite | `config_save()` with tmp+rename | Already implemented in Phase 5 |

**Key insight:** Most of the infrastructure already exists. Phase 6 is primarily about fixing lifetime bugs, removing the dual-path rendering, and adding memory verification -- not building new systems.

## Common Pitfalls

### Pitfall 1: Dangling Pointers from Temporary Hotkey Structs
**What goes wrong:** LVGL event callbacks dereference pointers to destroyed stack variables, causing crashes or garbage data.
**Why it happens:** `button_config_to_hotkey()` returns a stack-local `Hotkey`, and `&hk` is passed as user_data. The pointer is invalid as soon as the for-loop iteration ends.
**How to avoid:** Pass `&page.buttons[j]` (pointer into the long-lived global `AppConfig`) as user_data. Eliminate the `Hotkey` struct and `button_config_to_hotkey()` entirely -- `ButtonConfig` has all the same fields.
**Warning signs:** Random crashes on button press, garbled label text in serial output, inconsistent hotkey behavior.

### Pitfall 2: Config Goes Out of Scope
**What goes wrong:** `g_active_config` in ui.cpp points to freed memory after `setup()` or `handle_config_upload()` returns.
**Why it happens:** `AppConfig` is a local variable in these functions.
**How to avoid:** Make it `static` in file scope (or global). On reload, copy new data INTO the existing global rather than replacing the pointer.
**Warning signs:** Crash on first button press after boot, crash after config upload.

### Pitfall 3: LVGL Memory Fragmentation on Repeated Reloads
**What goes wrong:** After many reload cycles, `lv_mem_alloc()` fails because free memory is fragmented into small non-contiguous blocks, even though total free bytes is sufficient.
**Why it happens:** LVGL's built-in allocator (tlsf) is generally resistant to fragmentation, but repeatedly creating different-sized widget trees (e.g., 8 buttons then 12 buttons then 6 buttons) can fragment the 96KB pool over many cycles.
**How to avoid:** Monitor with `lv_mem_monitor()` after each rebuild. Log `free_biggest_size` and `free_cnt`. If `free_biggest_size` decreases significantly over 10+ reloads while `free_size` stays stable, fragmentation is occurring.
**Warning signs:** `lv_mem_monitor()` shows free_cnt increasing (more fragments) while free_biggest_size decreases. Eventually widget creation fails with LVGL assert.

### Pitfall 4: std::vector Reallocation Invalidates Pointers
**What goes wrong:** If the global `AppConfig`'s vectors (pages, buttons) are modified in place (push_back, resize), the internal array may be reallocated, invalidating all `ButtonConfig*` pointers stored as LVGL event user_data.
**Why it happens:** `std::vector` may relocate its storage when capacity changes.
**How to avoid:** On config reload, destroy all LVGL widgets FIRST (via `lv_obj_clean`), THEN update the config data, THEN recreate widgets. Never modify the config while widgets hold pointers into it.
**Warning signs:** Crash after adding/removing buttons from config, works fine on first load but crashes on reload.

### Pitfall 5: Forgetting to Reset Widget Pointer Statics After Clean
**What goes wrong:** After `lv_obj_clean(main_screen)`, statics like `tabview`, `stats_header`, `status_label`, `stat_labels[]` are dangling. If any code accesses them before they are reassigned, crash.
**Why it happens:** `lv_obj_clean()` frees the objects but cannot null the C++ pointers.
**How to avoid:** Immediately after `lv_obj_clean()`, set all widget pointer statics to `nullptr`. The rebuild function assigns them fresh values.
**Warning signs:** Crash in `update_stats()`, `hide_stats_header()`, or `update_device_status()` after a reload.

## Code Examples

### Example 1: Safe Button Creation with ButtonConfig* User Data
```cpp
// Source: Derived from current ui.cpp pattern, fixed for lifetime safety
static void btn_event_cb(lv_event_t *e) {
    const ButtonConfig *btn = (const ButtonConfig *)lv_event_get_user_data(e);
    if (!btn) return;

    if (btn->action_type == ACTION_MEDIA_KEY) {
        send_media_key_to_bridge(btn->consumer_code);
    } else {
        send_hotkey_to_bridge(btn->modifiers, btn->keycode);
    }

    if (status_label) {
        lv_label_set_text_fmt(status_label, LV_SYMBOL_OK " Sent: %s (%s)",
                              btn->label.c_str(), btn->description.c_str());
    }
}

static lv_obj_t *create_hotkey_button(lv_obj_t *parent, const ButtonConfig *btn) {
    lv_obj_t *widget = lv_btn_create(parent);
    lv_obj_set_size(widget, 170, 90);
    lv_obj_add_event_cb(widget, btn_event_cb, LV_EVENT_CLICKED, (void *)btn);

    // Styles (inline -- freed when widget is deleted)
    lv_obj_set_style_bg_color(widget, lv_color_hex(btn->color), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(widget, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(widget, 12, LV_PART_MAIN);
    // ... remaining styles ...

    // Icon
    if (!btn->icon.empty()) {
        lv_obj_t *icon = lv_label_create(widget);
        lv_label_set_text(icon, btn->icon.c_str());
        // ...
    }

    // Label
    lv_obj_t *label = lv_label_create(widget);
    lv_label_set_text(label, btn->label.c_str());

    // Description
    lv_obj_t *desc = lv_label_create(widget);
    lv_label_set_text(desc, btn->description.c_str());

    return widget;
}
```

### Example 2: Memory-Safe Rebuild Sequence
```cpp
// Source: Derived from LVGL 8.3 lv_obj_clean() documentation + lv_mem_monitor() API
void rebuild_ui(const AppConfig* cfg) {
    if (!cfg || !main_screen) return;

    lv_mem_monitor_t mon_pre;
    lv_mem_monitor(&mon_pre);

    // Step 1: Destroy all widgets on main screen
    lv_obj_clean(main_screen);

    // Step 2: Null all widget pointers (now dangling)
    tabview = nullptr;
    status_label = nullptr;
    stats_header = nullptr;
    stats_visible = false;
    rssi_label = nullptr;
    bright_btn = nullptr;
    memset(stat_labels, 0, sizeof(stat_labels));

    // Step 3: Recreate UI from config
    g_active_config = cfg;
    create_ui_widgets(main_screen, cfg);  // internal function

    // Step 4: Verify memory
    lv_mem_monitor_t mon_post;
    lv_mem_monitor(&mon_post);
    int32_t delta = (int32_t)(mon_pre.free_size - mon_post.free_size);
    Serial.printf("UI rebuild: LVGL mem free=%u->%u (delta=%d), frag=%u chunks, biggest=%u\n",
                  mon_pre.free_size, mon_post.free_size, delta,
                  mon_post.free_cnt, mon_post.free_biggest_size);
}
```

### Example 3: Global Config with Reload Support
```cpp
// main.cpp
static AppConfig g_app_config;  // Program lifetime

void setup() {
    // ...
    g_app_config = config_load();
    create_ui(&g_app_config);
}

// Called by config_server after upload
void on_config_reloaded() {
    AppConfig new_cfg = config_load();  // Parse from SD

    // Validate before committing
    if (!new_cfg.get_active_profile() ||
        new_cfg.get_active_profile()->pages.empty()) {
        Serial.println("Reload: invalid config, keeping current");
        return;
    }

    // Step 1: Clean all widgets (removes all pointers into g_app_config)
    // (done inside rebuild_ui)

    // Step 2: Replace config data
    g_app_config = new_cfg;

    // Step 3: Rebuild UI pointing into updated g_app_config
    rebuild_ui(&g_app_config);
}
```

## State of the Art

| Old Approach (Current Code) | New Approach (Phase 6) | Impact |
|-----------------------------|------------------------|--------|
| Dual render path (hardcoded OR config) | Single config-only path | Eliminates code duplication, hardcoded arrays become default config only |
| Stack-local Hotkey as event user_data | ButtonConfig* into global AppConfig | Fixes use-after-free crashes on every button press |
| Local AppConfig in setup() | Static/global AppConfig | Fixes dangling pointer after setup() returns |
| Tabview-only rebuild | Full lv_obj_clean() rebuild | Consistent state, no orphaned headers |
| No memory monitoring | lv_mem_monitor() on each rebuild | Proves DRVUI-05 compliance |

**Deprecated/outdated:**
- `Hotkey` struct in ui.cpp: Redundant with `ButtonConfig`. Should be removed entirely.
- `button_config_to_hotkey()`: Source of dangling pointer bug. Should be removed.
- `HotkeyPage` struct in ui.cpp: Redundant with `PageConfig`. Should be removed.
- Hardcoded `page1_hotkeys[]`, `page2_hotkeys[]`, `page3_hotkeys[]` arrays: Replaced by `config_create_defaults()`.

## Open Questions

1. **std::string in ButtonConfig and LVGL label lifetime**
   - What we know: `lv_label_set_text()` copies the string internally (LVGL docs confirm this). So `btn->label.c_str()` is safe to pass even though the underlying `std::string` could theoretically move.
   - What's unclear: Whether `std::string` inside a vector that is assigned-to (via `g_app_config = new_cfg`) properly handles copy semantics without invalidation during the assignment.
   - Recommendation: This should be fine with standard C++ move/copy semantics. The key is that `lv_obj_clean()` destroys all widgets BEFORE `g_app_config = new_cfg` replaces the data. Validate during testing by checking label text after reload.

2. **LVGL 96KB pool adequacy for large configs**
   - What we know: Current UI (3 pages, 36 buttons, header, stats header, clock screen, OTA screen) fits in 96KB. The tabview + 12 buttons per page uses roughly 30-40KB.
   - What's unclear: How much headroom exists for configs with 16 pages x 16 buttons (the maximum allowed by CONFIG_MAX_PAGES/CONFIG_MAX_BUTTONS).
   - Recommendation: A config with 16 pages x 16 buttons = 256 buttons would need significantly more memory. However, only the currently-visible tab's widgets are fully rendered. LVGL 8.3 tabview creates all tab contents upfront (not lazily). If memory becomes tight, either increase LV_MEM_SIZE or switch to LV_MEM_CUSTOM=1 with PSRAM. Test with a stress config during validation.

3. **Rebuild during active animation or event**
   - What we know: `lv_obj_clean()` should not be called from within an event callback for the object being cleaned. The config server upload handler runs from `web_server->handleClient()` which is called from `loop()`, not from an LVGL callback.
   - What's unclear: Whether an LVGL animation (e.g., tab switch transition) could be in progress when rebuild is triggered.
   - Recommendation: Use `lv_obj_del_async()` semantics if needed, or simply ensure rebuild is called from `loop()` context via a flag (set flag in upload handler, check in loop).

## Sources

### Primary (HIGH confidence)
- **LVGL 8.3 Official Documentation** - [Object deletion](https://docs.lvgl.io/8.3/overview/object.html): `lv_obj_del()`, `lv_obj_clean()`, `lv_obj_del_async()` behavior
- **LVGL 8.3 lv_mem.h** - `/data/Elcrow-Display-hotkeys/.pio/libdeps/display/lvgl/src/misc/lv_mem.h`: `lv_mem_monitor()` API, `lv_mem_monitor_t` struct fields
- **Current codebase** - `display/ui.cpp`, `display/main.cpp`, `display/config.cpp`, `display/config_server.cpp`: verified all patterns and bugs by direct code reading
- **LVGL Issue #2978** - [github.com/lvgl/lvgl/issues/2978](https://github.com/lvgl/lvgl/issues/2978): Styles initialized with `lv_style_init()` are NOT freed on `lv_obj_del()` (by design). Inline styles set via `lv_obj_set_style_*()` ARE freed.

### Secondary (MEDIUM confidence)
- **LVGL Forum** - [Memory fragmentation problem](https://forum.lvgl.io/t/memory-fragmentation-problem/14007): ESP32 users report fragmentation with frequent widget create/destroy cycles
- **LVGL Forum** - [Change screen and memory leak](https://forum.lvgl.io/t/change-screen-and-memory-leak/11033): Confirms `lv_obj_clean()` frees widget memory but not externally-allocated styles
- **LVGL Forum** - [Memory corruption when cleaning screen](https://forum.lvgl.io/t/memory-corruption-when-cleaning-screen/9529): Warns about calling `lv_obj_clean()` from within event callbacks

### Tertiary (LOW confidence)
- **Widget-pool pattern** mentioned in project roadmap: No standard LVGL API for this. The term appears to mean "pre-allocate a fixed widget tree and update properties on reload rather than destroy/recreate." However, LVGL 8.3 has no built-in object pool. The practical approach is: destroy all + recreate + verify with `lv_mem_monitor()`. If fragmentation proves problematic after testing, explore LV_MEM_CUSTOM=1 with PSRAM.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use, no new dependencies
- Architecture: HIGH - bugs and fixes verified by direct code reading, LVGL API confirmed from headers
- Pitfalls: HIGH for dangling pointers (verified in code), MEDIUM for memory fragmentation (depends on real-world usage patterns, needs testing)

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (stable domain, LVGL 8.3 is frozen)
