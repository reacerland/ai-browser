# Playwright Native Accessibility Interactions

**Date**: 2026-05-16
**Status**: Approved

## Problem

The current click/type/fill/hover interactions use coordinate-based mouse event dispatch via CDP. This is unreliable because:

1. Coordinates are affected by viewport scrolling, CSS transforms, and fixed/sticky positioning
2. Coordinate clicks bypass browser event dispatch — no `:hover`, focus, or proper click handler activation
3. SPA router links often don't respond to synthetic coordinate clicks
4. The `DOM.getBoxModel` call returns stale or incorrect positions for off-screen elements

Example: clicking `e12` (a "贴吧" link on Baidu News) returned coordinates `(1395.0, 15.5)` with no visible page change.

## Solution

Replace the custom CDP-based accessibility tree and coordinate interactions with Playwright's built-in `aria_snapshot(mode="ai")` and locator-based interactions.

### Architecture

```
Before:
  snapshot → CDP Accessibility.getFullAXTree → custom build_tree → custom render → ref_map
  click    → ref_map lookup → backendNodeId → DOM.getBoxModel → coordinates → Input.dispatchMouseEvent

After:
  snapshot → page.locator("body").aria_snapshot(mode="ai") → YAML output
  click    → parse YAML for ref → page.get_by_role(role, name=name).nth(n).click()
```

### Components

#### 1. Snapshot: `aria_snapshot(mode="ai")`

Replace `take_snapshot()` in `ax_tree.py` with a single call:

```python
def take_snapshot(page, compact=False):
    snapshot = page.locator("body").aria_snapshot(mode="ai")
    # parse YAML to build ref_map
    # optionally apply compact filtering
    return snapshot
```

Playwright's `mode="ai"` produces output like:
```
- link "贴吧" [ref=e12]
- textbox [ref=e129]
- button "百度一下" [ref=e130]
```

This replaces:
- `build_tree()` (~80 lines) — custom AX tree parsing
- `assign_refs()` (~20 lines) — custom ref assignment
- `render_tree()` (~25 lines) — custom tree rendering
- `compact_tree()` (~20 lines) — custom compact filtering

#### 2. Ref Resolution: Parse YAML Snapshot

Replace `ref_map.py`'s `RefEntry(backend_node_id, role, name, nth)` with a simpler structure:

```python
@dataclass
class RefEntry:
    role: str
    name: str
    nth: int  # 0-based occurrence of (role, name) in snapshot
```

Parse the YAML snapshot to populate `{ref_id -> RefEntry}`. Each line like `link "贴吧" [ref=e12]` maps to `RefEntry(role="link", name="贴吧", nth=0)`.

#### 3. Interactions: Playwright Locators

Replace all coordinate-based interactions with Playwright locator methods:

```python
class Interactions:
    def __init__(self, page, ref_map):
        self.page = page
        self.ref_map = ref_map

    def click(self, ref):
        entry = self._resolve(ref)
        self._locator(entry).click()

    def fill(self, ref, value):
        entry = self._resolve(ref)
        self._locator(entry).fill(value)

    def type(self, ref, text, clear=False):
        entry = self._resolve(ref)
        if clear:
            self._locator(entry).fill("")
        self._locator(entry).press_sequentially(text)

    def hover(self, ref):
        entry = self._resolve(ref)
        self._locator(entry).hover()

    def _locator(self, entry):
        loc = self.page.get_by_role(entry.role, name=entry.name)
        if entry.nth > 0:
            loc = loc.nth(entry.nth)
        return loc

    def _resolve(self, ref):
        entry = self.ref_map.get(ref)
        if not entry:
            raise ValueError(f"Unknown ref: {ref}")
        return entry
```

Key improvements:
- `locator.click()` auto-waits for element to be visible, scrolled into view, and stable
- `locator.fill()` properly sets input values and dispatches change events
- No coordinate math, no stale position issues
- Works with all JS frameworks and routing libraries

#### 4. Scroll and eval

- `scroll`: Replace CDP `mouseWheel` with `page.mouse.wheel(0, delta_y)`
- `eval_js`: Keep `page.evaluate()` (already using Playwright, no change needed)

#### 5. Compact mode

Implement compact filtering on the YAML output. The current `compact_tree()` logic (keep lines with `ref=` and their ancestors) can be adapted to work on the YAML text.

### Files Changed

| File | Change |
|------|--------|
| `ax_tree.py` | Gut and simplify to thin wrapper around `aria_snapshot()` + YAML parsing |
| `ref_map.py` | Simplify `RefEntry` to `(role, name, nth)`, remove `backend_node_id` |
| `interactions.py` | Replace CDP-based coordinate interactions with Playwright locators |
| `daemon.py` | Remove `CDPSession` usage; pass `page` to `Interactions` instead of `cdp + ref_map` |
| `browser_manager.py` | May be able to remove `get_cdp_session()` method |

### Files Removed (code)

- ~300 lines of custom AX tree parsing in `ax_tree.py`
- Coordinate math (`_box_center`, `_resolve_center`) in `interactions.py`
- CDP mouse event dispatch code in `interactions.py`
- `_find_node_by_role_name` re-query fallback in `interactions.py`

### Migration Notes

- The snapshot output format changes from our custom format to Playwright's YAML format
- User-facing CLI commands (`snapshot`, `click`, `fill`, etc.) remain the same
- The `ref=eN` format is preserved — Playwright's `mode="ai"` uses the same format
- No changes to `cli.py`, `client.py`, or `__main__.py`

### Risks and Mitigations

1. **Playwright `aria_snapshot` availability**: Requires Playwright >= 1.49 (ai mode). Mitigation: check `pyproject.toml` version constraint.
2. **YAML parsing**: Need to parse Playwright's YAML snapshot format. Mitigation: the format is simple line-based YAML, a regex parser is sufficient.
3. **nth calculation**: When multiple elements have the same role+name, we need correct nth indexing. Mitigation: count occurrences during YAML parsing, 0-based.
