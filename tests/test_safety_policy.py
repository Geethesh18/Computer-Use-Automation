import pytest

from src.artifacts.loader import load_artifact
from src.artifacts.models import (
    ActionType,
    RiskLevel,
)
from src.replay.engine import ReplayEngine
from src.replay.models import ReplayStatus
from src.safety.policy import (
    SafetyPolicy,
    SafetyViolation,
)
from src.surfaces.playwright_surface import PlaywrightSurface


ARTIFACT_PATH = (
    "artifacts/"
    "generated_lookup_savings_balance.v1.json"
)


def test_read_only_artifact_is_allowed():
    """
    The normal generated read-only banking artifact
    should be accepted by central safety policy.
    """

    artifact = load_artifact(
        ARTIFACT_PATH
    )

    policy = SafetyPolicy()

    # Should complete without raising SafetyViolation.
    policy.validate_artifact(
        artifact
    )


def test_external_origin_is_blocked():
    """
    Navigation outside the configured banking
    application origin must be rejected.
    """

    policy = SafetyPolicy()

    with pytest.raises(
        SafetyViolation
    ):
        policy.validate_url(
            "https://example.com/"
        )


def test_disallowed_action_is_blocked():
    """
    Central policy must be able to deny an action
    even if an artifact wants to use it.
    """

    policy = SafetyPolicy(
        allowed_actions={
            ActionType.FILL,
            ActionType.EXTRACT,
        }
    )

    with pytest.raises(
        SafetyViolation
    ):
        policy.validate_action(
            ActionType.CLICK
        )


def test_irreversible_artifact_is_blocked():
    """
    The central policy allows read-only capabilities
    by default.

    An artifact cannot grant itself permission simply
    by declaring a higher risk level.
    """

    artifact = load_artifact(
        ARTIFACT_PATH
    )

    artifact.policy.risk_level = (
        RiskLevel.IRREVERSIBLE
    )

    policy = SafetyPolicy()

    with pytest.raises(
        SafetyViolation
    ):
        policy.validate_artifact(
            artifact
        )


def test_replay_rejects_unsafe_artifact_before_execution():
    """
    ReplayEngine must reject an artifact with an
    external entrypoint before executing the workflow.
    """

    artifact = load_artifact(
        ARTIFACT_PATH
    )

    artifact.entrypoint.url = (
        "https://example.com/"
    )

    surface = PlaywrightSurface(
        headless=True
    )

    engine = ReplayEngine(
        surface=surface
    )

    result = engine.replay(
        artifact,
        {
            "member_id": "10001",
        },
    )

    assert (
        result.status
        == ReplayStatus.FAILURE
    )

    assert (
        result.code
        == "SAFETY_VIOLATION"
    )

    assert result.recoverable is False