from abc import ABC, abstractmethod

from src.discovery.models import (
    AgentDecision,
    Observation,
)


class LLMClient(ABC):

    @abstractmethod
    def decide(
        self,
        goal: str,
        observation: Observation,
        history: list[dict],
    ) -> AgentDecision:
        """
        Given the goal, current UI observation, and prior
        interaction history, decide the next action.
        """

        pass