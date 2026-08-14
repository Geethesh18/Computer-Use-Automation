from enum import Enum

from pydantic import BaseModel, ConfigDict


class DiscoveryAction(str, Enum):
    FILL = "fill"
    CLICK = "click"
    NAVIGATE = "navigate"
    READ = "read"
    COMPLETE = "complete"
    ESCALATE = "escalate"


class DiscoveryTarget(BaseModel):
    """
    UI target proposed by the discovery LLM.
    """

    model_config = ConfigDict(extra="forbid")

    role: str | None
    name: str | None
    text: str | None
    css: str | None


class DiscoveryOutputs(BaseModel):
    """
    Typed outputs the discovery agent may return
    when the goal is complete.
    """

    model_config = ConfigDict(extra="forbid")

    balance: float | None


class AgentDecision(BaseModel):
    """
    Exactly one decision returned by the LLM.
    """

    model_config = ConfigDict(extra="forbid")

    action: DiscoveryAction

    target: DiscoveryTarget | None

    value: str | None

    outputs: DiscoveryOutputs

    reason: str


class Observation(BaseModel):
    """
    Current state observed from the UI.
    """

    url: str

    visible_text: str


class DiscoveryStep(BaseModel):
    """
    One observe -> decide -> act iteration.
    """

    step_number: int

    observation: Observation

    decision: AgentDecision

    result: str | None = None


class DiscoveryResult(BaseModel):
    """
    Final result of an LLM-driven discovery run.
    """

    success: bool

    goal: str

    outputs: dict = {}

    steps: list[DiscoveryStep] = []

    reason: str | None = None