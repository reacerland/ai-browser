# Basic Interactions Enhancement Design

Date: 2026-05-16

## Context

auto-browser currently has 10 commands (open, close, snapshot, click, type, fill, scroll, screenshot, eval, ping). Compared to agent-browser's 100+ commands, the most critical gap is in basic element interaction — AI agents cannot query element state, wait for conditions, find elements by locator, or perform common operations like checkbox/dropdown/navigation without workarounds.

## Goal

Add 18 commands across 4 modules to bring auto-browser to feature-complete status for AI agent basic interaction. No architecture changes — all new commands follow the existing client → JSON-RPC → daemon → interactions → Playwright flow.

## Scope

**In scope:** element query, state check, wait, find, navigation, keyboard, checkbox, select, double-click, drag, scroll-into-view, hover CLI, count, upload, download.

**Out of scope:** network interception, cookie/storage management, multi-tab, batch, streaming, React devtools, performance metrics, AI chat, dashboard.

## New Commands

### Module 1: Element Query & State (4 commands)

#### `ab get <what> [ref] [options]`

Get element property or page info.

| what | args | source |
|------|------|--------|
| text | ref | `locator.text_content()` |
| html | ref | `locator.inner_html()` |
| value | ref | `locator.input_value()` |
| attr | ref, --name | `locator.get_attribute(name)` |
| title | (none) | `page.title` |
| url | (none) | `page.url` |
| box | ref | `locator.bounding_box()` |

#### `ab is <what> <ref>`

Check element state. Outputs `true` or `false`.

| what | source |
|------|--------|
| visible | `locator.is_visible()` |
| enabled | `locator.is_enabled()` |
| checked | `locator.is_checked()` |

#### `ab wait <ref|ms> [--timeout ms]`

Wait for element to appear (ref) or fixed duration (ms).

- Argument matching: `/^e\d+$/` → ref wait, `/^\d+$/` → time wait
- Ref wait: `locator.wait_for(state="visible", timeout=...)`
- Time wait: `page.wait_for_timeout(ms)`
- Default timeout: 25000ms

#### `ab find <locator> <value> [--name name]`

Find elements by Playwright locator type. Returns snapshot fragment with ref tags.

| locator | Playwright method |
|---------|-------------------|
| role | `page.get_by_role(value, name=name)` |
| text | `page.get_by_text(value)` |
| label | `page.get_by_label(value)` |
| placeholder | `page.get_by_placeholder(value)` |
| alt | `page.get_by_alt_text(value)` |
| title | `page.get_by_title(value)` |
| testid | `page.get_by_test_id(value)` |

`--name` only applies to `role` locator.

### Module 2: Navigation & Keyboard (5 commands)

#### `ab back`

`page.go_back()`

#### `ab forward`

`page.go_forward()`

#### `ab reload`

`page.reload()`

#### `ab press <key>`

`page.keyboard.press(key)`. Examples: Enter, Tab, Escape, Control+a, ArrowDown.

#### `ab select <ref> <value>`

`locator.select_option(value)` via ref resolution.

### Module 3: Checkbox & Enhanced Interaction (5 commands)

#### `ab check <ref>`

`locator.check()` via ref resolution.

#### `ab uncheck <ref>`

`locator.uncheck()` via ref resolution.

#### `ab dblclick <ref>`

`locator.dblclick()` via ref resolution. Standalone command, not a flag on click.

#### `ab drag <src_ref> <dst_ref>`

`source_locator.drag_to(target_locator)` via ref resolution of both arguments.

#### `ab scroll-into-view <ref>`

`locator.scroll_into_view_if_needed()` via ref resolution.

### Module 4: Auxiliary (4 commands)

#### `ab hover <ref>`

`locator.hover()` via ref resolution. Already exists as daemon method, adding CLI exposure.

#### `ab count <selector>`

`page.locator(selector).count()`. Uses CSS selector, not ref. Returns integer.

#### `ab upload <ref> <files...>`

`locator.set_input_files(files)` via ref resolution. Supports multiple files.

#### `ab download <ref> <save_path>`

```python
with page.expect_download() as d:
    locator.click()
download = d.value
download.save_as(save_path)
```

## Architecture

No structural changes. Each new command follows:

```
CLI (click command) → client.call(method, params) → daemon RPC handler → interactions method → Playwright
```

### File Changes

| File | Change | Description |
|------|--------|-------------|
| `src/auto_browser/cli.py` | Modify | Add 18 click command functions |
| `src/auto_browser/daemon.py` | Modify | Add 18 RPC handlers + dispatch registration |
| `src/auto_browser/interactions.py` | Modify | Add ~15 methods |
| `src/auto_browser/client.py` | Modify | Add corresponding client methods |
| `tests/test_*.py` | New | ~10 test files, ~29 tests total |

No changes to: `ax_tree.py`, `ref_map.py`, `browser_manager.py`.

## Error Handling

Use existing JSON-RPC error codes:

| Code | Meaning |
|------|---------|
| -32000 | General operation failure |
| -32002 | Element not found (invalid ref) |
| -32003 | Element not visible/interactable |
| -32601 | Method not found |
| -32603 | Internal error |

CLI catches errors, outputs `Error: <message>` to stderr, exits with code 1.

## Testing

~29 new tests across ~10 files using existing `conftest.py` browser_page fixture pattern:

- `test_get.py` — 6 tests (text/value/attr/html/title/url/box)
- `test_is.py` — 3 tests (visible/enabled/checked)
- `test_wait.py` — 2 tests (ref wait + time wait)
- `test_find.py` — 3 tests (role/text/label)
- `test_navigation.py` — 3 tests (back/forward/reload)
- `test_press.py` — 2 tests (Enter/Tab)
- `test_check.py` — 2 tests (check/uncheck)
- `test_select.py` — 1 test
- `test_dblclick.py` — 1 test
- `test_drag.py` — 1 test
- `test_scroll_into_view.py` — 1 test
- `test_hover_cli.py` — 1 test
- `test_count.py` — 1 test
- `test_upload.py` — 1 test
- `test_download.py` — 1 test

## Implementation Order

1. `interactions.py` — bottom-layer methods
2. `daemon.py` — RPC handlers calling interactions
3. `client.py` — client method wrappers
4. `cli.py` — click command functions
5. `tests/` — tests per module as each completes
