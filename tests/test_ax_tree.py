import json
from pathlib import Path

import pytest
from auto_browser.ax_tree import build_tree, TreeNode


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
