# Auto-Browser: Client+Daemon Browser Automation CLI

> Design spec for a CLI tool that provides AI agents with browser automation capabilities via accessibility tree snapshots and ref-based interactions.

## 1. Overview

Auto-browser is a client+daemon CLI tool that allows AI agents to control a browser. The daemon manages the browser lifecycle (launch, keep-alive, shutdown), and the client sends commands via JSON-RPC over Unix domain sockets.

**Target user:** AI agents (not human interactive use).

**Core capabilities (MVP):**
- Launch/close browser sessions with persistent state
- Navigate to URLs
- Accessibility tree snapshots with ref-based element identification
- Interact with elements (click, type, fill, scroll, hover)
- Screenshots and JS evaluation

## 2. Architecture

```
┌─────────────┐  Unix Socket   ┌──────────────────────────────────┐
│  CLI Client │ ◄─JSON-RPC───► │        Daemon Process             │
│  (stateless)│                │                                  │
│             │                │  JSON-RPC Server                  │
│  ab open    │                │    └─► Browser Manager            │
│  ab click   │                │         └─► Playwright Browser    │
│  ab snapshot│                │              └─► CDP Session      │
│  ...        │                │                  └─► AX Tree      │
└─────────────┘                └──────────────────────────────────┘
```

**One session = one daemon process = one browser instance.** Multiple sessions run independently with separate daemon processes, sockets, and user data directories.

### Dependencies

- **cloakbrowser**: Stealth Chromium launcher (wraps Playwright)
- **Playwright sync API**: Browser automation
- **Playwright CDP session**: Accessibility tree operations (`Accessibility.getFullAXTree`, `DOM.getBoxModel`, etc.)

## 3. Project Structure

```
auto-browser/
├── src/
│   └── auto_browser/
│       ├── __init__.py
│       ├── __main__.py         # python -m auto_browser entry
│       ├── cli.py              # CLI argument parsing (argparse)
│       ├── daemon.py           # Daemon process (JSON-RPC server)
│       ├── client.py           # Client (sends JSON-RPC to daemon)
│       ├── browser_manager.py  # Playwright browser lifecycle + CDP
│       ├── ax_tree.py          # AX tree snapshot + rendering
│       ├── ref_map.py          # Ref allocation and lookup
│       └── interactions.py     # click, type, fill, hover, scroll
├── pyproject.toml
└── tests/
```

## 4. CLI Commands

```
ab open <url> [--session NAME] [--headed]       # Start daemon + browser + navigate
ab close [--session NAME]                       # Close browser + daemon
ab snapshot [--compact] [--selector CSS]        # AX tree snapshot
ab click <ref|selector> [--double]              # Click element
ab type <ref|selector> <text> [--clear]         # Type text
ab fill <ref|selector> <value>                  # Clear + fill
ab scroll <up|down> <amount>                    # Scroll page
ab screenshot [--output path]                   # Take screenshot
ab eval <expression>                            # Execute JS
ab ping                                         # Health check
```

### Session Management

- `ab open <url>` — default session, temporary profile, no persistence
- `ab open <url> --session work` — named session with persistent user data at `~/.ab/work/chrome-data/`
- All subsequent commands for a named session must specify `--session <name>`
- Each session has its own daemon process, Unix socket, and browser instance
- `ab close --session work` — shuts down daemon, preserves user data directory

### Session Filesystem Layout

```
~/.ab/
├── default/
│   └── daemon.json            # pid, socket path
├── work/
│   ├── daemon.json            # pid, socket path, session name
│   └── chrome-data/           # Chromium user data (cookies, login state, etc.)
└── test/
    ├── daemon.json
    └── chrome-data/
```

### daemon.json Format

```json
{
  "pid": 1234,
  "socket": "/tmp/ab-work.sock",
  "session": "work",
  "headed": true,
  "user_data_dir": "/home/user/.ab/work/chrome-data"
}
```

## 5. JSON-RPC Protocol

### Request Format

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "snapshot",
  "params": {"compact": true}
}
```

### Response Format

```json
// Success
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {"content": "- navigation\n  - link \"Home\" [ref=e1]\n  ..."}
}

// Error
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {"code": -32002, "message": "Element e5 not found"}
}
```

### Methods

| Method | Params | Description |
|--------|--------|-------------|
| `ping` | `{}` | Health check |
| `shutdown` | `{}` | Stop daemon |
| `goto` | `{url}` | Navigate to URL |
| `snapshot` | `{compact?, selector?}` | AX tree snapshot |
| `click` | `{ref\|selector, button?, double?}` | Click element |
| `type` | `{ref\|selector, text, clear?}` | Type text |
| `fill` | `{ref\|selector, value}` | Clear + fill |
| `scroll` | `{direction, amount}` | Scroll page |
| `screenshot` | `{path?}` | Take screenshot |
| `eval` | `{expression}` | Execute JavaScript |

## 6. Daemon Design

### Lifecycle

1. `ab open` → client checks if daemon already running for session
   - If running: send `goto` to existing daemon (reuse browser, just navigate)
   - If not: fork daemon process, wait for socket to appear, then send `goto`
2. Daemon starts: create Playwright instance, launch browser via cloakbrowser, bind Unix socket
3. Daemon serves requests sequentially (sync, single-threaded)
4. `ab close` → client sends `shutdown`, daemon exits

### Client Daemon Lookup

```
1. Determine session_name (default or --session value)
2. Read ~/.ab/<session_name>/daemon.json
3. Check if pid is still alive (os.kill(pid, 0))
4. Connect to socket path from daemon.json
5. Send JSON-RPC request
```

### Browser Crash Recovery

If the browser crashes mid-session, the daemon detects it on the next request and restarts the browser automatically. The agent must re-navigate (state is lost on crash unless using persistent session).

## 7. Browser Manager

Wraps `cloakbrowser.launch()` and manages a single Playwright `Browser` instance.

**Responsibilities:**
- Launch browser with cloakbrowser (headless by default, `--headed` to show UI)
- For named sessions: pass `--user-data-dir=~/.ab/<session>/chrome-data` to Chromium
- Maintain one active `Page` (MVP — multi-tab later)
- Provide `get_cdp_session()` for AX tree operations
- Detect browser crashes and restart

**Launch configuration:**
```python
# Named session with persistent user data
args = ["--remote-debugging-port=0"]
if user_data_dir:
    args.append(f"--user-data-dir={user_data_dir}")

browser = launch(
    headless=not headed,
    args=args,
)
```

**Note:** `cloakbrowser.launch()` wraps `playwright.chromium.launch()`. Persistent user data is passed via Chrome's `--user-data-dir` flag (not a Playwright parameter). The default session omits this flag entirely (temporary profile).

## 8. AX Tree Snapshot

Implements the design from `access_tree.md` with MVP simplifications.

### Pipeline

```
take_snapshot()
  ├── 1. Enable CDP domains (DOM.enable, Accessibility.enable)
  ├── 2. Get full AX tree (Accessibility.getFullAXTree)
  ├── 3. Build tree structure
  │     ├── Filter ignored nodes (keep RootWebArea as entry)
  │     ├── Skip InlineTextBox nodes
  │     ├── Merge consecutive StaticText
  │     ├── Deduplicate redundant StaticText (parent == child)
  │     ├── Collapse single-child generic nodes
  │     └── Skip empty StaticText
  ├── 4. Assign refs (e1, e2, ...) to interactive + named content roles
  ├── 5. Resolve link URLs (optional, future)
  ├── 6. Render to indented text
  └── 7. Compact mode (optional)
```

### Role Classification

| Category | Roles | Ref condition |
|----------|-------|---------------|
| Interactive | button, link, textbox, checkbox, radio, combobox, listbox, menuitem, menuitemcheckbox, menuitemradio, option, searchbox, slider, spinbutton, switch, tab, treeitem, Iframe | Always |
| Content | heading, cell, gridcell, columnheader, rowheader, listitem, article, region, main, navigation | When name is non-empty |
| Structural | generic, group, list, table, row, ... | Never |

### MVP Scope

**Included:**
- Full tree building with filtering/merging/collapsing rules
- Ref allocation with deduplication (role+name tracker)
- Compact mode
- Scoped snapshot via CSS selector

**Not included (future iteration):**
- Cursor-interactive element scanning (JS injection for cursor:pointer, onclick, tabindex)
- Hidden input promotion (radio/checkbox inside labels)
- Iframe recursive snapshot

### Rendered Output Format

```
- role "name" [attr=val, ref=eN]: value_text

Example:
- navigation
  - link "Home" [ref=e1]
  - link "About" [ref=e2]
- main
  - heading "Sign In" [level=1]
  - textbox "Email" [ref=e3]
  - textbox "Password" [ref=e4, required]
  - button "Submit" [ref=e5]
  - checkbox "Remember me" [checked=false, ref=e6]
```

## 9. Ref Map

Per-snapshot mapping from ref ID to element metadata.

```python
RefEntry:
  backend_node_id: int      # Chrome DOM node ID
  role: str                 # "button", "link", etc.
  name: str                 # "Submit", "Home", etc.
  nth: int | None           # Disambiguation index for same role+name
  frame_id: str | None      # Iframe frame ID (not used in MVP)
```

**Lifecycle:**
- Cleared and rebuilt on every snapshot
- Refs are ephemeral — old refs become invalid after page navigation or DOM changes
- `next_ref` counter resets to 1 on each snapshot

## 10. Interactions

### Element Resolution (3-level fallback)

```
resolve_element(input):
  Level 1: Parse ref (e.g. "e1") → lookup RefMap → backendNodeId
           → DOM.getBoxModel(backendNodeId) → coordinates
           → success ✓ | stale → Level 2

  Level 2: Re-query AX tree → match by role+name+nth → new backendNodeId
           → DOM.getBoxModel → coordinates
           → success ✓ | fail → error

  Level 3: (non-ref input only) CSS selector → querySelector → coordinates
           → success ✓ | fail → error
```

### Operations

| Operation | Resolution | Mechanism |
|-----------|-----------|-----------|
| click | coordinates | CDP `Input.dispatchMouseEvent` (move, press, release) |
| type | objectId | CDP `DOM.resolveNode` → focus element → `Input.insertText` per char |
| fill | objectId | CDP `DOM.resolveNode` → focus + select + clear → `Input.insertText` |
| hover | coordinates | CDP `Input.dispatchMouseEvent` (move only) |
| scroll | N/A | CDP `Input.dispatchMouseEvent` with deltaX/deltaY |

## 11. Client Output

**stdout** — JSON for agent parsing:
```json
{"status": "ok", "data": {"content": "..."}}
{"status": "error", "error": {"code": -32002, "message": "Element e5 not found"}}
```

**stderr** — human-readable summary:
```
Clicked element e5 (button "Submit")
```

## 12. Error Codes

| Code | Meaning |
|------|---------|
| -32000 | Browser not launched |
| -32001 | Operation timeout |
| -32002 | Element not found (stale ref or bad selector) |
| -32003 | Invalid parameters |
| -32600 | Invalid JSON-RPC request |

### Timeouts

| Operation | Default |
|-----------|---------|
| goto | 30s |
| snapshot | 10s |
| interaction | 5s |

## 13. Future Iterations (Out of MVP Scope)

- Cursor-interactive element scanning (JS injection)
- Hidden input promotion (radio/checkbox inside labels)
- Iframe recursive snapshot
- Multi-tab support
- Cookie/session management commands
- File upload/download
- Network request interception
