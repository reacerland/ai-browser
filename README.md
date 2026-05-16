# ai-browser

[中文](README.zh-CN.md)

Browser automation CLI designed for AI agents. Provides a client-daemon architecture where a persistent daemon manages the browser lifecycle, and a stateless CLI client sends commands via JSON-RPC over Unix domain sockets.

## Design Goals

- **AI-agent-first**: CLI interface with structured JSON output, designed for programmatic consumption rather than human interactive use
- **Accessibility-driven**: Uses accessibility tree snapshots with ref-based element identification, enabling AI agents to understand and interact with pages without visual parsing
- **Session isolation**: Each session runs an independent daemon process with its own browser instance, Unix socket, and optional persistent user data directory
- **Stealth by default**: Built on cloakbrowser (Playwright-based stealth Chromium launcher) to avoid bot detection
- **Human-like interactions**: Optional humanization mode with configurable presets for natural mouse movement and typing patterns

## Use Cases

- AI agents browsing the web autonomously (research, form filling, data extraction)
- Automated QA and E2E testing driven by AI
- Web scraping with JavaScript-rendered pages
- Browser task automation in headless environments
- Multi-session workflows requiring independent browser contexts (e.g., testing with multiple accounts)

## Architecture

```
┌─────────────┐  Unix Socket   ┌──────────────────────────────────┐
│  CLI Client │ ◄─JSON-RPC───► │        Daemon Process             │
│  (stateless)│                │                                  │
│             │                │  JSON-RPC Server                  │
│  ai-browser open   │                │    └─► Browser Manager            │
│  ai-browser click  │                │         └─► Playwright Browser    │
│  ai-browser snap   │                │              └─► CDP Session      │
│  ...        │                │                  └─► AX Tree      │
└─────────────┘                └──────────────────────────────────┘
```

## Installation

Requires Python 3.13+.

```bash
# Clone the repository
git clone https://github.com/reacerland/ai-browser.git
cd ai-browser

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

## Usage

The `ai-browser` command is also available as `ai-browser` for convenience.

### Start browsing

```bash
# Open a URL (starts daemon and browser automatically)
ai-browser open https://example.com

# Open in headed mode (visible browser window)
ai-browser open https://example.com --headed

# Open with a named session (persistent profile at ~/.ab/work/chrome-data/)
ai-browser open https://example.com --session work

# Open with human-like interactions enabled
ai-browser open https://example.com --humanize --human-preset careful
```

### Interact with pages

```bash
# Get accessibility tree snapshot to understand page structure
ai-browser snapshot
ai-browser snapshot --compact              # Condensed view
ai-browser snapshot --selector "nav a"     # Filter by CSS selector

# Find elements by locator
ai-browser find role button --name "Submit"
ai-browser find text "Sign in"
ai-browser find label "Email"

# Interact with elements using ref identifiers from snapshot
ai-browser click A1                        # Click element with ref A1
ai-browser type A2 "hello@example.com"     # Type into element
ai-browser type A2 "text" --clear          # Clear field then type
ai-browser fill A3 "value"                 # Replace field content
ai-browser hover A4                        # Hover over element
ai-browser dblclick A5                     # Double-click element
ai-browser drag A6 A7                      # Drag element A6 to A7

# Form interactions
ai-browser select A8 "option_value"        # Select dropdown option
ai-browser check A9                        # Check a checkbox
ai-browser uncheck A9                      # Uncheck a checkbox
ai-browser upload A10 /path/to/file        # Upload file(s)

# Navigation
ai-browser scroll down --amount 500        # Scroll the page
ai-browser scroll-into-view A11            # Scroll element into view
ai-browser back                            # Go back in history
ai-browser forward                         # Go forward in history
ai-browser reload                          # Reload current page
ai-browser press Enter                     # Press a keyboard key
```

### Get page and element info

```bash
ai-browser get url                         # Current page URL
ai-browser get title                       # Page title
ai-browser get text A1                     # Element text content
ai-browser get html A1                     # Element inner HTML
ai-browser get value A1                    # Form element value
ai-browser get attr A1 --name href         # Element attribute
ai-browser get box A1                      # Element bounding box

ai-browser is visible A1                   # Check if element is visible
ai-browser is enabled A1                   # Check if element is enabled
ai-browser is checked A1                   # Check if checkbox is checked

ai-browser count "div.card"                # Count elements by CSS selector
ai-browser screenshot                      # Take a screenshot
ai-browser screenshot -o /tmp/page.png     # Save screenshot to file
ai-browser eval "document.title"           # Evaluate JavaScript
ai-browser download A1 /tmp/file.zip       # Download file by clicking element
```

### Session management

```bash
ai-browser ping                            # Check if daemon is alive
ai-browser close                           # Close default session
ai-browser close --session work            # Close named session
```

### Multi-session

```bash
# Each named session runs independently with its own browser
ai-browser open https://site-a.com --session alpha
ai-browser open https://site-b.com --session beta

ai-browser snapshot --session alpha        # Interact with alpha
ai-browser snapshot --session beta         # Interact with beta

ai-browser close --session alpha           # Close alpha, keep beta running
```

## Command Reference

| Command | Description |
|---------|-------------|
| `open <url>` | Start daemon + browser, navigate to URL |
| `close` | Close browser and stop daemon |
| `snapshot` | Get accessibility tree snapshot |
| `find <locator> <value>` | Find elements by role/text/label/etc. |
| `click <ref>` | Click an element |
| `type <ref> <text>` | Type text into an element |
| `fill <ref> <value>` | Replace element content |
| `scroll <up\|down>` | Scroll the page |
| `scroll-into-view <ref>` | Scroll element into view |
| `hover <ref>` | Hover over an element |
| `dblclick <ref>` | Double-click an element |
| `drag <src> <dst>` | Drag element to another |
| `select <ref> <value>` | Select dropdown option |
| `check <ref>` | Check a checkbox |
| `uncheck <ref>` | Uncheck a checkbox |
| `upload <ref> <files>` | Upload files to input |
| `download <ref> <path>` | Download file by clicking |
| `press <key>` | Press a keyboard key |
| `get <what> [ref]` | Get element property or page info |
| `is <what> <ref>` | Check element state |
| `count <selector>` | Count matching elements |
| `screenshot` | Take a screenshot |
| `eval <expression>` | Evaluate JavaScript |
| `back` | Go back in history |
| `forward` | Go forward in history |
| `reload` | Reload the page |
| `wait <target>` | Wait for element or time |
| `ping` | Check daemon health |

## Output Format

All commands output JSON to stdout:

```json
{"status": "ok", "data": {"title": "Example Page"}}
```

Error responses:

```json
{"status": "error", "error": {"code": -32000, "message": "Daemon not running. Use 'ai-browser open' first."}}
```

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run E2E tests
uv run pytest tests/e2e/
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

MIT License

Copyright (c) 2026 reacerland

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
