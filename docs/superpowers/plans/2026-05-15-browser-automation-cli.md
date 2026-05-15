# Auto-Browser CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a client+daemon CLI tool that lets AI agents control a browser via accessibility tree snapshots and ref-based interactions.

**Architecture:** One session = one daemon process = one browser instance. Client sends JSON-RPC over Unix sockets. Browser launched via cloakbrowser (stealth Playwright). AX tree and interactions use Playwright CDP sessions.

**Tech Stack:** Python 3.13, cloakbrowser, Playwright sync API + CDP sessions, Unix sockets + JSON-RPC 2.0, argparse

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/auto_browser/__init__.py` | Package init, version |
| `src/auto_browser/__main__.py` | `python -m auto_browser` entry point |
| `src/auto_browser/cli.py` | CLI argument parsing (argparse), command dispatch |
| `src/auto_browser/daemon.py` | Daemon process — JSON-RPC server over Unix socket |
| `src/auto_browser/client.py` | Client — connects to daemon, sends JSON-RPC, formats output |
| `src/auto_browser/browser_manager.py` | Browser lifecycle (launch/close), page + CDP session management |
| `src/auto_browser/ax_tree.py` | AX tree snapshot pipeline — build, filter, assign refs, render |
| `src/auto_browser/ref_map.py` | RefEntry + RefMap + RoleNameTracker data structures |
| `src/auto_browser/interactions.py` | Element resolution + click/type/fill/hover/scroll via CDP |
| `tests/conftest.py` | Shared pytest fixtures |
| `tests/test_ref_map.py` | Ref Map unit tests |
| `tests/test_ax_tree.py` | AX Tree unit tests (fixture data) |
| `tests/test_interactions.py` | Interaction integration tests |
| `tests/test_daemon.py` | Daemon + Client integration tests |
| `tests/fixtures/ax_tree_response.json` | Sample CDP AX tree response for unit tests |

---

## Task 1: Project Scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `src/auto_browser/__init__.py`
- Create: `src/auto_browser/__main__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Update pyproject.toml with src layout, test deps, and entry point**

```toml
[project]
name = "auto-browser"
version = "0.1.0"
description = "Client+daemon browser automation CLI for AI agents"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "cloakbrowser>=0.3.28",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[project.scripts]
ab = "auto_browser.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/auto_browser"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create src/auto_browser/\_\_init\_\_.py**

```python
"""Auto-browser: client+daemon browser automation CLI for AI agents."""
```

- [ ] **Step 3: Create src/auto_browser/\_\_main\_\_.py**

```python
from auto_browser.cli import main

main()
```

- [ ] **Step 4: Create tests/conftest.py**

```python
import pytest
```

- [ ] **Step 5: Create tests/ directory, verify project structure**

```bash
mkdir -p src/auto_browser tests
```

- [ ] **Step 6: Verify package resolves**

```bash
uv sync
uv run python -c "import auto_browser; print('ok')"
```

Expected: `ok`

- [ ] **Step 7: Verify pytest runs**

```bash
uv run pytest --co
```

Expected: no errors, possibly "no tests collected"

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: project scaffolding with src layout, pytest, ab entry point"
```

---

## Task 2: Ref Map

**Files:**
- Create: `src/auto_browser/ref_map.py`
- Create: `tests/test_ref_map.py`

**RefMap** stores the mapping from ref IDs ("e1", "e2", ...) to element metadata. It is cleared and rebuilt on every snapshot. **RoleNameTracker** disambiguates elements with the same role+name.

- [ ] **Step 1: Write test for RefEntry and RefMap basics**

```python
# tests/test_ref_map.py
import pytest
from auto_browser.ref_map import RefEntry, RefMap, RoleNameTracker


class TestRefEntry:
    def test_create(self):
        entry = RefEntry(backend_node_id=42, role="button", name="Submit", nth=None, frame_id=None)
        assert entry.backend_node_id == 42
        assert entry.role == "button"
        assert entry.name == "Submit"

    def test_default_values(self):
        entry = RefEntry(backend_node_id=1, role="link", name="")
        assert entry.nth is None
        assert entry.frame_id is None


class TestRefMap:
    def test_add_and_get(self):
        rm = RefMap()
        rm.add("e1", backend_node_id=10, role="button", name="OK", nth=None, frame_id=None)
        entry = rm.get("e1")
        assert entry.backend_node_id == 10
        assert entry.role == "button"

    def test_get_missing_returns_none(self):
        rm = RefMap()
        assert rm.get("e999") is None

    def test_clear_resets(self):
        rm = RefMap()
        rm.add("e1", backend_node_id=1, role="link", name="Home", nth=None, frame_id=None)
        rm.clear()
        assert rm.get("e1") is None

    def test_next_ref_increments(self):
        rm = RefMap()
        assert rm.next_ref_num() == 1
        rm.set_next_ref_num(5)
        assert rm.next_ref_num() == 5

    def test_clear_resets_next_ref(self):
        rm = RefMap()
        rm.set_next_ref_num(10)
        rm.clear()
        assert rm.next_ref_num() == 1


class TestRoleNameTracker:
    def test_track_unique(self):
        t = RoleNameTracker()
        nth = t.track("button", "OK", 0)
        assert nth == 0

    def test_track_duplicate_increments(self):
        t = RoleNameTracker()
        t.track("link", "Home", 0)
        nth1 = t.track("link", "Home", 1)
        assert nth1 == 1
        nth2 = t.track("link", "Home", 2)
        assert nth2 == 2

    def test_different_roles_independent(self):
        t = RoleNameTracker()
        t.track("link", "Home", 0)
        nth = t.track("button", "Home", 1)
        assert nth == 0

    def test_get_duplicates_only_returns_repeated(self):
        t = RoleNameTracker()
        t.track("link", "Home", 0)
        t.track("link", "Home", 1)
        t.track("button", "OK", 2)
        dups = t.get_duplicates()
        assert ("link", "Home") in dups
        assert dups[("link", "Home")] == 2
        assert ("button", "OK") not in dups

    def test_get_actual_nth_none_when_unique(self):
        t = RoleNameTracker()
        t.track("button", "OK", 0)
        assert t.get_actual_nth("button", "OK") is None

    def test_get_actual_nth_value_when_duplicate(self):
        t = RoleNameTracker()
        t.track("link", "Home", 0)
        t.track("link", "Home", 1)
        assert t.get_actual_nth("link", "Home", occurrence=0) == 0
        assert t.get_actual_nth("link", "Home", occurrence=1) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ref_map.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'auto_browser.ref_map'`

- [ ] **Step 3: Implement ref_map.py**

```python
# src/auto_browser/ref_map.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RefEntry:
    backend_node_id: int
    role: str
    name: str
    nth: int | None = None
    frame_id: str | None = None


class RefMap:
    def __init__(self) -> None:
        self._entries: dict[str, RefEntry] = {}
        self._next_ref: int = 1

    def add(
        self,
        ref_id: str,
        backend_node_id: int,
        role: str,
        name: str,
        nth: int | None,
        frame_id: str | None,
    ) -> None:
        self._entries[ref_id] = RefEntry(
            backend_node_id=backend_node_id,
            role=role,
            name=name,
            nth=nth,
            frame_id=frame_id,
        )

    def get(self, ref_id: str) -> RefEntry | None:
        return self._entries.get(ref_id)

    def clear(self) -> None:
        self._entries.clear()
        self._next_ref = 1

    def next_ref_num(self) -> int:
        return self._next_ref

    def set_next_ref_num(self, num: int) -> None:
        self._next_ref = num


class RoleNameTracker:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], int] = {}

    def track(self, role: str, name: str, node_idx: int) -> int:
        key = (role, name)
        nth = self._counts.get(key, 0)
        self._counts[key] = nth + 1
        return nth

    def get_duplicates(self) -> dict[tuple[str, str], int]:
        return {k: v for k, v in self._counts.items() if v > 1}

    def get_actual_nth(self, role: str, name: str, occurrence: int | None = None) -> int | None:
        key = (role, name)
        count = self._counts.get(key, 0)
        if count <= 1:
            return None
        return occurrence
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ref_map.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_browser/ref_map.py tests/test_ref_map.py
git commit -m "feat: add RefMap and RoleNameTracker for ref-based element tracking"
```

---

## Task 3: Browser Manager

**Files:**
- Create: `src/auto_browser/browser_manager.py`
- Create: `tests/test_browser_manager.py`

BrowserManager wraps cloakbrowser, handles `launch()` vs `launch_persistent_context()`, manages the active page, and provides CDP session access.

- [ ] **Step 1: Write integration test for BrowserManager**

```python
# tests/test_browser_manager.py
import tempfile
from pathlib import Path

import pytest
from auto_browser.browser_manager import BrowserManager


class TestBrowserManagerDefault:
    def test_start_and_close(self):
        bm = BrowserManager(session_name="default", headed=True, user_data_dir=None)
        bm.start()
        assert bm.page is not None
        assert bm.is_alive()
        bm.close()

    def test_get_cdp_session(self):
        bm = BrowserManager(session_name="default", headed=True, user_data_dir=None)
        bm.start()
        cdp = bm.get_cdp_session()
        assert cdp is not None
        result = cdp.send("Runtime.evaluate", {"expression": "1 + 1"})
        assert result["result"]["value"] == 2
        bm.close()

    def test_navigate(self):
        bm = BrowserManager(session_name="default", headed=True, user_data_dir=None)
        bm.start()
        bm.navigate("data:text/html,<h1>Hello</h1>")
        assert "Hello" in bm.page.content()
        bm.close()


class TestBrowserManagerPersistent:
    def test_persistent_session(self, tmp_path):
        data_dir = tmp_path / "chrome-data"
        data_dir.mkdir()
        bm = BrowserManager(session_name="test-persist", headed=True, user_data_dir=str(data_dir))
        bm.start()
        assert bm.page is not None
        assert bm.is_alive()
        bm.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_browser_manager.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement browser_manager.py**

```python
# src/auto_browser/browser_manager.py
from __future__ import annotations

from playwright.sync_api import Browser, BrowserContext, CDPSession, Page


class BrowserManager:
    def __init__(self, session_name: str, headed: bool, user_data_dir: str | None) -> None:
        self.session_name = session_name
        self.headed = headed
        self.user_data_dir = user_data_dir
        self._page: Page | None = None
        self._context: BrowserContext | None = None
        self._browser: Browser | None = None
        self._close_fn = None

    def start(self) -> None:
        if self.user_data_dir:
            self._start_persistent()
        else:
            self._start_default()

    def _start_default(self) -> None:
        from cloakbrowser import launch

        self._browser = launch(headless=not self.headed)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._close_fn = self._browser.close

    def _start_persistent(self) -> None:
        from cloakbrowser import launch_persistent_context

        self._context = launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=not self.headed,
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._close_fn = self._context.close

    @property
    def page(self) -> Page:
        assert self._page is not None, "Browser not started"
        return self._page

    def get_cdp_session(self) -> CDPSession:
        assert self._context is not None, "Browser not started"
        return self._context.new_cdp_session(self._page)

    def is_alive(self) -> bool:
        return self._page is not None and self._context is not None

    def navigate(self, url: str, timeout: float = 30_000) -> None:
        self.page.goto(url, timeout=timeout)

    def close(self) -> None:
        if self._close_fn is not None:
            self._close_fn()
        self._page = None
        self._context = None
        self._browser = None
        self._close_fn = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_browser_manager.py -v
```

Expected: all PASS (tests launch real browser, takes ~10s)

- [ ] **Step 5: Commit**

```bash
git add src/auto_browser/browser_manager.py tests/test_browser_manager.py
git commit -m "feat: add BrowserManager wrapping cloakbrowser launch + CDP sessions"
```

---

## Task 4: AX Tree Core — Building and Filtering

**Files:**
- Create: `src/auto_browser/ax_tree.py`
- Create: `tests/test_ax_tree.py`
- Create: `tests/fixtures/ax_tree_response.json`

This task implements the tree building pipeline: parse raw CDP AX nodes, build parent-child relationships, apply filtering rules (ignored, InlineTextBox, merge StaticText, deduplicate, collapse generic, skip empty).

- [ ] **Step 1: Create AX tree fixture data**

Create `tests/fixtures/ax_tree_response.json` — a simplified CDP `Accessibility.getFullAXTree` response that exercises all filtering rules:

```json
{
  "nodes": [
    {"nodeId": "root", "role": {"type": "role", "value": "RootWebArea"}, "name": {"type": "plainText", "value": ""}, "childIds": ["nav", "main"], "backendDOMNodeId": 1, "ignored": true},
    {"nodeId": "nav", "role": {"type": "role", "value": "navigation"}, "name": {"type": "plainText", "value": ""}, "childIds": ["link1", "link2"], "backendDOMNodeId": 2, "ignored": false},
    {"nodeId": "link1", "role": {"type": "role", "value": "link"}, "name": {"type": "plainText", "value": "Home"}, "childIds": ["st1", "st2"], "backendDOMNodeId": 3, "ignored": false, "properties": []},
    {"nodeId": "st1", "role": {"type": "role", "value": "StaticText"}, "name": {"type": "plainText", "value": "Go to "}, "childIds": [], "backendDOMNodeId": 4, "ignored": false},
    {"nodeId": "st2", "role": {"type": "role", "value": "StaticText"}, "name": {"type": "plainText", "value": "our homepage"}, "childIds": [], "backendDOMNodeId": 5, "ignored": false},
    {"nodeId": "link2", "role": {"type": "role", "value": "link"}, "name": {"type": "plainText", "value": "About"}, "childIds": ["st3"], "backendDOMNodeId": 6, "ignored": false},
    {"nodeId": "st3", "role": {"type": "role", "value": "StaticText"}, "name": {"type": "plainText", "value": "About"}, "childIds": [], "backendDOMNodeId": 7, "ignored": false},
    {"nodeId": "main", "role": {"type": "role", "value": "main"}, "name": {"type": "plainText", "value": ""}, "childIds": ["h1", "div-wrap"], "backendDOMNodeId": 8, "ignored": false},
    {"nodeId": "h1", "role": {"type": "role", "value": "heading"}, "name": {"type": "plainText", "value": "Title"}, "childIds": ["st4"], "backendDOMNodeId": 9, "ignored": false, "properties": [{"name": "level", "value": {"type": "integer", "value": 1}}]},
    {"nodeId": "st4", "role": {"type": "role", "value": "StaticText"}, "name": {"type": "plainText", "value": "Title"}, "childIds": [], "backendDOMNodeId": 10, "ignored": false},
    {"nodeId": "div-wrap", "role": {"type": "role", "value": "generic"}, "name": {"type": "plainText", "value": ""}, "childIds": ["div-inner"], "backendDOMNodeId": 11, "ignored": false},
    {"nodeId": "div-inner", "role": {"type": "role", "value": "generic"}, "name": {"type": "plainText", "value": ""}, "childIds": ["btn1"], "backendDOMNodeId": 12, "ignored": false},
    {"nodeId": "btn1", "role": {"type": "role", "value": "button"}, "name": {"type": "plainText", "value": "Submit"}, "childIds": ["st5"], "backendDOMNodeId": 13, "ignored": false},
    {"nodeId": "st5", "role": {"type": "role", "value": "StaticText"}, "name": {"type": "plainText", "value": "Submit"}, "childIds": [], "backendDOMNodeId": 14, "ignored": false},
    {"nodeId": "itb", "role": {"type": "role", "value": "InlineTextBox"}, "name": {"type": "plainText", "value": "hidden"}, "childIds": [], "backendDOMNodeId": 15, "ignored": false},
    {"nodeId": "st-empty", "role": {"type": "role", "value": "StaticText"}, "name": {"type": "plainText", "value": "\u00a0"}, "childIds": [], "backendDOMNodeId": 16, "ignored": false}
  ]
}
```

This fixture tests:
- Rule 1: RootWebArea ignored=true kept as entry
- Rule 2: InlineTextBox skipped
- Rule 3: Consecutive StaticText merged ("Go to " + "our homepage")
- Rule 4: Redundant StaticText deduplicated ("About" under link "About", "Submit" under button "Submit", "Title" under heading "Title")
- Rule 5: Generic single-child collapsed (div-wrap > div-inner > button)
- Rule 6: Empty StaticText skipped (non-breaking space)

- [ ] **Step 2: Write unit tests for tree building**

```python
# tests/test_ax_tree.py
import json
from pathlib import Path

import pytest
from auto_browser.ax_tree import build_tree, TreeNode
from auto_browser.ref_map import RefMap


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ax_tree_response.json"


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)["nodes"]


class TestBuildTree:
    def test_builds_tree_from_fixture(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        assert len(root_indices) > 0

    def test_inline_text_box_filtered(self):
        raw_nodes = load_fixture()
        nodes, _ = build_tree(raw_nodes)
        roles = [n.role for n in nodes]
        assert "InlineTextBox" not in roles

    def test_consecutive_static_text_merged(self):
        raw_nodes = load_fixture()
        nodes, _ = build_tree(raw_nodes)
        link1 = next(n for n in nodes if n.role == "link" and n.name == "Home")
        children = [nodes[i] for i in link1.children]
        static_texts = [c for c in children if c.role == "StaticText"]
        assert len(static_texts) == 1
        assert "Go to" in static_texts[0].name and "homepage" in static_texts[0].name

    def test_redundant_static_text_deduplicated(self):
        raw_nodes = load_fixture()
        nodes, _ = build_tree(raw_nodes)
        # link "About" has child StaticText "About" — should be cleared
        link2 = next(n for n in nodes if n.role == "link" and n.name == "About")
        children = [nodes[i] for i in link2.children]
        static_texts = [c for c in children if c.role == "StaticText" and c.name]
        assert len(static_texts) == 0

    def test_generic_single_child_collapsed(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        # After collapse, button "Submit" should be reachable without generic wrappers
        button_names = [n.name for n in nodes if n.role == "button"]
        assert "Submit" in button_names

    def test_empty_static_text_skipped(self):
        raw_nodes = load_fixture()
        nodes, _ = build_tree(raw_nodes)
        empty_statics = [n for n in nodes if n.role == "StaticText" and n.name.strip() == ""]
        assert len(empty_statics) == 0

    def test_tree_has_navigation(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        from_root = nodes[root_indices[0]]
        child_roles = [nodes[i].role for i in from_root.children]
        assert "navigation" in child_roles

    def test_depth_calculated(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        root = nodes[root_indices[0]]
        assert root.depth == 0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_ax_tree.py::TestBuildTree -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement ax_tree.py — TreeNode and build_tree**

```python
# src/auto_browser/ax_tree.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

INVISIBLE_CHARS = frozenset("\ufeff\u200b\u200c\u200d\u2060\u00a0")

INTERACTIVE_ROLES = frozenset({
    "button", "link", "textbox", "checkbox", "radio", "combobox",
    "listbox", "menuitem", "menuitemcheckbox", "menuitemradio",
    "option", "searchbox", "slider", "spinbutton", "switch",
    "tab", "treeitem", "Iframe",
})

CONTENT_ROLES = frozenset({
    "heading", "cell", "gridcell", "columnheader", "rowheader",
    "listitem", "article", "region", "main", "navigation",
})


@dataclass
class TreeNode:
    role: str
    name: str
    level: int | None = None
    checked: str | None = None
    expanded: bool | None = None
    selected: bool | None = None
    disabled: bool | None = None
    required: bool | None = None
    value_text: str | None = None
    backend_node_id: int | None = None
    children: list[int] = field(default_factory=list)
    parent_idx: int | None = None
    depth: int = 0
    has_ref: bool = False
    ref_id: str | None = None


def _ax_value(v: dict | None) -> str:
    if v is None:
        return ""
    return v.get("value", "") or ""


def _ax_prop(props: list[dict] | None, name: str) -> Any:
    if not props:
        return None
    for p in props:
        if p.get("name") == name:
            return p.get("value", {}).get("value")
    return None


def _is_invisible(text: str) -> bool:
    return all(c in INVISIBLE_CHARS for c in text)


def build_tree(raw_nodes: list[dict]) -> tuple[list[TreeNode], list[int]]:
    # Parse raw nodes, index by nodeId
    parsed: dict[str, int] = {}
    nodes: list[TreeNode] = []

    for raw in raw_nodes:
        role = _ax_value(raw.get("role"))
        ignored = raw.get("ignored", False)
        # Rule 1: skip ignored except RootWebArea
        if ignored and role != "RootWebArea":
            continue
        # Rule 2: skip InlineTextBox
        if role == "InlineTextBox":
            continue

        name = _ax_value(raw.get("name"))
        value = _ax_value(raw.get("value"))
        props = raw.get("properties")
        bid = raw.get("backendDOMNodeId")

        node = TreeNode(
            role=role,
            name=name,
            level=_ax_prop(props, "level"),
            checked=_ax_prop(props, "checked"),
            expanded=_ax_prop(props, "expanded"),
            selected=_ax_prop(props, "selected"),
            disabled=_ax_prop(props, "disabled"),
            required=_ax_prop(props, "required"),
            value_text=value if value else None,
            backend_node_id=bid,
        )
        parsed[raw["nodeId"]] = len(nodes)
        nodes.append(node)

    # Build parent-child using childIds
    child_id_to_idx: dict[str, int] = {}
    for node_id, idx in parsed.items():
        child_id_to_idx[node_id] = idx

    root_indices: list[int] = []
    for raw in raw_nodes:
        node_id = raw["nodeId"]
        if node_id not in parsed:
            continue
        idx = parsed[node_id]
        child_ids = raw.get("childIds", [])
        valid_children: list[int] = []
        for cid in child_ids:
            if cid in parsed:
                cidx = parsed[cid]
                valid_children.append(cidx)
                nodes[cidx].parent_idx = idx

        nodes[idx].children = valid_children
        if nodes[idx].parent_idx is None and nodes[idx].role == "RootWebArea":
            root_indices.append(idx)

    # Rule 3: merge consecutive StaticText
    for node in nodes:
        if not node.children:
            continue
        merged: list[int] = []
        i = 0
        while i < len(node.children):
            cidx = node.children[i]
            child = nodes[cidx]
            if child.role == "StaticText" and i + 1 < len(node.children):
                texts = [child.name]
                j = i + 1
                while j < len(node.children) and nodes[node.children[j]].role == "StaticText":
                    texts.append(nodes[node.children[j]].name)
                    j += 1
                if len(texts) > 1:
                    child.name = " ".join(texts)
                    merged.append(cidx)
                    i = j
                    continue
            merged.append(cidx)
            i += 1
        node.children = merged

    # Rule 4: deduplicate redundant StaticText
    for node in nodes:
        static_children = [i for i in node.children if nodes[i].role == "StaticText"]
        if len(static_children) == 1 and len(node.children) == 1:
            if nodes[static_children[0]].name == node.name:
                node.children = []

    # Rule 6: skip empty StaticText
    for node in nodes:
        node.children = [
            i for i in node.children
            if not (nodes[i].role == "StaticText" and _is_invisible(nodes[i].name))
        ]

    # Rule 5: collapse generic with <=1 children and no ref
    # (deferred — applied during rendering to avoid index invalidation)

    # Calculate depth
    def calc_depth(idx: int, depth: int) -> None:
        nodes[idx].depth = depth
        for cidx in nodes[idx].children:
            calc_depth(cidx, depth + 1)

    for ri in root_indices:
        calc_depth(ri, 0)

    return nodes, root_indices
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_ax_tree.py::TestBuildTree -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/auto_browser/ax_tree.py tests/test_ax_tree.py tests/fixtures/
git commit -m "feat: add AX tree building with filtering and merging rules"
```

---

## Task 5: AX Tree Rendering + Snapshot Pipeline

**Files:**
- Modify: `src/auto_browser/ax_tree.py`
- Modify: `tests/test_ax_tree.py`

Adds ref assignment, tree rendering (indented text), compact mode, and the full `take_snapshot()` function that ties everything together.

- [ ] **Step 1: Write tests for ref assignment and rendering**

Add to `tests/test_ax_tree.py`:

```python
from auto_browser.ref_map import RefMap, RoleNameTracker
from auto_browser.ax_tree import (
    assign_refs, render_tree, compact_tree, take_snapshot,
)


class TestAssignRefs:
    def test_interactive_roles_get_refs(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        button = next(n for n in nodes if n.role == "button")
        assert button.has_ref
        assert button.ref_id is not None
        assert ref_map.get(button.ref_id) is not None

    def test_content_roles_with_name_get_refs(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        heading = next(n for n in nodes if n.role == "heading")
        assert heading.has_ref

    def test_structural_roles_no_ref(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        for n in nodes:
            if n.role == "generic":
                assert not n.has_ref

    def test_ref_map_entries_have_backend_node_id(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        for n in nodes:
            if n.has_ref:
                entry = ref_map.get(n.ref_id)
                assert entry is not None
                assert entry.backend_node_id is not None


class TestRenderTree:
    def test_renders_indented_tree(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        output = render_tree(nodes, root_indices, ref_map)
        assert "link" in output
        assert "button" in output
        assert "Submit" in output

    def test_renders_ref_ids(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        output = render_tree(nodes, root_indices, ref_map)
        assert "ref=" in output

    def test_compact_mode(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        full = render_tree(nodes, root_indices, ref_map)
        compacted = compact_tree(full)
        # Compact should have fewer lines
        assert len(compacted.splitlines()) <= len(full.splitlines())
        # Compact should still contain refs
        assert "ref=" in compacted
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ax_tree.py::TestAssignRefs tests/test_ax_tree.py::TestRenderTree -v
```

Expected: FAIL — `ImportError: cannot import name 'assign_refs'`

- [ ] **Step 3: Implement assign_refs, render_tree, compact_tree, take_snapshot**

Add to `src/auto_browser/ax_tree.py`:

```python
from auto_browser.ref_map import RefMap, RoleNameTracker


def assign_refs(nodes: list[TreeNode], ref_map: RefMap) -> None:
    ref_map.clear()
    next_ref = ref_map.next_ref_num()
    tracker = RoleNameTracker()

    for idx, node in enumerate(nodes):
        should_ref = False
        if node.role in INTERACTIVE_ROLES:
            should_ref = True
        elif node.role in CONTENT_ROLES and node.name:
            should_ref = True

        if should_ref:
            nth_raw = tracker.track(node.role, node.name, idx)
            ref_id = f"e{next_ref}"
            next_ref += 1
            nth = tracker.get_actual_nth(node.role, node.name, nth_raw)
            ref_map.add(ref_id, node.backend_node_id, node.role, node.name, nth, None)
            node.has_ref = True
            node.ref_id = ref_id

    ref_map.set_next_ref_num(next_ref)


def _should_skip_render(node: TreeNode, nodes: list[TreeNode]) -> bool:
    """Rule 5: collapse generic with <=1 children and no ref."""
    if node.role == "generic" and not node.has_ref:
        if len(node.children) <= 1:
            return True
    return False


def _render_node(node: TreeNode, ref_map: RefMap) -> str:
    parts = []
    role = node.role
    if node.name:
        parts.append(f'{role} "{node.name}"')
    else:
        parts.append(role)

    attrs: list[str] = []
    if node.level is not None:
        attrs.append(f"level={node.level}")
    if node.checked is not None:
        attrs.append(f"checked={node.checked}")
    if node.expanded is not None:
        attrs.append(f"expanded={'true' if node.expanded else 'false'}")
    if node.selected:
        attrs.append("selected")
    if node.disabled:
        attrs.append("disabled")
    if node.required:
        attrs.append("required")
    if node.ref_id:
        entry = ref_map.get(node.ref_id)
        if entry and entry.nth is not None:
            attrs.append(f"nth={entry.nth}")
        attrs.append(f"ref={node.ref_id}")

    if attrs:
        parts.append("[" + ", ".join(attrs) + "]")

    line = " ".join(parts)
    if node.value_text:
        line += f": {node.value_text}"
    return line


def render_tree(nodes: list[TreeNode], root_indices: list[int], ref_map: RefMap) -> str:
    lines: list[str] = []

    def _render(idx: int, depth: int) -> None:
        node = nodes[idx]
        if _should_skip_render(node, nodes):
            for cidx in node.children:
                _render(cidx, depth)
            return
        # Rule 7: strip RootWebArea / WebArea
        if node.role in ("RootWebArea", "WebArea"):
            for cidx in node.children:
                _render(cidx, depth)
            return

        indent = "  " * depth
        lines.append(f"{indent}- {_render_node(node, ref_map)}")
        for cidx in node.children:
            _render(cidx, depth + 1)

    for ri in root_indices:
        _render(ri, 0)

    return "\n".join(lines)


def compact_tree(output: str) -> str:
    """Keep only lines with ref= or ': ' and their ancestor lines."""
    lines = output.splitlines()
    result_indices: set[int] = set()

    for i, line in enumerate(lines):
        if "ref=" in line or ": " in line.split("- ", 1)[-1] if "- " in line else False:
            result_indices.add(i)
            # Add all ancestors (lines with less indentation above)
            current_indent = len(line) - len(line.lstrip())
            for j in range(i - 1, -1, -1):
                jline = lines[j]
                j_indent = len(jline) - len(jline.lstrip())
                if j_indent < current_indent:
                    result_indices.add(j)
                    current_indent = j_indent

    return "\n".join(lines[i] for i in sorted(result_indices))


def take_snapshot(cdp, ref_map: RefMap, compact: bool = False, selector: str | None = None) -> str:
    """Full AX tree snapshot pipeline using a Playwright CDP session."""
    cdp.send("DOM.enable")
    cdp.send("Accessibility.enable")

    result = cdp.send("Accessibility.getFullAXTree")
    raw_nodes = result.get("nodes", [])

    nodes, root_indices = build_tree(raw_nodes)
    ref_map.clear()
    assign_refs(nodes, ref_map)

    output = render_tree(nodes, root_indices, ref_map)

    if compact:
        output = compact_tree(output)

    return output
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ax_tree.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_browser/ax_tree.py tests/test_ax_tree.py
git commit -m "feat: add AX tree ref assignment, rendering, compact mode, and snapshot pipeline"
```

---

## Task 6: Interactions

**Files:**
- Create: `src/auto_browser/interactions.py`
- Create: `tests/test_interactions.py`

Element resolution (3-level fallback) and interaction operations (click, type, fill, hover, scroll) via CDP.

- [ ] **Step 1: Write integration tests for interactions**

```python
# tests/test_interactions.py
import pytest
from auto_browser.browser_manager import BrowserManager
from auto_browser.interactions import Interactions
from auto_browser.ref_map import RefMap
from auto_browser.ax_tree import take_snapshot


@pytest.fixture
def browser_env():
    bm = BrowserManager(session_name="default", headed=True, user_data_dir=None)
    bm.start()
    bm.page.set_content("""
    <html><body>
        <input id="search" type="text" placeholder="Search">
        <button id="btn" onclick="document.title='clicked'">Click Me</button>
        <a id="link" href="#target">Link</a>
    </body></html>
    """)
    cdp = bm.get_cdp_session()
    ref_map = RefMap()
    ia = Interactions(cdp, ref_map, bm.page)
    yield bm, cdp, ref_map, ia
    bm.close()


class TestClick:
    def test_click_by_ref(self, browser_env):
        bm, cdp, ref_map, ia = browser_env
        take_snapshot(cdp, ref_map)
        btn_entry = None
        for n in ref_map._entries.values():
            if n.role == "button":
                btn_entry = n
                break
        assert btn_entry is not None
        # Find the ref_id for this entry
        ref_id = next(k for k, v in ref_map._entries.items() if v is btn_entry)
        ia.click(ref_id)
        assert bm.page.title() == "clicked"


class TestType:
    def test_type_by_ref(self, browser_env):
        bm, cdp, ref_map, ia = browser_env
        take_snapshot(cdp, ref_map)
        ref_id = next(k for k, v in ref_map._entries.items() if v.role == "textbox")
        ia.type(ref_id, "hello world")
        assert bm.page.locator("#search").input_value() == "hello world"


class TestFill:
    def test_fill_by_ref(self, browser_env):
        bm, cdp, ref_map, ia = browser_env
        take_snapshot(cdp, ref_map)
        ref_id = next(k for k, v in ref_map._entries.items() if v.role == "textbox")
        ia.fill(ref_id, "filled")
        assert bm.page.locator("#search").input_value() == "filled"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_interactions.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement interactions.py**

```python
# src/auto_browser/interactions.py
from __future__ import annotations

import re
import math
from typing import Any

from playwright.sync_api import CDPSession, Page

from auto_browser.ref_map import RefMap


def parse_ref(text: str) -> str | None:
    m = re.fullmatch(r"(?:@|ref=)?e(\d+)", text.strip())
    if m:
        return f"e{m.group(1)}"
    return None


def _box_center(quad: list[float]) -> tuple[float, float]:
    x = sum(quad[0::2]) / 4
    y = sum(quad[1::2]) / 4
    return x, y


class Interactions:
    def __init__(self, cdp: CDPSession, ref_map: RefMap, page: Page) -> None:
        self.cdp = cdp
        self.ref_map = ref_map
        self.page = page

    def _resolve_center(self, ref_or_selector: str) -> tuple[float, float]:
        ref_id = parse_ref(ref_or_selector)
        if ref_id:
            entry = self.ref_map.get(ref_id)
            if entry and entry.backend_node_id:
                try:
                    box = self.cdp.send("DOM.getBoxModel", {"backendNodeId": entry.backend_node_id})
                    quad = box["model"]["content"]
                    return _box_center(quad)
                except Exception:
                    pass  # stale, fall through to Level 2
            # Level 2: re-query AX tree
            if entry:
                fresh_id = self._find_node_by_role_name(entry.role, entry.name, entry.nth)
                if fresh_id:
                    box = self.cdp.send("DOM.getBoxModel", {"backendNodeId": fresh_id})
                    return _box_center(box["model"]["content"])
            raise ValueError(f"Could not locate element: {ref_or_selector}")
        else:
            # Level 3: CSS selector
            result = self.page.evaluate(f"""
                () => {{
                    const el = document.querySelector({ref_or_selector!r});
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
                }}
            """)
            if not result:
                raise ValueError(f"Element not found: {ref_or_selector}")
            return result["x"], result["y"]

    def _resolve_object_id(self, ref_or_selector: str) -> str:
        ref_id = parse_ref(ref_or_selector)
        if ref_id:
            entry = self.ref_map.get(ref_id)
            if entry and entry.backend_node_id:
                resolved = self.cdp.send("DOM.resolveNode", {"backendNodeId": entry.backend_node_id})
                return resolved["object"]["objectId"]
        raise ValueError(f"Could not resolve element object: {ref_or_selector}")

    def _find_node_by_role_name(self, role: str, name: str, nth: int | None) -> int | None:
        result = self.cdp.send("Accessibility.getFullAXTree")
        count = 0
        for node in result.get("nodes", []):
            n_role = (node.get("role") or {}).get("value", "")
            n_name = (node.get("name") or {}).get("value", "")
            if n_role == role and n_name == name:
                if nth is None or count == nth:
                    return node.get("backendDOMNodeId")
                count += 1
        return None

    def click(self, ref_or_selector: str, button: str = "left", double: bool = False) -> dict:
        x, y = self._resolve_center(ref_or_selector)
        click_count = 2 if double else 1
        self.cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": button, "buttons": 1, "clickCount": click_count,
        })
        self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": button, "buttons": 0, "clickCount": click_count,
        })
        return {"status": "ok", "action": "click", "x": x, "y": y}

    def type(self, ref_or_selector: str, text: str, clear: bool = False) -> dict:
        obj_id = self._resolve_object_id(ref_or_selector)
        self.cdp.send("Runtime.callFunctionOn", {
            "functionDeclaration": "function() { this.focus(); }",
            "objectId": obj_id,
        })
        if clear:
            self.cdp.send("Runtime.callFunctionOn", {
                "functionDeclaration": "function() { this.select(); this.value = ''; }",
                "objectId": obj_id,
            })
        for char in text:
            if char == "\n":
                self.cdp.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter"})
                self.cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter"})
            else:
                self.cdp.send("Input.insertText", {"text": char})
        return {"status": "ok", "action": "type", "text": text}

    def fill(self, ref_or_selector: str, value: str) -> dict:
        obj_id = self._resolve_object_id(ref_or_selector)
        self.cdp.send("Runtime.callFunctionOn", {
            "functionDeclaration": "function() { this.focus(); this.select(); this.value = ''; }",
            "objectId": obj_id,
        })
        self.cdp.send("Input.insertText", {"text": value})
        return {"status": "ok", "action": "fill", "value": value}

    def hover(self, ref_or_selector: str) -> dict:
        x, y = self._resolve_center(ref_or_selector)
        self.cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        return {"status": "ok", "action": "hover", "x": x, "y": y}

    def scroll(self, direction: str, amount: int = 300) -> dict:
        delta_y = -amount if direction == "up" else amount
        self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": 0, "y": 0,
            "deltaX": 0, "deltaY": delta_y,
        })
        return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount}

    def eval_js(self, expression: str) -> dict:
        result = self.cdp.send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if "exceptionDetails" in result:
            raise RuntimeError(f"JS error: {result['exceptionDetails']}")
        return {"status": "ok", "result": result.get("result", {})}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_interactions.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/auto_browser/interactions.py tests/test_interactions.py
git commit -m "feat: add interactions — click, type, fill, hover, scroll, eval via CDP"
```

---

## Task 7: Daemon + Client + CLI

**Files:**
- Create: `src/auto_browser/daemon.py`
- Create: `src/auto_browser/client.py`
- Create: `src/auto_browser/cli.py`
- Create: `tests/test_daemon.py`

This task ties everything together: JSON-RPC daemon server, client, session management, and CLI argument parsing.

### Part A: Daemon

- [ ] **Step 1: Write daemon integration test**

```python
# tests/test_daemon.py
import json
import os
import subprocess
import sys
import time

import pytest


class TestDaemonClientIntegration:
    def test_ping(self, tmp_path):
        socket_path = str(tmp_path / "test.sock")
        daemon_info = str(tmp_path / "daemon.json")

        # Start daemon as subprocess
        proc = subprocess.Popen(
            [sys.executable, "-m", "auto_browser", "_daemon", "--socket", socket_path, "--headed"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        # Wait for socket to appear
        for _ in range(50):
            if os.path.exists(socket_path):
                break
            time.sleep(0.1)
        else:
            proc.kill()
            raise RuntimeError("Daemon did not start")

        try:
            from auto_browser.client import Client
            client = Client(socket_path)
            result = client.call("ping")
            assert result["status"] == "ok"
        finally:
            proc.terminate()
            proc.wait(timeout=5)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_daemon.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement daemon.py**

```python
# src/auto_browser/daemon.py
from __future__ import annotations

import json
import os
import socket
import sys
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
        cdp = self.bm.get_cdp_session()
        return Interactions(cdp, self.ref_map, self.bm.page)

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
        cdp = self.bm.get_cdp_session()
        compact = params.get("compact", False)
        selector = params.get("selector")
        content = take_snapshot(cdp, self.ref_map, compact=compact, selector=selector)
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

### Part B: Client

- [ ] **Step 4: Implement client.py**

```python
# src/auto_browser/client.py
from __future__ import annotations

import json
import socket


class Client:
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        self._id = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or {},
        }
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        try:
            sock.sendall(json.dumps(request).encode() + b"\n")
            data = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
        finally:
            sock.close()

        response = json.loads(data.strip())
        if "error" in response:
            raise RuntimeError(f"Daemon error [{response['error']['code']}]: {response['error']['message']}")
        return response["result"]
```

### Part C: CLI + Session Management

- [ ] **Step 5: Implement cli.py**

```python
# src/auto_browser/cli.py
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from auto_browser.client import Client

BASE_DIR = Path.home() / ".ab"


def _session_dir(session: str) -> Path:
    return BASE_DIR / session


def _daemon_info_path(session: str) -> Path:
    return _session_dir(session) / "daemon.json"


def _read_daemon_info(session: str) -> dict | None:
    path = _daemon_info_path(session)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _is_daemon_running(session: str) -> bool:
    info = _read_daemon_info(session)
    if not info:
        return False
    try:
        os.kill(info["pid"], 0)
        return True
    except (ProcessLookupError, KeyError):
        return False


def _wait_for_socket(socket_path: str, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(socket_path):
            return True
        time.sleep(0.1)
    return False


def _ensure_session_dir(session: str, user_data_dir: str | None) -> tuple[str, str | None]:
    sdir = _session_dir(session)
    sdir.mkdir(parents=True, exist_ok=True)
    if user_data_dir:
        udd = sdir / "chrome-data"
        udd.mkdir(exist_ok=True)
        return str(sdir), str(udd)
    return str(sdir), None


def cmd_open(args: argparse.Namespace) -> None:
    session = args.session or "default"
    url = args.url
    headed = args.headed
    user_data_dir = args.session is not None  # persistent only for named sessions

    session_dir, udd = _ensure_session_dir(session, user_data_dir)
    socket_path = f"/tmp/ab-{session}.sock"

    if _is_daemon_running(session):
        # Reuse existing daemon, just navigate
        info = _read_daemon_info(session)
        client = Client(info["socket"])
        result = client.call("goto", {"url": url})
        _output(result)
        return

    # Write daemon info placeholder
    daemon_info = {
        "pid": os.getpid(),
        "socket": socket_path,
        "session": session,
        "headed": headed,
        "user_data_dir": udd,
    }

    # Fork daemon process
    proc = subprocess.Popen(
        [sys.executable, "-m", "auto_browser", "_daemon",
         "--socket", socket_path,
         "--session", session,
         "--session-dir", session_dir,
         *(["--headed"] if headed else []),
         *(["--user-data-dir", udd] if udd else []),
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    daemon_info["pid"] = proc.pid
    with open(_daemon_info_path(session), "w") as f:
        json.dump(daemon_info, f)

    # Wait for daemon to be ready
    if not _wait_for_socket(socket_path):
        print(json.dumps({"status": "error", "error": {"message": "Daemon failed to start"}}))
        sys.exit(1)

    # Send goto
    client = Client(socket_path)
    result = client.call("goto", {"url": url})
    _output(result)


def cmd_close(args: argparse.Namespace) -> None:
    session = args.session or "default"
    if not _is_daemon_running(session):
        _output({"status": "ok", "message": "Daemon not running"})
        return
    info = _read_daemon_info(session)
    client = Client(info["socket"])
    result = client.call("shutdown")
    _output(result)


def cmd_action(args: argparse.Namespace) -> None:
    session = args.session or "default"
    if not _is_daemon_running(session):
        print(json.dumps({"status": "error", "error": {"code": -32000, "message": "Daemon not running. Use 'ab open' first."}}))
        sys.exit(1)
    info = _read_daemon_info(session)
    client = Client(info["socket"])
    params = {}
    if hasattr(args, "ref") and args.ref:
        params["ref"] = args.ref
    if hasattr(args, "text") and args.text:
        params["text"] = args.text
    if hasattr(args, "value") and args.value:
        params["value"] = args.value
    if hasattr(args, "compact") and args.compact:
        params["compact"] = True
    if hasattr(args, "selector") and args.selector:
        params["selector"] = args.selector
    if hasattr(args, "direction") and args.direction:
        params["direction"] = args.direction
    if hasattr(args, "amount") and args.amount:
        params["amount"] = args.amount
    if hasattr(args, "expression") and args.expression:
        params["expression"] = args.expression
    if hasattr(args, "output") and args.output:
        params["path"] = args.output
    if hasattr(args, "double") and args.double:
        params["double"] = True
    if hasattr(args, "clear") and args.clear:
        params["clear"] = True

    result = client.call(args.action, params)
    _output(result)


def _output(result: dict) -> None:
    print(json.dumps({"status": "ok", "data": result}))
    if "content" in result:
        print(result["content"], file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ab", description="Auto-browser CLI")
    parser.add_argument("--session", "-s", help="Session name")

    sub = parser.add_subparsers(dest="command")

    # open
    p_open = sub.add_parser("open")
    p_open.add_argument("url")
    p_open.add_argument("--headed", action="store_true")

    # close
    sub.add_parser("close")

    # snapshot
    p_snap = sub.add_parser("snapshot")
    p_snap.add_argument("--compact", action="store_true")
    p_snap.add_argument("--selector")

    # click
    p_click = sub.add_parser("click")
    p_click.add_argument("ref")
    p_click.add_argument("--double", action="store_true")

    # type
    p_type = sub.add_parser("type")
    p_type.add_argument("ref")
    p_type.add_argument("text")
    p_type.add_argument("--clear", action="store_true")

    # fill
    p_fill = sub.add_parser("fill")
    p_fill.add_argument("ref")
    p_fill.add_argument("value")

    # scroll
    p_scroll = sub.add_parser("scroll")
    p_scroll.add_argument("direction", choices=["up", "down"])
    p_scroll.add_argument("--amount", type=int, default=300)

    # screenshot
    p_ss = sub.add_parser("screenshot")
    p_ss.add_argument("--output")

    # eval
    p_eval = sub.add_parser("eval")
    p_eval.add_argument("expression")

    # ping
    sub.add_parser("ping")

    # Internal: daemon mode
    p_daemon = sub.add_parser("_daemon")
    p_daemon.add_argument("--socket", required=True)
    p_daemon.add_argument("--headed", action="store_true")
    p_daemon.add_argument("--user-data-dir")
    p_daemon.add_argument("--session", default="default")
    p_daemon.add_argument("--session-dir")

    args = parser.parse_args()

    if args.command == "_daemon":
        from auto_browser.daemon import run_daemon
        run_daemon(
            socket_path=args.socket,
            headed=args.headed,
            user_data_dir=args.user_data_dir,
            session_name=args.session,
        )
    elif args.command == "open":
        cmd_open(args)
    elif args.command == "close":
        cmd_close(args)
    elif args.command in ("snapshot", "click", "type", "fill", "scroll", "screenshot", "eval", "ping"):
        args.action = args.command
        cmd_action(args)
    else:
        parser.print_help()
```

- [ ] **Step 6: Run daemon integration test**

```bash
uv run pytest tests/test_daemon.py -v
```

Expected: PASS

- [ ] **Step 7: Update \_\_main\_\_.py to support daemon mode**

The `__main__.py` already calls `cli.main()`, which handles the `_daemon` subcommand. No change needed.

- [ ] **Step 8: Verify end-to-end**

```bash
uv run ab open "data:text/html,<h1>Test</h1><button>OK</button>" --headed --session test-e2e
uv run ab snapshot --session test-e2e
uv run ab close --session test-e2e
```

Expected: snapshot shows AX tree with heading and button refs.

- [ ] **Step 9: Commit**

```bash
git add src/auto_browser/daemon.py src/auto_browser/client.py src/auto_browser/cli.py tests/test_daemon.py
git commit -m "feat: add daemon, client, CLI with session management and JSON-RPC protocol"
```
