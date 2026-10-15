
import json
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from ai_dlc.construction.schemas import ConstructionPlan


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

if not api_key:
    raise RuntimeError("ANTHROPIC_API_KEY is missing")

client = Anthropic(api_key=api_key)


def generate_construction_plan(
    project: str,
    service: str,
    requirement: str,
    approved_story: dict,
    reviewer: str,
    review_comment: str = "",
) -> dict:
    """Generate a Construction plan from an approved Inception artifact."""

    
    prompt = f"""
Create a concise Construction plan for an approved software requirement.

Project: {project}
Service: {service}
Requirement: {requirement}
Approved story and acceptance criteria:
{json.dumps(approved_story, separators=(",", ":"))}
Reviewer: {reviewer}
Review comment: {review_comment or "None"}

Return ONLY one valid JSON object matching this schema:
{{
  "technical_design": "Short design summary",
  "architecture_decisions": ["decision"],
  "affected_components": ["component"],
  "tasks": [
    {{
      "task_id": "TASK-001",
      "title": "Short title",
      "description": "Actionable implementation steps",
      "service": "{service}",
      "dependencies": [],
      "acceptance_criteria_ids": ["AC-1"],
      "test_plan": ["test"]
    }}
  ],
  "implementation_order": ["TASK-001"],
  "risks": ["risk"],
  "assumptions": ["assumption"],
  "overall_test_strategy": "Short test strategy",
  "status": "generated"
}}

Rules:
- Generate at most 5 implementation tasks.
- Keep each description under 50 words.
- Include relevant validation, authorization, error handling, and tests.
- Map tasks to existing acceptance-criteria IDs where possible.
- Use consistent task IDs and dependencies.
- Do not claim to inspect files, modify code, or run tests.
- Keep lists concise; use empty arrays when appropriate.
- Include only valid JSON. No Markdown fences or extra text.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    text_parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]

    if not text_parts:
        raise RuntimeError("Anthropic returned an empty Construction plan")

    raw_text = "\n".join(text_parts).strip()

    # Handle an optional JSON markdown fence.
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_text = "\n".join(lines).strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Construction model response was not valid JSON"
        ) from exc

    plan = ConstructionPlan.model_validate(parsed)
    return plan.model_dump()
