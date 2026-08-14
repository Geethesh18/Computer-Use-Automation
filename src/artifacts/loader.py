import json
from pathlib import Path

from src.artifacts.models import CapabilityArtifact


def load_artifact(path: str | Path) -> CapabilityArtifact:
    artifact_path = Path(path)

    if not artifact_path.exists():
        raise FileNotFoundError(
            f"Artifact not found: {artifact_path}"
        )

    with artifact_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return CapabilityArtifact.model_validate(data)