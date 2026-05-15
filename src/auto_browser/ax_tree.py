from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from auto_browser.ref_map import RefMap, RoleNameTracker

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

    # Build lookup: nodeId -> raw node (for resolving skipped nodes)
    raw_by_id: dict[str, dict] = {r["nodeId"]: r for r in raw_nodes}

    # Build parent-child using childIds, bypassing skipped (ignored) nodes
    def _resolve_children(raw_entry: dict) -> list[int]:
        collected: list[int] = []
        for cid in raw_entry.get("childIds", []):
            if cid in parsed:
                collected.append(parsed[cid])
            elif cid in raw_by_id:
                # Skipped node — adopt its children recursively
                collected.extend(_resolve_children(raw_by_id[cid]))
        return collected

    root_indices: list[int] = []
    for raw in raw_nodes:
        node_id = raw["nodeId"]
        if node_id not in parsed:
            continue
        idx = parsed[node_id]
        valid_children = _resolve_children(raw)
        for cidx in valid_children:
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


def assign_refs(nodes: list[TreeNode], ref_map: RefMap) -> None:
    ref_map.clear()
    next_ref = ref_map.next_ref_num()
    tracker = RoleNameTracker()

    for idx, node in enumerate(nodes):
        should_ref = False
        if node.role in INTERACTIVE_ROLES:
            should_ref = True
        elif node.role in CONTENT_ROLES and node.name:
            should_ref = True

        if should_ref:
            nth_raw = tracker.track(node.role, node.name, idx)
            ref_id = f"e{next_ref}"
            next_ref += 1
            nth = tracker.get_actual_nth(node.role, node.name, nth_raw)
            ref_map.add(ref_id, node.backend_node_id, node.role, node.name, nth, None)
            node.has_ref = True
            node.ref_id = ref_id

    ref_map.set_next_ref_num(next_ref)


def _should_skip_render(node: TreeNode, nodes: list[TreeNode]) -> bool:
    if node.role == "generic" and not node.has_ref:
        if len(node.children) <= 1:
            return True
    return False


def _render_node(node: TreeNode, ref_map: RefMap) -> str:
    parts = []
    role = node.role
    if node.name:
        parts.append(f'{role} "{node.name}"')
    else:
        parts.append(role)

    attrs: list[str] = []
    if node.level is not None:
        attrs.append(f"level={node.level}")
    if node.checked is not None:
        attrs.append(f"checked={node.checked}")
    if node.expanded is not None:
        attrs.append(f"expanded={'true' if node.expanded else 'false'}")
    if node.selected:
        attrs.append("selected")
    if node.disabled:
        attrs.append("disabled")
    if node.required:
        attrs.append("required")
    if node.ref_id:
        entry = ref_map.get(node.ref_id)
        if entry and entry.nth is not None:
            attrs.append(f"nth={entry.nth}")
        attrs.append(f"ref={node.ref_id}")

    if attrs:
        parts.append("[" + ", ".join(attrs) + "]")

    line = " ".join(parts)
    if node.value_text:
        line += f": {node.value_text}"
    return line


def render_tree(nodes: list[TreeNode], root_indices: list[int], ref_map: RefMap) -> str:
    lines: list[str] = []

    def _render(idx: int, depth: int) -> None:
        node = nodes[idx]
        if _should_skip_render(node, nodes):
            for cidx in node.children:
                _render(cidx, depth)
            return
        if node.role in ("RootWebArea", "WebArea"):
            for cidx in node.children:
                _render(cidx, depth)
            return

        indent = "  " * depth
        lines.append(f"{indent}- {_render_node(node, ref_map)}")
        for cidx in node.children:
            _render(cidx, depth + 1)

    for ri in root_indices:
        _render(ri, 0)

    return "\n".join(lines)


def compact_tree(output: str) -> str:
    lines = output.splitlines()
    result_indices: set[int] = set()

    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if "- " in stripped:
            content_part = stripped.split("- ", 1)[1]
            if "ref=" in content_part or ": " in content_part:
                result_indices.add(i)
                current_indent = len(line) - len(line.lstrip())
                for j in range(i - 1, -1, -1):
                    jline = lines[j]
                    j_indent = len(jline) - len(jline.lstrip())
                    if j_indent < current_indent:
                        result_indices.add(j)
                        current_indent = j_indent

    return "\n".join(lines[i] for i in sorted(result_indices))


def take_snapshot(cdp, ref_map: RefMap, compact: bool = False, selector: str | None = None) -> str:
    cdp.send("DOM.enable")
    cdp.send("Accessibility.enable")

    result = cdp.send("Accessibility.getFullAXTree")
    raw_nodes = result.get("nodes", [])

    nodes, root_indices = build_tree(raw_nodes)
    ref_map.clear()
    assign_refs(nodes, ref_map)

    output = render_tree(nodes, root_indices, ref_map)

    if compact:
        output = compact_tree(output)

    return output
