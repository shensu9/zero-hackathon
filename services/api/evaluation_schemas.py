from pydantic import BaseModel, Field

from critic_schemas import (
    CriticIssueType,
    CriticSeverity,
)


class EvaluationFinding(BaseModel):
    step_order: int | None = None
    claim: str
    issue_type: CriticIssueType
    severity: CriticSeverity
    explanation: str


class PlanEvaluation(BaseModel):
    findings: list[EvaluationFinding] = Field(
        default_factory=list,
        max_length=20,
    )

    medium_high_findings: int = 0

    unlisted_resource_count: int = 0
    unsupported_physical_claim_count: int = 0
    unsupported_capability_count: int = 0
    hidden_assumption_count: int = 0
    safety_or_uncertainty_count: int = 0
    constraint_violation_count: int = 0

    accepted: bool = False