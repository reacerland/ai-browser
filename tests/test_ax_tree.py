import json
from pathlib import Path

import pytest
from auto_browser.ax_tree import build_tree, TreeNode
from auto_browser.ref_map import RefMap, RoleNameTracker
from auto_browser.ax_tree import (
    assign_refs, render_tree, compact_tree, take_snapshot,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ax_tree_response.json"


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)["nodes"]


class TestBuildTree:
    def test_builds_tree_from_fixture(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        assert len(root_indices) > 0

    def test_inline_text_box_filtered(self):
        raw_nodes = load_fixture()
        nodes, _ = build_tree(raw_nodes)
        roles = [n.role for n in nodes]
        assert "InlineTextBox" not in roles

    def test_consecutive_static_text_merged(self):
        raw_nodes = load_fixture()
        nodes, _ = build_tree(raw_nodes)
        link1 = next(n for n in nodes if n.role == "link" and n.name == "Home")
        children = [nodes[i] for i in link1.children]
        static_texts = [c for c in children if c.role == "StaticText"]
        assert len(static_texts) == 1
        assert "Go to" in static_texts[0].name and "homepage" in static_texts[0].name

    def test_redundant_static_text_deduplicated(self):
        raw_nodes = load_fixture()
        nodes, _ = build_tree(raw_nodes)
        link2 = next(n for n in nodes if n.role == "link" and n.name == "About")
        children = [nodes[i] for i in link2.children]
        static_texts = [c for c in children if c.role == "StaticText" and c.name]
        assert len(static_texts) == 0

    def test_generic_single_child_collapsed(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        button_names = [n.name for n in nodes if n.role == "button"]
        assert "Submit" in button_names

    def test_empty_static_text_skipped(self):
        raw_nodes = load_fixture()
        nodes, _ = build_tree(raw_nodes)
        empty_statics = [n for n in nodes if n.role == "StaticText" and n.name.strip() == ""]
        assert len(empty_statics) == 0

    def test_tree_has_navigation(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        from_root = nodes[root_indices[0]]
        child_roles = [nodes[i].role for i in from_root.children]
        assert "navigation" in child_roles

    def test_depth_calculated(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        root = nodes[root_indices[0]]
        assert root.depth == 0


class TestAssignRefs:
    def test_interactive_roles_get_refs(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        button = next(n for n in nodes if n.role == "button")
        assert button.has_ref
        assert button.ref_id is not None
        assert ref_map.get(button.ref_id) is not None

    def test_content_roles_with_name_get_refs(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        heading = next(n for n in nodes if n.role == "heading")
        assert heading.has_ref

    def test_structural_roles_no_ref(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        for n in nodes:
            if n.role == "generic":
                assert not n.has_ref

    def test_ref_map_entries_have_backend_node_id(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        for n in nodes:
            if n.has_ref:
                entry = ref_map.get(n.ref_id)
                assert entry is not None
                assert entry.backend_node_id is not None


class TestRenderTree:
    def test_renders_indented_tree(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        output = render_tree(nodes, root_indices, ref_map)
        assert "link" in output
        assert "button" in output
        assert "Submit" in output

    def test_renders_ref_ids(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        output = render_tree(nodes, root_indices, ref_map)
        assert "ref=" in output

    def test_compact_mode(self):
        raw_nodes = load_fixture()
        nodes, root_indices = build_tree(raw_nodes)
        ref_map = RefMap()
        assign_refs(nodes, ref_map)
        full = render_tree(nodes, root_indices, ref_map)
        compacted = compact_tree(full)
        assert len(compacted.splitlines()) <= len(full.splitlines())
        assert "ref=" in compacted
