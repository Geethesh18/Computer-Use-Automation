from src.artifacts.models import Locator
from src.discovery.llm import LLMClient
from src.discovery.models import (
    AgentDecision,
    DiscoveryAction,
    DiscoveryResult,
    DiscoveryStep,
    Observation,
)
from src.surfaces.base import ComputerSurface


class DiscoveryAgent:

    def __init__(
        self,
        surface: ComputerSurface,
        llm: LLMClient,
        max_steps: int = 15,
    ):
        self.surface = surface
        self.llm = llm
        self.max_steps = max_steps

    def run(
        self,
        goal: str,
        entrypoint: str,
    ) -> DiscoveryResult:

        history: list[dict] = []
        steps: list[DiscoveryStep] = []

        try:
            self.surface.start()
            self.surface.navigate(entrypoint)

            for step_number in range(
                1,
                self.max_steps + 1,
            ):
                # -----------------------------------------
                # Observe current UI state
                # -----------------------------------------

                observation = self._observe()

                # -----------------------------------------
                # Ask LLM for exactly one next action
                # -----------------------------------------

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

                # -----------------------------------------
                # Goal completed
                # -----------------------------------------

                if decision.action == DiscoveryAction.COMPLETE:
                    step.result = "goal_completed"

                    steps.append(step)

                    return DiscoveryResult(
                        success=True,
                        goal=goal,
                        outputs=decision.outputs.model_dump(
                            exclude_none=True
                        ),
                        steps=steps,
                        reason=decision.reason,
                    )

                # -----------------------------------------
                # Human escalation requested
                # -----------------------------------------

                if decision.action == DiscoveryAction.ESCALATE:
                    step.result = "escalation_requested"

                    steps.append(step)

                    return DiscoveryResult(
                        success=False,
                        goal=goal,
                        steps=steps,
                        reason=decision.reason,
                    )

                # -----------------------------------------
                # Execute model decision
                # -----------------------------------------

                try:
                    self._execute(decision)

                    step.result = "executed"

                except Exception as exc:
                    step.result = (
                        f"execution_error: {exc}"
                    )

                    steps.append(step)

                    history.append(
                        {
                            "step_number": step_number,
                            "action": decision.action.value,
                            "target": (
                                decision.target.model_dump()
                                if decision.target
                                else None
                            ),
                            "value": decision.value,
                            "reason": decision.reason,
                            "result": step.result,
                        }
                    )

                    # Discovery is allowed to recover from
                    # an action failure. The next LLM call
                    # receives the failed action and error
                    # message in history and can choose a
                    # more appropriate target.
                    continue

                # -----------------------------------------
                # Successful step
                # -----------------------------------------

                steps.append(step)

                # -----------------------------------------
                # Record history for next LLM decision
                # -----------------------------------------

                history.append(
                    {
                        "step_number": step_number,
                        "action": decision.action.value,
                        "target": (
                            decision.target.model_dump()
                            if decision.target
                            else None
                        ),
                        "value": decision.value,
                        "reason": decision.reason,
                        "result": step.result,
                    }
                )

            # ---------------------------------------------
            # Maximum-step stopping condition
            # ---------------------------------------------

            return DiscoveryResult(
                success=False,
                goal=goal,
                steps=steps,
                reason="Maximum discovery steps reached.",
            )

        finally:
            self.surface.stop()

    # =====================================================
    # Observation
    # =====================================================

    def _observe(self) -> Observation:
        return Observation(
            url=self.surface.get_url(),
            visible_text=self.surface.get_visible_text(),
        )

    # =====================================================
    # Action execution
    # =====================================================

    def _execute(
        self,
        decision: AgentDecision,
    ) -> None:

        # ---------------------------------------------
        # FILL
        # ---------------------------------------------

        if decision.action == DiscoveryAction.FILL:

            if decision.target is None:
                raise ValueError(
                    "Fill action requires a target."
                )

            if decision.value is None:
                raise ValueError(
                    "Fill action requires a value."
                )

            target = self._to_locator(
                decision
            )

            self.surface.fill(
                target,
                decision.value,
            )

            return

        # ---------------------------------------------
        # CLICK
        # ---------------------------------------------

        if decision.action == DiscoveryAction.CLICK:

            if decision.target is None:
                raise ValueError(
                    "Click action requires a target."
                )

            target = self._to_locator(
                decision
            )

            self.surface.click(
                target
            )

            return

        # ---------------------------------------------
        # NAVIGATE
        # ---------------------------------------------

        if decision.action == DiscoveryAction.NAVIGATE:

            if decision.value is None:
                raise ValueError(
                    "Navigate action requires a URL."
                )

            self.surface.navigate(
                decision.value
            )

            return

        # ---------------------------------------------
        # READ
        # ---------------------------------------------

        if decision.action == DiscoveryAction.READ:
            return

        raise ValueError(
            f"Unsupported discovery action: "
            f"{decision.action}"
        )

    # =====================================================
    # Discovery target -> internal surface locator
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