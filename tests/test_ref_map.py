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
