import re
from typing import Any

from src.artifacts.models import (
    ActionType,
    CapabilityArtifact,
    CapabilityMetadata,
    Checkpoint,
    CheckpointType,
    Entrypoint,
    InputParameter,
    Locator,
    OutcomeDefinition,
    OutputDefinition,
    ParameterType,
    PolicyMetadata,
    RiskLevel,
    Step,
)
from src.discovery.models import (
    DiscoveryAction,
    DiscoveryResult,
)


class ArtifactBuilder:
    """
    Converts a successful LLM discovery result into a
    reusable deterministic capability artifact.

    The builder:
    - keeps successful discovered UI actions
    - removes discovery-only reasoning/actions
    - parameterizes invocation-specific values
    - derives deterministic checkpoints
    - adds typed output extraction
    """

    def build_lookup_savings_balance(
        self,
        discovery: DiscoveryResult,
        discovered_member_id: str,
    ) -> CapabilityArtifact:

        # -------------------------------------------------
        # Validate discovery result
        # -------------------------------------------------

        if not discovery.success:
            raise ValueError(
                "Cannot build an artifact from an "
                "unsuccessful discovery run."
            )

        if "balance" not in discovery.outputs:
            raise ValueError(
                "Discovery did not produce the required "
                "'balance' output."
            )

        if not discovered_member_id:
            raise ValueError(
                "discovered_member_id cannot be empty."
            )

        steps: list[Step] = []

        # -------------------------------------------------
        # Convert discovery actions into replay actions
        # -------------------------------------------------

        for discovery_step in discovery.steps:

            decision = discovery_step.decision

            # COMPLETE represents discovery completion.
            # It is not an executable replay action.
            if decision.action == DiscoveryAction.COMPLETE:
                continue

            # READ only asks for another observation.
            # Replay already executes known deterministic
            # actions, so READ is not needed.
            if decision.action == DiscoveryAction.READ:
                continue

            # An escalated discovery should not become a
            # normal deterministic capability.
            if decision.action == DiscoveryAction.ESCALATE:
                raise ValueError(
                    "Cannot build an artifact from an "
                    "escalated discovery run."
                )

            # Only successfully executed discovery actions
            # should become part of the artifact.
            if discovery_step.result != "executed":
                continue

            target = None

            if decision.target is not None:
                target = Locator(
                    role=decision.target.role,
                    name=decision.target.name,
                    text=decision.target.text,
                    css=decision.target.css,
                )

            action = self._map_action(
                decision.action
            )

            value: Any = decision.value

            # -------------------------------------------------
            # Parameterize discovery-specific input
            # -------------------------------------------------

            if (
                decision.action == DiscoveryAction.FILL
                and decision.value == discovered_member_id
            ):
                value = "{{ member_id }}"

            # -------------------------------------------------
            # Derive checkpoint from the next observation
            # -------------------------------------------------

            checkpoint = self._derive_checkpoint(
                discovery=discovery,
                step_number=discovery_step.step_number,
                discovered_member_id=discovered_member_id,
            )

            step = Step(
                id=self._step_id(
                    discovery_step.step_number,
                    decision.action,
                ),
                action=action,
                target=target,
                value=value,
                checkpoint=checkpoint,
            )

            steps.append(step)

        # -------------------------------------------------
        # Add deterministic output extraction
        # -------------------------------------------------

        # Discovery finishes when the LLM observes the
        # requested balance. Replay needs an explicit
        # extraction operation to produce the declared
        # output.
        steps.append(
            Step(
                id="extract_balance",
                action=ActionType.EXTRACT,
                target=Locator(
                    text="Current Balance"
                ),
                output="balance",
            )
        )

        # -------------------------------------------------
        # Construct typed capability artifact
        # -------------------------------------------------

        return CapabilityArtifact(
            schema_version="1.0",

            capability=CapabilityMetadata(
                name="lookup_savings_balance",
                version="1.0.0",
                description=(
                    "Look up a member and return their "
                    "current savings balance"
                ),
            ),

            inputs=[
                InputParameter(
                    name="member_id",
                    type=ParameterType.STRING,
                    required=True,
                    description=(
                        "Member identifier used for lookup"
                    ),
                )
            ],

            outputs=[
                OutputDefinition(
                    name="balance",
                    type=ParameterType.NUMBER,
                    description=(
                        "Current savings account balance"
                    ),
                )
            ],

            entrypoint=Entrypoint(
                url=self._entrypoint(
                    discovery
                )
            ),

            steps=steps,

            success_condition=Checkpoint(
                type=CheckpointType.TEXT_PRESENT,
                value="Current Balance",
            ),

            business_outcomes=[
                OutcomeDefinition(
                    code="MEMBER_NOT_FOUND",
                    detect=Checkpoint(
                        type=CheckpointType.TEXT_PRESENT,
                        value="No member record was found",
                    ),
                    description=(
                        "No member exists for the supplied "
                        "member ID"
                    ),
                )
            ],

            failure_conditions=[
                OutcomeDefinition(
                    code="PERMISSION_DENIED",
                    detect=Checkpoint(
                        type=CheckpointType.TEXT_PRESENT,
                        value="Permission Denied",
                    ),
                    description=(
                        "Account information cannot be accessed"
                    ),
                )
            ],

            policy=PolicyMetadata(
                allowed_action_types=[
                    ActionType.NAVIGATE,
                    ActionType.FILL,
                    ActionType.CLICK,
                    ActionType.EXTRACT,
                ],
                risk_level=RiskLevel.READ_ONLY,
            ),
        )

    # =====================================================
    # Discovery action -> replay action
    # =====================================================

    def _map_action(
        self,
        action: DiscoveryAction,
    ) -> ActionType:

        mapping = {
            DiscoveryAction.FILL: ActionType.FILL,
            DiscoveryAction.CLICK: ActionType.CLICK,
            DiscoveryAction.NAVIGATE: ActionType.NAVIGATE,
        }

        if action not in mapping:
            raise ValueError(
                f"Discovery action '{action}' cannot be "
                "converted into a replay action."
            )

        return mapping[action]

    # =====================================================
    # Generate stable step identifier
    # =====================================================

    def _step_id(
        self,
        step_number: int,
        action: DiscoveryAction,
    ) -> str:

        return (
            f"discovered_{step_number}_"
            f"{action.value}"
        )

    # =====================================================
    # Determine artifact entrypoint
    # =====================================================

    def _entrypoint(
        self,
        discovery: DiscoveryResult,
    ) -> str:

        if not discovery.steps:
            raise ValueError(
                "Discovery contains no steps."
            )

        return (
            discovery
            .steps[0]
            .observation
            .url
        )

    # =====================================================
    # Derive reusable checkpoints
    # =====================================================

    def _derive_checkpoint(
        self,
        discovery: DiscoveryResult,
        step_number: int,
        discovered_member_id: str,
    ) -> Checkpoint | None:
        """
        Derive a reusable checkpoint from the URL observed
        after a discovered action.

        The next discovery observation represents the
        state reached after the current action.

        Any occurrence of the concrete member ID used
        during discovery is replaced with {{ member_id }}
        so the checkpoint works with future invocations.

        Example:

        Discovery:
            /members/10001/accounts

        Artifact:
            /members/{{ member_id }}/accounts
        """

        current_index = (
            step_number - 1
        )

        next_index = (
            current_index + 1
        )

        # There is no following observation from which
        # to derive a checkpoint.
        if next_index >= len(
            discovery.steps
        ):
            return None

        current_url = (
            discovery
            .steps[current_index]
            .observation
            .url
        )

        next_url = (
            discovery
            .steps[next_index]
            .observation
            .url
        )

        # If the action did not change location,
        # don't create a URL checkpoint.
        if next_url == current_url:
            return None

        path = self._url_path(
            next_url
        )

        if not path:
            return None

        # -------------------------------------------------
        # Generalize discovery-specific member ID
        # -------------------------------------------------

        parameterized_path = (
            path.replace(
                discovered_member_id,
                "{{ member_id }}",
            )
        )

        return Checkpoint(
            type=CheckpointType.URL_CONTAINS,
            value=parameterized_path,
        )

    # =====================================================
    # Extract URL path
    # =====================================================

    def _url_path(
        self,
        url: str,
    ) -> str:
        """
        Convert:

        http://127.0.0.1:8000/members/10001/accounts

        into:

        /members/10001/accounts
        """

        match = re.match(
            r"https?://[^/]+(/.*)?$",
            url,
        )

        if not match:
            return url

        path = match.group(1)

        return path or "/"