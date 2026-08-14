import json
import re
from pathlib import Path

from src.handoff.models import HandoffPackage


class HandoffManager:
    """
    Creates durable, structured handoff evidence when
    automation cannot safely continue.
    """

    def __init__(
        self,
        evidence_dir: str | Path = "evidence/handoffs",
    ):
        self.evidence_dir = Path(
            evidence_dir
        )

    def save(
        self,
        package: HandoffPackage,
        name: str,
    ) -> str:

        self.evidence_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_name = re.sub(
            r"[^a-zA-Z0-9_-]",
            "_",
            name,
        )

        path = (
            self.evidence_dir
            / f"{safe_name}.json"
        )

        path.write_text(
            json.dumps(
                package.model_dump(
                    mode="json"
                ),
                indent=2,
            ),
            encoding="utf-8",
        )

        return str(path)