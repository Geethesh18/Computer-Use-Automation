from src.artifacts.models import Locator
from src.surfaces.playwright_surface import PlaywrightSurface


def test_playwright_surface_can_navigate_mock_bank():
    surface = PlaywrightSurface(headless=True)

    try:
        surface.start()

        surface.navigate("http://127.0.0.1:8000/")

        assert "Member Search" in surface.get_visible_text()

        surface.fill(
            Locator(
                role="textbox",
                name="Member ID",
            ),
            "10001",
        )

        surface.click(
            Locator(
                role="button",
                name="Search Member",
            )
        )

        assert "/members/10001" in surface.get_url()
        assert "Alex Morgan" in surface.get_visible_text()

    finally:
        surface.stop()