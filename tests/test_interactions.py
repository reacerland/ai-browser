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
