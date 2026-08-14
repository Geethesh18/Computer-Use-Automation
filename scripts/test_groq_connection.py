from src.discovery.groq_client import GroqLLMClient
from src.discovery.models import Observation


def main():
    llm = GroqLLMClient()

    observation = Observation(
        url="http://127.0.0.1:8000/",
        visible_text="""
Community Trust Banking System

Internal Member Services Portal

Member Search

Enter a member ID to retrieve the member record.

Member ID

Search Member
""".strip(),
    )

    decision = llm.decide(
        goal=(
            "Look up member 10001 and return "
            "their current savings balance."
        ),
        observation=observation,
        history=[],
    )

    print(
        decision.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()