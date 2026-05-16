# Snapshot Optimization Design

## Problem

The `ab snapshot` command returns large accessibility trees, consuming excessive tokens when fed to LLMs. The current implementation delegates entirely to Playwright's `aria_snapshot(mode="ai")` with only a basic `_compact()` filter that keeps ref-bearing lines and their ancestors.

## Goal

Reduce snapshot output size by 40-60% through structural filtering inspired by agent-browser's `render_tree()` approach, without switching away from Playwright.

## Approach: Enhanced YAML Post-Processing

Parse Playwright's YAML output into a `TreeNode` tree, apply agent-browser-style filtering rules, then re-render to YAML. This gives us structural control without needing raw CDP access.

### Data Flow

```
Playwright aria_snapshot(mode="ai") → YAML text
  → parse_yaml_tree() → list[TreeNode]
  → render_tree(filters) → filtered YAML text
  → compact() (optional post-render pass)
  → return
```

### TreeNode Structure

```python
@dataclass
class TreeNode:
    role: str
    name: str
    ref: str | None       # e.g. "e12"
    attrs: dict           # level, checked, expanded, selected, disabled, required
    children: list[TreeNode]
    indent: int           # original indentation level
```

Parent-child relationships are built from YAML indentation (2 spaces per level).

### Filtering Rules (applied during render_tree)

| # | Rule | Logic | Impact |
|---|------|-------|--------|
| 1 | Collapse empty nodes | Skip nodes with empty role, render children directly | Noise removal |
| 2 | Collapse generic nodes | `generic` with no ref and <=1 children → render children directly | Remove `<div>` wrappers |
| 3 | Skip invisible text | `StaticText` with only whitespace/zero-width chars → skip | Noise removal |
| 4 | Strip RootWebArea/WebArea | Top-level wrappers → render children directly | Reduce indentation |
| 5 | Interactive mode | Only render nodes with ref; non-interactive nodes still traverse children | Biggest token savings |
| 6 | Depth limit | Configurable max indentation depth | Control verbosity |

**Default mode** applies rules 1-4. **Interactive mode** (`--interactive`) adds rule 5. **Depth** (`--depth N`) adds rule 6.

### Rendering Format

Each rendered node follows agent-browser's format:

```
- role "name" [attr=val, ref=eN]
```

- `name` is JSON-escaped if present
- `attrs` includes level, checked, expanded, selected, disabled, required
- `ref` is included only for interactive/content elements

## API Changes

### `take_snapshot()` signature

```python
def take_snapshot(
    page, ref_map, *,
    compact=False,
    interactive=False,
    depth=None,
    selector=None,
) -> str
```

- `selector`: if provided, use `page.locator(selector)` instead of `page.locator("body")` (fixes currently unused param)

### Daemon `_snapshot()`

```python
def _snapshot(self, params: dict) -> dict:
    content = take_snapshot(
        self.bm.page, self.ref_map,
        compact=params.get("compact", False),
        interactive=params.get("interactive", False),
        depth=params.get("depth"),
    )
    return {"status": "ok", "content": content}
```

### CLI `snapshot` command

```python
@cli.command()
@click.option("--compact", is_flag=True, help="Compact output mode.")
@click.option("--interactive", is_flag=True, help="Only show interactive elements.")
@click.option("--depth", type=int, help="Max tree depth.")
@click.option("--selector", help="CSS selector to scope the snapshot.")
def snapshot(ctx, compact, interactive, depth, selector):
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_browser/snapshot_tree.py` | **New** (~120 lines) | TreeNode, parse_yaml_tree, render_tree, compact |
| `src/ai_browser/ax_tree.py` | **Modify** | take_snapshot uses snapshot_tree; remove _compact |
| `src/ai_browser/ref_map.py` | **Modify** | parse_snapshot updated to work from TreeNode tree |
| `src/ai_browser/daemon.py` | **Modify** | _snapshot passes interactive/depth/selector params |
| `src/ai_browser/cli.py` | **Modify** | Add --interactive, --depth options |
| `tests/test_snapshot_tree.py` | **New** (~80 lines) | Unit tests for parse, filter rules, render |

## Out of Scope

- CDP-based cursor-interactive element discovery (adds completeness, not token reduction)
- Hidden input promotion (same reasoning)
- Snapshot diffing
- Iframe handling (beyond what Playwright already provides)
- Caching
