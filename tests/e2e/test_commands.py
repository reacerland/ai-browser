from __future__ import annotations

from pathlib import Path

import pytest

from conftest import ab, find_ref, parse_refs


class TestLifecycle:
    def test_open_and_ping(self, e2e):
        r = ab("ping")
        assert r.returncode == 0
        assert "ok" in r.stdout

    def test_snapshot(self, e2e):
        r = ab("snapshot")
        assert r.returncode == 0
        assert "[ref=" in r.stderr

    def test_snapshot_compact(self, e2e):
        full = ab("snapshot")
        compact = ab("snapshot", "--compact")
        assert compact.returncode == 0
        assert len(compact.stderr) < len(full.stderr)


class TestNavigation:
    def test_click_link_then_back_forward(self, e2e):
        ref = e2e.ref("link", "Go to Section 2")
        ab("click", ref)
        r = ab("back")
        assert r.returncode == 0
        r = ab("forward")
        assert r.returncode == 0

    def test_reload(self, e2e):
        r = ab("reload")
        assert r.returncode == 0


class TestGet:
    def test_get_title(self, e2e):
        r = ab("get", "title")
        assert r.returncode == 0
        assert "E2E Test Page" in r.stdout

    def test_get_url(self, e2e):
        r = ab("get", "url")
        assert r.returncode == 0
        assert "localhost" in r.stdout
        assert "test_page.html" in r.stdout

    def test_get_text(self, e2e):
        ref = e2e.ref("button", "Submit")
        r = ab("get", "text", ref)
        assert r.returncode == 0
        assert "Submit" in r.stdout

    def test_get_value(self, e2e):
        ref = e2e.ref("textbox")
        r = ab("get", "value", ref)
        assert r.returncode == 0
        assert "Alice" in r.stdout

    def test_get_html(self, e2e):
        ref = e2e.ref("button", "Submit")
        r = ab("get", "html", ref)
        assert r.returncode == 0
        assert "Submit" in r.stdout

    def test_get_attr(self, e2e):
        ref = e2e.ref("img")
        r = ab("get", "attr", ref, "--name", "alt")
        assert r.returncode == 0
        assert "Logo" in r.stdout

    def test_get_box(self, e2e):
        ref = e2e.ref("button", "Submit")
        r = ab("get", "box", ref)
        assert r.returncode == 0
        assert "x" in r.stdout


class TestIs:
    def test_is_visible(self, e2e):
        ref = e2e.ref("button", "Submit")
        r = ab("is", "visible", ref)
        assert r.returncode == 0
        assert "true" in r.stdout

    def test_is_hidden_element(self, e2e):
        r = ab("eval", "document.getElementById('hidden-el').style.display")
        assert "none" in r.stdout

    def test_is_enabled(self, e2e):
        ref = e2e.ref("button", "Submit")
        r = ab("is", "enabled", ref)
        assert r.returncode == 0
        assert "true" in r.stdout

    def test_is_disabled_element(self, e2e):
        r = ab("eval", "document.getElementById('disabled-btn').disabled")
        assert "true" in r.stdout

    def test_is_checked(self, e2e):
        ref = e2e.ref("checkbox")
        r = ab("is", "checked", ref)
        assert r.returncode == 0
        assert "false" in r.stdout


class TestInteractions:
    def test_click(self, e2e):
        ref = e2e.ref("button", "Submit")
        ab("click", ref)
        r = ab("get", "title")
        assert "submitted" in r.stdout

    def test_dblclick(self, e2e):
        ref = e2e.ref("button", "Submit")
        r = ab("dblclick", ref)
        assert r.returncode == 0

    def test_type(self, e2e):
        ref = e2e.ref("textbox")
        ab("type", ref, "hello", "--clear")
        r = ab("get", "value", ref)
        assert "hello" in r.stdout

    def test_fill(self, e2e):
        ref = e2e.ref("textbox")
        ab("fill", ref, "new@email.com")
        r = ab("get", "value", ref)
        assert "new@email.com" in r.stdout

    def test_press(self, e2e):
        ref = e2e.ref("textbox")
        ab("click", ref)
        r = ab("press", "End")
        assert r.returncode == 0

    def test_check_uncheck(self, e2e):
        ref = e2e.ref("checkbox")
        ab("check", ref)
        r = ab("is", "checked", ref)
        assert "true" in r.stdout
        ab("uncheck", ref)
        r = ab("is", "checked", ref)
        assert "false" in r.stdout

    def test_select(self, e2e):
        ref = e2e.ref("combobox")
        r = ab("select", ref, "green")
        assert r.returncode == 0

    def test_hover(self, e2e):
        ref = e2e.ref("button", "Submit")
        r = ab("hover", ref)
        assert r.returncode == 0

    def test_scroll(self, e2e):
        r = ab("scroll", "down", "--amount", "500")
        assert r.returncode == 0

    def test_scroll_into_view(self, e2e):
        snap = e2e.fresh_snapshot()
        try:
            ref = find_ref(snap, "text", "Section 2 Content")
        except ValueError:
            try:
                ref = find_ref(snap, "paragraph", "Section 2 Content")
            except ValueError:
                pytest.skip("Section 2 element not found in snapshot")
        r = ab("scroll-into-view", ref)
        assert r.returncode == 0


class TestAdvanced:
    def test_find_role(self, e2e):
        r = ab("find", "role", "button", "--name", "Submit")
        assert r.returncode == 0
        assert "Submit" in r.stdout

    def test_find_text(self, e2e):
        r = ab("find", "text", "Hello World")
        assert r.returncode == 0
        assert "Hello" in r.stdout

    def test_find_placeholder(self, e2e):
        r = ab("find", "placeholder", "Enter name")
        assert r.returncode == 0

    def test_count(self, e2e):
        r = ab("count", ".action-btn")
        assert r.returncode == 0
        assert r.stdout.strip() == "3"

    def test_eval(self, e2e):
        r = ab("eval", "document.title")
        assert r.returncode == 0
        assert "E2E Test Page" in r.stdout

    def test_wait_time(self, e2e):
        r = ab("wait", "100")
        assert r.returncode == 0


class TestFileOperations:
    def test_download(self, e2e, tmp_path):
        save_path = str(tmp_path / "downloaded.txt")
        snap = e2e.fresh_snapshot()
        try:
            ref = find_ref(snap, "link", "Download File")
        except ValueError:
            pytest.skip("Download link not found in snapshot")
        r = ab("download", ref, save_path)
        assert r.returncode == 0
        assert Path(save_path).exists()


class TestClose:
    def test_close(self, http_server):
        url = f"{http_server}/test_page.html"
        r = ab("open", url)
        assert r.returncode == 0
        r = ab("close")
        assert r.returncode == 0
        r = ab("ping")
        assert r.returncode != 0


class TestErrors:
    def test_unknown_ref(self, e2e):
        r = ab("click", "e999")
        assert r.returncode != 0

    def test_no_daemon(self):
        r = ab("snapshot")
        assert r.returncode != 0
