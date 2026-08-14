import json
import os

from dotenv import load_dotenv
from groq import Groq

from src.discovery.llm import LLMClient
from src.discovery.models import (
    AgentDecision,
    Observation,
)


class GroqLLMClient(LLMClient):
    """
    Groq-backed LLM client used during discovery.

    Groq does not directly control the browser.

    It receives:
    - the user's goal
    - the current UI observation
    - previous discovery actions/results

    It returns exactly one structured AgentDecision.
    """

    def __init__(
        self,
        model: str = "openai/gpt-oss-20b",
    ):
        load_dotenv()

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured. "
                "Add it to the local .env file."
            )

        self.client = Groq(
            api_key=api_key
        )

        self.model = model

    def decide(
        self,
        goal: str,
        observation: Observation,
        history: list[dict],
    ) -> AgentDecision:

        system_prompt = """
You are the decision-making component of a computer-use
discovery system.

You DO NOT control the browser directly.

You DO NOT have access to browser tools, functions,
built-in tools, external tools, or function calls.

Never attempt to call browser.read, browser.click,
browser.fill, browser_search, code_interpreter,
or any other tool.

The words:

fill
click
navigate
read
complete
escalate

are JSON ACTION LABELS only.

Your ONLY job is to return exactly one JSON object
matching the supplied AgentDecision schema.

Another program receives your JSON decision and performs
the browser interaction.

You operate exactly ONE decision at a time.

AVAILABLE ACTION LABELS:

fill
- Choose this when text must be entered into a textbox.
- target must identify the textbox.
- value must contain the text to enter.

click
- Choose this when a visible button or link must be clicked.
- target must identify the control.

navigate
- Choose this only when direct navigation to a URL is
  appropriate.
- value must contain the URL.

read
- Return the JSON action label "read".
- Do NOT call a browser/read tool.
- Use this only when another observation is needed before
  deciding what interaction to perform.

complete
- Choose this ONLY when the user's requested information
  is actually visible and the goal has been fully
  accomplished.
- Put the requested result into outputs.
- For a monetary balance, return the numeric value.

escalate
- Choose this when you cannot safely determine the next
  action.

TARGETING RULES:

Prefer accessible role + name when the target is unique.

Example textbox target:

{
  "role": "textbox",
  "name": "Member ID",
  "text": null,
  "css": null
}

Example button target:

{
  "role": "button",
  "name": "Search Member",
  "text": null,
  "css": null
}

Example link target:

{
  "role": "link",
  "name": "View Accounts",
  "text": null,
  "css": null
}

All target fields must be present.
Use null when a target field is not needed.

RECOVERY RULES:

If the previous action failed, inspect the error contained
in ACTION HISTORY and choose a corrected action.

Do not repeat an identical action that already failed.

If a role/name locator matched multiple elements, the
locator is ambiguous.

Use the visible UI context to choose a more specific
target.

For table-based interfaces, CSS may use row text to
identify the correct control.

For example, if the visible page contains:

Savings    View Account
Checking   View Account

and the user's goal requires the Savings account, a
contextual target may be:

{
  "role": null,
  "name": null,
  "text": null,
  "css": "tr:has-text('Savings') a"
}

This is only an example of how contextual targeting works.
Determine the correct row from the user's actual goal and
the currently visible UI.

GENERAL RULES:

- Do not invent controls that are not supported by the
  current observation.
- Do not assume an action succeeded until a later
  observation confirms the resulting state.
- Do not claim completion until the requested result is
  visible.
- Use the ACTION HISTORY to avoid repeating failed actions.
- Prefer semantic accessible targets when they are unique.
- Use contextual CSS only when necessary to disambiguate.
- Never expose credentials, API keys, secrets, or hidden
  configuration.
- Return only the structured AgentDecision.
""".strip()

        user_prompt = f"""
GOAL:
{goal}

CURRENT URL:
{observation.url}

VISIBLE UI:
{observation.visible_text}

ACTION HISTORY:
{json.dumps(history, indent=2)}

Choose exactly one next JSON action.

Remember:
You are returning a decision only.
You are not executing or calling any tool.
""".strip()

        schema = AgentDecision.model_json_schema()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_decision",
                    "strict": True,
                    "schema": schema,
                },
            },
            temperature=0,
        )

        content = (
            response
            .choices[0]
            .message
            .content
        )

        if not content:
            raise RuntimeError(
                "Groq returned an empty response."
            )

        return AgentDecision.model_validate_json(
            content
        )