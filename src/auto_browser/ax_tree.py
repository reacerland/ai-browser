from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

INVISIBLE_CHARS = frozenset("\ufeff\u200b\u200c\u200d\u2060\u00a0")

INTERACTIVE_ROLES = frozenset({
    "button", "link", "textbox", "checkbox", "radio", "combobox",
    "listbox", "menuitem", "menuitemcheckbox", "menuitemradio",
    "option", "searchbox", "slider", "spinbutton", "switch",
    "tab", "treeitem", "Iframe",
})

CONTENT_ROLES = frozenset({
    "heading", "cell", "gridcell", "columnheader", "rowheader",
    "listitem", "article", "region", "main", "navigation",
})


@dataclass
class TreeNode:
    role: str
    name: str
    level: int | None = None
    checked: str | None = None
    expanded: bool | None = None
    selected: bool | None = None
    disabled: bool | None = None
    required: bool | None = None
    value_text: str | None = None
    backend_node_id: int | None = None
    children: list[int] = field(default_factory=list)
    parent_idx: int | None = None
    depth: int = 0
    has_ref: bool = False
    ref_id: str | None = None


def _ax_value(v: dict | None) -> str:
    if v is None:
        return ""
    return v.get("value", "") or ""


def _ax_prop(props: list[dict] | None, name: str) -> Any:
    if not props:
        return None
    for p in props:
        if p.get("name") == name:
            return p.get("value", {}).get("value")
    return None


def _is_invisible(text: str) -> bool:
    return all(c in INVISIBLE_CHARS for c in text)


def build_tree(raw_nodes: list[dict]) -> tuple[list[TreeNode], list[int]]:
    # Parse raw nodes, index by nodeId
    parsed: dict[str, int] = {}
    nodes: list[TreeNode] = []

    for raw in raw_nodes:
        role = _ax_value(raw.get("role"))
        name = _ax_value(raw.get("name"))
        ignored = raw.get("ignored", False)
        # Rule 1: skip ignored except RootWebArea
        if ignored and role != "RootWebArea":
            continue
        # Rule 2: skip InlineTextBox and empty StaticText
        if role == "InlineTextBox":
            continue
        if role == "StaticText" and _is_invisible(name):
            continue

        value = _ax_value(raw.get("value"))
        props = raw.get("properties")
        bid = raw.get("backendDOMNodeId")

        node = TreeNode(
            role=role,
            name=name,
            level=_ax_prop(props, "level"),
            checked=_ax_prop(props, "checked"),
            expanded=_ax_prop(props, "expanded"),
            selected=_ax_prop(props, "selected"),
            disabled=_ax_prop(props, "disabled"),
            required=_ax_prop(props, "required"),
            value_text=value if value else None,
            backend_node_id=bid,
        )
        parsed[raw["nodeId"]] = len(nodes)
        nodes.append(node)

    # Build parent-child using childIds
    child_id_to_idx: dict[str, int] = {}
    for node_id, idx in parsed.items():
        child_id_to_idx[node_id] = idx

    root_indices: list[int] = []
    for raw in raw_nodes:
        node_id = raw["nodeId"]
        if node_id not in parsed:
            continue
        idx = parsed[node_id]
        child_ids = raw.get("childIds", [])
        valid_children: list[int] = []
        for cid in child_ids:
            if cid in parsed:
                cidx = parsed[cid]
                valid_children.append(cidx)
                nodes[cidx].parent_idx = idx

        nodes[idx].children = valid_children
        if nodes[idx].parent_idx is None and nodes[idx].role == "RootWebArea":
            root_indices.append(idx)

    # Rule 3: merge consecutive StaticText
    for node in nodes:
        if not node.children:
            continue
        merged: list[int] = []
        i = 0
        while i < len(node.children):
            cidx = node.children[i]
            child = nodes[cidx]
            if child.role == "StaticText" and i + 1 < len(node.children):
                texts = [child.name]
                j = i + 1
                while j < len(node.children) and nodes[node.children[j]].role == "StaticText":
                    texts.append(nodes[node.children[j]].name)
                    j += 1
                if len(texts) > 1:
                    child.name = " ".join(texts)
                    merged.append(cidx)
                    i = j
                    continue
            merged.append(cidx)
            i += 1
        node.children = merged

    # Rule 4: deduplicate redundant StaticText
    for node in nodes:
        static_children = [i for i in node.children if nodes[i].role == "StaticText"]
        if len(static_children) == 1 and len(node.children) == 1:
            if nodes[static_children[0]].name == node.name:
                node.children = []

    # Rule 6: skip empty StaticText
    for node in nodes:
        node.children = [
            i for i in node.children
            if not (nodes[i].role == "StaticText" and _is_invisible(nodes[i].name))
        ]

    # Rule 5: collapse generic with <=1 children and no ref
    # (deferred -- applied during rendering to avoid index invalidation)

    # Calculate depth
    def calc_depth(idx: int, depth: int) -> None:
        nodes[idx].depth = depth
        for cidx in nodes[idx].children:
            calc_depth(cidx, depth + 1)

    for ri in root_indices:
        calc_depth(ri, 0)

    return nodes, root_indices
