from typing import Any

from pydantic import BaseModel, Field


class HandoffPackage(BaseModel):
    """
    Structured context supplied to a human when
    automation cannot safely continue.
    """

    reason_code: str

    reason: str

    goal: str | None = None

    current_url: str | None = None

    last_observation: str | None = None

    failed_step: str | None = None

    attempted_actions: list[dict[str, Any]] = Field(
        default_factory=list
    )

    evidence_path: str | None = None

    suggested_human_action: str | None = None