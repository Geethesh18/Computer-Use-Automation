from src.artifacts.models import (
    ActionType,
    Locator,
)
from src.discovery.llm import LLMClient
from src.discovery.models import (
    AgentDecision,
    DiscoveryAction,
    DiscoveryResult,
    DiscoveryStep,
    Observation,
)
from src.handoff.manager import HandoffManager
from src.handoff.models import HandoffPackage
from src.safety.policy import (
    SafetyPolicy,
    SafetyViolation,
)
from src.surfaces.base import ComputerSurface


class DiscoveryAgent:
    """
    LLM-driven discovery agent.

    The LLM proposes one action at a time.

    Central deterministic safety policy decides whether
    the proposed action may execute.

    Ordinary UI execution failures may be returned to the
    LLM for recovery.

    Safety violations are never retried or sent back to
    the model for circumvention. They produce a structured
    human handoff.
    """

    def __init__(
        self,
        surface: ComputerSurface,
        llm: LLMClient,
        max_steps: int = 15,
        safety_policy: SafetyPolicy | None = None,
        handoff_manager: HandoffManager | None = None,
    ):
        self.surface = surface
        self.llm = llm
        self.max_steps = max_steps

        self.safety_policy = (
            safety_policy
            if safety_policy is not None
            else SafetyPolicy()
        )

        self.handoff_manager = (
            handoff_manager
            if handoff_manager is not None
            else HandoffManager()
        )

    # =====================================================
    # Main discovery loop
    # =====================================================

    def run(
        self,
        goal: str,
        entrypoint: str,
    ) -> DiscoveryResult:

        history: list[dict] = []
        steps: list[DiscoveryStep] = []

        surface_started = False

        try:
            # -------------------------------------------------
            # Validate entrypoint BEFORE starting the surface
            # -------------------------------------------------

            try:
                self.safety_policy.validate_url(
                    entrypoint
                )

            except SafetyViolation as exc:
                evidence_path = self._create_handoff(
                    reason_code="SAFETY_VIOLATION",
                    reason=str(exc),
                    goal=goal,
                    current_url=entrypoint,
                    last_observation=None,
                    failed_step="entrypoint",
                    attempted_actions=history,
                    name="discovery_entrypoint_safety_violation",
                    suggested_human_action=(
                        "Review the requested application "
                        "entrypoint and the configured safety "
                        "policy before continuing."
                    ),
                )

                return DiscoveryResult(
                    success=False,
                    goal=goal,
                    steps=steps,
                    reason=(
                        "Safety policy blocked discovery "
                        f"entrypoint. Handoff saved to "
                        f"{evidence_path}"
                    ),
                )

            # -------------------------------------------------
            # Start surface
            # -------------------------------------------------

            self.surface.start()
            surface_started = True

            self.surface.navigate(
                entrypoint
            )

            # -------------------------------------------------
            # Observe -> decide -> act loop
            # -------------------------------------------------

            for step_number in range(
                1,
                self.max_steps + 1,
            ):
                # ---------------------------------------------
                # Observe current UI state
                # ---------------------------------------------

                observation = self._observe()

                # ---------------------------------------------
                # Ask LLM for exactly one next decision
                # ---------------------------------------------

                decision = self.llm.decide(
                    goal=goal,
                    observation=observation,
                    history=history,
                )

                step = DiscoveryStep(
                    step_number=step_number,
                    observation=observation,
                    decision=decision,
                )

                # =============================================
                # COMPLETE
                # =============================================

                if (
                    decision.action
                    == DiscoveryAction.COMPLETE
                ):
                    step.result = "goal_completed"

                    steps.append(
                        step
                    )

                    return DiscoveryResult(
                        success=True,
                        goal=goal,
                        outputs=(
                            decision.outputs.model_dump(
                                exclude_none=True
                            )
                        ),
                        steps=steps,
                        reason=decision.reason,
                    )

                # =============================================
                # EXPLICIT MODEL ESCALATION
                # =============================================

                if (
                    decision.action
                    == DiscoveryAction.ESCALATE
                ):
                    step.result = (
                        "escalation_requested"
                    )

                    steps.append(
                        step
                    )

                    attempted_actions = (
                        history
                        + [
                            self._history_entry(
                                step_number,
                                decision,
                                step.result,
                            )
                        ]
                    )

                    evidence_path = (
                        self._create_handoff(
                            reason_code=(
                                "MODEL_ESCALATION"
                            ),
                            reason=decision.reason,
                            goal=goal,
                            current_url=(
                                observation.url
                            ),
                            last_observation=(
                                observation.visible_text
                            ),
                            failed_step=str(
                                step_number
                            ),
                            attempted_actions=(
                                attempted_actions
                            ),
                            name=(
                                "discovery_model_"
                                "escalation"
                            ),
                            suggested_human_action=(
                                "Inspect the current UI "
                                "and determine the "
                                "appropriate next action."
                            ),
                        )
                    )

                    return DiscoveryResult(
                        success=False,
                        goal=goal,
                        steps=steps,
                        reason=(
                            f"{decision.reason} "
                            f"Handoff saved to "
                            f"{evidence_path}"
                        ),
                    )

                # =============================================
                # EXECUTE MODEL DECISION
                # =============================================

                try:
                    self._execute(
                        decision
                    )

                    step.result = "executed"

                # =============================================
                # SAFETY VIOLATION
                #
                # Never retry.
                # Never ask the model to bypass policy.
                # =============================================

                except SafetyViolation as exc:
                    step.result = (
                        f"safety_violation: {exc}"
                    )

                    steps.append(
                        step
                    )

                    attempted_actions = (
                        history
                        + [
                            self._history_entry(
                                step_number,
                                decision,
                                step.result,
                            )
                        ]
                    )

                    evidence_path = (
                        self._create_handoff(
                            reason_code=(
                                "SAFETY_VIOLATION"
                            ),
                            reason=str(exc),
                            goal=goal,
                            current_url=(
                                observation.url
                            ),
                            last_observation=(
                                observation.visible_text
                            ),
                            failed_step=str(
                                step_number
                            ),
                            attempted_actions=(
                                attempted_actions
                            ),
                            name=(
                                "discovery_safety_"
                                "violation"
                            ),
                            suggested_human_action=(
                                "Review the proposed "
                                "action and central safety "
                                "policy before continuing "
                                "manually."
                            ),
                        )
                    )

                    return DiscoveryResult(
                        success=False,
                        goal=goal,
                        steps=steps,
                        reason=(
                            "Safety policy blocked "
                            "discovery. "
                            f"Handoff saved to "
                            f"{evidence_path}"
                        ),
                    )

                # =============================================
                # ORDINARY EXECUTION FAILURE
                #
                # Recoverable discovery error.
                # Feed it into history and let the model
                # choose a corrected action.
                # =============================================

                except Exception as exc:
                    step.result = (
                        f"execution_error: {exc}"
                    )

                    steps.append(
                        step
                    )

                    history.append(
                        self._history_entry(
                            step_number,
                            decision,
                            step.result,
                        )
                    )

                    continue

                # =============================================
                # SUCCESSFUL STEP
                # =============================================

                steps.append(
                    step
                )

                history.append(
                    self._history_entry(
                        step_number,
                        decision,
                        step.result,
                    )
                )

            # -------------------------------------------------
            # Maximum-step stopping condition
            # -------------------------------------------------

            last_observation = (
                steps[-1].observation
                if steps
                else None
            )

            evidence_path = self._create_handoff(
                reason_code="MAX_STEPS_EXCEEDED",
                reason=(
                    "Maximum discovery steps reached."
                ),
                goal=goal,
                current_url=(
                    last_observation.url
                    if last_observation
                    else None
                ),
                last_observation=(
                    last_observation.visible_text
                    if last_observation
                    else None
                ),
                failed_step=(
                    str(self.max_steps)
                ),
                attempted_actions=history,
                name="discovery_max_steps",
                suggested_human_action=(
                    "Review the discovery trace and "
                    "determine whether the workflow "
                    "changed or requires manual "
                    "intervention."
                ),
            )

            return DiscoveryResult(
                success=False,
                goal=goal,
                steps=steps,
                reason=(
                    "Maximum discovery steps reached. "
                    f"Handoff saved to "
                    f"{evidence_path}"
                ),
            )

        finally:
            # Only stop the surface if it actually started.
            if surface_started:
                self.surface.stop()

    # =====================================================
    # Observation
    # =====================================================

    def _observe(
        self,
    ) -> Observation:

        return Observation(
            url=self.surface.get_url(),
            visible_text=(
                self.surface.get_visible_text()
            ),
        )

    # =====================================================
    # Execute one LLM-proposed action
    # =====================================================

    def _execute(
        self,
        decision: AgentDecision,
    ) -> None:
        """
        Execute one discovery decision.

        The LLM proposes the action.

        SafetyPolicy decides whether that action is
        permitted before ComputerSurface executes it.
        """

        # =============================================
        # FILL
        # =============================================

        if (
            decision.action
            == DiscoveryAction.FILL
        ):
            if decision.target is None:
                raise ValueError(
                    "Fill action requires a target."
                )

            if decision.value is None:
                raise ValueError(
                    "Fill action requires a value."
                )

            # Central deterministic authorization.
            self.safety_policy.validate_action(
                ActionType.FILL
            )

            target = self._to_locator(
                decision
            )

            self.surface.fill(
                target,
                decision.value,
            )

            return

        # =============================================
        # CLICK
        # =============================================

        if (
            decision.action
            == DiscoveryAction.CLICK
        ):
            if decision.target is None:
                raise ValueError(
                    "Click action requires a target."
                )

            # Central deterministic authorization.
            self.safety_policy.validate_action(
                ActionType.CLICK
            )

            target = self._to_locator(
                decision
            )

            self.surface.click(
                target
            )

            return

        # =============================================
        # NAVIGATE
        # =============================================

        if (
            decision.action
            == DiscoveryAction.NAVIGATE
        ):
            if decision.value is None:
                raise ValueError(
                    "Navigate action requires a URL."
                )

            # First authorize the action type.
            self.safety_policy.validate_action(
                ActionType.NAVIGATE
            )

            # Then authorize the destination.
            self.safety_policy.validate_url(
                decision.value
            )

            self.surface.navigate(
                decision.value
            )

            return

        # =============================================
        # READ
        # =============================================

        if (
            decision.action
            == DiscoveryAction.READ
        ):
            # READ performs no computer action.
            # The next loop iteration will observe
            # the current state again.
            return

        raise ValueError(
            f"Unsupported discovery action: "
            f"{decision.action}"
        )

    # =====================================================
    # DiscoveryTarget -> internal Locator
    # =====================================================

    def _to_locator(
        self,
        decision: AgentDecision,
    ) -> Locator:

        if decision.target is None:
            raise ValueError(
                "Action requires a target."
            )

        return Locator(
            role=decision.target.role,
            name=decision.target.name,
            text=decision.target.text,
            css=decision.target.css,
        )

    # =====================================================
    # History helper
    # =====================================================

    def _history_entry(
        self,
        step_number: int,
        decision: AgentDecision,
        result: str | None,
    ) -> dict:
        """
        Normalize one discovery action for subsequent
        LLM context and handoff evidence.
        """

        return {
            "step_number": step_number,
            "action": decision.action.value,
            "target": (
                decision.target.model_dump()
                if decision.target
                else None
            ),
            "value": decision.value,
            "reason": decision.reason,
            "result": result,
        }

    # =====================================================
    # Handoff helper
    # =====================================================

    def _create_handoff(
        self,
        reason_code: str,
        reason: str,
        goal: str,
        current_url: str | None,
        last_observation: str | None,
        failed_step: str | None,
        attempted_actions: list[dict],
        name: str,
        suggested_human_action: str,
    ) -> str:
        """
        Create and persist a structured human handoff.
        """

        package = HandoffPackage(
            reason_code=reason_code,
            reason=reason,
            goal=goal,
            current_url=current_url,
            last_observation=last_observation,
            failed_step=failed_step,
            attempted_actions=attempted_actions,
            suggested_human_action=(
                suggested_human_action
            ),
        )

        return self.handoff_manager.save(
            package,
            name,
        )