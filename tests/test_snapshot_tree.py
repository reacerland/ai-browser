"""Unit tests for snapshot_tree module."""
from __future__ import annotations

import pytest

from ai_browser.snapshot_tree import (
    TreeNode,
    compact_tree,
    parse_yaml_tree,
    render_tree,
)


# ---------------------------------------------------------------------------
# TreeNode creation
# ---------------------------------------------------------------------------


class TestTreeNode:
    def test_basic_creation(self):
        node = TreeNode(role="button", name="Submit", ref="e1", attrs={})
        assert node.role == "button"
        assert node.name == "Submit"
        assert node.ref == "e1"
        assert node.attrs == {}
        assert node.children == []
        assert node.indent == 0

    def test_with_children(self):
        child = TreeNode(role="StaticText", name="Hello", ref=None, attrs={}, indent=1)
        parent = TreeNode(role="button", name="Go", ref="e1", attrs={}, children=[child], indent=0)
        assert len(parent.children) == 1
        assert parent.children[0].name == "Hello"

    def test_attrs_dict(self):
        node = TreeNode(role="heading", name="Title", ref="e2", attrs={"level": "1", "checked": True}, indent=0)
        assert node.attrs["level"] == "1"
        assert node.attrs["checked"] is True


# ---------------------------------------------------------------------------
# parse_yaml_tree
# ---------------------------------------------------------------------------


class TestParseYamlTree:
    def test_empty_input(self):
        assert parse_yaml_tree("") == []
        assert parse_yaml_tree("  ") == []

    def test_single_node_no_attrs(self):
        yaml = '- button "Submit"'
        roots = parse_yaml_tree(yaml)
        assert len(roots) == 1
        assert roots[0].role == "button"
        assert roots[0].name == "Submit"
        assert roots[0].ref is None

    def test_single_node_with_ref(self):
        yaml = '- button "Submit" [ref=e1]'
        roots = parse_yaml_tree(yaml)
        assert len(roots) == 1
        assert roots[0].ref == "e1"

    def test_multiple_attrs(self):
        yaml = '- heading "Title" [level=1, ref=e2]'
        roots = parse_yaml_tree(yaml)
        assert roots[0].attrs == {"level": "1"}
        assert roots[0].ref == "e2"

    def test_boolean_attr(self):
        yaml = '- checkbox "Accept" [checked, ref=e3]'
        roots = parse_yaml_tree(yaml)
        assert roots[0].attrs["checked"] is True
        assert roots[0].ref == "e3"

    def test_no_name_node(self):
        yaml = "- textbox [ref=e5]"
        roots = parse_yaml_tree(yaml)
        assert roots[0].role == "textbox"
        assert roots[0].name == ""
        assert roots[0].ref == "e5"

    def test_indent_builds_parent_child(self):
        yaml = (
            '- RootWebArea "Page" [ref=e1]\n'
            '  - heading "Title" [level=1, ref=e2]\n'
            '  - button "Go" [ref=e3]'
        )
        roots = parse_yaml_tree(yaml)
        assert len(roots) == 1
        assert roots[0].role == "RootWebArea"
        assert len(roots[0].children) == 2
        assert roots[0].children[0].role == "heading"
        assert roots[0].children[1].role == "button"

    def test_deeper_indent(self):
        yaml = (
            '- generic [ref=e1]\n'
            '  - generic [ref=e2]\n'
            '    - button "Deep" [ref=e3]'
        )
        roots = parse_yaml_tree(yaml)
        assert len(roots) == 1
        assert roots[0].children[0].children[0].name == "Deep"

    def test_indent_levels_recorded(self):
        yaml = (
            '- button "A" [ref=e1]\n'
            '  - button "B" [ref=e2]\n'
            '    - button "C" [ref=e3]'
        )
        roots = parse_yaml_tree(yaml)
        assert roots[0].indent == 0
        assert roots[0].children[0].indent == 1
        assert roots[0].children[0].children[0].indent == 2

    def test_generic_no_attrs(self):
        yaml = "- generic"
        roots = parse_yaml_tree(yaml)
        assert roots[0].role == "generic"
        assert roots[0].name == ""
        assert roots[0].ref is None

    def test_static_text(self):
        yaml = '- StaticText "Hello world"'
        roots = parse_yaml_tree(yaml)
        assert roots[0].role == "StaticText"
        assert roots[0].name == "Hello world"

    def test_mixed_attrs_with_ref(self):
        yaml = '- treeitem "Item" [expanded, level=2, ref=e10]'
        roots = parse_yaml_tree(yaml)
        assert roots[0].attrs["expanded"] is True
        assert roots[0].attrs["level"] == "2"
        assert roots[0].ref == "e10"


# ---------------------------------------------------------------------------
# render_tree
# ---------------------------------------------------------------------------


class TestRenderTree:
    # --- Rule 1: empty role collapse ---
    def test_empty_role_collapse(self):
        node = TreeNode(role="", name="", ref=None, attrs={}, children=[
            TreeNode(role="button", name="Go", ref="e1", attrs={}, indent=1),
        ], indent=0)
        result = render_tree([node])
        assert "button" in result
        assert result.startswith("- button")

    # --- Rule 2: generic with no ref and <=1 children → collapse ---
    def test_generic_no_ref_one_child_collapses(self):
        node = TreeNode(role="generic", name="", ref=None, attrs={}, children=[
            TreeNode(role="button", name="Go", ref="e1", attrs={}, indent=1),
        ], indent=0)
        result = render_tree([node])
        assert "- button" in result
        assert "generic" not in result

    def test_generic_no_ref_zero_children_collapses(self):
        node = TreeNode(role="generic", name="", ref=None, attrs={}, children=[], indent=0)
        result = render_tree([node])
        assert result == ""

    def test_generic_with_ref_not_collapsed(self):
        node = TreeNode(role="generic", name="", ref="e1", attrs={}, children=[], indent=0)
        result = render_tree([node])
        assert "generic" in result
        assert "ref=e1" in result

    def test_generic_no_ref_two_children_not_collapsed(self):
        child1 = TreeNode(role="button", name="A", ref="e1", attrs={}, indent=1)
        child2 = TreeNode(role="button", name="B", ref="e2", attrs={}, indent=1)
        node = TreeNode(role="generic", name="", ref=None, attrs={}, children=[child1, child2], indent=0)
        result = render_tree([node])
        assert "generic" in result

    # --- Rule 3: skip invisible StaticText ---
    def test_whitespace_static_text_skipped(self):
        node = TreeNode(role="StaticText", name="   ", ref=None, attrs={}, indent=0)
        result = render_tree([node])
        assert result == ""

    def test_zero_width_static_text_skipped(self):
        node = TreeNode(role="StaticText", name="\u200b", ref=None, attrs={}, indent=0)
        result = render_tree([node])
        assert result == ""

    def test_visible_static_text_kept(self):
        node = TreeNode(role="StaticText", name="Hello", ref=None, attrs={}, indent=0)
        result = render_tree([node])
        assert "Hello" in result

    # --- Rule 4: strip RootWebArea / WebArea ---
    def test_rootwebarea_stripped(self):
        child = TreeNode(role="button", name="Go", ref="e1", attrs={}, indent=1)
        root = TreeNode(role="RootWebArea", name="Page", ref="e0", attrs={}, children=[child], indent=0)
        result = render_tree([root])
        assert "RootWebArea" not in result
        assert "button" in result

    def test_webarea_stripped(self):
        child = TreeNode(role="link", name="Home", ref="e1", attrs={}, indent=1)
        root = TreeNode(role="WebArea", name="Frame", ref="e0", attrs={}, children=[child], indent=0)
        result = render_tree([root])
        assert "WebArea" not in result
        assert "link" in result

    # --- Rule 5: interactive mode ---
    def test_interactive_only_shows_ref_nodes(self):
        child_with_ref = TreeNode(role="button", name="Go", ref="e1", attrs={}, indent=1)
        child_no_ref = TreeNode(role="StaticText", name="Label", ref=None, attrs={}, indent=1)
        root = TreeNode(role="generic", name="", ref=None, attrs={}, children=[child_no_ref, child_with_ref], indent=0)
        result = render_tree([root], interactive=True)
        assert "button" in result
        assert "StaticText" not in result

    def test_interactive_traverses_children_of_non_ref(self):
        grandchild = TreeNode(role="button", name="Deep", ref="e2", attrs={}, indent=2)
        child = TreeNode(role="generic", name="", ref=None, attrs={}, children=[grandchild], indent=1)
        root = TreeNode(role="generic", name="", ref=None, attrs={}, children=[child], indent=0)
        result = render_tree([root], interactive=True)
        assert "Deep" in result

    # --- Rule 6: depth limit ---
    def test_depth_limit(self):
        grandchild = TreeNode(role="button", name="Deep", ref="e2", attrs={}, indent=2)
        child = TreeNode(role="button", name="Mid", ref="e1", attrs={}, children=[grandchild], indent=1)
        root = TreeNode(role="button", name="Top", ref="e0", attrs={}, children=[child], indent=0)
        result = render_tree([root], depth=2)
        assert "Top" in result
        assert "Mid" in result
        assert "Deep" not in result

    def test_depth_limit_one(self):
        child = TreeNode(role="button", name="Child", ref="e1", attrs={}, indent=1)
        root = TreeNode(role="button", name="Root", ref="e0", attrs={}, children=[child], indent=0)
        result = render_tree([root], depth=1)
        assert "Root" in result
        assert "Child" not in result

    # --- General rendering ---
    def test_name_json_escaped(self):
        node = TreeNode(role="StaticText", name='He said "hi"', ref=None, attrs={}, indent=0)
        result = render_tree([node])
        assert '"He said \\"hi\\""' in result

    def test_attrs_rendering(self):
        node = TreeNode(role="heading", name="Title", ref="e1", attrs={"level": "1"}, indent=0)
        result = render_tree([node])
        assert "level=1" in result
        assert "ref=e1" in result

    def test_boolean_attr_rendering(self):
        node = TreeNode(role="checkbox", name="OK", ref="e1", attrs={"checked": True}, indent=0)
        result = render_tree([node])
        assert "checked" in result

    def test_roundtrip_simple(self):
        yaml = '- button "Submit" [ref=e1]\n- link "Go" [ref=e2]'
        roots = parse_yaml_tree(yaml)
        result = render_tree(roots)
        assert "- button" in result
        assert "- link" in result

    def test_empty_roots(self):
        assert render_tree([]) == ""


# ---------------------------------------------------------------------------
# compact_tree
# ---------------------------------------------------------------------------


class TestCompactTree:
    def test_keeps_lines_with_ref(self):
        rendered = "- button \"Go\" [ref=e1]\n- StaticText \"Label\""
        result = compact_tree(rendered)
        assert "ref=e1" in result
        assert "StaticText" not in result

    def test_keeps_ancestors(self):
        rendered = (
            "- generic\n"
            "  - button \"Go\" [ref=e1]"
        )
        result = compact_tree(rendered)
        assert "generic" in result
        assert "ref=e1" in result

    def test_empty_input(self):
        assert compact_tree("") == ""

    def test_no_refs_empty_output(self):
        rendered = "- StaticText \"Hello\"\n- StaticText \"World\""
        assert compact_tree(rendered) == ""

    def test_multiple_refs_nested(self):
        rendered = (
            "- generic\n"
            "  - button \"A\" [ref=e1]\n"
            "  - StaticText \"desc\"\n"
            "  - button \"B\" [ref=e2]"
        )
        result = compact_tree(rendered)
        assert "generic" in result
        assert "ref=e1" in result
        assert "ref=e2" in result
        assert "desc" not in result

    def test_deeply_nested_ancestors(self):
        rendered = (
            "- generic\n"
            "  - generic\n"
            "    - generic\n"
            "      - button \"Deep\" [ref=e5]"
        )
        result = compact_tree(rendered)
        assert result.count("generic") == 3
        assert "ref=e5" in result


# ---------------------------------------------------------------------------
# Integration: parse → render → compact
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_pipeline(self):
        yaml = (
            '- RootWebArea "Test Page" [ref=e1]\n'
            '  - heading "Welcome" [level=1, ref=e2]\n'
            '  - generic\n'
            '    - button "Submit" [ref=e3]\n'
            '    - StaticText "Info text"\n'
            '  - link "Help" [ref=e4]'
        )
        roots = parse_yaml_tree(yaml)
        rendered = render_tree(roots)
        # RootWebArea stripped
        assert "RootWebArea" not in rendered
        # generic with 2 children stays
        assert "generic" in rendered
        # StaticText visible text kept
        assert "Info text" in rendered

        compacted = compact_tree(rendered)
        # Only ref lines + ancestors
        assert "ref=e2" in compacted
        assert "ref=e3" in compacted
        assert "ref=e4" in compacted
        assert "Info text" not in compacted

    def test_interactive_pipeline(self):
        yaml = (
            '- RootWebArea "Page" [ref=e1]\n'
            '  - heading "Title" [level=1, ref=e2]\n'
            '  - StaticText "desc"\n'
            '  - button "Go" [ref=e3]'
        )
        roots = parse_yaml_tree(yaml)
        result = render_tree(roots, interactive=True)
        assert "heading" in result
        assert "button" in result
        assert "StaticText" not in result
