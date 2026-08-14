import json

from src.artifacts.builder import ArtifactBuilder
from src.discovery.models import DiscoveryResult
from src.replay.engine import ReplayEngine
from src.replay.models import ReplayStatus
from src.surfaces.playwright_surface import PlaywrightSurface


DISCOVERY_PATH = (
    "evidence/discovery_success_10001.json"
)


def test_discovery_to_artifact_to_new_input_replay():
    """
    End-to-end proof of the core architecture:

    genuine discovery evidence
            ->
    reusable capability artifact
            ->
    deterministic replay
            ->
    different invocation input

    The discovery was performed with member 10001.

    Replay is performed with member 10002 without an LLM.
    """

    # -------------------------------------------------
    # 1. Load genuine LLM discovery evidence
    # -------------------------------------------------

    with open(
        DISCOVERY_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        discovery_data = json.load(
            file
        )

    discovery = (
        DiscoveryResult.model_validate(
            discovery_data
        )
    )

    assert discovery.success is True

    assert (
        discovery.outputs["balance"]
        == 4520.75
    )

    # -------------------------------------------------
    # 2. Build reusable artifact
    # -------------------------------------------------

    builder = ArtifactBuilder()

    artifact = (
        builder.build_lookup_savings_balance(
            discovery=discovery,
            discovered_member_id="10001",
        )
    )

    # -------------------------------------------------
    # 3. Verify discovery input was parameterized
    # -------------------------------------------------

    assert (
        artifact.steps[0].value
        == "{{ member_id }}"
    )

    # Ensure concrete discovery member ID is not
    # embedded in generated URL checkpoints.

    checkpoint_values = [
        step.checkpoint.value
        for step in artifact.steps
        if step.checkpoint is not None
    ]

    assert all(
        "10001" not in value
        for value in checkpoint_values
    )

    # -------------------------------------------------
    # 4. Replay with DIFFERENT input
    # -------------------------------------------------

    surface = PlaywrightSurface(
        headless=True
    )

    engine = ReplayEngine(
        surface=surface
    )

    result = engine.replay(
        artifact,
        {
            "member_id": "10002",
        },
    )

    # -------------------------------------------------
    # 5. Verify deterministic generalized replay
    # -------------------------------------------------

    assert (
        result.status
        == ReplayStatus.SUCCESS
    )

    assert (
        result.outputs["balance"]
        == 9875.20
    )