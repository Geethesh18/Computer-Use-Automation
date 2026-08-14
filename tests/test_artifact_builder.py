import json

from src.artifacts.builder import ArtifactBuilder
from src.discovery.models import DiscoveryResult


DISCOVERY_PATH = "evidence/discovery_success_10001.json"


def load_discovery() -> DiscoveryResult:
    with open(
        DISCOVERY_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return DiscoveryResult.model_validate(data)


def test_builder_creates_reusable_artifact():
    discovery = load_discovery()

    builder = ArtifactBuilder()

    artifact = builder.build_lookup_savings_balance(
        discovery=discovery,
        discovered_member_id="10001",
    )

    assert artifact.schema_version == "1.0"

    assert (
        artifact.capability.name
        == "lookup_savings_balance"
    )

    assert len(artifact.steps) == 5

    # Concrete discovery input must become a parameter.
    fill_step = artifact.steps[0]

    assert fill_step.value == "{{ member_id }}"

    # Artifact declares the expected output.
    assert artifact.outputs[0].name == "balance"


def test_builder_parameterizes_url_checkpoints():
    discovery = load_discovery()

    builder = ArtifactBuilder()

    artifact = builder.build_lookup_savings_balance(
        discovery=discovery,
        discovered_member_id="10001",
    )

    checkpoint_values = [
        step.checkpoint.value
        for step in artifact.steps
        if step.checkpoint is not None
    ]

    assert "/members/{{ member_id }}" in checkpoint_values

    assert (
        "/members/{{ member_id }}/accounts"
        in checkpoint_values
    )

    assert (
        "/members/{{ member_id }}/accounts/savings"
        in checkpoint_values
    )

    # Discovery-specific ID must not remain embedded
    # inside generated checkpoints.
    assert all(
        "10001" not in value
        for value in checkpoint_values
    )


def test_builder_preserves_discovered_savings_locator():
    discovery = load_discovery()

    builder = ArtifactBuilder()

    artifact = builder.build_lookup_savings_balance(
        discovery=discovery,
        discovered_member_id="10001",
    )

    savings_steps = [
        step
        for step in artifact.steps
        if (
            step.target is not None
            and step.target.css is not None
            and "Savings" in step.target.css
        )
    ]

    assert len(savings_steps) == 1

    assert (
        savings_steps[0].target.css
        == "tr:has-text('Savings') a"
    )