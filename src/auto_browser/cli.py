from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import click

from auto_browser.client import Client

BASE_DIR = Path.home() / ".ab"


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
        return True
    except (ProcessLookupError, KeyError):
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
@click.option("--session", "-s", default="default", help="Session name.")
@click.pass_context
def cli(ctx: click.Context, session: str) -> None:
    """Auto-browser CLI — browser automation for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["session"] = session


@cli.command("open")
@click.argument("url")
@click.option("--headed", is_flag=True, help="Run browser in headed mode.")
@click.pass_context
def open_cmd(ctx: click.Context, url: str, headed: bool) -> None:
    """Open a URL. Starts daemon if not running."""
    session = ctx.obj["session"]
    user_data_dir = ctx.obj["session"] != "default"

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    session_dir, udd = _ensure_session_dir(session, user_data_dir)
    socket_path = f"/tmp/ab-{session}.sock"

    if _is_daemon_running(session):
        info = _read_daemon_info(session)
        client = Client(info["socket"])
        result = client.call("goto", {"url": url})
        _output(result)
        return

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

    daemon_info = {
        "pid": proc.pid,
        "socket": socket_path,
        "session": session,
        "headed": headed,
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
    session = ctx.obj["session"]
    if not _is_daemon_running(session):
        _output({"status": "ok", "message": "Daemon not running"})
        return
    info = _read_daemon_info(session)
    client = Client(info["socket"])
    result = client.call("shutdown")
    _output(result)


@cli.command()
@click.option("--compact", is_flag=True, help="Compact output mode.")
@click.option("--selector", help="CSS selector to filter elements.")
@click.pass_context
def snapshot(ctx: click.Context, compact: bool, selector: str | None) -> None:
    """Get accessibility tree snapshot of the current page."""
    session = ctx.obj["session"]
    client = _get_client(session)
    params: dict = {}
    if compact:
        params["compact"] = True
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


def main() -> None:
    cli()
