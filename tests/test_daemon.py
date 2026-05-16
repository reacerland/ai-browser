import json
import os
import subprocess
import sys
import time

import pytest


class TestDaemonClientIntegration:
    def test_ping(self, tmp_path):
        socket_path = str(tmp_path / "test.sock")

        proc = subprocess.Popen(
            [sys.executable, "-m", "ai_browser", "_daemon", "--socket", socket_path, "--headed"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for _ in range(50):
            if os.path.exists(socket_path):
                break
            time.sleep(0.1)
        else:
            proc.kill()
            raise RuntimeError("Daemon did not start")

        try:
            from ai_browser.client import Client
            client = Client(socket_path)
            result = client.call("ping")
            assert result["status"] == "ok"
        finally:
            proc.terminate()
            proc.wait(timeout=5)
