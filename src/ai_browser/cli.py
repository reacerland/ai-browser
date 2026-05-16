from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import click

from ai_browser.client import Client

BASE_DIR = Path.home() / ".ai-browser"


def _session_dir(session: str) -> Path:
    return BASE_DIR / session


def _daemon_info_path(session: str) -> Path:
    return _session_dir(session) / "daemon.json"


def _read_daemon_info(session: str) -> dict | None:
    path = _daemon_info_path(session)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _is_daemon_running(session: str) -> bool:
    info = _read_daemon_info(session)
    if not info:
        return False
    try:
        os.kill(info["pid"], 0)
    except (ProcessLookupError, KeyError):
        return False
    sock_path = info.get("socket", "")
    if not sock_path or not os.path.exists(sock_path):
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(sock_path)
        s.close()
        return True
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        return False


def _wait_for_socket(socket_path: str, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(socket_path):
            return True
        time.sleep(0.1)
    return False


def _ensure_session_dir(session: str, user_data_dir: str | None) -> tuple[str, str | None]:
    sdir = _session_dir(session)
    sdir.mkdir(parents=True, exist_ok=True)
    if user_data_dir:
        udd = sdir / "chrome-data"
        udd.mkdir(exist_ok=True)
        return str(sdir), str(udd)
    return str(sdir), None


def _output(result: dict) -> None:
    print(json.dumps({"status": "ok", "data": result}))
    if "content" in result:
        print(result["content"], file=sys.stderr)


def _get_client(session: str) -> Client:
    if not _is_daemon_running(session):
        click.echo(json.dumps({
            "status": "error",
            "error": {"code": -32000, "message": "Daemon not running. Use 'ab open' first."},
        }))
        raise SystemExit(1)
    info = _read_daemon_info(session)
    return Client(info["socket"])


@click.group()
@click.option("--session", "-s", default=None, help="Session name.")
@click.pass_context
def cli(ctx: click.Context, session: str | None) -> None:
    """AI Browser CLI — browser automation for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["session"] = session or "default"
    ctx.obj["explicit_session"] = session is not None


@cli.command("open")
@click.argument("url")
@click.option("--headed", is_flag=True, help="Run browser in headed mode.")
@click.option("--humanize", is_flag=True, help="Enable human-like interactions.")
@click.option("--human-preset", type=click.Choice(["default", "careful"]), default="default", help="Humanize preset (default: default).")
@click.pass_context
def open_cmd(ctx: click.Context, url: str, headed: bool, humanize: bool, human_preset: str) -> None:
    """Open a URL. Starts daemon if not running."""
    session = ctx.obj["session"]
    user_data_dir = ctx.obj["session"] != "default"

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    session_dir, udd = _ensure_session_dir(session, user_data_dir)
    socket_path = f"/tmp/ab-{session}.sock"

    if _is_daemon_running(session):
        info = _read_daemon_info(session)
        if headed and not info.get("headed", False):
            click.echo(
                "Warning: daemon already running in headless mode. "
                f"Close first to switch: ab --session {session} close",
                err=True,
            )
        try:
            client = Client(info["socket"])
            result = client.call("goto", {"url": url})
            _output(result)
            return
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            # Stale daemon info — clean up and start fresh
            info_path = _daemon_info_path(session)
            if info_path.exists():
                info_path.unlink()
            stale_sock = info.get("socket", "")
            if stale_sock and os.path.exists(stale_sock):
                os.unlink(stale_sock)

    proc = subprocess.Popen(
        [sys.executable, "-m", "ai_browser", "_daemon",
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

    daemon_info = {
        "pid": proc.pid,
        "socket": socket_path,
        "session": session,
        "headed": headed,
        "humanize": humanize,
        "human_preset": human_preset,
        "user_data_dir": udd,
    }
    with open(_daemon_info_path(session), "w") as f:
        json.dump(daemon_info, f)

    if not _wait_for_socket(socket_path):
        click.echo(json.dumps({"status": "error", "error": {"message": "Daemon failed to start"}}))
        raise SystemExit(1)

    client = Client(socket_path)
    result = client.call("goto", {"url": url})
    _output(result)


@cli.command()
@click.pass_context
def close(ctx: click.Context) -> None:
    """Close the browser and stop the daemon."""
    if ctx.obj["explicit_session"]:
        _close_session(ctx.obj["session"])
    else:
        _close_all_sessions()


def _close_session(session: str) -> None:
    info = _read_daemon_info(session)
    if not info:
        _output({"status": "ok", "message": f"Session '{session}' not running"})
        return
    try:
        client = Client(info["socket"])
        result = client.call("shutdown")
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        result = {"status": "ok", "message": f"Session '{session}' not running"}
    _cleanup_session_files(session, info)
    _output(result)


def _close_all_sessions() -> None:
    if not BASE_DIR.exists():
        _output({"status": "ok", "message": "No sessions found"})
        return
    results = []
    for session_dir in sorted(BASE_DIR.iterdir()):
        if not session_dir.is_dir():
            continue
        session = session_dir.name
        info = _read_daemon_info(session)
        if not info:
            continue
        try:
            client = Client(info["socket"])
            client.call("shutdown")
            results.append({"session": session, "status": "closed"})
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            results.append({"session": session, "status": "already_stopped"})
        _cleanup_session_files(session, info)
    if not results:
        _output({"status": "ok", "message": "No active sessions"})
    else:
        _output({"status": "ok", "closed": results})


def _cleanup_session_files(session: str, info: dict) -> None:
    info_path = _daemon_info_path(session)
    if info_path.exists():
        info_path.unlink()
    socket_path = info.get("socket", "")
    if socket_path and os.path.exists(socket_path):
        os.unlink(socket_path)


@cli.command()
@click.option("--compact", is_flag=True, help="Compact output mode.")
@click.option("--interactive", is_flag=True, help="Only show interactive elements.")
@click.option("--depth", type=int, default=None, help="Max tree depth.")
@click.option("--selector", help="CSS selector to scope the snapshot.")
@click.pass_context
def snapshot(ctx: click.Context, compact: bool, interactive: bool, depth: int | None, selector: str | None) -> None:
    """Get accessibility tree snapshot of the current page."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {}
    if compact:
        params["compact"] = True
    if interactive:
        params["interactive"] = True
    if depth is not None:
        params["depth"] = depth
    if selector:
        params["selector"] = selector
    result = client.call("snapshot", params)
    _output(result)


@cli.command("click")
@click.argument("ref")
@click.option("--double", is_flag=True, help="Double-click.")
@click.pass_context
def click_cmd(ctx: click.Context, ref: str, double: bool) -> None:
    """Click an element by its ref identifier."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {"ref": ref}
    if double:
        params["double"] = True
    result = client.call("click", params)
    _output(result)


@cli.command("type")
@click.argument("ref")
@click.argument("text")
@click.option("--clear", is_flag=True, help="Clear field before typing.")
@click.pass_context
def type_cmd(ctx: click.Context, ref: str, text: str, clear: bool) -> None:
    """Type text into an element."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {"ref": ref, "text": text}
    if clear:
        params["clear"] = True
    result = client.call("type", params)
    _output(result)


@cli.command()
@click.argument("ref")
@click.argument("value")
@click.pass_context
def fill(ctx: click.Context, ref: str, value: str) -> None:
    """Fill a form field with a value (replaces existing content)."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("fill", {"ref": ref, "value": value})
    _output(result)


@cli.command()
@click.argument("direction", type=click.Choice(["up", "down"]))
@click.option("--amount", type=int, default=300, help="Scroll distance in pixels.")
@click.pass_context
def scroll(ctx: click.Context, direction: str, amount: int) -> None:
    """Scroll the page up or down."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("scroll", {"direction": direction, "amount": amount})
    _output(result)


@cli.command()
@click.option("--output", "-o", help="Save screenshot to file path.")
@click.pass_context
def screenshot(ctx: click.Context, output: str | None) -> None:
    """Take a screenshot of the current page."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {}
    if output:
        params["path"] = output
    result = client.call("screenshot", params)
    _output(result)


@cli.command()
@click.argument("expression")
@click.pass_context
def eval(ctx: click.Context, expression: str) -> None:
    """Evaluate JavaScript expression in the page."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("eval", {"expression": expression})
    _output(result)


@cli.command("get")
@click.argument("what", type=click.Choice(["text", "html", "value", "attr", "title", "url", "box"]))
@click.argument("ref", required=False)
@click.option("--name", help="Attribute name (for attr type).")
@click.pass_context
def get_cmd(ctx: click.Context, what: str, ref: str | None, name: str | None) -> None:
    """Get element property or page info."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {"what": what}
    if ref:
        params["ref"] = ref
    if name:
        params["name"] = name
    result = client.call("get", params)
    if "value" in result:
        print(result["value"])
    else:
        _output(result)


@cli.command("is")
@click.argument("what", type=click.Choice(["visible", "enabled", "checked"]))
@click.argument("ref")
@click.pass_context
def is_cmd(ctx: click.Context, what: str, ref: str) -> None:
    """Check element state (outputs true/false)."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("is", {"what": what, "ref": ref})
    print(str(result.get("value", False)).lower())


@cli.command("wait")
@click.argument("target")
@click.option("--timeout", type=int, default=25000, help="Timeout in ms (default: 25000).")
@click.pass_context
def wait_cmd(ctx: click.Context, target: str, timeout: int) -> None:
    """Wait for element (ref) or time (ms)."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("wait", {"target": target, "timeout": timeout})
    _output(result)


@cli.command("find")
@click.argument("locator", type=click.Choice(["role", "text", "label", "placeholder", "alt", "title", "testid"]))
@click.argument("value")
@click.option("--name", help="Name filter (only for role locator).")
@click.pass_context
def find_cmd(ctx: click.Context, locator: str, value: str, name: str | None) -> None:
    """Find elements by locator type."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {"locator": locator, "value": value}
    if name:
        params["name"] = name
    result = client.call("find", params)
    if "content" in result:
        print(result["content"])
    else:
        _output(result)


@cli.command()
@click.pass_context
def back(ctx: click.Context) -> None:
    """Go back in browser history."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("back")
    _output(result)


@cli.command()
@click.pass_context
def forward(ctx: click.Context) -> None:
    """Go forward in browser history."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("forward")
    _output(result)


@cli.command()
@click.pass_context
def reload(ctx: click.Context) -> None:
    """Reload the current page."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("reload")
    _output(result)


@cli.command()
@click.argument("key")
@click.pass_context
def press(ctx: click.Context, key: str) -> None:
    """Press a keyboard key (e.g. Enter, Tab, Escape, Control+a)."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("press", {"key": key})
    _output(result)


@cli.command("select")
@click.argument("ref")
@click.argument("value")
@click.pass_context
def select_cmd(ctx: click.Context, ref: str, value: str) -> None:
    """Select an option in a dropdown by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("select", {"ref": ref, "value": value})
    _output(result)


@cli.command()
@click.argument("ref")
@click.pass_context
def check(ctx: click.Context, ref: str) -> None:
    """Check a checkbox by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("check", {"ref": ref})
    _output(result)


@cli.command()
@click.argument("ref")
@click.pass_context
def uncheck(ctx: click.Context, ref: str) -> None:
    """Uncheck a checkbox by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("uncheck", {"ref": ref})
    _output(result)


@cli.command()
@click.argument("ref")
@click.pass_context
def dblclick(ctx: click.Context, ref: str) -> None:
    """Double-click an element by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("dblclick", {"ref": ref})
    _output(result)


@cli.command()
@click.argument("src_ref")
@click.argument("dst_ref")
@click.pass_context
def drag(ctx: click.Context, src_ref: str, dst_ref: str) -> None:
    """Drag element to another element by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("drag", {"src": src_ref, "dst": dst_ref})
    _output(result)


@cli.command("scroll-into-view")
@click.argument("ref")
@click.pass_context
def scroll_into_view_cmd(ctx: click.Context, ref: str) -> None:
    """Scroll element into view by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("scroll_into_view", {"ref": ref})
    _output(result)


@cli.command()
@click.argument("ref")
@click.pass_context
def hover(ctx: click.Context, ref: str) -> None:
    """Hover over an element by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("hover", {"ref": ref})
    _output(result)


@cli.command()
@click.argument("selector")
@click.pass_context
def count(ctx: click.Context, selector: str) -> None:
    """Count elements matching a CSS selector."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("count", {"selector": selector})
    print(result.get("value", 0))


@cli.command()
@click.argument("ref")
@click.argument("files", nargs=-1, required=True)
@click.pass_context
def upload(ctx: click.Context, ref: str, files: tuple[str, ...]) -> None:
    """Upload files to a file input by ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("upload", {"ref": ref, "files": list(files)})
    _output(result)


@cli.command()
@click.argument("ref")
@click.argument("path")
@click.pass_context
def download(ctx: click.Context, ref: str, path: str) -> None:
    """Download a file by clicking element ref."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("download", {"ref": ref, "path": path})
    _output(result)


@cli.command()
@click.pass_context
def ping(ctx: click.Context) -> None:
    """Check if the daemon is alive."""
    session = ctx.obj["session"]
    client = _get_client(session)
    result = client.call("ping")
    _output(result)


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
    from ai_browser.daemon import run_daemon
    run_daemon(
        socket_path=socket,
        headed=headed,
        user_data_dir=user_data_dir,
        session_name=session,
        humanize=humanize,
        human_preset=human_preset,
    )


def main() -> None:
    cli()
