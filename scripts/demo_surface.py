import time

from src.artifacts.models import Locator
from src.surfaces.playwright_surface import PlaywrightSurface


def main():
    surface = PlaywrightSurface(
        headless=False,
        timeout_ms=5000,
    )

    try:
        # Start Chromium
        surface.start()

        # 1. Open the banking application
        surface.navigate("http://127.0.0.1:8000/")
        time.sleep(1)

        # 2. Enter member ID
        surface.fill(
            Locator(
                role="textbox",
                name="Member ID",
            ),
            "10001",
        )
        time.sleep(1)

        # 3. Search for the member
        surface.click(
            Locator(
                role="button",
                name="Search Member",
            )
        )
        time.sleep(1)

        # 4. Open member accounts
        surface.click(
            Locator(
                role="link",
                name="View Accounts",
            )
        )
        time.sleep(1)

        # 5. Open the Savings account
        surface.click(
            Locator(
                css="tr:has-text('Savings') a"
            )
        )
        time.sleep(1)

        # 6. Display final state
        print("\nCurrent URL:")
        print(surface.get_url())

        print("\nVisible page text:")
        print(surface.get_visible_text())

        # 7. Save evidence
        surface.screenshot(
            "evidence/step4_surface_demo.png"
        )

        print(
            "\nScreenshot saved to "
            "evidence/step4_surface_demo.png"
        )

        # Keep browser visible briefly
        time.sleep(3)

    finally:
        surface.stop()


if __name__ == "__main__":
    main()