# Snapshot Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce snapshot output size by 40-60% through structural filtering of Playwright's accessibility tree YAML output.

**Architecture:** Parse Playwright's `aria_snapshot(mode="ai")` YAML into a `TreeNode` tree, apply 6 filtering rules inspired by agent-browser's `render_tree()`, then re-render to YAML. New module `snapshot_tree.py` handles parsing/filtering/rendering; existing `ax_tree.py` delegates to it.

**Tech Stack:** Python 3.10+, Playwright (sync API), pytest

---

### Task 1: Create `snapshot_tree.py` — TreeNode dataclass and YAML parser

**Files:**
- Create: `src/ai_browser/snapshot_tree.py`
- Create: `tests/test_snapshot_tree.py`

- [ ] **Step 1: Write failing tests for TreeNode and parse_yaml_tree**

```python
# tests/test_snapshot_tree.py
import pytest
from ai_browser.snapshot_tree import TreeNode, parse_yaml_tree


SIMPLE_YAML = """\
- RootWebArea "Test Page" [ref=e1]
  - heading "Welcome" [level=1, ref=e2]
  - button "Submit" [ref=e3]
"""

GENERIC_YAML = """\
- RootWebArea [ref=e1]
  - generic
    - generic
      - button "Click" [ref=e2]
  - generic
    - StaticText "Hello"
    - StaticText " World"
"""

EMPTY_YAML = ""


class TestTreeNode:
    def test_create(self):
        node = TreeNode(role="button", name="OK", ref="e1", attrs={}, children=[], indent=0)
        assert node.role == "button"
        assert node.name == "OK"
        assert node.ref == "e1"

    def test_defaults(self):
        node = TreeNode(role="generic", name="", ref=None, attrs={}, children=[], indent=2)
        assert node.ref is None
        assert node.children == []


class TestParseYamlTree:
    def test_simple_tree(self):
        roots = parse_yaml_tree(SIMPLE_YAML)
        assert len(roots) == 1
        root = roots[0]
        assert root.role == "RootWebArea"
        assert root.name == "Test Page"
        assert root.ref == "e1"
        assert len(root.children) == 2
        assert root.children[0].role == "heading"
        assert root.children[0].ref == "e2"
        assert root.children[0].attrs.get("level") == "1"
        assert root.children[1].role == "button"
        assert root.children[1].ref == "e3"

    def test_generic_nodes(self):
        roots = parse_yaml_tree(GENERIC_YAML)
        assert len(roots) == 1
        root = roots[0]
        assert root.role == "RootWebArea"
        assert len(root.children) == 2
        first_generic = root.children[0]
        assert first_generic.role == "generic"
        assert first_generic.ref is None
        assert len(first_generic.children) == 1
        nested = first_generic.children[0]
        assert nested.role == "generic"
        assert nested.children[0].role == "button"

    def test_empty_input(self):
        roots = parse_yaml_tree(EMPTY_YAML)
        assert roots == []

    def test_parent_child_indent(self):
        roots = parse_yaml_tree(SIMPLE_YAML)
        root = roots[0]
        for child in root.children:
            assert child.indent == 1

    def test_attrs_parsed(self):
        roots = parse_yaml_tree(SIMPLE_YAML)
        heading = roots[0].children[0]
        assert heading.attrs.get("level") == "1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/test_snapshot_tree.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_browser.snapshot_tree'`

- [ ] **Step 3: Implement TreeNode and parse_yaml_tree**

```python
# src/ai_browser/snapshot_tree.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class TreeNode:
    role: str
    name: str
    ref: str | None
    attrs: dict
    children: list[TreeNode]
    indent: int


# Matches: - role "name" [key=val, ref=eN]
# or: - role [ref=eN]
# or: - role "name"
# or: - role
_LINE_RE = re.compile(
    r'^(\s*)-\s+'          # indent + list prefix (group 1)
    r'(\w+)'               # role (group 2)
    r'(?:\s+"([^"]*)")?'   # optional "name" (group 3)
    r'(?:\s+\[([^\]]*)])?' # optional [attrs] (group 4)
)

_INVISIBLE_CHARS = re.compile(r'[\ufeff\u200b\u200c\u200d\u2060\u00a0]')


def parse_yaml_tree(yaml_text: str) -> list[TreeNode]:
    if not yaml_text or not yaml_text.strip():
        return []

    lines = yaml_text.splitlines()
    nodes: list[TreeNode] = []

    for line in lines:
        m = _LINE_RE.match(line)
        if not m:
            continue

        indent_str = m.group(1)
        indent = len(indent_str) // 2
        role = m.group(2)
        name = m.group(3) or ""
        attrs_str = m.group(4) or ""

        attrs: dict = {}
        ref = None
        if attrs_str:
            for part in attrs_str.split(","):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    if k.strip() == "ref":
                        ref = v.strip()
                    else:
                        attrs[k.strip()] = v.strip()
                else:
                    attrs[part] = True

        nodes.append(TreeNode(role=role, name=name, ref=ref, attrs=attrs, children=[], indent=indent))

    # Build parent-child relationships using indent levels
    roots: list[TreeNode] = []
    stack: list[TreeNode] = []  # stack of potential parents at each indent level

    for node in nodes:
        # Pop stack until we find a parent at a lower indent
        while stack and stack[-1].indent >= node.indent:
            stack.pop()

        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)

        stack.append(node)

    return roots
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/test_snapshot_tree.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_browser/snapshot_tree.py tests/test_snapshot_tree.py
git commit -m "feat: add TreeNode and YAML tree parser for snapshot optimization"
```

---

### Task 2: Implement `render_tree` with filtering rules 1-4

**Files:**
- Modify: `src/ai_browser/snapshot_tree.py`
- Modify: `tests/test_snapshot_tree.py`

- [ ] **Step 1: Write failing tests for render_tree (rules 1-4)**

Add to `tests/test_snapshot_tree.py`:

```python
from ai_browser.snapshot_tree import render_tree


# A helper to build trees for testing
def _node(role, name="", ref=None, attrs=None, children=None, indent=0):
    return TreeNode(
        role=role, name=name, ref=ref,
        attrs=attrs or {}, children=children or [], indent=indent,
    )


class TestRenderTreeDefaultFilters:
    """Rules 1-4 applied by default (empty collapse, generic collapse, invisible text, RootWebArea strip)."""

    def test_strips_rootwebarea(self):
        """Rule 4: RootWebArea children rendered directly."""
        tree = [_node("RootWebArea", "Page", ref="e1", children=[
            _node("button", "OK", ref="e2", indent=1),
        ])]
        result = render_tree(tree)
        assert "RootWebArea" not in result
        assert '- button "OK"' in result

    def test_strips_webarea(self):
        """Rule 4: WebArea also stripped."""
        tree = [_node("WebArea", children=[
            _node("link", "Home", ref="e1", indent=1),
        ])]
        result = render_tree(tree)
        assert "WebArea" not in result
        assert '- link "Home"' in result

    def test_collapse_generic_with_no_ref_one_child(self):
        """Rule 2: generic with no ref and <=1 children collapsed."""
        tree = [_node("generic", children=[
            _node("button", "Go", ref="e1", indent=1),
        ])]
        result = render_tree(tree)
        assert "generic" not in result
        assert '- button "Go"' in result

    def test_collapse_generic_with_zero_children(self):
        """Rule 2: generic with no ref and 0 children collapsed to nothing."""
        tree = [_node("generic")]
        result = render_tree(tree)
        assert result.strip() == ""

    def test_keeps_generic_with_ref(self):
        """Generic with ref is NOT collapsed."""
        tree = [_node("generic", "Section", ref="e1")]
        result = render_tree(tree)
        assert "generic" in result

    def test_keeps_generic_with_multiple_children(self):
        """Generic with 2+ children is NOT collapsed."""
        tree = [_node("generic", children=[
            _node("button", "A", ref="e1", indent=1),
            _node("button", "B", ref="e2", indent=1),
        ])]
        result = render_tree(tree)
        assert "generic" in result

    def test_skip_invisible_statictext(self):
        """Rule 3: StaticText with only whitespace/invisible chars skipped."""
        tree = [_node("StaticText", name="\u200b\u00a0")]
        result = render_tree(tree)
        assert result.strip() == ""

    def test_keeps_visible_statictext(self):
        """Visible StaticText is kept."""
        tree = [_node("StaticText", name="Hello")]
        result = render_tree(tree)
        assert "Hello" in result

    def test_rendered_format_with_attrs(self):
        """Rendered line includes attrs and ref."""
        tree = [_node("heading", "Title", ref="e1", attrs={"level": "1"})]
        result = render_tree(tree)
        assert '- heading "Title" [level=1, ref=e1]' in result

    def test_rendered_format_no_name(self):
        """Node without name omits the quoted name."""
        tree = [_node("textbox", ref="e1")]
        result = render_tree(tree)
        assert "- textbox [ref=e1]" in result

    def test_empty_role_collapsed(self):
        """Rule 1: Empty role nodes collapse, children rendered."""
        tree = [_node("", children=[
            _node("button", "X", ref="e1", indent=1),
        ])]
        result = render_tree(tree)
        assert "- " not in result.split("\n")[0] if result.strip() else True
        assert '- button "X"' in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/test_snapshot_tree.py::TestRenderTreeDefaultFilters -v`
Expected: FAIL — `ImportError: cannot import name 'render_tree'`

- [ ] **Step 3: Implement render_tree with rules 1-4**

Add to `src/ai_browser/snapshot_tree.py`:

```python
def render_tree(
    roots: list[TreeNode],
    *,
    interactive: bool = False,
    depth: int | None = None,
) -> str:
    output: list[str] = []
    for root in roots:
        _render_node(root, 0, output, interactive=interactive, depth=depth)
    return "\n".join(output)


def _render_node(
    node: TreeNode,
    indent: int,
    output: list[str],
    *,
    interactive: bool,
    depth: int | None,
) -> None:
    # Rule 1: collapse empty-role nodes
    if not node.role:
        for child in node.children:
            _render_node(child, indent, output, interactive=interactive, depth=depth)
        return

    # Rule 2: collapse generic with no ref and <=1 children
    if node.role == "generic" and not node.ref and len(node.children) <= 1:
        for child in node.children:
            _render_node(child, indent, output, interactive=interactive, depth=depth)
        return

    # Rule 3: skip invisible StaticText
    if node.role == "StaticText" and not _INVISIBLE_CHARS.sub("", node.name).strip():
        return

    # Rule 4: strip RootWebArea/WebArea wrappers
    if node.role in ("RootWebArea", "WebArea"):
        for child in node.children:
            _render_node(child, indent, output, interactive=interactive, depth=depth)
        return

    # Rule 5: interactive mode
    if interactive and not node.ref:
        for child in node.children:
            _render_node(child, indent, output, interactive=interactive, depth=depth)
        return

    # Rule 6: depth limit
    if depth is not None and indent >= depth:
        return

    # Build the line
    prefix = "  " * indent
    line = f"{prefix}- {node.role}"

    if node.name:
        escaped = json.dumps(node.name, ensure_ascii=False)
        line += f" {escaped}"

    # Build attrs string
    attr_parts: list[str] = []
    for k, v in node.attrs.items():
        if v is True:
            attr_parts.append(k)
        else:
            attr_parts.append(f"{k}={v}")
    if node.ref:
        attr_parts.append(f"ref={node.ref}")

    if attr_parts:
        line += f" [{', '.join(attr_parts)}]"

    output.append(line)

    for child in node.children:
        _render_node(child, indent + 1, output, interactive=interactive, depth=depth)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/test_snapshot_tree.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_browser/snapshot_tree.py tests/test_snapshot_tree.py
git commit -m "feat: add render_tree with filtering rules 1-4"
```

---

### Task 3: Implement compact mode and interactive/depth options

**Files:**
- Modify: `src/ai_browser/snapshot_tree.py`
- Modify: `tests/test_snapshot_tree.py`

- [ ] **Step 1: Write failing tests for compact, interactive, and depth**

Add to `tests/test_snapshot_tree.py`:

```python
class TestRenderTreeInteractive:
    def test_interactive_only_shows_ref_nodes(self):
        tree = [_node("generic", children=[
            _node("button", "Go", ref="e1", indent=1),
            _node("StaticText", "some text", indent=1),
        ])]
        result = render_tree(tree, interactive=True)
        assert "button" in result
        assert "StaticText" not in result

    def test_interactive_traverses_children(self):
        """Non-interactive nodes still traverse their children."""
        tree = [_node("generic", children=[
            _node("generic", children=[
                _node("link", "Deep", ref="e1", indent=2),
            ], indent=1),
        ])]
        result = render_tree(tree, interactive=True)
        assert '- link "Deep"' in result


class TestRenderTreeDepth:
    def test_depth_limits_indent(self):
        tree = [_node("generic", children=[
            _node("generic", children=[
                _node("button", "Deep", ref="e1", indent=2),
            ], indent=1),
        ])]
        result = render_tree(tree, depth=1)
        assert "Deep" not in result

    def test_depth_zero_shows_only_roots(self):
        tree = [
            _node("button", "A", ref="e1"),
            _node("generic", children=[
                _node("button", "B", ref="e2", indent=1),
            ]),
        ]
        result = render_tree(tree, depth=0)
        assert "- button \"A\"" in result
        assert "- button \"B\"" not in result


class TestCompact:
    def test_compact_keeps_ref_lines(self):
        from ai_browser.snapshot_tree import compact_tree
        rendered = '- generic\n  - button "OK" [ref=e1]\n  - StaticText "info"'
        result = compact_tree(rendered)
        assert "ref=e1" in result
        assert "StaticText" not in result

    def test_compact_keeps_ancestors(self):
        from ai_browser.snapshot_tree import compact_tree
        rendered = '- navigation\n  - link "Home" [ref=e1]\n  - link "About" [ref=e2]'
        result = compact_tree(rendered)
        assert "navigation" in result
        assert "ref=e1" in result

    def test_compact_empty_when_no_refs(self):
        from ai_browser.snapshot_tree import compact_tree
        rendered = '- generic\n  - StaticText "hello"'
        result = compact_tree(rendered)
        assert result.strip() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/test_snapshot_tree.py::TestRenderTreeInteractive tests/test_snapshot_tree.py::TestRenderTreeDepth tests/test_snapshot_tree.py::TestCompact -v`
Expected: FAIL — `ImportError: cannot import name 'compact_tree'`

- [ ] **Step 3: Implement compact_tree**

Add to `src/ai_browser/snapshot_tree.py`:

```python
def compact_tree(rendered: str) -> str:
    if not rendered.strip():
        return ""

    lines = rendered.splitlines()
    keep = [False] * len(lines)

    for i, line in enumerate(lines):
        if "ref=" in line:
            keep[i] = True
            my_indent = len(line) - len(line.lstrip())
            for j in range(i - 1, -1, -1):
                ancestor_indent = len(lines[j]) - len(lines[j].lstrip())
                if ancestor_indent < my_indent:
                    keep[j] = True
                    my_indent = ancestor_indent

    return "\n".join(line for i, line in enumerate(lines) if keep[i])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/test_snapshot_tree.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_browser/snapshot_tree.py tests/test_snapshot_tree.py
git commit -m "feat: add compact_tree, interactive mode, and depth limit"
```

---

### Task 4: Wire up `ax_tree.py` to use `snapshot_tree`

**Files:**
- Modify: `src/ai_browser/ax_tree.py`
- Modify: `src/ai_browser/ref_map.py`
- Modify: `tests/test_ax_tree.py`

- [ ] **Step 1: Write failing test for new take_snapshot behavior**

Add to `tests/test_ax_tree.py`:

```python
class TestTakeSnapshotOptimized:
    def test_output_smaller_than_raw(self, simple_page):
        """Optimized output should be smaller than raw aria_snapshot."""
        ref_map = RefMap()
        output = take_snapshot(simple_page, ref_map)
        raw = simple_page.locator("body").aria_snapshot(mode="ai")
        # Default filtering should reduce size
        assert len(output) <= len(raw)

    def test_ref_map_still_populated(self, simple_page):
        """Ref map should still get all refs from the snapshot."""
        ref_map = RefMap()
        take_snapshot(simple_page, ref_map)
        entries = list(ref_map._entries.values())
        roles = {e.role for e in entries}
        assert "button" in roles or "link" in roles

    def test_interactive_mode(self, simple_page):
        """Interactive mode should only include ref-bearing nodes."""
        ref_map = RefMap()
        output = take_snapshot(simple_page, ref_map, interactive=True)
        assert "ref=" in output
        # Count lines — interactive should have fewer
        ref_map2 = RefMap()
        full = take_snapshot(simple_page, ref_map2, interactive=False)
        assert output.count("\n") <= full.count("\n")

    def test_depth_limit(self, simple_page):
        """Depth-limited snapshot should be smaller."""
        ref_map = RefMap()
        output = take_snapshot(simple_page, ref_map, depth=1)
        ref_map2 = RefMap()
        full = take_snapshot(simple_page, ref_map2)
        assert len(output) <= len(full)

    def test_selector_scopes_snapshot(self, simple_page):
        """Selector should scope the snapshot to matching elements."""
        ref_map = RefMap()
        output = take_snapshot(simple_page, ref_map, selector="#btn")
        assert "button" in output.lower() or "Click" in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/test_ax_tree.py::TestTakeSnapshotOptimized -v`
Expected: FAIL — `TypeError: take_snapshot() got an unexpected keyword argument 'interactive'`

- [ ] **Step 3: Update ref_map.py — parse_snapshot from TreeNode tree**

Replace `parse_snapshot` in `src/ai_browser/ref_map.py` to also accept a list of `TreeNode` objects:

```python
# src/ai_browser/ref_map.py — full replacement
from __future__ import annotations

import re
from dataclasses import dataclass

from ai_browser.snapshot_tree import TreeNode


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


def parse_snapshot(yaml_text: str) -> RefMap:
    ref_map = RefMap()
    if not yaml_text:
        return ref_map
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


def populate_ref_map_from_tree(nodes: list[TreeNode], ref_map: RefMap) -> None:
    """Walk TreeNode tree and populate ref_map with all ref-bearing nodes."""
    ref_map.clear()
    counts: dict[tuple[str, str], int] = {}
    _walk_tree(nodes, ref_map, counts)


def _walk_tree(
    nodes: list[TreeNode], ref_map: RefMap, counts: dict[tuple[str, str], int]
) -> None:
    for node in nodes:
        if node.ref:
            key = (node.role, node.name)
            nth = counts.get(key, 0)
            counts[key] = nth + 1
            ref_map.add(node.ref, node.role, node.name, nth)
        _walk_tree(node.children, ref_map, counts)


_LINE_RE = re.compile(
    r'^\s*-\s+'
    r'(\w+)'
    r'(?:\s+"([^"]*)")?'
    r'.*?\[ref=(e\d+)\]'
)
```

- [ ] **Step 4: Update ax_tree.py to use snapshot_tree**

```python
# src/ai_browser/ax_tree.py — full replacement
from __future__ import annotations

from playwright.sync_api import Page

from ai_browser.ref_map import RefMap, populate_ref_map_from_tree
from ai_browser.snapshot_tree import parse_yaml_tree, render_tree, compact_tree


def take_snapshot(
    page: Page,
    ref_map: RefMap,
    *,
    compact: bool = False,
    interactive: bool = False,
    depth: int | None = None,
    selector: str | None = None,
) -> str:
    locator = page.locator(selector) if selector else page.locator("body")
    raw_yaml = locator.aria_snapshot(mode="ai")
    roots = parse_yaml_tree(raw_yaml)

    # Populate ref_map from the parsed tree (before filtering)
    populate_ref_map_from_tree(roots, ref_map)

    rendered = render_tree(roots, interactive=interactive, depth=depth)

    if compact:
        rendered = compact_tree(rendered)

    return rendered


# Keep for backward compat with existing tests
from ai_browser.ref_map import parse_snapshot as parse_snapshot_yaml
```

- [ ] **Step 5: Run all tests**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/test_ax_tree.py tests/test_ref_map.py tests/test_snapshot_tree.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ai_browser/ax_tree.py src/ai_browser/ref_map.py tests/test_ax_tree.py
git commit -m "feat: wire ax_tree to snapshot_tree for filtered rendering"
```

---

### Task 5: Update daemon and CLI with new snapshot options

**Files:**
- Modify: `src/ai_browser/daemon.py` (lines 171-174)
- Modify: `src/ai_browser/cli.py` (lines 233-247)

- [ ] **Step 1: Update daemon `_snapshot()` to pass new params**

In `src/ai_browser/daemon.py`, replace lines 171-174:

```python
    def _snapshot(self, params: dict) -> dict:
        content = take_snapshot(
            self.bm.page, self.ref_map,
            compact=params.get("compact", False),
            interactive=params.get("interactive", False),
            depth=params.get("depth"),
            selector=params.get("selector"),
        )
        return {"status": "ok", "content": content}
```

- [ ] **Step 2: Update CLI snapshot command with new options**

In `src/ai_browser/cli.py`, replace lines 233-247:

```python
@cli.command()
@click.option("--compact", is_flag=True, help="Compact output mode.")
@click.option("--interactive", is_flag=True, help="Only show interactive elements.")
@click.option("--depth", type=int, default=None, help="Max tree depth.")
@click.option("--selector", help="CSS selector to scope the snapshot.")
@click.pass_context
def snapshot(ctx: click.Context, compact: bool, interactive: bool, depth: int | None, selector: str | None) -> None:
    """Get accessibility tree snapshot of the current page."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {}
    if compact:
        params["compact"] = True
    if interactive:
        params["interactive"] = True
    if depth is not None:
        params["depth"] = depth
    if selector:
        params["selector"] = selector
    result = client.call("snapshot", params)
    _output(result)
```

- [ ] **Step 3: Run existing tests to verify nothing broken**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/ -v --ignore=tests/e2e`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/ai_browser/daemon.py src/ai_browser/cli.py
git commit -m "feat: add --interactive, --depth options to snapshot CLI and daemon"
```

---

### Task 6: Integration test and final verification

**Files:**
- Modify: `tests/test_ax_tree.py`

- [ ] **Step 1: Add integration test comparing output sizes**

Add to `tests/test_ax_tree.py`:

```python
COMPLEX_HTML = """<html><body>
<div class="wrapper">
  <div class="inner">
    <div class="deep">
      <nav>
        <a href="/home">Home</a>
        <a href="/about">About</a>
      </nav>
    </div>
  </div>
  <main>
    <h1>Welcome</h1>
    <p>Some paragraph text here.</p>
    <form>
      <input type="text" placeholder="Search">
      <button type="submit">Go</button>
    </form>
  </main>
</div>
</body></html>"""


@pytest.fixture
def complex_page(browser_page):
    browser_page.goto("data:text/html," + urllib.parse.quote(COMPLEX_HTML))
    return browser_page


class TestSnapshotSizeReduction:
    def test_default_smaller_than_raw(self, complex_page):
        ref_map = RefMap()
        output = take_snapshot(complex_page, ref_map)
        raw = complex_page.locator("body").aria_snapshot(mode="ai")
        assert len(output) < len(raw), (
            f"Filtered ({len(output)}) should be smaller than raw ({len(raw)})"
        )

    def test_interactive_much_smaller(self, complex_page):
        ref_map1 = RefMap()
        full = take_snapshot(complex_page, ref_map1)
        ref_map2 = RefMap()
        interactive = take_snapshot(complex_page, ref_map2, interactive=True)
        assert len(interactive) < len(full), (
            f"Interactive ({len(interactive)}) should be smaller than full ({len(full)})"
        )

    def test_compact_plus_interactive_smallest(self, complex_page):
        ref_map1 = RefMap()
        full = take_snapshot(complex_page, ref_map1)
        ref_map2 = RefMap()
        smallest = take_snapshot(complex_page, ref_map2, compact=True, interactive=True)
        assert len(smallest) <= len(full)

    def test_depth_1_smaller_than_full(self, complex_page):
        ref_map1 = RefMap()
        full = take_snapshot(complex_page, ref_map1)
        ref_map2 = RefMap()
        shallow = take_snapshot(complex_page, ref_map2, depth=1)
        assert len(shallow) <= len(full)
```

- [ ] **Step 2: Run all tests**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/ -v --ignore=tests/e2e`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_ax_tree.py
git commit -m "test: add integration tests for snapshot size reduction"
```

---

### Task 7: Update E2E tests if needed

**Files:**
- Modify: `tests/e2e/test_commands.py` (if snapshot tests reference old output format)

- [ ] **Step 1: Check if E2E tests reference snapshot output format**

Run: `cd /home/zenos/workspace/auto-browser && grep -n "snapshot" tests/e2e/test_commands.py`

If E2E tests check specific snapshot output format, update them to match the new filtered format (no RootWebArea wrapper, no generic collapse, etc.). The ref IDs and element roles should remain the same — only structural elements (RootWebArea, generic wrappers) may be removed.

- [ ] **Step 2: Run E2E tests**

Run: `cd /home/zenos/workspace/auto-browser && python -m pytest tests/e2e/ -v`
Expected: All E2E tests PASS

- [ ] **Step 3: Commit any E2E fixes**

```bash
git add tests/e2e/
git commit -m "fix: update E2E tests for new snapshot output format"
```
