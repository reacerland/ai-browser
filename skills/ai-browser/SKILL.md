---
name: ai-browser
description: Use when navigating websites, filling forms, clicking buttons, scraping page content, or performing any browser automation. Triggers include "open URL", "click on page", "browse to", "check website", "fill form", "web search", "take screenshot", "download file", or any task requiring a real browser session.
---

# ai-browser

Headless browser automation CLI for AI agents. Uses Playwright (cloakbrowser) under the hood with a ref-based interaction model.

Binary: `ai-browser` or `aib`. All commands output JSON `{"status":"ok","data":{...}}`.

## Setup

Before using any command, ensure ai-browser is installed. Check first:

```bash
ai-browser ping 2>/dev/null || echo "NOT_INSTALLED"
```

If not installed, determine the project location and install:

**From source (project directory):**

```bash
cd /path/to/ai-browser
uv sync
```

**From source with pip:**

```bash
cd /path/to/ai-browser
pip install -e .
```

**Requirements:** Python >= 3.13, cloakbrowser >= 0.3.28.

After install, verify the CLI is available:

```bash
ai-browser --help
```

If the project is not available locally, ask the user for the ai-browser repository location or clone URL.

## Core Loop

```
open URL → snapshot → interact by ref → snapshot → repeat → close
```

Every interaction uses **refs** (`e1`, `e5`, etc.) from the accessibility tree snapshot. You cannot guess refs — you must snapshot first.

## Quick Reference

### Lifecycle

| Command | Example |
|---------|---------|
| Open browser + navigate | `ai-browser open https://example.com` |
| Close session | `ai-browser close` |
| Close named session | `ai-browser close -s shopping` |
| Check daemon alive | `ai-browser ping` |

`open` auto-prepends `https://`. Flags: `--headed` (visible window), `--humanize` (human-like input).

### Inspect Page

| Command | Example |
|---------|---------|
| Accessibility tree | `ai-browser snapshot` |
| Minimal tree (refs only) | `ai-browser snapshot --interactive --compact` |
| Find elements | `ai-browser find role button` |
| Get page URL | `ai-browser get url` |
| Get page title | `ai-browser get title` |
| Get element text | `ai-browser get text e5` |
| Get element HTML | `ai-browser get html e5` |
| Get input value | `ai-browser get value e3` |
| Get attribute | `ai-browser get attr e5 --name href` |
| Check visibility | `ai-browser is visible e3` |
| Count elements | `ai-browser count "button.submit"` |
| Run JavaScript | `ai-browser eval "document.title"` |
| Screenshot | `ai-browser screenshot -o page.png` |

### Interact (all need a ref)

| Command | Example |
|---------|---------|
| Click | `ai-browser click e3` |
| Type text | `ai-browser type e5 "hello"` |
| Fill (replace) | `ai-browser fill e5 "new value"` |
| Clear + type | `ai-browser type e5 "text" --clear` |
| Select dropdown | `ai-browser select e2 "Option A"` |
| Check/uncheck | `ai-browser check e4` / `ai-browser uncheck e4` |
| Hover | `ai-browser hover e3` |
| Double-click | `ai-browser dblclick e3` |
| Drag and drop | `ai-browser drag e2 e5` |
| Upload file | `ai-browser upload e1 /path/to/file.pdf` |
| Download | `ai-browser download e3 ./save.zip` |
| Press key | `ai-browser press Enter` |
| Scroll | `ai-browser scroll down --amount 500` |

### Navigation

| Command | Example |
|---------|---------|
| Go back | `ai-browser back` |
| Go forward | `ai-browser forward` |
| Reload | `ai-browser reload` |
| Wait for element | `ai-browser wait e7 --timeout 5000` |
| Scroll element into view | `ai-browser scroll-into-view e5` |

### Named Sessions

Append `-s <name>` to any command for parallel sessions. Each gets its own browser context and data dir at `~/.ai-browser/<name>/chrome-data/`.

## Typical Workflows

### Search and extract

```bash
ai-browser open https://google.com
ai-browser snapshot --interactive --compact
# Find the search input ref from snapshot, e.g. e3
ai-browser type e3 "playwright testing" --clear
ai-browser press Enter
ai-browser wait e5                          # Wait for results
ai-browser snapshot --interactive --compact  # See result links
ai-browser get text e7                      # Extract first result title
ai-browser close
```

### Fill a form

```bash
ai-browser open https://example.com/form
ai-browser snapshot --interactive --compact
# Identify form field refs from snapshot
ai-browser fill e3 "John Doe"
ai-browser fill e5 "john@example.com"
ai-browser select e7 "United States"
ai-browser check e9                         # Accept terms
ai-browser click e11                        # Submit
ai-browser snapshot                         # Verify result
ai-browser close
```

### Scrape page content

```bash
ai-browser open https://news.site.com
ai-browser snapshot --compact               # Full tree with compact mode
# Read text from specific elements
ai-browser get text e3                      # Headline
ai-browser get text e5                      # Article body
ai-browser get attr e7 --name href          # Link URL
ai-browser close
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using ref without snapshot | Always `snapshot` first to get fresh refs |
| Stale refs after navigation | Re-snapshot after any page change |
| Guessing ref IDs | Refs are dynamic — never hardcode |
| Forgetting `--clear` when replacing text | Use `fill` to replace, or `type --clear` |
| Not waiting after click | Use `wait <ref>` or `snapshot` to verify |
| Long snapshot eating tokens | Use `--interactive --compact` for minimal output |
| Missing scheme in URL | `open` auto-adds `https://`, but be explicit for clarity |

## Token-Saving Tips

- `--interactive --compact` shows only ref-bearing elements — use this by default
- Remove `--compact` when you need full page structure context
- Use `get text <ref>` to extract specific data instead of re-snapshotting
- `find` locates elements without a full snapshot

## Error Handling

All errors return `{"status":"error","error":{"code":...,"message":"..."}}`.

Common errors:
- `Daemon not running` → run `ai-browser open <url>` first
- `Ref not found: eN` → re-snapshot, refs expire after navigation
- `Timeout waiting for element` → increase `--timeout` or check if element exists
- `Element not visible` → use `scroll-into-view` before interacting
