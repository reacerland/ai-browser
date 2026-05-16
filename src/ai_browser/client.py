from __future__ import annotations

import json
import socket


class Client:
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        self._id = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or {},
        }
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        try:
            sock.sendall(json.dumps(request).encode() + b"\n")
            data = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
        finally:
            sock.close()

        response = json.loads(data.strip())
        if "error" in response:
            raise RuntimeError(f"Daemon error [{response['error']['code']}]: {response['error']['message']}")
        return response["result"]
