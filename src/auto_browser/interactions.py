from __future__ import annotations

import re

from playwright.sync_api import CDPSession, Page

from auto_browser.ref_map import RefMap


def parse_ref(text: str) -> str | None:
    m = re.fullmatch(r"(?:@|ref=)?e(\d+)", text.strip())
    if m:
        return f"e{m.group(1)}"
    return None


def _box_center(quad: list[float]) -> tuple[float, float]:
    x = sum(quad[0::2]) / 4
    y = sum(quad[1::2]) / 4
    return x, y


class Interactions:
    def __init__(self, cdp: CDPSession, ref_map: RefMap, page: Page) -> None:
        self.cdp = cdp
        self.ref_map = ref_map
        self.page = page

    def _resolve_center(self, ref_or_selector: str) -> tuple[float, float]:
        ref_id = parse_ref(ref_or_selector)
        if ref_id:
            entry = self.ref_map.get(ref_id)
            if entry and entry.backend_node_id:
                try:
                    box = self.cdp.send("DOM.getBoxModel", {"backendNodeId": entry.backend_node_id})
                    return _box_center(box["model"]["content"])
                except Exception:
                    pass
            # Level 2: re-query AX tree
            if entry:
                fresh_id = self._find_node_by_role_name(entry.role, entry.name, entry.nth)
                if fresh_id:
                    box = self.cdp.send("DOM.getBoxModel", {"backendNodeId": fresh_id})
                    return _box_center(box["model"]["content"])
            raise ValueError(f"Could not locate element: {ref_or_selector}")
        else:
            # Level 3: CSS selector
            result = self.page.evaluate(f"""
                () => {{
                    const el = document.querySelector({ref_or_selector!r});
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
                }}
            """)
            if not result:
                raise ValueError(f"Element not found: {ref_or_selector}")
            return result["x"], result["y"]

    def _resolve_object_id(self, ref_or_selector: str) -> str:
        ref_id = parse_ref(ref_or_selector)
        if ref_id:
            entry = self.ref_map.get(ref_id)
            if entry and entry.backend_node_id:
                resolved = self.cdp.send("DOM.resolveNode", {"backendNodeId": entry.backend_node_id})
                return resolved["object"]["objectId"]
        raise ValueError(f"Could not resolve element object: {ref_or_selector}")

    def _find_node_by_role_name(self, role: str, name: str, nth: int | None) -> int | None:
        result = self.cdp.send("Accessibility.getFullAXTree")
        count = 0
        for node in result.get("nodes", []):
            n_role = (node.get("role") or {}).get("value", "")
            n_name = (node.get("name") or {}).get("value", "")
            if n_role == role and n_name == name:
                if nth is None or count == nth:
                    return node.get("backendDOMNodeId")
                count += 1
        return None

    def click(self, ref_or_selector: str, button: str = "left", double: bool = False) -> dict:
        x, y = self._resolve_center(ref_or_selector)
        click_count = 2 if double else 1
        self.cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": button, "buttons": 1, "clickCount": click_count,
        })
        self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": button, "buttons": 0, "clickCount": click_count,
        })
        return {"status": "ok", "action": "click", "x": x, "y": y}

    def type(self, ref_or_selector: str, text: str, clear: bool = False) -> dict:
        obj_id = self._resolve_object_id(ref_or_selector)
        self.cdp.send("Runtime.callFunctionOn", {
            "functionDeclaration": "function() { this.focus(); }",
            "objectId": obj_id,
        })
        if clear:
            self.cdp.send("Runtime.callFunctionOn", {
                "functionDeclaration": "function() { this.select(); this.value = ''; }",
                "objectId": obj_id,
            })
        for char in text:
            if char == "\n":
                self.cdp.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter"})
                self.cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter"})
            else:
                self.cdp.send("Input.insertText", {"text": char})
        return {"status": "ok", "action": "type", "text": text}

    def fill(self, ref_or_selector: str, value: str) -> dict:
        obj_id = self._resolve_object_id(ref_or_selector)
        self.cdp.send("Runtime.callFunctionOn", {
            "functionDeclaration": "function() { this.focus(); this.select(); this.value = ''; }",
            "objectId": obj_id,
        })
        self.cdp.send("Input.insertText", {"text": value})
        return {"status": "ok", "action": "fill", "value": value}

    def hover(self, ref_or_selector: str) -> dict:
        x, y = self._resolve_center(ref_or_selector)
        self.cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        return {"status": "ok", "action": "hover", "x": x, "y": y}

    def scroll(self, direction: str, amount: int = 300) -> dict:
        delta_y = -amount if direction == "up" else amount
        self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": 0, "y": 0,
            "deltaX": 0, "deltaY": delta_y,
        })
        return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount}

    def eval_js(self, expression: str) -> dict:
        result = self.cdp.send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if "exceptionDetails" in result:
            raise RuntimeError(f"JS error: {result['exceptionDetails']}")
        return {"status": "ok", "result": result.get("result", {})}
