from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    FILL = "fill"
    CLICK = "click"
    EXTRACT = "extract"


class ParameterType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"


class CheckpointType(str, Enum):
    URL_CONTAINS = "url_contains"
    TEXT_PRESENT = "text_present"
    ELEMENT_PRESENT = "element_present"


class Locator(BaseModel):
    role: str | None = None
    name: str | None = None
    text: str | None = None
    css: str | None = None


class Checkpoint(BaseModel):
    type: CheckpointType
    value: str


class InputParameter(BaseModel):
    name: str
    type: ParameterType
    required: bool = True
    description: str | None = None


class OutputDefinition(BaseModel):
    name: str
    type: ParameterType
    description: str | None = None


class CapabilityMetadata(BaseModel):
    name: str
    version: str
    description: str


class Entrypoint(BaseModel):
    url: str


class Step(BaseModel):
    id: str
    action: ActionType
    target: Locator | None = None
    value: Any | None = None
    output: str | None = None
    checkpoint: Checkpoint | None = None


class OutcomeDefinition(BaseModel):
    code: str
    detect: Checkpoint
    description: str | None = None


class PolicyMetadata(BaseModel):
    allowed_action_types: list[ActionType]
    risk_level: RiskLevel = RiskLevel.READ_ONLY


class CapabilityArtifact(BaseModel):
    schema_version: str = Field(
        description="Version of the capability artifact schema"
    )

    capability: CapabilityMetadata
    inputs: list[InputParameter]
    outputs: list[OutputDefinition]
    entrypoint: Entrypoint
    steps: list[Step]
    success_condition: Checkpoint
    business_outcomes: list[OutcomeDefinition] = []
    failure_conditions: list[OutcomeDefinition] = []
    policy: PolicyMetadata