from pydantic import BaseModel, Field

from schemas import CapabilityType


class CapabilityUse(BaseModel):
    item_id: str = Field(
        min_length=1,
        max_length=100,
    )

    capability: CapabilityType

    purpose: str = Field(
        min_length=1,
        max_length=250,
    )


class PlanStep(BaseModel):
    order: int = Field(
        ge=1,
        le=10,
    )

    action: str = Field(
        min_length=1,
        max_length=300,
    )

    item_ids: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    capability_uses: list[CapabilityUse] = Field(
        default_factory=list,
        max_length=10,
    )

    why_it_helps: str = Field(
        min_length=1,
        max_length=300,
    )


class PhysicalPlan(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=120,
    )

    summary: str = Field(
        min_length=1,
        max_length=500,
    )

    item_ids_used: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    steps: list[PlanStep] = Field(
        min_length=1,
        max_length=8,
    )

    assumptions: list[str] = Field(
        default_factory=list,
        max_length=8,
    )

    unresolved_risks: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    constraint_check: list[str] = Field(
        default_factory=list,
        max_length=6,
    )