from __future__ import annotations

from playwright.sync_api import Page

from ai_browser.ref_map import RefMap, parse_snapshot
from ai_browser.snapshot_tree import compact_tree, parse_yaml_tree, render_tree


def take_snapshot(
    page: Page,
    ref_map: RefMap,
    *,
    compact: bool = False,
    interactive: bool = False,
    depth: int | None = None,
    selector: str | None = None,
) -> str:
    """Take an accessibility snapshot of the page.

    Parses the raw YAML through the snapshot_tree pipeline for filtering
    and optional compacting, and populates *ref_map* with ref-bearing nodes.
    """
    locator = page.locator(selector) if selector else page.locator("body")
    raw_yaml = locator.aria_snapshot(mode="ai")
    roots = parse_yaml_tree(raw_yaml)

    from ai_browser.ref_map import populate_ref_map_from_tree
    populate_ref_map_from_tree(roots, ref_map)

    rendered = render_tree(roots, interactive=interactive, depth=depth)
    if compact:
        rendered = compact_tree(rendered)
    return rendered


# Public alias for backward compatibility with existing tests
parse_snapshot_yaml = parse_snapshot
