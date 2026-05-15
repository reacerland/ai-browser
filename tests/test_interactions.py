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
