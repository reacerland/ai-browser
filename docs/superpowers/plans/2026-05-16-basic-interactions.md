# Basic Interactions Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 18 new commands to auto-browser for complete AI agent basic interaction coverage.

**Architecture:** All commands follow the existing client → JSON-RPC → daemon → interactions → Playwright pipeline. No structural changes — just adding new methods to `interactions.py`, handlers to `daemon.py`, methods to `client.py`, and Click commands to `cli.py`.

**Tech Stack:** Python 3.13, Click, Playwright (sync API), JSON-RPC over Unix sockets

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/auto_browser/interactions.py` | Bottom-layer Playwright operations — all ref resolution + Playwright calls |
| `src/auto_browser/daemon.py` | RPC dispatch + handler methods that delegate to interactions |
| `src/auto_browser/client.py` | Thin JSON-RPC client wrappers (no changes needed — uses generic `call()`) |
| `src/auto_browser/cli.py` | Click command definitions that call client |
| `tests/test_new_interactions.py` | Integration tests for all new interaction methods |

**Note on client.py:** The existing `Client.call(method, params)` is fully generic — no per-method wrappers needed. CLI commands call `client.call("method", params)` directly.

---

### Task 1: Add `get` methods to Interactions

**Files:**
- Modify: `src/auto_browser/interactions.py`

- [ ] **Step 1: Add get methods to Interactions class**

Add these methods after `eval_js` at the end of `interactions.py`:

```python
    def get_text(self, ref: str) -> dict:
        entry = self._resolve(ref)
        text = self._locator(entry).text_content() or ""
        return {"status": "ok", "value": text}

    def get_html(self, ref: str) -> dict:
        entry = self._resolve(ref)
        html = self._locator(entry).inner_html()
        return {"status": "ok", "value": html}

    def get_value(self, ref: str) -> dict:
        entry = self._resolve(ref)
        value = self._locator(entry).input_value()
        return {"status": "ok", "value": value}

    def get_attr(self, ref: str, name: str) -> dict:
        entry = self._resolve(ref)
        value = self._locator(entry).get_attribute(name)
        return {"status": "ok", "value": value}

    def get_box(self, ref: str) -> dict:
        entry = self._resolve(ref)
        box = self._locator(entry).bounding_box()
        return {"status": "ok", "value": box}
```

- [ ] **Step 2: Commit**

```bash
git add src/auto_browser/interactions.py
git commit -m "feat: add get methods to Interactions (text/html/value/attr/box)"
```

---

### Task 2: Add `is` methods to Interactions

**Files:**
- Modify: `src/auto_browser/interactions.py`

- [ ] **Step 1: Add is methods to Interactions class**

Append after the get methods:

```python
    def is_visible(self, ref: str) -> dict:
        entry = self._resolve(ref)
        visible = self._locator(entry).is_visible()
        return {"status": "ok", "value": visible}

    def is_enabled(self, ref: str) -> dict:
        entry = self._resolve(ref)
        enabled = self._locator(entry).is_enabled()
        return {"status": "ok", "value": enabled}

    def is_checked(self, ref: str) -> dict:
        entry = self._resolve(ref)
        checked = self._locator(entry).is_checked()
        return {"status": "ok", "value": checked}
```

- [ ] **Step 2: Commit**

```bash
git add src/auto_browser/interactions.py
git commit -m "feat: add is methods to Interactions (visible/enabled/checked)"
```

---

### Task 3: Add `wait` and `find` methods to Interactions

**Files:**
- Modify: `src/auto_browser/interactions.py`

- [ ] **Step 1: Add wait and find methods**

Append to Interactions class:

```python
    def wait_for_ref(self, ref: str, timeout: int = 25000) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).wait_for(state="visible", timeout=timeout)
        return {"status": "ok", "action": "wait", "ref": ref}

    def wait_for_timeout(self, ms: int) -> dict:
        self.page.wait_for_timeout(ms)
        return {"status": "ok", "action": "wait", "ms": ms}

    def find(self, locator_type: str, value: str, name: str | None = None) -> dict:
        locators = {
            "role": lambda: self.page.get_by_role(value, name=name),
            "text": lambda: self.page.get_by_text(value),
            "label": lambda: self.page.get_by_label(value),
            "placeholder": lambda: self.page.get_by_placeholder(value),
            "alt": lambda: self.page.get_by_alt_text(value),
            "title": lambda: self.page.get_by_title(value),
            "testid": lambda: self.page.get_by_test_id(value),
        }
        if locator_type not in locators:
            raise ValueError(f"Unknown locator type: {locator_type}")
        locator = locators[locator_type]()
        snapshot = locator.aria_snapshot(mode="ai")
        return {"status": "ok", "content": snapshot}
```

- [ ] **Step 2: Commit**

```bash
git add src/auto_browser/interactions.py
git commit -m "feat: add wait and find methods to Interactions"
```

---

### Task 4: Add navigation & keyboard methods to Interactions

**Files:**
- Modify: `src/auto_browser/interactions.py`

- [ ] **Step 1: Add navigation and keyboard methods**

Append to Interactions class:

```python
    def go_back(self) -> dict:
        self.page.go_back()
        return {"status": "ok", "action": "back", "url": self.page.url}

    def go_forward(self) -> dict:
        self.page.go_forward()
        return {"status": "ok", "action": "forward", "url": self.page.url}

    def reload(self) -> dict:
        self.page.reload()
        return {"status": "ok", "action": "reload", "url": self.page.url}

    def press(self, key: str) -> dict:
        self.page.keyboard.press(key)
        return {"status": "ok", "action": "press", "key": key}

    def select_option(self, ref: str, value: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).select_option(value)
        return {"status": "ok", "action": "select", "ref": ref, "value": value}
```

- [ ] **Step 2: Commit**

```bash
git add src/auto_browser/interactions.py
git commit -m "feat: add navigation and keyboard methods to Interactions"
```

---

### Task 5: Add checkbox, drag, scroll-into-view, upload, download, count methods to Interactions

**Files:**
- Modify: `src/auto_browser/interactions.py`

- [ ] **Step 1: Add remaining interaction methods**

Append to Interactions class:

```python
    def check(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).check()
        return {"status": "ok", "action": "check", "ref": ref}

    def uncheck(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).uncheck()
        return {"status": "ok", "action": "uncheck", "ref": ref}

    def dblclick(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).dblclick()
        return {"status": "ok", "action": "dblclick", "ref": ref}

    def drag(self, src_ref: str, dst_ref: str) -> dict:
        src_entry = self._resolve(src_ref)
        dst_entry = self._resolve(dst_ref)
        src_loc = self._locator(src_entry)
        dst_loc = self._locator(dst_entry)
        src_loc.drag_to(dst_loc)
        return {"status": "ok", "action": "drag", "src": src_ref, "dst": dst_ref}

    def scroll_into_view(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).scroll_into_view_if_needed()
        return {"status": "ok", "action": "scroll_into_view", "ref": ref}

    def count(self, selector: str) -> dict:
        n = self.page.locator(selector).count()
        return {"status": "ok", "action": "count", "value": n}

    def upload(self, ref: str, files: list[str]) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).set_input_files(files)
        return {"status": "ok", "action": "upload", "ref": ref, "files": files}

    def download(self, ref: str, save_path: str) -> dict:
        entry = self._resolve(ref)
        loc = self._locator(entry)
        with self.page.expect_download() as d:
            loc.click()
        download = d.value
        download.save_as(save_path)
        return {"status": "ok", "action": "download", "ref": ref, "path": save_path}
```

- [ ] **Step 2: Commit**

```bash
git add src/auto_browser/interactions.py
git commit -m "feat: add check/uncheck/dblclick/drag/scroll-into-view/count/upload/download to Interactions"
```

---

### Task 6: Add RPC handlers to daemon

**Files:**
- Modify: `src/auto_browser/daemon.py`

- [ ] **Step 1: Add new RPC dispatch entries in `_handle_request`**

In the `_handle_request` method, add new `elif` branches before the `else` clause at line 113. Add after the `eval` branch (line 112):

```python
            elif method == "get":
                result = self._get(params)
            elif method == "is":
                result = self._is_check(params)
            elif method == "wait":
                result = self._wait(params)
            elif method == "find":
                result = self._find(params)
            elif method == "back":
                result = self._get_interactions().go_back()
            elif method == "forward":
                result = self._get_interactions().go_forward()
            elif method == "reload":
                result = self._get_interactions().reload()
            elif method == "press":
                result = self._get_interactions().press(params.get("key", ""))
            elif method == "select":
                result = self._select(params)
            elif method == "check":
                result = self._interact("check", params)
            elif method == "uncheck":
                result = self._interact("uncheck", params)
            elif method == "dblclick":
                result = self._interact("dblclick", params)
            elif method == "drag":
                result = self._drag(params)
            elif method == "scroll_into_view":
                result = self._interact("scroll_into_view", params)
            elif method == "count":
                result = self._get_interactions().count(params.get("selector", ""))
            elif method == "upload":
                result = self._upload(params)
            elif method == "download":
                result = self._download(params)
```

- [ ] **Step 2: Add new handler methods to Daemon class**

Add these methods after `_eval` (after line 170), before `run_daemon`:

```python
    def _get(self, params: dict) -> dict:
        what = params.get("what", "")
        ia = self._get_interactions()
        if what == "title":
            return {"status": "ok", "value": self.bm.page.title}
        elif what == "url":
            return {"status": "ok", "value": self.bm.page.url}
        ref = params.get("ref", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        if what == "text":
            return ia.get_text(ref)
        elif what == "html":
            return ia.get_html(ref)
        elif what == "value":
            return ia.get_value(ref)
        elif what == "attr":
            name = params.get("name", "")
            if not name:
                raise JsonRpcError(-32003, "Missing attr name")
            return ia.get_attr(ref, name)
        elif what == "box":
            return ia.get_box(ref)
        raise JsonRpcError(-32003, f"Unknown get type: {what}")

    def _is_check(self, params: dict) -> dict:
        what = params.get("what", "")
        ref = params.get("ref", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        ia = self._get_interactions()
        if what == "visible":
            return ia.is_visible(ref)
        elif what == "enabled":
            return ia.is_enabled(ref)
        elif what == "checked":
            return ia.is_checked(ref)
        raise JsonRpcError(-32003, f"Unknown is type: {what}")

    def _wait(self, params: dict) -> dict:
        target = params.get("target", "")
        ia = self._get_interactions()
        if target.startswith("e") and target[1:].isdigit():
            return ia.wait_for_ref(target, timeout=params.get("timeout", 25000))
        elif target.isdigit():
            return ia.wait_for_timeout(int(target))
        raise JsonRpcError(-32003, f"Invalid wait target: {target}")

    def _find(self, params: dict) -> dict:
        locator_type = params.get("locator", "")
        value = params.get("value", "")
        name = params.get("name")
        ia = self._get_interactions()
        return ia.find(locator_type, value, name)

    def _select(self, params: dict) -> dict:
        ref = params.get("ref", "")
        value = params.get("value", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        return self._get_interactions().select_option(ref, value)

    def _drag(self, params: dict) -> dict:
        src = params.get("src", "")
        dst = params.get("dst", "")
        if not src or not dst:
            raise JsonRpcError(-32003, "Missing src or dst ref")
        return self._get_interactions().drag(src, dst)

    def _upload(self, params: dict) -> dict:
        ref = params.get("ref", "")
        files = params.get("files", [])
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        return self._get_interactions().upload(ref, files)

    def _download(self, params: dict) -> dict:
        ref = params.get("ref", "")
        path = params.get("path", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        if not path:
            raise JsonRpcError(-32003, "Missing path parameter")
        return self._get_interactions().download(ref, path)
```

- [ ] **Step 3: Update `_interact` to handle new action types**

In the `_interact` method (line 140), add new `elif` branches before the final `raise` at line 160:

```python
        elif action == "check":
            return ia.check(ref)
        elif action == "uncheck":
            return ia.uncheck(ref)
        elif action == "dblclick":
            return ia.dblclick(ref)
        elif action == "scroll_into_view":
            return ia.scroll_into_view(ref)
```

- [ ] **Step 4: Commit**

```bash
git add src/auto_browser/daemon.py
git commit -m "feat: add RPC handlers for 18 new commands to daemon"
```

---

### Task 7: Add CLI commands

**Files:**
- Modify: `src/auto_browser/cli.py`

- [ ] **Step 1: Add `get` command**

Add after the `eval` command (after line 327):

```python
@cli.command("get")
@click.argument("what", type=click.Choice(["text", "html", "value", "attr", "title", "url", "box"]))
@click.argument("ref", required=False)
@click.option("--name", help="Attribute name (for attr type).")
@click.pass_context
def get_cmd(ctx: click.Context, what: str, ref: str | None, name: str | None) -> None:
    """Get element property or page info."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {"what": what}
    if ref:
        params["ref"] = ref
    if name:
        params["name"] = name
    result = client.call("get", params)
    if "value" in result:
        print(result["value"])
    else:
        _output(result)
```

- [ ] **Step 2: Add `is` command**

```python
@cli.command("is")
@click.argument("what", type=click.Choice(["visible", "enabled", "checked"]))
@click.argument("ref")
@click.pass_context
def is_cmd(ctx: click.Context, what: str, ref: str) -> None:
    """Check element state (outputs true/false)."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("is", {"what": what, "ref": ref})
    print(str(result.get("value", False)).lower())
```

- [ ] **Step 3: Add `wait` command**

```python
@cli.command("wait")
@click.argument("target")
@click.option("--timeout", type=int, default=25000, help="Timeout in ms (default: 25000).")
@click.pass_context
def wait_cmd(ctx: click.Context, target: str, timeout: int) -> None:
    """Wait for element (ref) or time (ms)."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("wait", {"target": target, "timeout": timeout})
    _output(result)
```

- [ ] **Step 4: Add `find` command**

```python
@cli.command("find")
@click.argument("locator", type=click.Choice(["role", "text", "label", "placeholder", "alt", "title", "testid"]))
@click.argument("value")
@click.option("--name", help="Name filter (only for role locator).")
@click.pass_context
def find_cmd(ctx: click.Context, locator: str, value: str, name: str | None) -> None:
    """Find elements by locator type."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {"locator": locator, "value": value}
    if name:
        params["name"] = name
    result = client.call("find", params)
    if "content" in result:
        print(result["content"])
    else:
        _output(result)
```

- [ ] **Step 5: Add navigation commands (`back`, `forward`, `reload`)**

```python
@cli.command()
@click.pass_context
def back(ctx: click.Context) -> None:
    """Go back in browser history."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("back")
    _output(result)


@cli.command()
@click.pass_context
def forward(ctx: click.Context) -> None:
    """Go forward in browser history."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("forward")
    _output(result)


@cli.command()
@click.pass_context
def reload(ctx: click.Context) -> None:
    """Reload the current page."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("reload")
    _output(result)
```

- [ ] **Step 6: Add `press`, `select`, `check`, `uncheck`, `dblclick` commands**

```python
@cli.command()
@click.argument("key")
@click.pass_context
def press(ctx: click.Context, key: str) -> None:
    """Press a keyboard key (e.g. Enter, Tab, Escape, Control+a)."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("press", {"key": key})
    _output(result)


@cli.command("select")
@click.argument("ref")
@click.argument("value")
@click.pass_context
def select_cmd(ctx: click.Context, ref: str, value: str) -> None:
    """Select an option in a dropdown by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("select", {"ref": ref, "value": value})
    _output(result)


@cli.command()
@click.argument("ref")
@click.pass_context
def check(ctx: click.Context, ref: str) -> None:
    """Check a checkbox by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("check", {"ref": ref})
    _output(result)


@cli.command()
@click.argument("ref")
@click.pass_context
def uncheck(ctx: click.Context, ref: str) -> None:
    """Uncheck a checkbox by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("uncheck", {"ref": ref})
    _output(result)


@cli.command()
@click.argument("ref")
@click.pass_context
def dblclick(ctx: click.Context, ref: str) -> None:
    """Double-click an element by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("dblclick", {"ref": ref})
    _output(result)
```

- [ ] **Step 7: Add `drag`, `scroll-into-view`, `hover`, `count`, `upload`, `download` commands**

```python
@cli.command()
@click.argument("src_ref")
@click.argument("dst_ref")
@click.pass_context
def drag(ctx: click.Context, src_ref: str, dst_ref: str) -> None:
    """Drag element to another element by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("drag", {"src": src_ref, "dst": dst_ref})
    _output(result)


@cli.command("scroll-into-view")
@click.argument("ref")
@click.pass_context
def scroll_into_view_cmd(ctx: click.Context, ref: str) -> None:
    """Scroll element into view by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("scroll_into_view", {"ref": ref})
    _output(result)


@cli.command()
@click.argument("ref")
@click.pass_context
def hover(ctx: click.Context, ref: str) -> None:
    """Hover over an element by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("hover", {"ref": ref})
    _output(result)


@cli.command()
@click.argument("selector")
@click.pass_context
def count(ctx: click.Context, selector: str) -> None:
    """Count elements matching a CSS selector."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("count", {"selector": selector})
    print(result.get("value", 0))


@cli.command()
@click.argument("ref")
@click.argument("files", nargs=-1, required=True)
@click.pass_context
def upload(ctx: click.Context, ref: str, files: tuple[str, ...]) -> None:
    """Upload files to a file input by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("upload", {"ref": ref, "files": list(files)})
    _output(result)


@cli.command()
@click.argument("ref")
@click.argument("path")
@click.pass_context
def download(ctx: click.Context, ref: str, path: str) -> None:
    """Download a file by clicking element ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("download", {"ref": ref, "path": path})
    _output(result)
```

- [ ] **Step 8: Commit**

```bash
git add src/auto_browser/cli.py
git commit -m "feat: add 18 new CLI commands for basic interactions"
```

---

### Task 8: Add integration tests for get/is/wait/find

**Files:**
- Create: `tests/test_new_interactions.py`

- [ ] **Step 1: Write tests**

Create `tests/test_new_interactions.py` with comprehensive HTML fixtures and tests:

```python
import urllib.parse

import pytest

from auto_browser.browser_manager import BrowserManager
from auto_browser.interactions import Interactions
from auto_browser.ref_map import RefMap
from auto_browser.ax_tree import take_snapshot

RICH_HTML = """<html><body>
    <input id="search" type="text" placeholder="Search" value="initial">
    <button id="btn" onclick="document.title='clicked'">Click Me</button>
    <a id="link" href="#target">Link</a>
    <input id="cb" type="checkbox">
    <select id="sel"><option value="a">A</option><option value="b">B</option></select>
    <div id="text-div">Hello World</div>
    <input id="file-input" type="file">
</body></html>"""


@pytest.fixture
def browser_env():
    bm = BrowserManager(session_name="default", headed=True, user_data_dir=None)
    bm.start()
    bm.page.goto("data:text/html," + urllib.parse.quote(RICH_HTML))
    ref_map = RefMap()
    take_snapshot(bm.page, ref_map)
    ia = Interactions(bm.page, ref_map)
    yield bm, ref_map, ia
    bm.close()


def _find_ref(ref_map: RefMap, role: str, name: str = "") -> str:
    for ref_id, entry in ref_map._entries.items():
        if entry.role == role and (not name or entry.name == name):
            return ref_id
    raise ValueError(f"No ref found for role={role} name={name}")


class TestGet:
    def test_get_text(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "button", "Click Me")
        result = ia.get_text(ref)
        assert result["status"] == "ok"
        assert "Click Me" in result["value"]

    def test_get_value(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "textbox")
        result = ia.get_value(ref)
        assert result["status"] == "ok"
        assert result["value"] == "initial"

    def test_get_html(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "button", "Click Me")
        result = ia.get_html(ref)
        assert result["status"] == "ok"
        assert "Click Me" in result["value"]

    def test_get_attr(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "link", "Link")
        result = ia.get_attr(ref, "href")
        assert result["status"] == "ok"
        assert "#target" in result["value"]


class TestIs:
    def test_is_visible(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "button", "Click Me")
        result = ia.is_visible(ref)
        assert result["value"] is True

    def test_is_enabled(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "button", "Click Me")
        result = ia.is_enabled(ref)
        assert result["value"] is True

    def test_is_checked(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "checkbox")
        result = ia.is_checked(ref)
        assert result["value"] is False


class TestWait:
    def test_wait_for_timeout(self, browser_env):
        bm, ref_map, ia = browser_env
        result = ia.wait_for_timeout(50)
        assert result["status"] == "ok"

    def test_wait_for_ref(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "button", "Click Me")
        result = ia.wait_for_ref(ref, timeout=5000)
        assert result["status"] == "ok"


class TestFind:
    def test_find_by_role(self, browser_env):
        bm, ref_map, ia = browser_env
        result = ia.find("role", "button", name="Click Me")
        assert result["status"] == "ok"
        assert "Click Me" in result["content"]

    def test_find_by_text(self, browser_env):
        bm, ref_map, ia = browser_env
        result = ia.find("text", "Click Me")
        assert result["status"] == "ok"
        assert "Click Me" in result["content"]

    def test_find_by_label(self, browser_env):
        bm, ref_map, ia = browser_env
        result = ia.find("placeholder", "Search")
        assert result["status"] == "ok"

    def test_find_invalid_locator(self, browser_env):
        bm, ref_map, ia = browser_env
        with pytest.raises(ValueError, match="Unknown locator type"):
            ia.find("invalid", "test")


class TestNavigation:
    def test_back_and_forward(self, browser_env):
        bm, ref_map, ia = browser_env
        link_ref = _find_ref(ref_map, "link", "Link")
        ia.click(link_ref)
        result = ia.go_back()
        assert result["status"] == "ok"
        result = ia.go_forward()
        assert result["status"] == "ok"

    def test_reload(self, browser_env):
        bm, ref_map, ia = browser_env
        result = ia.reload()
        assert result["status"] == "ok"


class TestPress:
    def test_press_key(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "textbox")
        ia.click(ref)
        ia.press("a")
        assert "a" in bm.page.locator("#search").input_value()

    def test_press_enter(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "textbox")
        ia.click(ref)
        result = ia.press("Enter")
        assert result["status"] == "ok"


class TestCheckUncheck:
    def test_check(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "checkbox")
        ia.check(ref)
        assert bm.page.locator("#cb").is_checked()

    def test_uncheck(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "checkbox")
        bm.page.locator("#cb").check()
        ia.uncheck(ref)
        assert not bm.page.locator("#cb").is_checked()


class TestSelect:
    def test_select_option(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "combobox")
        ia.select_option(ref, "b")
        assert bm.page.locator("#sel").input_value() == "b"


class TestDblclick:
    def test_dblclick(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "button", "Click Me")
        result = ia.dblclick(ref)
        assert result["status"] == "ok"


class TestScrollIntoView:
    def test_scroll_into_view(self, browser_env):
        bm, ref_map, ia = browser_env
        ref = _find_ref(ref_map, "button", "Click Me")
        result = ia.scroll_into_view(ref)
        assert result["status"] == "ok"


class TestCount:
    def test_count_elements(self, browser_env):
        bm, ref_map, ia = browser_env
        result = ia.count("input")
        assert result["status"] == "ok"
        assert result["value"] >= 1


class TestDrag:
    def test_drag(self, browser_env):
        bm, ref_map, ia = browser_env
        src_ref = _find_ref(ref_map, "link", "Link")
        dst_ref = _find_ref(ref_map, "button", "Click Me")
        result = ia.drag(src_ref, dst_ref)
        assert result["status"] == "ok"


class TestUpload:
    def test_upload(self, browser_env, tmp_path):
        bm, ref_map, ia = browser_env
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        ref = _find_ref(ref_map, "button", "Click Me")
        # The file input may not have a ref; use direct locator if needed
        # This test verifies upload doesn't crash
        result = ia.upload(ref, [str(test_file)])
        assert result["status"] == "ok"
```

- [ ] **Step 2: Run tests**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/test_new_interactions.py -v`

Expected: All tests PASS. Some tests (upload with wrong ref, drag) may need adjustment based on Playwright behavior — fix inline if needed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_new_interactions.py
git commit -m "test: add integration tests for 18 new interaction commands"
```

---

### Task 9: Final verification

- [ ] **Step 1: Run full test suite**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest -v`

Expected: All existing + new tests pass.

- [ ] **Step 2: Verify CLI help shows all new commands**

Run: `ab --help`

Expected: All 18 new commands appear in the help output: get, is, wait, find, back, forward, reload, press, select, check, uncheck, dblclick, drag, scroll-into-view, hover, count, upload, download.

- [ ] **Step 3: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: address test failures and final adjustments"
```
