from pathlib import Path

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from src.artifacts.models import Locator
from src.surfaces.base import ComputerSurface


class PlaywrightSurface(ComputerSurface):

    def __init__(
        self,
        headless: bool = False,
        timeout_ms: int = 5000,
    ):
        self.headless = headless
        self.timeout_ms = timeout_ms

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError(
                "Surface has not been started. Call start() first."
            )

        return self._page

    def start(self) -> None:
        self._playwright = sync_playwright().start()

        self._browser = self._playwright.chromium.launch(
            headless=self.headless
        )

        self._context = self._browser.new_context()

        self._page = self._context.new_page()

        self._page.set_default_timeout(self.timeout_ms)

    def stop(self) -> None:
        if self._context is not None:
            self._context.close()

        if self._browser is not None:
            self._browser.close()

        if self._playwright is not None:
            self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    def navigate(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded")

    def click(self, target: Locator) -> None:
        locator = self._resolve_locator(target)
        locator.click()

    def fill(self, target: Locator, value: str) -> None:
        locator = self._resolve_locator(target)
        locator.fill(value)

    def extract_text(self, target: Locator) -> str:
        locator = self._resolve_locator(target)

        return locator.inner_text().strip()

    def get_url(self) -> str:
        return self.page.url

    def get_visible_text(self) -> str:
        return self.page.locator("body").inner_text()

    def screenshot(self, path: str | Path) -> None:
        screenshot_path = Path(path)

        screenshot_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.page.screenshot(
            path=str(screenshot_path),
            full_page=True,
        )

    def _resolve_locator(self, target: Locator):
        """
        Resolve an artifact locator into a Playwright locator.

        Preferred order:
        1. accessibility role + name
        2. text
        3. CSS fallback
        """

        if target.role and target.name:
            return self.page.get_by_role(
                target.role,
                name=target.name,
                exact=True,
            )

        if target.text:
            return self.page.get_by_text(
                target.text,
                exact=True,
            )

        if target.css:
            return self.page.locator(target.css)

        raise ValueError(
            "Locator must provide role/name, text, or css."
        )