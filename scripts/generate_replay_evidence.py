import json
from pathlib import Path

from src.artifacts.loader import load_artifact
from src.replay.engine import ReplayEngine
from src.surfaces.playwright_surface import PlaywrightSurface


ARTIFACT_PATH = (
    "artifacts/"
    "generated_lookup_savings_balance.v1.json"
)

EVIDENCE_DIR = Path(
    "evidence/replay"
)


def run_replay(
    member_id: str,
) -> dict:
    """
    Run deterministic replay for one member ID.

    The generated artifact is used.
    No LLM is involved in this execution path.
    """

    artifact = load_artifact(
        ARTIFACT_PATH
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
            "member_id": member_id,
        },
    )

    return result.model_dump(
        mode="json"
    )


def save_result(
    name: str,
    result: dict,
) -> None:
    """
    Save one replay result as structured JSON evidence.
    """

    EVIDENCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        EVIDENCE_DIR
        / f"{name}.json"
    )

    path.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Saved: {path}"
    )


def main():
    """
    Generate deterministic replay evidence.

    Scenarios:

    10001
        Successful replay for the member originally
        used during discovery.

    10002
        Successful replay with a different input,
        proving artifact reuse.

    99999
        Expected MEMBER_NOT_FOUND business outcome.

    10003
        Expected PERMISSION_DENIED hard failure.
    """

    scenarios = {
        "success_10001": "10001",
        "success_10002": "10002",
        "member_not_found_99999": "99999",
        "permission_denied_10003": "10003",
    }

    print(
        "Generating deterministic replay evidence..."
    )

    print()

    for name, member_id in scenarios.items():

        print(
            f"Running member_id={member_id}"
        )

        result = run_replay(
            member_id
        )

        save_result(
            name,
            result,
        )

        print(
            json.dumps(
                result,
                indent=2,
            )
        )

        print()

    print(
        "Replay evidence generation complete."
    )


if __name__ == "__main__":
    main()