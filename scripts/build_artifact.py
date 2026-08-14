import argparse
import json
from pathlib import Path

from src.artifacts.builder import ArtifactBuilder
from src.discovery.models import DiscoveryResult


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic capability artifact "
            "from a successful discovery trace."
        )
    )

    parser.add_argument(
        "discovery",
        help="Path to successful discovery JSON",
    )

    parser.add_argument(
        "--member-id",
        required=True,
        help=(
            "Concrete member ID used during discovery. "
            "It will be replaced with {{ member_id }}."
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "artifacts/"
            "generated_lookup_savings_balance.v1.json"
        ),
        help="Output artifact path",
    )

    args = parser.parse_args()

    discovery_path = Path(
        args.discovery
    )

    data = json.loads(
        discovery_path.read_text(
            encoding="utf-8"
        )
    )

    discovery = (
        DiscoveryResult.model_validate(
            data
        )
    )

    builder = ArtifactBuilder()

    artifact = (
        builder.build_lookup_savings_balance(
            discovery=discovery,
            discovered_member_id=args.member_id,
        )
    )

    output_path = Path(
        args.output
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        artifact.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    print(
        f"Artifact generated successfully:"
    )

    print(output_path)

    print()

    print(
        f"Capability: "
        f"{artifact.capability.name}"
    )

    print(
        f"Version: "
        f"{artifact.capability.version}"
    )

    print(
        f"Steps: {len(artifact.steps)}"
    )


if __name__ == "__main__":
    main()