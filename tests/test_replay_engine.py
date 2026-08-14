import pytest

from src.artifacts.loader import load_artifact
from src.replay.engine import ReplayEngine
from src.replay.models import ReplayStatus
from src.surfaces.playwright_surface import PlaywrightSurface


ARTIFACT_PATH = "artifacts/lookup_savings_balance.v1.json"


def replay_for(member_id: str):
    artifact = load_artifact(ARTIFACT_PATH)

    surface = PlaywrightSurface(
        headless=True
    )

    engine = ReplayEngine(surface)

    return engine.replay(
        artifact,
        {
            "member_id": member_id,
        },
    )


def test_replay_returns_balance_for_member_10001():
    result = replay_for("10001")

    assert result.status == ReplayStatus.SUCCESS
    assert result.outputs["balance"] == pytest.approx(4520.75)


def test_same_artifact_replays_for_member_10002():
    result = replay_for("10002")

    assert result.status == ReplayStatus.SUCCESS
    assert result.outputs["balance"] == pytest.approx(9875.20)


def test_member_not_found_is_business_outcome():
    result = replay_for("99999")

    assert result.status == ReplayStatus.BUSINESS_OUTCOME
    assert result.code == "MEMBER_NOT_FOUND"


def test_permission_denied_is_failure():
    result = replay_for("10003")

    assert result.status == ReplayStatus.FAILURE
    assert result.code == "PERMISSION_DENIED"