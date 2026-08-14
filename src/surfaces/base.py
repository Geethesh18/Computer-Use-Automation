from abc import ABC, abstractmethod
from pathlib import Path

from src.artifacts.models import Locator


class ComputerSurface(ABC):
    """
    Abstract interface for interacting with a computer surface.

    Discovery and replay depend on this interface rather than
    directly depending on Playwright.
    """

    @abstractmethod
    def start(self) -> None:
        """Start the surface/session."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the surface/session."""
        pass

    @abstractmethod
    def navigate(self, url: str) -> None:
        """Navigate to a target location."""
        pass

    @abstractmethod
    def click(self, target: Locator) -> None:
        """Click a UI control."""
        pass

    @abstractmethod
    def fill(self, target: Locator, value: str) -> None:
        """Enter text into a UI control."""
        pass

    @abstractmethod
    def extract_text(self, target: Locator) -> str:
        """Extract text associated with a target."""
        pass

    @abstractmethod
    def get_url(self) -> str:
        """Return the current location."""
        pass

    @abstractmethod
    def get_visible_text(self) -> str:
        """Return visible textual state."""
        pass

    @abstractmethod
    def screenshot(self, path: str | Path) -> None:
        """Capture evidence of the current state."""
        pass