import pytest
from pydantic import ValidationError

from src.artifacts.loader import load_artifact
from src.artifacts.models import CapabilityArtifact


def test_lookup_savings_balance_artifact_is_valid():
    artifact = load_artifact(
        "artifacts/lookup_savings_balance.v1.json"
    )

    assert artifact.schema_version == "1.0"
    assert artifact.capability.name == "lookup_savings_balance"
    assert artifact.capability.version == "1.0.0"

    assert len(artifact.inputs) == 1
    assert artifact.inputs[0].name == "member_id"

    assert len(artifact.outputs) == 1
    assert artifact.outputs[0].name == "balance"

    assert len(artifact.steps) == 5


def test_invalid_action_is_rejected():
    invalid_artifact = {
        "schema_version": "1.0",
        "capability": {
            "name": "invalid_capability",
            "version": "1.0.0",
            "description": "Invalid test capability",
        },
        "inputs": [],
        "outputs": [],
        "entrypoint": {
            "url": "http://127.0.0.1:8000/"
        },
        "steps": [
            {
                "id": "dangerous_step",
                "action": "destroy_database",
            }
        ],
        "success_condition": {
            "type": "text_present",
            "value": "Done",
        },
        "policy": {
            "allowed_action_types": ["click"],
            "risk_level": "read_only",
        },
    }

    with pytest.raises(ValidationError):
        CapabilityArtifact.model_validate(invalid_artifact)