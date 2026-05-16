import pytest
from ai_browser.ref_map import RefEntry, RefMap, parse_snapshot


class TestRefEntry:
    def test_create(self):
        entry = RefEntry(role="button", name="Submit", nth=0)
        assert entry.role == "button"
        assert entry.name == "Submit"
        assert entry.nth == 0

    def test_default_nth(self):
        entry = RefEntry(role="link", name="Home", nth=0)
        assert entry.nth == 0


class TestRefMap:
    def test_add_and_get(self):
        rm = RefMap()
        rm.add("e1", role="button", name="OK", nth=0)
        entry = rm.get("e1")
        assert entry.role == "button"
        assert entry.name == "OK"
        assert entry.nth == 0

    def test_get_missing_returns_none(self):
        rm = RefMap()
        assert rm.get("e999") is None

    def test_clear_resets(self):
        rm = RefMap()
        rm.add("e1", role="link", name="Home", nth=0)
        rm.clear()
        assert rm.get("e1") is None


class TestParseSnapshot:
    def test_parses_single_element(self):
        yaml_text = '- button "Submit" [ref=e1]'
        rm = parse_snapshot(yaml_text)
        entry = rm.get("e1")
        assert entry is not None
        assert entry.role == "button"
        assert entry.name == "Submit"
        assert entry.nth == 0

    def test_parses_element_without_name(self):
        yaml_text = "- textbox [ref=e5]"
        rm = parse_snapshot(yaml_text)
        entry = rm.get("e5")
        assert entry is not None
        assert entry.role == "textbox"
        assert entry.name == ""

    def test_tracks_nth_for_duplicate_role_name(self):
        yaml_text = '- link "Home" [ref=e1]\n- link "About" [ref=e2]\n- link "Home" [ref=e3]'
        rm = parse_snapshot(yaml_text)
        assert rm.get("e1").nth == 0
        assert rm.get("e3").nth == 1  # second "link Home"
        assert rm.get("e2").nth == 0  # only "link About"

    def test_empty_snapshot(self):
        rm = parse_snapshot("")
        assert rm.get("e1") is None

    def test_lines_without_ref_ignored(self):
        yaml_text = '- heading "Title"\n- button "OK" [ref=e1]'
        rm = parse_snapshot(yaml_text)
        assert rm.get("e1") is not None
        assert rm.get("e2") is None

    def test_name_with_special_chars(self):
        yaml_text = '- link "foo/bar?baz=1" [ref=e10]'
        rm = parse_snapshot(yaml_text)
        entry = rm.get("e10")
        assert entry is not None
        assert entry.name == "foo/bar?baz=1"
