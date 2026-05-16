# src/auto_browser/daemon.py
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
    def __init__(self, socket_path: str, headed: bool, user_data_dir: str | None, session_name: str, humanize: bool = False, human_preset: str = "default") -> None:
        self.socket_path = socket_path
        self.bm = BrowserManager(session_name=session_name, headed=headed, user_data_dir=user_data_dir)
        self.ref_map = RefMap()
        self._running = False
        self._humanize = humanize
        self._human_preset = human_preset

    def start(self) -> None:
        self.bm.start()
        self._apply_humanize()
        self._running = True
        self._serve()

    def _apply_humanize(self) -> None:
        if not self._humanize:
            return
        from cloakbrowser.human import resolve_config, patch_page, _CursorState
        config = resolve_config(preset=self._human_preset)
        cursor = _CursorState()
        patch_page(self.bm.page, config, cursor)

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
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

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
            elif method == "get":
                result = self._get(params)
            elif method == "is":
                result = self._is_check(params)
            elif method == "wait":
                result = self._wait(params)
            elif method == "find":
                result = self._find(params)
            elif method == "back":
                result = self._get_interactions().go_back()
            elif method == "forward":
                result = self._get_interactions().go_forward()
            elif method == "reload":
                result = self._get_interactions().reload()
            elif method == "press":
                result = self._get_interactions().press(params.get("key", ""))
            elif method == "select":
                result = self._select(params)
            elif method == "check":
                result = self._interact("check", params)
            elif method == "uncheck":
                result = self._interact("uncheck", params)
            elif method == "dblclick":
                result = self._interact("dblclick", params)
            elif method == "drag":
                result = self._drag(params)
            elif method == "scroll_into_view":
                result = self._interact("scroll_into_view", params)
            elif method == "count":
                result = self._get_interactions().count(params.get("selector", ""))
            elif method == "upload":
                result = self._upload(params)
            elif method == "download":
                result = self._download(params)
            else:
                raise JsonRpcError(-32601, f"Method not found: {method}")
        except JsonRpcError as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": e.code, "message": e.message}}

        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _get_interactions(self) -> Interactions:
        return Interactions(self.bm.page, self.ref_map)

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
        compact = params.get("compact", False)
        content = take_snapshot(self.bm.page, self.ref_map, compact=compact)
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
        elif action == "check":
            return ia.check(ref)
        elif action == "uncheck":
            return ia.uncheck(ref)
        elif action == "dblclick":
            return ia.dblclick(ref)
        elif action == "scroll_into_view":
            return ia.scroll_into_view(ref)
        raise JsonRpcError(-32601, f"Unknown action: {action}")

    def _screenshot(self, params: dict) -> dict:
        path = params.get("path", "screenshot.png")
        self.bm.page.screenshot(path=path)
        return {"status": "ok", "path": path}

    def _eval(self, params: dict) -> dict:
        expression = params.get("expression", "")
        ia = self._get_interactions()
        return ia.eval_js(expression)

    def _get(self, params: dict) -> dict:
        what = params.get("what", "")
        ia = self._get_interactions()
        if what == "title":
            return {"status": "ok", "value": self.bm.page.title()}
        elif what == "url":
            return {"status": "ok", "value": self.bm.page.url}
        ref = params.get("ref", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        if what == "text":
            return ia.get_text(ref)
        elif what == "html":
            return ia.get_html(ref)
        elif what == "value":
            return ia.get_value(ref)
        elif what == "attr":
            name = params.get("name", "")
            if not name:
                raise JsonRpcError(-32003, "Missing attr name")
            return ia.get_attr(ref, name)
        elif what == "box":
            return ia.get_box(ref)
        raise JsonRpcError(-32003, f"Unknown get type: {what}")

    def _is_check(self, params: dict) -> dict:
        what = params.get("what", "")
        ref = params.get("ref", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        ia = self._get_interactions()
        if what == "visible":
            return ia.is_visible(ref)
        elif what == "enabled":
            return ia.is_enabled(ref)
        elif what == "checked":
            return ia.is_checked(ref)
        raise JsonRpcError(-32003, f"Unknown is type: {what}")

    def _wait(self, params: dict) -> dict:
        target = params.get("target", "")
        ia = self._get_interactions()
        if target.startswith("e") and target[1:].isdigit():
            return ia.wait_for_ref(target, timeout=params.get("timeout", 25000))
        elif target.isdigit():
            return ia.wait_for_timeout(int(target))
        raise JsonRpcError(-32003, f"Invalid wait target: {target}")

    def _find(self, params: dict) -> dict:
        locator_type = params.get("locator", "")
        value = params.get("value", "")
        name = params.get("name")
        ia = self._get_interactions()
        return ia.find(locator_type, value, name)

    def _select(self, params: dict) -> dict:
        ref = params.get("ref", "")
        value = params.get("value", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        return self._get_interactions().select_option(ref, value)

    def _drag(self, params: dict) -> dict:
        src = params.get("src", "")
        dst = params.get("dst", "")
        if not src or not dst:
            raise JsonRpcError(-32003, "Missing src or dst ref")
        return self._get_interactions().drag(src, dst)

    def _upload(self, params: dict) -> dict:
        ref = params.get("ref", "")
        files = params.get("files", [])
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        return self._get_interactions().upload(ref, files)

    def _download(self, params: dict) -> dict:
        ref = params.get("ref", "")
        path = params.get("path", "")
        if not ref:
            raise JsonRpcError(-32003, "Missing ref parameter")
        if not path:
            raise JsonRpcError(-32003, "Missing path parameter")
        return self._get_interactions().download(ref, path)


def run_daemon(socket_path: str, headed: bool, user_data_dir: str | None, session_name: str, humanize: bool = False, human_preset: str = "default") -> None:
    daemon = Daemon(socket_path, headed, user_data_dir, session_name, humanize, human_preset)
    daemon.start()
