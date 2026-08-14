from src.discovery.agent import DiscoveryAgent
from src.discovery.llm import LLMClient
from src.discovery.models import (
    AgentDecision,
    DiscoveryAction,
    DiscoveryOutputs,
    DiscoveryTarget,
)
from src.surfaces.playwright_surface import PlaywrightSurface


class FakeLLMClient(LLMClient):

    def __init__(self):
        self.call_count = 0

    def decide(
        self,
        goal,
        observation,
        history,
    ):
        self.call_count += 1

        # Step 1: Fill Member ID
        if self.call_count == 1:
            return AgentDecision(
                action=DiscoveryAction.FILL,

                target=DiscoveryTarget(
                    role="textbox",
                    name="Member ID",
                    text=None,
                    css=None,
                ),

                value="10001",

                outputs=DiscoveryOutputs(
                    balance=None
                ),

                reason="Enter the requested member ID.",
            )

        # Step 2: Click Search Member
        if self.call_count == 2:
            return AgentDecision(
                action=DiscoveryAction.CLICK,

                target=DiscoveryTarget(
                    role="button",
                    name="Search Member",
                    text=None,
                    css=None,
                ),

                value=None,

                outputs=DiscoveryOutputs(
                    balance=None
                ),

                reason="Submit the member search.",
            )

        # Step 3: Complete the test discovery
        if self.call_count == 3:
            return AgentDecision(
                action=DiscoveryAction.COMPLETE,

                target=None,

                value=None,

                outputs=DiscoveryOutputs(
                    balance=None
                ),

                reason="Test discovery completed.",
            )

        raise RuntimeError(
            "Unexpected FakeLLMClient call."
        )


def test_discovery_agent_observe_decide_act_loop():

    surface = PlaywrightSurface(
        headless=True
    )

    llm = FakeLLMClient()

    agent = DiscoveryAgent(
        surface=surface,
        llm=llm,
        max_steps=5,
    )

    result = agent.run(
        goal="Look up member 10001.",
        entrypoint="http://127.0.0.1:8000/",
    )

    assert result.success is True

    assert len(result.steps) == 3

    assert (
        result.steps[0].decision.action
        == DiscoveryAction.FILL
    )

    assert (
        result.steps[1].decision.action
        == DiscoveryAction.CLICK
    )

    assert (
        result.steps[2].decision.action
        == DiscoveryAction.COMPLETE
    )