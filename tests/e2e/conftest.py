from __future__ import annotations

import re
import socket
import subprocess
import time
from pathlib import Path

import pytest

E2E_DIR = Path(__file__).parent
SESSION = "e2e"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def ab(*args: str, session: str = SESSION) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ai-browser", "--session", session, *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def parse_refs(snapshot_yaml: str) -> dict[str, tuple[str, str]]:
    """Parse snapshot YAML, return {ref_id: (role, name)}."""
    refs: dict[str, tuple[str, str]] = {}
    line_re = re.compile(r'^\s*-\s+(\w+)(?:\s+"([^"]*)")?.*?\[ref=(e\d+)\]')
    for line in snapshot_yaml.splitlines():
        m = line_re.match(line)
        if m:
            role, name, ref_id = m.group(1), m.group(2) or "", m.group(3)
            refs[ref_id] = (role, name)
    return refs


def find_ref(snapshot_yaml: str, role: str, name: str = "") -> str:
    """Find ref ID by role and optional name from snapshot YAML."""
    for ref_id, (r, n) in parse_refs(snapshot_yaml).items():
        if r == role and (not name or n == name):
            return ref_id
    raise ValueError(f"No ref for role={role} name={name}")


@pytest.fixture(scope="session")
def http_server():
    port = _free_port()
    proc = subprocess.Popen(
        ["python", "-m", "http.server", str(port), "--directory", str(E2E_DIR)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://localhost:{port}"
    # Wait for server ready
    for _ in range(50):
        try:
            with socket.create_connection(("localhost", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.1)
    yield base_url
    proc.terminate()
    proc.wait()


@pytest.fixture
def e2e(http_server):
    """Open the test page, provide helpers, close on teardown."""
    url = f"{http_server}/test_page.html"
    result = ab("open", url)
    assert result.returncode == 0, f"open failed: {result.stderr}"

    # Take snapshot and provide helpers
    snap_result = ab("snapshot")
    snapshot_yaml = snap_result.stderr

    class Helpers:
        base_url = http_server
        snapshot = snapshot_yaml

        @staticmethod
        def ref(role: str, name: str = "") -> str:
            return find_ref(snapshot_yaml, role, name)

        @staticmethod
        def fresh_snapshot() -> str:
            r = ab("snapshot")
            return r.stderr

    yield Helpers()

    ab("close")
