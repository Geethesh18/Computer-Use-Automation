from src.artifacts.loader import load_artifact
from src.replay.engine import ReplayEngine
from src.replay.models import ReplayStatus
from src.surfaces.playwright_surface import PlaywrightSurface


ARTIFACT_PATH = (
    "artifacts/generated_lookup_savings_balance.v1.json"
)


class FlakyPlaywrightSurface(PlaywrightSurface):
    """
    Simulates one transient click failure.

    The first click fails.
    Later clicks behave normally.
    """

    def __init__(self):
        super().__init__(
            headless=True
        )

        self.failed_once = False

    def click(self, target):

        if not self.failed_once:
            self.failed_once = True

            raise RuntimeError(
                "Simulated transient click failure"
            )

        return super().click(target)


class AlwaysFailingPlaywrightSurface(
    PlaywrightSurface
):
    """
    Simulates a permanent click failure.
    """

    def __init__(self):
        super().__init__(
            headless=True
        )

        self.click_attempts = 0

    def click(self, target):

        self.click_attempts += 1

        raise RuntimeError(
            "Simulated permanent click failure"
        )


def test_replay_recovers_from_transient_click_failure():

    artifact = load_artifact(
        ARTIFACT_PATH
    )

    surface = FlakyPlaywrightSurface()

    engine = ReplayEngine(
        surface=surface,
        max_retries=2,
    )

    result = engine.replay(
        artifact,
        {
            "member_id": "10001",
        },
    )

    assert result.status == ReplayStatus.SUCCESS

    assert result.outputs["balance"] == 4520.75

    assert surface.failed_once is True


def test_replay_stops_after_retry_budget():

    artifact = load_artifact(
        ARTIFACT_PATH
    )

    surface = AlwaysFailingPlaywrightSurface()

    engine = ReplayEngine(
        surface=surface,
        max_retries=2,
    )

    result = engine.replay(
        artifact,
        {
            "member_id": "10001",
        },
    )

    assert result.status == ReplayStatus.FAILURE

    assert result.code == "STEP_EXECUTION_FAILED"

    # Initial attempt + 2 retries
    assert result.attempts == 3

    assert result.recoverable is False

    assert surface.click_attempts == 3