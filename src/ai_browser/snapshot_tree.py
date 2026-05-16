"""Parse, render, and compact Playwright aria_snapshot YAML trees."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class TreeNode:
    """A single node in a parsed snapshot tree."""

    role: str
    name: str
    ref: str | None  # e.g. "e12"
    attrs: dict  # level, checked, expanded, etc.
    children: list[TreeNode] = field(default_factory=list)
    indent: int = 0  # original indentation level


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Matches lines like:
#   - button "Submit" [ref=e1, level=1, checked]
#   - heading "Welcome" [level=1, ref=e2]
#   - textbox [ref=e5]
#   - StaticText "Hello"
#   - generic
_LINE_RE = re.compile(
    r'^(?P<prefix>\s*)-\s+'
    r'(?P<role>\S+)'              # role (required)
    r'(?:\s+"(?P<name>[^"]*)")?'  # optional "name"
    r'(?:\s+\[(?P<attrs>[^\]]*)\])?'  # optional [attrs] block
)

_INDENT_SIZE = 2  # spaces per indent level


def _parse_attrs(raw: str | None) -> tuple[dict, str | None]:
    """Parse the bracket attrs block into (attrs_dict, ref_value).

    Handles key=value pairs and bare key (boolean True).
    Extracts ``ref=`` as the *ref* field (removed from attrs dict).
    """
    attrs: dict = {}
    ref: str | None = None
    if not raw:
        return attrs, ref
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            key, value = token.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "ref":
                ref = value
            else:
                attrs[key] = value
        else:
            attrs[token] = True
    return attrs, ref


def parse_yaml_tree(yaml_text: str) -> list[TreeNode]:
    """Parse Playwright aria_snapshot YAML text into a list of root TreeNodes."""
    if not yaml_text or not yaml_text.strip():
        return []

    roots: list[TreeNode] = []
    # Stack of (indent_level, node). The last entry is the current parent.
    stack: list[tuple[int, TreeNode]] = []

    for line in yaml_text.splitlines():
        if not line.strip():
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue

        role = m.group("role")
        name = m.group("name") or ""
        raw_attrs = m.group("attrs")
        indent_spaces = len(m.group("prefix"))
        indent_level = indent_spaces // _INDENT_SIZE

        attrs, ref = _parse_attrs(raw_attrs)
        node = TreeNode(
            role=role,
            name=name,
            ref=ref,
            attrs=attrs,
            children=[],
            indent=indent_level,
        )

        # Pop stack until we find the parent (indent < current)
        while stack and stack[-1][0] >= indent_level:
            stack.pop()

        if stack:
            stack[-1][1].children.append(node)
        else:
            roots.append(node)

        stack.append((indent_level, node))

    return roots


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# Zero-width and invisible Unicode categories
_INVISIBLE_RE = re.compile(
    r"[\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff\u00ad\s]"
)


def _has_visible_chars(text: str) -> bool:
    """Return True if *text* contains at least one visible character."""
    return bool(_INVISIBLE_RE.sub("", text))


def _render_node(
    node: TreeNode,
    out_lines: list[str],
    indent: int,
    *,
    interactive: bool = False,
    depth: int | None = None,
) -> None:
    """Recursively render *node* into *out_lines* at the given indent."""
    # Apply filtering / collapsing rules, yielding child nodes to render
    # directly when the current node is suppressed.

    # Rule 6 — depth limit
    if depth is not None and indent >= depth:
        return

    # Rule 4 — strip RootWebArea / WebArea
    if node.role in ("RootWebArea", "WebArea"):
        for child in node.children:
            _render_node(child, out_lines, indent, interactive=interactive, depth=depth)
        return

    # Rule 1 — empty role collapse
    if not node.role:
        for child in node.children:
            _render_node(child, out_lines, indent, interactive=interactive, depth=depth)
        return

    # Rule 2 — generic with no ref and <=1 children → collapse
    if node.role == "generic" and node.ref is None and len(node.children) <= 1:
        for child in node.children:
            _render_node(child, out_lines, indent, interactive=interactive, depth=depth)
        return

    # Rule 3 — skip invisible StaticText (whitespace / zero-width chars only)
    if node.role == "StaticText" and not _has_visible_chars(node.name):
        return

    # Rule 5 — interactive mode: only render nodes with ref
    if interactive and node.ref is None:
        # Still traverse children; they may have refs
        for child in node.children:
            _render_node(child, out_lines, indent, interactive=interactive, depth=depth)
        return

    # Build the line for this node
    prefix = "  " * indent + "- "
    parts: list[str] = [node.role]
    if node.name:
        parts.append(json.dumps(node.name, ensure_ascii=False))

    # Collect attr tokens
    attr_tokens: list[str] = []
    for key, value in node.attrs.items():
        if value is True:
            attr_tokens.append(key)
        else:
            attr_tokens.append(f"{key}={value}")
    if node.ref is not None:
        attr_tokens.append(f"ref={node.ref}")

    if attr_tokens:
        parts.append("[" + ", ".join(attr_tokens) + "]")

    out_lines.append(prefix + " ".join(parts))

    # Render children at indent + 1
    for child in node.children:
        _render_node(child, out_lines, indent + 1, interactive=interactive, depth=depth)


def render_tree(
    roots: list[TreeNode],
    *,
    interactive: bool = False,
    depth: int | None = None,
) -> str:
    """Render a list of root TreeNodes back into YAML text."""
    out_lines: list[str] = []
    for root in roots:
        _render_node(root, out_lines, 0, interactive=interactive, depth=depth)
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Compacting
# ---------------------------------------------------------------------------

def compact_tree(rendered: str) -> str:
    """Post-render pass: keep only lines with ref= and their ancestor lines."""
    lines = rendered.splitlines()
    if not lines:
        return ""

    keep: set[int] = set()

    for i, line in enumerate(lines):
        if "ref=" not in line:
            continue
        keep.add(i)
        # Walk backwards to include ancestors (less-indented lines)
        current_indent = len(line) - len(line.lstrip())
        for j in range(i - 1, -1, -1):
            j_line = lines[j]
            if not j_line.strip():
                continue
            j_indent = len(j_line) - len(j_line.lstrip())
            if j_indent < current_indent:
                keep.add(j)
                current_indent = j_indent

    return "\n".join(lines[i] for i in sorted(keep))
