# Humanize Interaction Support

**Date**: 2026-05-16
**Status**: Approved

## Problem

Browser automation interactions (click, type, fill, hover, scroll) appear mechanical and can be detected by anti-bot systems. The `cloakbrowser` dependency already includes a `human` module that monkey-patches Playwright's page methods with human-like behavior (variable delays, mouse wobble, typing mistakes, etc.), but auto_browser doesn't expose it.

## Solution

Add `--humanize` and `--human-preset` flags to the CLI `open` command and daemon startup. When enabled, call `cloakbrowser.human.patch_page()` on the session's page after browser launch.

### Architecture

```
CLI: ab open URL --humanize --human-preset careful
  → daemon subprocess with --humanize --human-preset careful
    → BrowserManager starts browser
    → resolve_config(preset="careful") → HumanConfig
    → patch_page(page, config, cursor_state)
    → all subsequent click/type/fill/hover/scroll are humanized
```

### Components

#### 1. CLI flags on `open` command

Add two options to the `open` Click command:
- `--humanize` (boolean flag): Enable human-like interactions
- `--human-preset` (choice: "default" | "careful"): Which preset to use (default: "default")

Pass these to the daemon subprocess via `--humanize` and `--human-preset` arguments.

#### 2. Daemon accepts humanize params

`Daemon.__init__` gains `humanize: bool` and `human_preset: str` parameters. After browser start, if `humanize=True`:
```python
from cloakbrowser.human import resolve_config, patch_page, _CursorState

config = resolve_config(preset=human_preset)
cursor = _CursorState()
patch_page(self.bm.page, config, cursor)
```

#### 3. No changes to Interactions

`patch_page` replaces `page.click`, `page.fill`, etc. with humanized versions. Playwright's `locator.click()` internally delegates through the same patched methods, so `Interactions` code needs no changes.

### Files Changed

| File | Change |
|------|--------|
| `cli.py` | Add `--humanize`/`--human-preset` flags to `open` and `_daemon` commands |
| `daemon.py` | Accept humanize params, call `patch_page` after browser start |
| `browser_manager.py` | No changes |

### Presets

- `"default"`: Moderate humanization, good balance of speed and realism
- `"careful"`: Slower, more cautious — higher delays, more pauses, less overshoot
