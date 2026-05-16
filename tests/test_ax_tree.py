import urllib.parse

import pytest
from playwright.sync_api import Page

from ai_browser.ref_map import RefMap
from ai_browser.ax_tree import take_snapshot, parse_snapshot_yaml


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


# ---------------------------------------------------------------------------
# New optimized snapshot tests (snapshot_tree pipeline)
# ---------------------------------------------------------------------------

HTML_COMPLEX = """<html><body>
    <h1>Title</h1>
    <div>
        <p>Paragraph one</p>
        <p>Paragraph two</p>
        <button id="btn1">Button A</button>
        <a href="#x">Link A</a>
        <input id="inp" type="text" placeholder="Type here">
    </div>
    <div>
        <div>
            <button id="btn2">Button B</button>
        </div>
    </div>
</body></html>"""


@pytest.fixture
def complex_page(browser_page):
    browser_page.goto("data:text/html," + urllib.parse.quote(HTML_COMPLEX))
    return browser_page


class TestTakeSnapshotOptimized:
    def test_output_smaller_than_raw(self, complex_page):
        """Filtered/rendered output should be no larger than the raw aria_snapshot."""
        ref_map = RefMap()
        raw = complex_page.locator("body").aria_snapshot(mode="ai")
        rendered = take_snapshot(complex_page, ref_map)
        assert len(rendered) <= len(raw)

    def test_ref_map_still_populated(self, complex_page):
        """ref_map should still receive all ref-bearing entries."""
        ref_map = RefMap()
        take_snapshot(complex_page, ref_map)
        entries = list(ref_map._entries.values())
        roles = {e.role for e in entries}
        assert "button" in roles

    def test_interactive_mode(self, complex_page):
        """Interactive mode should produce fewer lines than the full render."""
        ref_map_full = RefMap()
        full = take_snapshot(complex_page, ref_map_full, interactive=False)
        ref_map_interactive = RefMap()
        interactive = take_snapshot(complex_page, ref_map_interactive, interactive=True)
        assert interactive.count("\n") < full.count("\n")

    def test_depth_limit(self, complex_page):
        """Depth-limited snapshot should be smaller than full snapshot."""
        ref_map_full = RefMap()
        full = take_snapshot(complex_page, ref_map_full)
        ref_map_depth = RefMap()
        depth = take_snapshot(complex_page, ref_map_depth, depth=1)
        assert len(depth) <= len(full)

    def test_selector_scopes_snapshot(self, complex_page):
        """Selector should scope the snapshot to a sub-element."""
        ref_map_all = RefMap()
        all_output = take_snapshot(complex_page, ref_map_all)
        ref_map_btn = RefMap()
        btn_output = take_snapshot(complex_page, ref_map_btn, selector="#btn1")
        assert len(btn_output) < len(all_output)


# ---------------------------------------------------------------------------
# Snapshot size reduction tests (realistic HTML)
# ---------------------------------------------------------------------------

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
def size_page(browser_page):
    browser_page.goto("data:text/html," + urllib.parse.quote(COMPLEX_HTML))
    return browser_page


class TestSnapshotSizeReduction:
    def test_default_smaller_than_raw(self, size_page):
        """Filtered output length should be less than raw aria_snapshot length."""
        ref_map = RefMap()
        raw = size_page.locator("body").aria_snapshot(mode="ai")
        rendered = take_snapshot(size_page, ref_map)
        assert len(rendered) < len(raw)

    def test_interactive_much_smaller(self, size_page):
        """Interactive mode should produce fewer characters than full mode."""
        ref_map_full = RefMap()
        full = take_snapshot(size_page, ref_map_full, interactive=False)
        ref_map_interactive = RefMap()
        interactive = take_snapshot(size_page, ref_map_interactive, interactive=True)
        assert len(interactive) < len(full)

    def test_compact_plus_interactive_smallest(self, size_page):
        """compact+interactive combined should be no larger than full output."""
        ref_map_full = RefMap()
        full = take_snapshot(size_page, ref_map_full, compact=False, interactive=False)
        ref_map_both = RefMap()
        both = take_snapshot(size_page, ref_map_both, compact=True, interactive=True)
        assert len(both) <= len(full)

    def test_depth_1_smaller_than_full(self, size_page):
        """depth=1 should produce output no larger than full depth."""
        ref_map_full = RefMap()
        full = take_snapshot(size_page, ref_map_full)
        ref_map_depth = RefMap()
        depth = take_snapshot(size_page, ref_map_depth, depth=1)
        assert len(depth) <= len(full)
