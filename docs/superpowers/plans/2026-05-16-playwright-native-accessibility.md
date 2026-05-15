# Playwright Native Accessibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace custom CDP-based accessibility tree + coordinate interactions with Playwright's native `aria_snapshot(mode="ai")` and locator-based click/fill/type/hover.

**Architecture:** The snapshot system calls `page.locator("body").aria_snapshot(mode="ai")` which returns YAML with `[ref=eN]` tags. A simple parser extracts `{ref_id → (role, name, nth)}` from the YAML text. Interactions resolve refs to Playwright locators via `page.get_by_role(role, name=name).nth(n)` and call native `.click()`, `.fill()`, etc.

**Tech Stack:** Playwright 1.59.0 (sync API), Python 3.13

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/auto_browser/ref_map.py` | Rewrite | `RefEntry(role, name, nth)` + `RefMap` + `parse_snapshot(yaml_text) -> RefMap` |
| `src/auto_browser/ax_tree.py` | Rewrite | Thin wrapper: `take_snapshot(page, ref_map, compact=False) -> str` |
| `src/auto_browser/interactions.py` | Rewrite | Playwright locator-based click/fill/type/hover/scroll/eval |
| `src/auto_browser/daemon.py` | Modify | Remove CDP session usage, pass `page` only |
| `src/auto_browser/browser_manager.py` | Modify | Remove `get_cdp_session()` |
| `tests/test_ref_map.py` | Rewrite | Tests for new `RefEntry`, `RefMap`, `parse_snapshot` |
| `tests/test_ax_tree.py` | Rewrite | Tests for new `take_snapshot` (needs real Playwright page) |
| `tests/test_interactions.py` | Modify | Update fixture to use new `Interactions(page, ref_map)` signature |

---

### Task 1: Rewrite `ref_map.py`

**Files:**
- Rewrite: `src/auto_browser/ref_map.py`
- Rewrite: `tests/test_ref_map.py`

- [ ] **Step 1: Write the failing tests for new `RefEntry` and `RefMap`**

```python
# tests/test_ref_map.py
import pytest
from auto_browser.ref_map import RefEntry, RefMap, parse_snapshot


class TestRefEntry:
    def test_create(self):
        entry = RefEntry(role="button", name="Submit", nth=0)
        assert entry.role == "button"
        assert entry.name == "Submit"
        assert entry.nth == 0

    def test_default_nth(self):
        entry = RefEntry(role="link", name="Home", nth=0)
        assert entry.nth == 0


class TestRefMap:
    def test_add_and_get(self):
        rm = RefMap()
        rm.add("e1", role="button", name="OK", nth=0)
        entry = rm.get("e1")
        assert entry.role == "button"
        assert entry.name == "OK"
        assert entry.nth == 0

    def test_get_missing_returns_none(self):
        rm = RefMap()
        assert rm.get("e999") is None

    def test_clear_resets(self):
        rm = RefMap()
        rm.add("e1", role="link", name="Home", nth=0)
        rm.clear()
        assert rm.get("e1") is None


class TestParseSnapshot:
    def test_parses_single_element(self):
        yaml_text = '- button "Submit" [ref=e1]'
        rm = parse_snapshot(yaml_text)
        entry = rm.get("e1")
        assert entry is not None
        assert entry.role == "button"
        assert entry.name == "Submit"
        assert entry.nth == 0

    def test_parses_element_without_name(self):
        yaml_text = "- textbox [ref=e5]"
        rm = parse_snapshot(yaml_text)
        entry = rm.get("e5")
        assert entry is not None
        assert entry.role == "textbox"
        assert entry.name == ""

    def test_tracks_nth_for_duplicate_role_name(self):
        yaml_text = '- link "Home" [ref=e1]\n- link "About" [ref=e2]\n- link "Home" [ref=e3]'
        rm = parse_snapshot(yaml_text)
        assert rm.get("e1").nth == 0
        assert rm.get("e3").nth == 1  # second "link Home"
        assert rm.get("e2").nth == 0  # only "link About"

    def test_empty_snapshot(self):
        rm = parse_snapshot("")
        assert rm.get("e1") is None

    def test_lines_without_ref_ignored(self):
        yaml_text = '- heading "Title"\n- button "OK" [ref=e1]'
        rm = parse_snapshot(yaml_text)
        assert rm.get("e1") is not None
        assert rm.get("e2") is None

    def test_name_with_special_chars(self):
        yaml_text = '- link "foo/bar?baz=1" [ref=e10]'
        rm = parse_snapshot(yaml_text)
        entry = rm.get("e10")
        assert entry is not None
        assert entry.name == "foo/bar?baz=1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/zenos/workspace/auto-browser && uv run pytest tests/test_ref_map.py -v`
Expected: FAIL — `ImportError` for `parse_snapshot`, old `RefEntry` has different fields.

- [ ] **Step 3: Rewrite `ref_map.py`**

```python
# src/auto_browser/ref_map.py
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RefEntry:
    role: str
    name: str
    nth: int


class RefMap:
    def __init__(self) -> None:
        self._entries: dict[str, RefEntry] = {}

    def add(self, ref_id: str, role: str, name: str, nth: int) -> None:
        self._entries[ref_id] = RefEntry(role=role, name=name, nth=nth)

    def get(self, ref_id: str) -> RefEntry | None:
        return self._entries.get(ref_id)

    def clear(self) -> None:
        self._entries.clear()


# Matches lines like: - button "Submit" [ref=e1]
# or: - textbox [ref=e5]
# or: - link "foo/bar" [ref=e10]
_LINE_RE = re.compile(
    r'^\s*-\s+'           # list item prefix with indentation
    r'(\w+)'              # role (group 1)
    r'(?:\s+"([^"]*)")?'  # optional "name" (group 2)
    r'.*?\[ref=(e\d+)\]'  # [ref=eN] (group 3)
)


def parse_snapshot(yaml_text: str) -> RefMap:
    ref_map = RefMap()
    if not yaml_text:
        return ref_map

    # Track occurrences of (role, name) for nth calculation
    counts: dict[tuple[str, str], int] = {}

    for line in yaml_text.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        role = m.group(1)
        name = m.group(2) or ""
        ref_id = m.group(3)
        key = (role, name)
        nth = counts.get(key, 0)
        counts[key] = nth + 1
        ref_map.add(ref_id, role, name, nth)

    return ref_map
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/zenos/workspace/auto-browser && uv run pytest tests/test_ref_map.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/auto_browser/ref_map.py tests/test_ref_map.py
git commit -m "refactor: rewrite ref_map for Playwright aria_snapshot ref parsing"
```

---

### Task 2: Rewrite `ax_tree.py`

**Files:**
- Rewrite: `src/auto_browser/ax_tree.py`
- Rewrite: `tests/test_ax_tree.py`
- Remove fixture: `tests/fixtures/ax_tree_response.json` (no longer needed)

- [ ] **Step 1: Write the failing tests for new `take_snapshot`**

```python
# tests/test_ax_tree.py
import urllib.parse

import pytest
from playwright.sync_api import Page

from auto_browser.ref_map import RefMap
from auto_browser.ax_tree import take_snapshot, parse_snapshot_yaml


HTML_SIMPLE = """<html><body>
    <h1>Title</h1>
    <button id="btn">Click Me</button>
    <a href="#link">Link</a>
    <input id="search" type="text" placeholder="Search">
</body></html>"""

HTML_DUPLICATES = """<html><body>
    <button>OK</button>
    <button>OK</button>
    <button>Cancel</button>
</body></html>"""


@pytest.fixture
def simple_page(browser_page):
    browser_page.goto("data:text/html," + urllib.parse.quote(HTML_SIMPLE))
    return browser_page


@pytest.fixture
def dup_page(browser_page):
    browser_page.goto("data:text/html," + urllib.parse.quote(HTML_DUPLICATES))
    return browser_page


class TestTakeSnapshot:
    def test_returns_yaml_string(self, simple_page):
        ref_map = RefMap()
        output = take_snapshot(simple_page, ref_map)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_contains_refs(self, simple_page):
        ref_map = RefMap()
        output = take_snapshot(simple_page, ref_map)
        assert "ref=" in output

    def test_ref_map_populated(self, simple_page):
        ref_map = RefMap()
        take_snapshot(simple_page, ref_map)
        # Should have at least a button and a link
        entries = list(ref_map._entries.values())
        roles = {e.role for e in entries}
        assert "button" in roles or "link" in roles

    def test_duplicate_elements_get_different_refs(self, dup_page):
        ref_map = RefMap()
        take_snapshot(dup_page, ref_map)
        ok_entries = [(k, v) for k, v in ref_map._entries.items() if v.name == "OK"]
        assert len(ok_entries) == 2
        # Different ref IDs
        assert ok_entries[0][0] != ok_entries[1][0]

    def test_compact_mode(self, simple_page):
        ref_map = RefMap()
        full = take_snapshot(simple_page, ref_map, compact=False)
        ref_map2 = RefMap()
        compact = take_snapshot(simple_page, ref_map2, compact=True)
        assert len(compact) <= len(full)


class TestParseSnapshotYaml:
    def test_extracts_refs(self):
        yaml_text = '- button "Click Me" [ref=e1]\n- link "Go" [ref=e2]'
        rm = parse_snapshot_yaml(yaml_text)
        assert rm.get("e1") is not None
        assert rm.get("e2") is not None

    def test_empty_input(self):
        rm = parse_snapshot_yaml("")
        assert rm.get("e1") is None
```

- [ ] **Step 2: Write conftest fixture for Playwright page**

The existing `conftest.py` is empty. Add a shared fixture that provides a real Playwright `Page`:

```python
# tests/conftest.py
import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture
def browser_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        yield page
        context.close()
        browser.close()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/zenos/workspace/auto-browser && uv run pytest tests/test_ax_tree.py -v`
Expected: FAIL — `ImportError` for `parse_snapshot_yaml`, old `take_snapshot` has different signature.

- [ ] **Step 4: Rewrite `ax_tree.py`**

```python
# src/auto_browser/ax_tree.py
from __future__ import annotations

from playwright.sync_api import Page

from auto_browser.ref_map import RefMap, parse_snapshot


def take_snapshot(page: Page, ref_map: RefMap, compact: bool = False) -> str:
    snapshot = page.locator("body").aria_snapshot(mode="ai")
    parsed = parse_snapshot(snapshot)
    # Copy parsed entries into the provided ref_map
    ref_map.clear()
    for ref_id, entry in parsed._entries.items():
        ref_map.add(ref_id, entry.role, entry.name, entry.nth)
    if compact:
        snapshot = _compact(snapshot)
    return snapshot


def _compact(yaml_text: str) -> str:
    lines = yaml_text.splitlines()
    result_indices: set[int] = set()

    for i, line in enumerate(lines):
        if "[ref=" in line:
            result_indices.add(i)
            current_indent = len(line) - len(line.lstrip())
            for j in range(i - 1, -1, -1):
                jline = lines[j]
                j_indent = len(jline) - len(jline.lstrip())
                if j_indent < current_indent:
                    result_indices.add(j)
                    current_indent = j_indent

    return "\n".join(lines[i] for i in sorted(result_indices))


# Public alias for testing
parse_snapshot_yaml = parse_snapshot
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/zenos/workspace/auto-browser && uv run pytest tests/test_ax_tree.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Delete old fixture file**

```bash
rm tests/fixtures/ax_tree_response.json
```

- [ ] **Step 7: Commit**

```bash
git add src/auto_browser/ax_tree.py tests/test_ax_tree.py tests/conftest.py
git rm tests/fixtures/ax_tree_response.json
git commit -m "refactor: replace custom CDP snapshot with Playwright aria_snapshot"
```

---

### Task 3: Rewrite `interactions.py`

**Files:**
- Rewrite: `src/auto_browser/interactions.py`
- Modify: `tests/test_interactions.py`

- [ ] **Step 1: Write the failing tests for new Playwright-based interactions**

```python
# tests/test_interactions.py
import urllib.parse

import pytest

from auto_browser.browser_manager import BrowserManager
from auto_browser.interactions import Interactions
from auto_browser.ref_map import RefMap
from auto_browser.ax_tree import take_snapshot

HTML_CONTENT = """<html><body>
    <input id="search" type="text" placeholder="Search">
    <button id="btn" onclick="document.title='clicked'">Click Me</button>
    <a id="link" href="#target">Link</a>
</body></html>"""


@pytest.fixture
def browser_env():
    bm = BrowserManager(session_name="default", headed=True, user_data_dir=None)
    bm.start()
    bm.page.goto("data:text/html," + urllib.parse.quote(HTML_CONTENT))
    ref_map = RefMap()
    ia = Interactions(bm.page, ref_map)
    yield bm, ref_map, ia
    bm.close()


def _find_ref(ref_map: RefMap, role: str, name: str = "") -> str:
    for ref_id, entry in ref_map._entries.items():
        if entry.role == role and (not name or entry.name == name):
            return ref_id
    raise ValueError(f"No ref found for role={role} name={name}")


class TestClick:
    def test_click_by_ref(self, browser_env):
        bm, ref_map, ia = browser_env
        take_snapshot(bm.page, ref_map)
        ref_id = _find_ref(ref_map, "button", "Click Me")
        ia.click(ref_id)
        assert bm.page.title() == "clicked"


class TestType:
    def test_type_by_ref(self, browser_env):
        bm, ref_map, ia = browser_env
        take_snapshot(bm.page, ref_map)
        ref_id = _find_ref(ref_map, "textbox")
        ia.type(ref_id, "hello world")
        assert bm.page.locator("#search").input_value() == "hello world"


class TestFill:
    def test_fill_by_ref(self, browser_env):
        bm, ref_map, ia = browser_env
        take_snapshot(bm.page, ref_map)
        ref_id = _find_ref(ref_map, "textbox")
        ia.fill(ref_id, "filled")
        assert bm.page.locator("#search").input_value() == "filled"


class TestScroll:
    def test_scroll_down(self, browser_env):
        bm, ref_map, ia = browser_env
        result = ia.scroll("down", 300)
        assert result["status"] == "ok"
        assert result["direction"] == "down"


class TestHover:
    def test_hover_by_ref(self, browser_env):
        bm, ref_map, ia = browser_env
        take_snapshot(bm.page, ref_map)
        ref_id = _find_ref(ref_map, "button", "Click Me")
        result = ia.hover(ref_id)
        assert result["status"] == "ok"


class TestEvalJs:
    def test_eval_returns_result(self, browser_env):
        bm, ref_map, ia = browser_env
        result = ia.eval_js("1 + 1")
        assert result["status"] == "ok"


class TestInvalidRef:
    def test_click_unknown_ref_raises(self, browser_env):
        bm, ref_map, ia = browser_env
        with pytest.raises(ValueError, match="Unknown ref"):
            ia.click("e999")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/zenos/workspace/auto-browser && uv run pytest tests/test_interactions.py -v`
Expected: FAIL — `Interactions.__init__` expects different arguments.

- [ ] **Step 3: Rewrite `interactions.py`**

```python
# src/auto_browser/interactions.py
from __future__ import annotations

from playwright.sync_api import Page

from auto_browser.ref_map import RefMap


class Interactions:
    def __init__(self, page: Page, ref_map: RefMap) -> None:
        self.page = page
        self.ref_map = ref_map

    def _resolve(self, ref: str):
        entry = self.ref_map.get(ref)
        if not entry:
            raise ValueError(f"Unknown ref: {ref}")
        return entry

    def _locator(self, entry):
        loc = self.page.get_by_role(entry.role, name=entry.name)
        if entry.nth > 0:
            loc = loc.nth(entry.nth)
        return loc

    def click(self, ref: str, button: str = "left", double: bool = False) -> dict:
        entry = self._resolve(ref)
        loc = self._locator(entry)
        if double:
            loc.dblclick(button=button)
        else:
            loc.click(button=button)
        return {"status": "ok", "action": "click", "ref": ref}

    def type(self, ref: str, text: str, clear: bool = False) -> dict:
        entry = self._resolve(ref)
        loc = self._locator(entry)
        if clear:
            loc.fill("")
        loc.press_sequentially(text)
        return {"status": "ok", "action": "type", "text": text}

    def fill(self, ref: str, value: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).fill(value)
        return {"status": "ok", "action": "fill", "value": value}

    def hover(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).hover()
        return {"status": "ok", "action": "hover", "ref": ref}

    def scroll(self, direction: str, amount: int = 300) -> dict:
        delta_y = -amount if direction == "up" else amount
        self.page.mouse.wheel(0, delta_y)
        return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount}

    def eval_js(self, expression: str) -> dict:
        result = self.page.evaluate(expression)
        return {"status": "ok", "result": result}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/zenos/workspace/auto-browser && uv run pytest tests/test_interactions.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/auto_browser/interactions.py tests/test_interactions.py
git commit -m "refactor: replace CDP coordinate interactions with Playwright locators"
```

---

### Task 4: Update `daemon.py` and `browser_manager.py`

**Files:**
- Modify: `src/auto_browser/daemon.py`
- Modify: `src/auto_browser/browser_manager.py`
- Modify: `tests/test_daemon.py` (if needed)

- [ ] **Step 1: Update `daemon.py` to remove CDP session usage**

Key changes to `daemon.py`:
1. Remove `cdp` variable from `_snapshot()` — call `take_snapshot(self.bm.page, ...)` instead of `take_snapshot(cdp, ...)`
2. Remove `get_cdp_session()` call from `_get_interactions()` — use `Interactions(self.bm.page, self.ref_map)` instead
3. Remove unused import of `CDPSession` if present

The updated methods:

```python
# In daemon.py, update these methods:

def _get_interactions(self) -> Interactions:
    return Interactions(self.bm.page, self.ref_map)

def _snapshot(self, params: dict) -> dict:
    compact = params.get("compact", False)
    selector = params.get("selector")
    content = take_snapshot(self.bm.page, self.ref_map, compact=compact)
    return {"status": "ok", "content": content}
```

Full updated `daemon.py`:

```python
# src/auto_browser/daemon.py
from __future__ import annotations

import json
import os
import socket
from typing import Any

from auto_browser.browser_manager import BrowserManager
from auto_browser.ref_map import RefMap
from auto_browser.ax_tree import take_snapshot
from auto_browser.interactions import Interactions


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message


class Daemon:
    def __init__(self, socket_path: str, headed: bool, user_data_dir: str | None, session_name: str) -> None:
        self.socket_path = socket_path
        self.bm = BrowserManager(session_name=session_name, headed=headed, user_data_dir=user_data_dir)
        self.ref_map = RefMap()
        self._running = False

    def start(self) -> None:
        self.bm.start()
        self._running = True
        self._serve()

    def _serve(self) -> None:
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.socket_path)
        server.listen(1)
        server.settimeout(1.0)

        while self._running:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            try:
                data = b""
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in data:
                        break
                if data:
                    request = json.loads(data.strip())
                    response = self._handle_request(request)
                    conn.sendall(json.dumps(response).encode() + b"\n")
            except Exception as e:
                try:
                    error_resp = {
                        "jsonrpc": "2.0", "id": None,
                        "error": {"code": -32603, "message": str(e)},
                    }
                    conn.sendall(json.dumps(error_resp).encode() + b"\n")
                except Exception:
                    pass
            finally:
                conn.close()
        server.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def _handle_request(self, request: dict) -> dict:
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        try:
            if method == "shutdown":
                result = self._shutdown()
            elif method == "ping":
                result = {"status": "ok"}
            elif method == "goto":
                result = self._goto(params)
            elif method == "snapshot":
                result = self._snapshot(params)
            elif method == "click":
                result = self._interact("click", params)
            elif method == "type":
                result = self._interact("type", params)
            elif method == "fill":
                result = self._interact("fill", params)
            elif method == "hover":
                result = self._interact("hover", params)
            elif method == "scroll":
                result = self._interact("scroll", params)
            elif method == "screenshot":
                result = self._screenshot(params)
            elif method == "eval":
                result = self._eval(params)
            else:
                raise JsonRpcError(-32601, f"Method not found: {method}")
        except JsonRpcError as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": e.code, "message": e.message}}

        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _get_interactions(self) -> Interactions:
        return Interactions(self.bm.page, self.ref_map)

    def _shutdown(self) -> dict:
        self._running = False
        self.bm.close()
        return {"status": "ok"}

    def _goto(self, params: dict) -> dict:
        url = params.get("url")
        if not url:
            raise JsonRpcError(-32003, "Missing url parameter")
        self.bm.navigate(url)
        return {"status": "ok", "url": url, "title": self.bm.page.title()}

    def _snapshot(self, params: dict) -> dict:
        compact = params.get("compact", False)
        content = take_snapshot(self.bm.page, self.ref_map, compact=compact)
        return {"status": "ok", "content": content}

    def _interact(self, action: str, params: dict) -> dict:
        ia = self._get_interactions()
        ref = params.get("ref") or params.get("selector", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref or selector")

        if action == "click":
            return ia.click(ref, double=params.get("double", False))
        elif action == "type":
            text = params.get("text", "")
            return ia.type(ref, text, clear=params.get("clear", False))
        elif action == "fill":
            value = params.get("value", "")
            return ia.fill(ref, value)
        elif action == "hover":
            return ia.hover(ref)
        elif action == "scroll":
            direction = params.get("direction", "down")
            amount = params.get("amount", 300)
            return ia.scroll(direction, amount)
        raise JsonRpcError(-32601, f"Unknown action: {action}")

    def _screenshot(self, params: dict) -> dict:
        path = params.get("path", "screenshot.png")
        self.bm.page.screenshot(path=path)
        return {"status": "ok", "path": path}

    def _eval(self, params: dict) -> dict:
        expression = params.get("expression", "")
        ia = self._get_interactions()
        return ia.eval_js(expression)


def run_daemon(socket_path: str, headed: bool, user_data_dir: str | None, session_name: str) -> None:
    daemon = Daemon(socket_path, headed, user_data_dir, session_name)
    daemon.start()
```

- [ ] **Step 2: Remove `get_cdp_session()` from `browser_manager.py`**

In `browser_manager.py`:
- Remove the `get_cdp_session` method (lines 52-54)
- Remove `CDPSession` from the import on line 3

The import becomes:
```python
from playwright.sync_api import Browser, BrowserContext, Page
```

Remove this method entirely:
```python
    def get_cdp_session(self) -> CDPSession:
        assert self._context is not None, "Browser not started"
        return self._context.new_cdp_session(self._page)
```

- [ ] **Step 3: Run all tests**

Run: `cd /home/zenos/workspace/auto-browser && uv run pytest tests/ -v`
Expected: All tests PASS. The daemon integration test (`test_daemon.py`) should still pass since it only tests `ping`.

- [ ] **Step 4: Commit**

```bash
git add src/auto_browser/daemon.py src/auto_browser/browser_manager.py tests/
git commit -m "refactor: remove CDP session usage, use Playwright page directly"
```

---

### Task 5: End-to-end verification

**Files:** None (manual testing)

- [ ] **Step 1: Start daemon and test snapshot**

```bash
cd /home/zenos/workspace/auto-browser
uv run ab open https://news.baidu.com
```

- [ ] **Step 2: Test snapshot output format**

```bash
uv run ab -s zenos snapshot
```

Expected: YAML-format output with `[ref=eN]` tags (different from previous custom format).

- [ ] **Step 3: Test click interaction**

```bash
uv run ab -s zenos click e12
```

Expected: Click succeeds and page actually navigates (unlike before where coordinate-based click had no effect).

- [ ] **Step 4: Test close**

```bash
uv run ab -s zenos close
```

Expected: Clean shutdown.

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes for Playwright native interactions"
```
