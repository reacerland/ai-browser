import pytest
from auto_browser.browser_manager import BrowserManager


class TestBrowserManagerDefault:
    def test_start_and_close(self):
        bm = BrowserManager(session_name="default", headed=True, user_data_dir=None)
        bm.start()
        assert bm.page is not None
        assert bm.is_alive()
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
