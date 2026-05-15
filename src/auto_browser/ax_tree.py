from __future__ import annotations

from playwright.sync_api import Page

from auto_browser.ref_map import RefMap, parse_snapshot


def take_snapshot(page: Page, ref_map: RefMap, compact: bool = False) -> str:
    snapshot = page.locator("body").aria_snapshot(mode="ai")
    parsed = parse_snapshot(snapshot)
    # Copy parsed entries into the provided ref_map
    ref_map.clear()
    for ref_id, entry in parsed._entries.items():
        ref_map.add(ref_id, entry.role, entry.name, entry.nth)
    if compact:
        snapshot = _compact(snapshot)
    return snapshot


def _compact(yaml_text: str) -> str:
    lines = yaml_text.splitlines()
    result_indices: set[int] = set()

    for i, line in enumerate(lines):
        if "[ref=" in line:
            result_indices.add(i)
            current_indent = len(line) - len(line.lstrip())
            for j in range(i - 1, -1, -1):
                jline = lines[j]
                j_indent = len(jline) - len(jline.lstrip())
                if j_indent < current_indent:
                    result_indices.add(j)
                    current_indent = j_indent

    return "\n".join(lines[i] for i in sorted(result_indices))


# Public alias for testing
parse_snapshot_yaml = parse_snapshot
