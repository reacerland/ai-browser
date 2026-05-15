# Humanize Interaction Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--humanize` and `--human-preset` flags to the CLI that enable cloakbrowser's human-like interaction behavior for the entire browser session.

**Architecture:** CLI passes humanize params to daemon subprocess. Daemon calls `cloakbrowser.human.resolve_config(preset)` → `patch_page(page, config, cursor)` after browser launch. `patch_page` monkey-patches `page.click/type/fill/hover` etc., so all Playwright locator calls automatically get humanized behavior — no changes to `Interactions` class needed.

**Tech Stack:** cloakbrowser `human` module, Click CLI

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/auto_browser/daemon.py` | Modify | Accept humanize params, call `patch_page` after browser start |
| `src/auto_browser/cli.py` | Modify | Add `--humanize` / `--human-preset` flags to `open` and `_daemon` commands |

---

### Task 1: Add humanize support to daemon.py

**Files:**
- Modify: `src/auto_browser/daemon.py`

- [ ] **Step 1: Update `Daemon.__init__` and `run_daemon` to accept humanize params**

Change `Daemon.__init__` signature at line 22:

```python
# Before:
def __init__(self, socket_path: str, headed: bool, user_data_dir: str | None, session_name: str) -> None:
    self.socket_path = socket_path
    self.bm = BrowserManager(session_name=session_name, headed=headed, user_data_dir=user_data_dir)
    self.ref_map = RefMap()
    self._running = False

# After:
def __init__(self, socket_path: str, headed: bool, user_data_dir: str | None, session_name: str, humanize: bool = False, human_preset: str = "default") -> None:
    self.socket_path = socket_path
    self.bm = BrowserManager(session_name=session_name, headed=headed, user_data_dir=user_data_dir)
    self.ref_map = RefMap()
    self._running = False
    self._humanize = humanize
    self._human_preset = human_preset
```

- [ ] **Step 2: Add `_apply_humanize` method and call it from `start`**

Insert after `__init__`:

```python
    def _apply_humanize(self) -> None:
        if not self._humanize:
            return
        from cloakbrowser.human import resolve_config, patch_page, _CursorState
        config = resolve_config(preset=self._human_preset)
        cursor = _CursorState()
        patch_page(self.bm.page, config, cursor)
```

Update `start` method (line 28):

```python
# Before:
    def start(self) -> None:
        self.bm.start()
        self._running = True
        self._serve()

# After:
    def start(self) -> None:
        self.bm.start()
        self._apply_humanize()
        self._running = True
        self._serve()
```

- [ ] **Step 3: Update `run_daemon` function at line 162**

```python
# Before:
def run_daemon(socket_path: str, headed: bool, user_data_dir: str | None, session_name: str) -> None:
    daemon = Daemon(socket_path, headed, user_data_dir, session_name)
    daemon.start()

# After:
def run_daemon(socket_path: str, headed: bool, user_data_dir: str | None, session_name: str, humanize: bool = False, human_preset: str = "default") -> None:
    daemon = Daemon(socket_path, headed, user_data_dir, session_name, humanize, human_preset)
    daemon.start()
```

- [ ] **Step 4: Commit**

```bash
git add src/auto_browser/daemon.py
git commit -m "feat: add humanize/human_preset params to daemon

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Add CLI flags for humanize

**Files:**
- Modify: `src/auto_browser/cli.py`

- [ ] **Step 1: Add flags to `open_cmd`**

Update the `open_cmd` function signature at line 104:

```python
# Before:
@cli.command("open")
@click.argument("url")
@click.option("--headed", is_flag=True, help="Run browser in headed mode.")
@click.pass_context
def open_cmd(ctx: click.Context, url: str, headed: bool) -> None:

# After:
@cli.command("open")
@click.argument("url")
@click.option("--headed", is_flag=True, help="Run browser in headed mode.")
@click.option("--humanize", is_flag=True, help="Enable human-like interactions.")
@click.option("--human-preset", type=click.Choice(["default", "careful"]), default="default", help="Humanize preset (default: default).")
@click.pass_context
def open_cmd(ctx: click.Context, url: str, headed: bool, humanize: bool, human_preset: str) -> None:
```

- [ ] **Step 2: Pass humanize flags to daemon subprocess**

Update the subprocess.Popen call at line 137:

```python
# Before:
    proc = subprocess.Popen(
        [sys.executable, "-m", "auto_browser", "_daemon",
         "--socket", socket_path,
         "--session", session,
         "--session-dir", session_dir,
         *(["--headed"] if headed else []),
         *(["--user-data-dir", udd] if udd else []),
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

# After:
    proc = subprocess.Popen(
        [sys.executable, "-m", "auto_browser", "_daemon",
         "--socket", socket_path,
         "--session", session,
         "--session-dir", session_dir,
         *(["--headed"] if headed else []),
         *(["--humanize"] if humanize else []),
         *(["--human-preset", human_preset] if humanize else []),
         *(["--user-data-dir", udd] if udd else []),
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
```

Also save humanize info in daemon_info dict at line 149:

```python
# Before:
    daemon_info = {
        "pid": proc.pid,
        "socket": socket_path,
        "session": session,
        "headed": headed,
        "user_data_dir": udd,
    }

# After:
    daemon_info = {
        "pid": proc.pid,
        "socket": socket_path,
        "session": session,
        "headed": headed,
        "humanize": humanize,
        "human_preset": human_preset,
        "user_data_dir": udd,
    }
```

- [ ] **Step 3: Add flags to `_daemon` command**

Update the `_daemon` command at line 299:

```python
# Before:
@cli.command("_daemon", hidden=True)
@click.option("--socket", required=True)
@click.option("--headed", is_flag=True)
@click.option("--user-data-dir")
@click.option("--session", default="default")
@click.option("--session-dir")
def _daemon(socket: str, headed: bool, user_data_dir: str | None, session: str, session_dir: str | None) -> None:
    """Internal: run the daemon process."""
    from auto_browser.daemon import run_daemon
    run_daemon(
        socket_path=socket,
        headed=headed,
        user_data_dir=user_data_dir,
        session_name=session,
    )

# After:
@cli.command("_daemon", hidden=True)
@click.option("--socket", required=True)
@click.option("--headed", is_flag=True)
@click.option("--humanize", is_flag=True)
@click.option("--human-preset", type=click.Choice(["default", "careful"]), default="default")
@click.option("--user-data-dir")
@click.option("--session", default="default")
@click.option("--session-dir")
def _daemon(socket: str, headed: bool, humanize: bool, human_preset: str, user_data_dir: str | None, session: str, session_dir: str | None) -> None:
    """Internal: run the daemon process."""
    from auto_browser.daemon import run_daemon
    run_daemon(
        socket_path=socket,
        headed=headed,
        user_data_dir=user_data_dir,
        session_name=session,
        humanize=humanize,
        human_preset=human_preset,
    )
```

- [ ] **Step 4: Commit**

```bash
git add src/auto_browser/cli.py
git commit -m "feat: add --humanize and --human-preset CLI flags

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: End-to-end verification

- [ ] **Step 1: Test with humanize enabled**

```bash
cd /home/zenos/workspace/auto-browser
uv run ab open https://example.com --humanize --human-preset careful
```

Expected: Opens successfully, no errors.

- [ ] **Step 2: Test snapshot and click**

```bash
uv run ab snapshot
uv run ab click e6
```

Expected: Click works, page navigates (may be slower due to humanize delays).

- [ ] **Step 3: Test without humanize**

```bash
uv run ab close
uv run ab open https://example.com
uv run ab snapshot
uv run ab click e6
```

Expected: Click works at normal speed.

- [ ] **Step 4: Test preset validation**

```bash
uv run ab open https://example.com --human-preset invalid
```

Expected: Click exits with error "Invalid value for '--human-preset'".

- [ ] **Step 5: Close and cleanup**

```bash
uv run ab close
```
