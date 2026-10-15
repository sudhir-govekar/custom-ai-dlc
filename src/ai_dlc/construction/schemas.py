
from typing import Literal
from pydantic import BaseModel, Field


class ConstructionTask(BaseModel):
    task_id: str
    title: str
    description: str
    service: str
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria_ids: list[str] = Field(default_factory=list)
    test_plan: list[str] = Field(default_factory=list)


class ConstructionPlan(BaseModel):
    technical_design: str
    architecture_decisions: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    tasks: list[ConstructionTask]
    implementation_order: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    overall_test_strategy: str
    status: Literal["generated"] = "generated"
