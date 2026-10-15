import json
import re

from anthropic import Anthropic
import os
import json

from dotenv import load_dotenv

# Load .env from the project root
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../")
)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

api_key = os.getenv("ANTHROPIC_API_KEY")
model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

if not api_key:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is missing. Check the project root .env file."
    )

client = Anthropic(api_key=api_key)

from ai_dlc.inception.schemas import (
    RequirementRequest,
    StoryArtifacts,
)


SYSTEM_PROMPT = """
You are a senior business analyst for Node.js and TypeScript
microservices.

Create a detailed, testable user story from the supplied requirement.

Return one JSON object with these fields:
{
  "title": "short title",
  "user_story": "As a ..., I want ..., so that ...",
  "business_value": "business outcome",
  "priority": "low | medium | high | critical",
  "functional_requirements": ["..."],
  "acceptance_criteria": [
    {
      "id": "AC-01",
      "title": "...",
      "given": "...",
      "when": "...",
      "then": "..."
    }
  ],
  "open_questions": ["..."]
}

Use Given/When/Then for acceptance criteria.
Do not invent confirmed business decisions.
Record unresolved ambiguities in open_questions.
Return JSON only, with no Markdown fences.
"""


def generate_story(request: RequirementRequest) -> StoryArtifacts:
    # client = Anthropic()

    response = client.messages.create(
        model=__import__("os").getenv(
            "ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"
        ),
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Project: {request.project}\n"
                f"Service: {request.service}\n"
                f"Requirement:\n{request.requirement}"
            ),
        }],
    )

    text = "".join(
        block.text
        for block in response.content
        if block.type == "text"
    ).strip()

    # Tolerate a model response wrapped in a JSON code fence.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    payload = json.loads(text)
    return StoryArtifacts.model_validate(payload)