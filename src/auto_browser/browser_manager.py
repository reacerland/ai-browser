from __future__ import annotations

from playwright.sync_api import Browser, BrowserContext, Page


class BrowserManager:
    """Wraps cloakbrowser launch functions and manages the active page."""

    def __init__(
        self,
        session_name: str,
        headed: bool,
        user_data_dir: str | None,
    ) -> None:
        self.session_name = session_name
        self.headed = headed
        self.user_data_dir = user_data_dir
        self._page: Page | None = None
        self._context: BrowserContext | None = None
        self._browser: Browser | None = None
        self._close_fn = None

    def start(self) -> None:
        if self.user_data_dir:
            self._start_persistent()
        else:
            self._start_default()

    def _start_default(self) -> None:
        from cloakbrowser import launch

        self._browser = launch(headless=not self.headed)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._close_fn = self._browser.close

    def _start_persistent(self) -> None:
        from cloakbrowser import launch_persistent_context

        self._context = launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=not self.headed,
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._close_fn = self._context.close

    @property
    def page(self) -> Page:
        assert self._page is not None, "Browser not started"
        return self._page

    def is_alive(self) -> bool:
        return self._page is not None and self._context is not None

    def navigate(self, url: str, timeout: float = 30_000) -> None:
        self.page.goto(url, timeout=timeout)

    def close(self) -> None:
        if self._close_fn is not None:
            self._close_fn()
        self._page = None
        self._context = None
        self._browser = None
        self._close_fn = None
