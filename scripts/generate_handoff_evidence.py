from src.discovery.agent import DiscoveryAgent
from src.discovery.llm import LLMClient
from src.discovery.models import (
    AgentDecision,
    DiscoveryAction,
    DiscoveryOutputs,
)
from src.handoff.manager import HandoffManager
from src.safety.policy import SafetyPolicy
from src.surfaces.playwright_surface import PlaywrightSurface


class UnsafeNavigationLLM(LLMClient):
    """
    Deterministic test double used only to demonstrate
    safety enforcement and human handoff.

    This is NOT genuine LLM discovery evidence.
    """

    def decide(
        self,
        goal,
        observation,
        history,
    ):
        return AgentDecision(
            action=DiscoveryAction.NAVIGATE,
            target=None,
            value="https://example.com/",
            outputs=DiscoveryOutputs(
                balance=None
            ),
            reason=(
                "Demonstrate that external navigation "
                "is blocked by central policy."
            ),
        )


def main():

    surface = PlaywrightSurface(
        headless=True
    )

    llm = UnsafeNavigationLLM()

    handoff_manager = HandoffManager(
        evidence_dir="evidence/handoffs"
    )

    agent = DiscoveryAgent(
        surface=surface,
        llm=llm,
        max_steps=2,
        safety_policy=SafetyPolicy(),
        handoff_manager=handoff_manager,
    )

    result = agent.run(
        goal=(
            "Safety demonstration: attempt "
            "external navigation."
        ),
        entrypoint="http://127.0.0.1:8000/",
    )

    print(
        result.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()