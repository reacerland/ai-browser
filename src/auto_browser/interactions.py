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

    def get_text(self, ref: str) -> dict:
        entry = self._resolve(ref)
        text = self._locator(entry).text_content() or ""
        return {"status": "ok", "value": text}

    def get_html(self, ref: str) -> dict:
        entry = self._resolve(ref)
        html = self._locator(entry).inner_html()
        return {"status": "ok", "value": html}

    def get_value(self, ref: str) -> dict:
        entry = self._resolve(ref)
        value = self._locator(entry).input_value()
        return {"status": "ok", "value": value}

    def get_attr(self, ref: str, name: str) -> dict:
        entry = self._resolve(ref)
        value = self._locator(entry).get_attribute(name)
        return {"status": "ok", "value": value}

    def get_box(self, ref: str) -> dict:
        entry = self._resolve(ref)
        box = self._locator(entry).bounding_box()
        return {"status": "ok", "value": box}

    def is_visible(self, ref: str) -> dict:
        entry = self._resolve(ref)
        visible = self._locator(entry).is_visible()
        return {"status": "ok", "value": visible}

    def is_enabled(self, ref: str) -> dict:
        entry = self._resolve(ref)
        enabled = self._locator(entry).is_enabled()
        return {"status": "ok", "value": enabled}

    def is_checked(self, ref: str) -> dict:
        entry = self._resolve(ref)
        checked = self._locator(entry).is_checked()
        return {"status": "ok", "value": checked}

    def wait_for_ref(self, ref: str, timeout: int = 25000) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).wait_for(state="visible", timeout=timeout)
        return {"status": "ok", "action": "wait", "ref": ref}

    def wait_for_timeout(self, ms: int) -> dict:
        self.page.wait_for_timeout(ms)
        return {"status": "ok", "action": "wait", "ms": ms}

    def find(self, locator_type: str, value: str, name: str | None = None) -> dict:
        locators = {
            "role": lambda: self.page.get_by_role(value, name=name),
            "text": lambda: self.page.get_by_text(value),
            "label": lambda: self.page.get_by_label(value),
            "placeholder": lambda: self.page.get_by_placeholder(value),
            "alt": lambda: self.page.get_by_alt_text(value),
            "title": lambda: self.page.get_by_title(value),
            "testid": lambda: self.page.get_by_test_id(value),
        }
        if locator_type not in locators:
            raise ValueError(f"Unknown locator type: {locator_type}")
        locator = locators[locator_type]()
        snapshot = locator.aria_snapshot(mode="ai")
        return {"status": "ok", "content": snapshot}

    def go_back(self) -> dict:
        self.page.go_back()
        return {"status": "ok", "action": "back", "url": self.page.url}

    def go_forward(self) -> dict:
        self.page.go_forward()
        return {"status": "ok", "action": "forward", "url": self.page.url}

    def reload(self) -> dict:
        self.page.reload()
        return {"status": "ok", "action": "reload", "url": self.page.url}

    def press(self, key: str) -> dict:
        self.page.keyboard.press(key)
        return {"status": "ok", "action": "press", "key": key}

    def select_option(self, ref: str, value: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).select_option(value)
        return {"status": "ok", "action": "select", "ref": ref, "value": value}

    def check(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).check()
        return {"status": "ok", "action": "check", "ref": ref}

    def uncheck(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).uncheck()
        return {"status": "ok", "action": "uncheck", "ref": ref}

    def dblclick(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).dblclick()
        return {"status": "ok", "action": "dblclick", "ref": ref}

    def drag(self, src_ref: str, dst_ref: str) -> dict:
        src_entry = self._resolve(src_ref)
        dst_entry = self._resolve(dst_ref)
        src_loc = self._locator(src_entry)
        dst_loc = self._locator(dst_entry)
        src_loc.drag_to(dst_loc)
        return {"status": "ok", "action": "drag", "src": src_ref, "dst": dst_ref}

    def scroll_into_view(self, ref: str) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).scroll_into_view_if_needed()
        return {"status": "ok", "action": "scroll_into_view", "ref": ref}

    def count(self, selector: str) -> dict:
        n = self.page.locator(selector).count()
        return {"status": "ok", "action": "count", "value": n}

    def upload(self, ref: str, files: list[str]) -> dict:
        entry = self._resolve(ref)
        self._locator(entry).set_input_files(files)
        return {"status": "ok", "action": "upload", "ref": ref, "files": files}

    def download(self, ref: str, save_path: str) -> dict:
        entry = self._resolve(ref)
        loc = self._locator(entry)
        with self.page.expect_download() as d:
            loc.click()
        download = d.value
        download.save_as(save_path)
        return {"status": "ok", "action": "download", "ref": ref, "path": save_path}
