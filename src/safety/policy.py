from urllib.parse import urlparse

from src.artifacts.models import (
    ActionType,
    CapabilityArtifact,
    RiskLevel,
)


class SafetyViolation(Exception):
    """
    Raised when an action or capability violates
    centrally enforced safety policy.
    """


class SafetyPolicy:
    """
    Deterministic safety boundary shared by discovery
    and replay.

    The policy is authoritative.

    Artifacts and LLM decisions may describe or propose
    actions, but they cannot grant themselves permission.
    """

    def __init__(
        self,
        allowed_origins: set[str] | None = None,
        allowed_actions: set[ActionType] | None = None,
        allowed_risk_levels: set[RiskLevel] | None = None,
    ):
        self.allowed_origins = (
            allowed_origins
            if allowed_origins is not None
            else {
                "http://127.0.0.1:8000",
                "http://localhost:8000",
            }
        )

        self.allowed_actions = (
            allowed_actions
            if allowed_actions is not None
            else {
                ActionType.NAVIGATE,
                ActionType.FILL,
                ActionType.CLICK,
                ActionType.EXTRACT,
            }
        )

        self.allowed_risk_levels = (
            allowed_risk_levels
            if allowed_risk_levels is not None
            else {
                RiskLevel.READ_ONLY,
            }
        )

    # =====================================================
    # Capability validation
    # =====================================================

    def validate_artifact(
        self,
        artifact: CapabilityArtifact,
    ) -> None:
        """
        Validate the artifact before replay starts.
        """

        if (
            artifact.policy.risk_level
            not in self.allowed_risk_levels
        ):
            raise SafetyViolation(
                "Artifact risk level is not permitted: "
                f"{artifact.policy.risk_level.value}"
            )

        self.validate_url(
            artifact.entrypoint.url
        )

        for action in (
            artifact.policy.allowed_action_types
        ):
            if action not in self.allowed_actions:
                raise SafetyViolation(
                    "Artifact requests an action type "
                    "that central policy does not allow: "
                    f"{action.value}"
                )

        for step in artifact.steps:
            self.validate_action(
                step.action
            )

            if (
                step.action == ActionType.NAVIGATE
                and isinstance(step.value, str)
                and not self._contains_template(
                    step.value
                )
            ):
                self.validate_url(
                    step.value
                )

    # =====================================================
    # Action validation
    # =====================================================

    def validate_action(
        self,
        action: ActionType,
    ) -> None:

        if action not in self.allowed_actions:
            raise SafetyViolation(
                "Action is not permitted by central "
                f"policy: {action.value}"
            )

    # =====================================================
    # URL / origin validation
    # =====================================================

    def validate_url(
        self,
        url: str,
    ) -> None:

        origin = self._origin(
            url
        )

        if origin not in self.allowed_origins:
            raise SafetyViolation(
                "Navigation outside the allowed origin "
                f"is blocked: {origin}"
            )

    def _origin(
        self,
        url: str,
    ) -> str:

        parsed = urlparse(
            url
        )

        if not parsed.scheme or not parsed.netloc:
            raise SafetyViolation(
                f"Invalid absolute URL: {url}"
            )

        return (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
        )

    def _contains_template(
        self,
        value: str,
    ) -> bool:

        return (
            "{{" in value
            and "}}" in value
        )