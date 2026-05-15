# End-to-End Test Suite Design

Date: 2026-05-16

## Context

auto-browser has 28 CLI commands with unit/integration tests using Playwright fixtures directly. There are no E2E tests that exercise the full CLI → daemon → browser pipeline via subprocess. This creates risk that the CLI layer, daemon RPC dispatch, or session management could break without detection.

## Goal

Create a no-mock E2E test suite that starts a local HTTP server with a test page, invokes `auto-browser` CLI commands via subprocess, and verifies stdout/returncode for all 28 commands.

## Architecture

```
conftest.py fixture:
  1. Write test_page.html to temp dir
  2. Start http.server on random port
  3. Wait for server ready

Each test:
  1. ab("open", url)  — start daemon + navigate
  2. ab("snapshot")   — get refs for interaction
  3. ab("<command>")  — execute command under test
  4. Assert stdout/returncode
  5. ab("close")      — cleanup

conftest.py teardown:
  Kill http.server subprocess
```

## File Structure

| File | Responsibility |
|------|---------------|
| `tests/e2e/conftest.py` | HTTP server fixture, `ab()` helper, snapshot parsing |
| `tests/e2e/test_page.html` | Static HTML with all interaction elements |
| `tests/e2e/test_commands.py` | 36 E2E tests covering all 28 commands |

## Test Page Elements

| Element | Commands Covered |
|---------|-----------------|
| Text input (with value) | type, fill, get value, press |
| Button (onclick changes title) | click, dblclick, get text |
| Link (hash navigation) | click → back, forward |
| Checkbox | check, uncheck, is checked |
| Select dropdown | select |
| File upload input | upload |
| Download link | download |
| Long scrollable area | scroll, scroll-into-view |
| Image with alt | get attr, find by alt |
| Multiple same-class buttons | find, count |
| Disabled button | is enabled |
| Hidden element | is visible |
| Input with placeholder | find by placeholder |
| Element with aria-label | find by label |
| Draggable elements | drag |

## Test Cases (36 total)

### Group 1: Lifecycle + Navigation (6 tests)

| Test | Command | Verification |
|------|---------|-------------|
| test_open | `open <url>` | returncode=0, stdout contains "ok" |
| test_snapshot | `snapshot` | stdout contains `[ref=` |
| test_snapshot_compact | `snapshot --compact` | stdout shorter than full |
| test_ping | `ping` | stdout contains "ok" |
| test_back_forward | click link → `back` → `forward` | URL changes |
| test_reload | `reload` | returncode=0 |

### Group 2: Element Query (7 tests)

| Test | Command | Verification |
|------|---------|-------------|
| test_get_title | `get title` | stdout = page title |
| test_get_url | `get url` | stdout contains localhost |
| test_get_text | `get text <ref>` | stdout contains button text |
| test_get_value | `get value <ref>` | stdout = input value |
| test_get_html | `get html <ref>` | stdout contains HTML tags |
| test_get_attr | `get attr <ref> --name alt` | stdout = "Logo" |
| test_get_box | `get box <ref>` | stdout contains JSON with coordinates |

### Group 3: State Checks (5 tests)

| Test | Command | Verification |
|------|---------|-------------|
| test_is_visible | `is visible <ref>` | stdout = "true" |
| test_is_hidden | `is visible <ref>` (hidden element) | stdout = "false" |
| test_is_enabled | `is enabled <ref>` | stdout = "true" |
| test_is_disabled | `is enabled <ref>` (disabled button) | stdout = "false" |
| test_is_checked | `is checked <ref>` | stdout = "false" |

### Group 4: Interactions (11 tests)

| Test | Command | Verification |
|------|---------|-------------|
| test_click | `click <ref>` | title changes to "submitted" |
| test_dblclick | `dblclick <ref>` | returncode=0 |
| test_type | `type <ref> "hello"` | get value contains "hello" |
| test_fill | `fill <ref> "new@email.com"` | get value = "new@email.com" |
| test_press | click input → `press Tab` | returncode=0 |
| test_check | `check <ref>` → `is checked` | stdout = "true" |
| test_uncheck | `uncheck <ref>` → `is checked` | stdout = "false" |
| test_select | `select <ref> green` | returncode=0 |
| test_hover | `hover <ref>` | returncode=0 |
| test_scroll | `scroll down --amount 500` | returncode=0 |
| test_scroll_into_view | `scroll-into-view <ref>` | returncode=0 |

### Group 5: Advanced Operations (6 tests)

| Test | Command | Verification |
|------|---------|-------------|
| test_find_role | `find role button --name Submit` | stdout contains "Submit" |
| test_find_text | `find text "Hello World"` | stdout contains text |
| test_find_placeholder | `find placeholder "Enter name"` | stdout contains text |
| test_count | `count .action-btn` | stdout = "3" |
| test_eval | `eval "document.title"` | stdout contains title |
| test_wait_time | `wait 100` | returncode=0 |

### Group 6: File Operations (2 tests)

| Test | Command | Verification |
|------|---------|-------------|
| test_upload | `upload <ref> <file>` | returncode=0 |
| test_download | `download <ref> <path>` | file exists with correct content |

### Group 7: Close (1 test)

| Test | Command | Verification |
|------|---------|-------------|
| test_close | `close` | returncode=0 |

### Group 8: Error Handling (2 tests)

| Test | Command | Verification |
|------|---------|-------------|
| test_unknown_ref | `click e999` | returncode≠0 |
| test_no_daemon | `snapshot` without open | returncode≠0 |

## Helper Design

### `ab()` function

```python
def ab(*args, session="e2e") -> subprocess.CompletedProcess:
    return subprocess.run(
        ["auto-browser", "--session", session, *args],
        capture_output=True, text=True, timeout=30
    )
```

### `e2e_server` fixture

- Starts `python -m http.server` on random port serving `test_page.html`
- Yields base URL
- Teardown kills server process

### `e2e_session` fixture

- Depends on `e2e_server`
- Calls `ab("open", url)`
- Yields session helper
- Teardown calls `ab("close")`

### Snapshot ref extraction

Helper to parse `ab("snapshot")` output and find ref IDs by element criteria, since tests need refs to interact with elements.

## Constraints

- No mocking — every test runs the real CLI, real daemon, real browser
- Tests run sequentially (shared daemon session)
- HTTP server started once per test session (session-scoped fixture)
- Each test uses the same daemon session (module-scoped or function-scoped open/close)
