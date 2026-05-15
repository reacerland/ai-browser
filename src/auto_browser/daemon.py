from __future__ import annotations

import json
import os
import socket
from typing import Any

from auto_browser.browser_manager import BrowserManager
from auto_browser.ref_map import RefMap
from auto_browser.ax_tree import take_snapshot
from auto_browser.interactions import Interactions


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message


class Daemon:
    def __init__(self, socket_path: str, headed: bool, user_data_dir: str | None, session_name: str) -> None:
        self.socket_path = socket_path
        self.bm = BrowserManager(session_name=session_name, headed=headed, user_data_dir=user_data_dir)
        self.ref_map = RefMap()
        self._running = False

    def start(self) -> None:
        self.bm.start()
        self._running = True
        self._serve()

    def _serve(self) -> None:
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.socket_path)
        server.listen(1)
        server.settimeout(1.0)

        while self._running:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            try:
                data = b""
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in data:
                        break
                if data:
                    request = json.loads(data.strip())
                    response = self._handle_request(request)
                    conn.sendall(json.dumps(response).encode() + b"\n")
            except Exception as e:
                try:
                    error_resp = {
                        "jsonrpc": "2.0", "id": None,
                        "error": {"code": -32603, "message": str(e)},
                    }
                    conn.sendall(json.dumps(error_resp).encode() + b"\n")
                except Exception:
                    pass
            finally:
                conn.close()
        server.close()

    def _handle_request(self, request: dict) -> dict:
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        try:
            if method == "shutdown":
                result = self._shutdown()
            elif method == "ping":
                result = {"status": "ok"}
            elif method == "goto":
                result = self._goto(params)
            elif method == "snapshot":
                result = self._snapshot(params)
            elif method == "click":
                result = self._interact("click", params)
            elif method == "type":
                result = self._interact("type", params)
            elif method == "fill":
                result = self._interact("fill", params)
            elif method == "hover":
                result = self._interact("hover", params)
            elif method == "scroll":
                result = self._interact("scroll", params)
            elif method == "screenshot":
                result = self._screenshot(params)
            elif method == "eval":
                result = self._eval(params)
            else:
                raise JsonRpcError(-32601, f"Method not found: {method}")
        except JsonRpcError as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": e.code, "message": e.message}}

        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _get_interactions(self) -> Interactions:
        cdp = self.bm.get_cdp_session()
        return Interactions(cdp, self.ref_map, self.bm.page)

    def _shutdown(self) -> dict:
        self._running = False
        self.bm.close()
        return {"status": "ok"}

    def _goto(self, params: dict) -> dict:
        url = params.get("url")
        if not url:
            raise JsonRpcError(-32003, "Missing url parameter")
        self.bm.navigate(url)
        return {"status": "ok", "url": url, "title": self.bm.page.title()}

    def _snapshot(self, params: dict) -> dict:
        cdp = self.bm.get_cdp_session()
        compact = params.get("compact", False)
        selector = params.get("selector")
        content = take_snapshot(cdp, self.ref_map, compact=compact, selector=selector)
        return {"status": "ok", "content": content}

    def _interact(self, action: str, params: dict) -> dict:
        ia = self._get_interactions()
        ref = params.get("ref") or params.get("selector", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref or selector")

        if action == "click":
            return ia.click(ref, double=params.get("double", False))
        elif action == "type":
            text = params.get("text", "")
            return ia.type(ref, text, clear=params.get("clear", False))
        elif action == "fill":
            value = params.get("value", "")
            return ia.fill(ref, value)
        elif action == "hover":
            return ia.hover(ref)
        elif action == "scroll":
            direction = params.get("direction", "down")
            amount = params.get("amount", 300)
            return ia.scroll(direction, amount)
        raise JsonRpcError(-32601, f"Unknown action: {action}")

    def _screenshot(self, params: dict) -> dict:
        path = params.get("path", "screenshot.png")
        self.bm.page.screenshot(path=path)
        return {"status": "ok", "path": path}

    def _eval(self, params: dict) -> dict:
        expression = params.get("expression", "")
        ia = self._get_interactions()
        return ia.eval_js(expression)


def run_daemon(socket_path: str, headed: bool, user_data_dir: str | None, session_name: str) -> None:
    daemon = Daemon(socket_path, headed, user_data_dir, session_name)
    daemon.start()
