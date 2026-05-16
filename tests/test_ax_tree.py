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
