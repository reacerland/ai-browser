import urllib.parse

import pytest

from ai_browser.browser_manager import BrowserManager
from ai_browser.interactions import Interactions
from ai_browser.ref_map import RefMap
from ai_browser.ax_tree import take_snapshot

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

    def test_find_by_placeholder(self, browser_env):
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
