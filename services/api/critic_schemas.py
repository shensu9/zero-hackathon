from enum import Enum

from pydantic import BaseModel, Field


class CriticIssueType(str, Enum):
    UNLISTED_RESOURCE = "unlisted_resource"
    UNSUPPORTED_PHYSICAL_CLAIM = "unsupported_physical_claim"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    HIDDEN_ASSUMPTION = "hidden_assumption"
    SAFETY_OR_UNCERTAINTY = "safety_or_uncertainty"
    CONSTRAINT_VIOLATION = "constraint_violation"


class CriticSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanCriticFinding(BaseModel):
    step_order: int | None = Field(
        default=None,
        ge=1,
        le=10,
    )

    claim: str = Field(
        min_length=1,
        max_length=300,
    )

    issue_type: CriticIssueType

    severity: CriticSeverity

    explanation: str = Field(
        min_length=1,
        max_length=400,
    )

    recommended_fix: str = Field(
        min_length=1,
        max_length=400,
    )


class PlanCriticResult(BaseModel):
    passed: bool

    findings: list[PlanCriticFinding] = Field(
        default_factory=list,
        max_length=20,
    )