from enum import Enum
from typing import Any

from pydantic import BaseModel


class ReplayStatus(str, Enum):
    SUCCESS = "success"
    BUSINESS_OUTCOME = "business_outcome"
    FAILURE = "failure"


class ReplayResult(BaseModel):
    status: ReplayStatus

    outputs: dict[str, Any] = {}

    code: str | None = None

    step_id: str | None = None

    message: str | None = None

    expected: str | None = None

    observed: str | None = None

    attempts: int | None = None

    recoverable: bool | None = None