import argparse
import json

from src.artifacts.loader import load_artifact
from src.replay.engine import ReplayEngine
from src.surfaces.playwright_surface import PlaywrightSurface


def main():
    parser = argparse.ArgumentParser(
        description="Deterministically replay a capability artifact."
    )

    parser.add_argument(
        "artifact",
        help="Path to the capability artifact JSON file",
    )

    parser.add_argument(
        "--member-id",
        required=True,
        help="Member ID used for the capability invocation",
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser during replay",
    )

    args = parser.parse_args()

    artifact = load_artifact(args.artifact)

    surface = PlaywrightSurface(
        headless=not args.headed
    )

    engine = ReplayEngine(surface)

    result = engine.replay(
        artifact,
        {
            "member_id": args.member_id,
        },
    )

    print(
        json.dumps(
            result.model_dump(mode="json"),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()