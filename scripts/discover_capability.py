import argparse
import json
from pathlib import Path

from src.discovery.agent import DiscoveryAgent
from src.discovery.groq_client import GroqLLMClient
from src.surfaces.playwright_surface import PlaywrightSurface


def main():
    parser = argparse.ArgumentParser(
        description="Run an LLM-driven UI discovery."
    )

    parser.add_argument(
        "--goal",
        required=True,
        help="Natural-language goal for the discovery agent.",
    )

    parser.add_argument(
        "--entrypoint",
        default="http://127.0.0.1:8000/",
        help="Application entry point.",
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show Chromium while discovery runs.",
    )

    args = parser.parse_args()

    surface = PlaywrightSurface(
        headless=not args.headed,
        timeout_ms=5000,
    )

    llm = GroqLLMClient()

    agent = DiscoveryAgent(
        surface=surface,
        llm=llm,
        max_steps=12,
    )

    print("\nStarting LLM-driven discovery...")
    print(f"Goal: {args.goal}")
    print(f"Entrypoint: {args.entrypoint}")
    print()

    result = agent.run(
        goal=args.goal,
        entrypoint=args.entrypoint,
    )

    evidence_dir = Path("evidence")

    evidence_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        evidence_dir
        / "discovery_run.json"
    )

    output_path.write_text(
        result.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            result.model_dump(
                mode="json"
            ),
            indent=2,
        )
    )

    print(
        "\nDiscovery evidence saved to:"
    )

    print(output_path)


if __name__ == "__main__":
    main()