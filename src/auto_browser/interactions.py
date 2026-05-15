from __future__ import annotations

from playwright.sync_api import Page

from auto_browser.ref_map import RefMap


class Interactions:
    def __init__(self, page: Page, ref_map: RefMap) -> None:
        self.page = page
        self.ref_map = ref_map

    def _resolve(self, ref: str):
        entry = self.ref_map.get(ref)
        if not entry:
            raise ValueError(f"Unknown ref: {ref}")
        return entry

    def _locator(self, entry):
        loc = self.page.get_by_role(entry.role, name=entry.name)
        if entry.nth > 0:
            loc = loc.nth(entry.nth)
        return loc

    def click(self, ref: str, button: str = "left", double: bool = False) -> dict:
        entry = self._resolve(ref)
        loc = self._locator(entry)
        if double:
            loc.dblclick(button=button)
        else:
            loc.click(button=button)
        return {"status": "ok", "action": "click", "ref": ref}

    def type(self, ref: str, text: str, clear: bool = False) -> dict:
        entry = self._resolve(ref)
        loc = self._locator(entry)
        if clear:
            loc.fill("")
        loc.press_sequentially(text)
        return {"status": "ok", "action": "type", "text": text}

    def fill(self, ref: str, value: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).fill(value)
        return {"status": "ok", "action": "fill", "value": value}

    def hover(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).hover()
        return {"status": "ok", "action": "hover", "ref": ref}

    def scroll(self, direction: str, amount: int = 300) -> dict:
        delta_y = -amount if direction == "up" else amount
        self.page.mouse.wheel(0, delta_y)
        return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount}

    def eval_js(self, expression: str) -> dict:
        result = self.page.evaluate(expression)
        return {"status": "ok", "result": result}
