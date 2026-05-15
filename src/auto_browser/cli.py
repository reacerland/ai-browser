from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

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


def cmd_open(args: argparse.Namespace) -> None:
    session = args.session or "default"
    url = args.url
    headed = args.headed
    user_data_dir = args.session is not None

    session_dir, udd = _ensure_session_dir(session, user_data_dir)
    socket_path = f"/tmp/ab-{session}.sock"

    if _is_daemon_running(session):
        info = _read_daemon_info(session)
        client = Client(info["socket"])
        result = client.call("goto", {"url": url})
        _output(result)
        return

    daemon_info = {
        "pid": os.getpid(),
        "socket": socket_path,
        "session": session,
        "headed": headed,
        "user_data_dir": udd,
    }

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

    daemon_info["pid"] = proc.pid
    with open(_daemon_info_path(session), "w") as f:
        json.dump(daemon_info, f)

    if not _wait_for_socket(socket_path):
        print(json.dumps({"status": "error", "error": {"message": "Daemon failed to start"}}))
        sys.exit(1)

    client = Client(socket_path)
    result = client.call("goto", {"url": url})
    _output(result)


def cmd_close(args: argparse.Namespace) -> None:
    session = args.session or "default"
    if not _is_daemon_running(session):
        _output({"status": "ok", "message": "Daemon not running"})
        return
    info = _read_daemon_info(session)
    client = Client(info["socket"])
    result = client.call("shutdown")
    _output(result)


def cmd_action(args: argparse.Namespace) -> None:
    session = args.session or "default"
    if not _is_daemon_running(session):
        print(json.dumps({"status": "error", "error": {"code": -32000, "message": "Daemon not running. Use 'ab open' first."}}))
        sys.exit(1)
    info = _read_daemon_info(session)
    client = Client(info["socket"])
    params = {}
    if hasattr(args, "ref") and args.ref:
        params["ref"] = args.ref
    if hasattr(args, "text") and args.text:
        params["text"] = args.text
    if hasattr(args, "value") and args.value:
        params["value"] = args.value
    if hasattr(args, "compact") and args.compact:
        params["compact"] = True
    if hasattr(args, "selector") and args.selector:
        params["selector"] = args.selector
    if hasattr(args, "direction") and args.direction:
        params["direction"] = args.direction
    if hasattr(args, "amount") and args.amount:
        params["amount"] = args.amount
    if hasattr(args, "expression") and args.expression:
        params["expression"] = args.expression
    if hasattr(args, "output") and args.output:
        params["path"] = args.output
    if hasattr(args, "double") and args.double:
        params["double"] = True
    if hasattr(args, "clear") and args.clear:
        params["clear"] = True

    result = client.call(args.action, params)
    _output(result)


def _output(result: dict) -> None:
    print(json.dumps({"status": "ok", "data": result}))
    if "content" in result:
        print(result["content"], file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ab", description="Auto-browser CLI")
    parser.add_argument("--session", "-s", help="Session name")

    sub = parser.add_subparsers(dest="command")

    p_open = sub.add_parser("open")
    p_open.add_argument("url")
    p_open.add_argument("--headed", action="store_true")

    sub.add_parser("close")

    p_snap = sub.add_parser("snapshot")
    p_snap.add_argument("--compact", action="store_true")
    p_snap.add_argument("--selector")

    p_click = sub.add_parser("click")
    p_click.add_argument("ref")
    p_click.add_argument("--double", action="store_true")

    p_type = sub.add_parser("type")
    p_type.add_argument("ref")
    p_type.add_argument("text")
    p_type.add_argument("--clear", action="store_true")

    p_fill = sub.add_parser("fill")
    p_fill.add_argument("ref")
    p_fill.add_argument("value")

    p_scroll = sub.add_parser("scroll")
    p_scroll.add_argument("direction", choices=["up", "down"])
    p_scroll.add_argument("--amount", type=int, default=300)

    p_ss = sub.add_parser("screenshot")
    p_ss.add_argument("--output")

    p_eval = sub.add_parser("eval")
    p_eval.add_argument("expression")

    sub.add_parser("ping")

    p_daemon = sub.add_parser("_daemon")
    p_daemon.add_argument("--socket", required=True)
    p_daemon.add_argument("--headed", action="store_true")
    p_daemon.add_argument("--user-data-dir")
    p_daemon.add_argument("--session", default="default")
    p_daemon.add_argument("--session-dir")

    args = parser.parse_args()

    if args.command == "_daemon":
        from auto_browser.daemon import run_daemon
        run_daemon(
            socket_path=args.socket,
            headed=args.headed,
            user_data_dir=args.user_data_dir,
            session_name=args.session,
        )
    elif args.command == "open":
        cmd_open(args)
    elif args.command == "close":
        cmd_close(args)
    elif args.command in ("snapshot", "click", "type", "fill", "scroll", "screenshot", "eval", "ping"):
        args.action = args.command
        cmd_action(args)
    else:
        parser.print_help()
