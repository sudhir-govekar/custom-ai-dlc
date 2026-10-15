from typing import Literal
from pydantic import BaseModel, Field


class RequirementRequest(BaseModel):
    project: str = Field(min_length=2, max_length=100)
    service: str = Field(min_length=2, max_length=100)
    requirement: str = Field(min_length=20, max_length=10000)


class AcceptanceCriterion(BaseModel):
    id: str
    title: str
    given: str
    when: str
    then: str


class StoryArtifacts(BaseModel):
    title: str
    user_story: str
    business_value: str
    priority: Literal["low", "medium", "high", "critical"]
    functional_requirements: list[str]
    acceptance_criteria: list[AcceptanceCriterion]
    open_questions: list[str]


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=2, max_length=100)
    comment: str = Field(default="", max_length=2000)