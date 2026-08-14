import json

from src.discovery.agent import DiscoveryAgent
from src.discovery.llm import LLMClient
from src.discovery.models import (
    AgentDecision,
    DiscoveryAction,
    DiscoveryOutputs,
)
from src.handoff.manager import HandoffManager
from src.handoff.models import HandoffPackage
from src.safety.policy import SafetyPolicy
from src.surfaces.playwright_surface import PlaywrightSurface


# =========================================================
# Test 1:
# Handoff package can be persisted as JSON
# =========================================================


def test_handoff_package_is_saved(tmp_path):

    manager = HandoffManager(
        evidence_dir=tmp_path
    )

    package = HandoffPackage(
        reason_code="TEST_ESCALATION",
        reason="Automation requires human review.",
        goal="Test goal",
        current_url="http://127.0.0.1:8000/",
        last_observation="Test UI",
        failed_step="3",
        attempted_actions=[
            {
                "action": "click"
            }
        ],
        suggested_human_action=(
            "Inspect the current screen."
        ),
    )

    path = manager.save(
        package,
        "test_handoff",
    )

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    assert (
        data["reason_code"]
        == "TEST_ESCALATION"
    )

    assert (
        data["current_url"]
        == "http://127.0.0.1:8000/"
    )

    assert (
        data["suggested_human_action"]
        == "Inspect the current screen."
    )


# =========================================================
# Fake LLM:
# deliberately proposes unsafe external navigation
# =========================================================


class UnsafeNavigationLLM(LLMClient):

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
                "Attempt external navigation."
            ),
        )


# =========================================================
# Test 2:
# Discovery must block unsafe LLM action and create handoff
# =========================================================


def test_discovery_blocks_unsafe_llm_navigation(
    tmp_path,
):

    surface = PlaywrightSurface(
        headless=True
    )

    llm = UnsafeNavigationLLM()

    handoff_manager = HandoffManager(
        evidence_dir=tmp_path
    )

    agent = DiscoveryAgent(
        surface=surface,
        llm=llm,
        max_steps=2,
        safety_policy=SafetyPolicy(),
        handoff_manager=handoff_manager,
    )

    result = agent.run(
        goal="Unsafe navigation test",
        entrypoint="http://127.0.0.1:8000/",
    )

    # Discovery must stop.
    assert result.success is False

    # Safety policy should be the reason.
    assert (
        "Safety policy blocked"
        in result.reason
    )

    # Exactly one handoff file should have been created.
    files = list(
        tmp_path.glob("*.json")
    )

    assert len(files) == 1

    # Read the generated handoff evidence.
    data = json.loads(
        files[0].read_text(
            encoding="utf-8"
        )
    )

    assert (
        data["reason_code"]
        == "SAFETY_VIOLATION"
    )

    assert (
        data["goal"]
        == "Unsafe navigation test"
    )

    assert (
        data["current_url"]
        == "http://127.0.0.1:8000/"
    )

    assert (
        data["failed_step"]
        == "1"
    )

    assert len(
        data["attempted_actions"]
    ) == 1

    assert (
        data["attempted_actions"][0]["action"]
        == "navigate"
    )

    assert (
        data["attempted_actions"][0]["value"]
        == "https://example.com/"
    )

    assert (
        data["suggested_human_action"]
        is not None
    )