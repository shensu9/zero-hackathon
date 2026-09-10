from enum import Enum

from pydantic import BaseModel, Field


class VerificationGateIssueType(
    str,
    Enum,
):
    EXECUTES_GATED_ACTION = (
        "executes_gated_action"
    )

    ASSUMES_REQUIREMENT_MET = (
        "assumes_requirement_met"
    )

    UNSAFE_VERIFICATION = (
        "unsafe_verification"
    )

    NOT_ACTUALLY_VERIFIABLE = (
        "not_actually_verifiable"
    )


class VerificationGateSeverity(
    str,
    Enum,
):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VerificationGateFinding(
    BaseModel,
):
    requirement_index: int = Field(
        ge=0,
    )

    issue_type: VerificationGateIssueType

    severity: VerificationGateSeverity

    claim: str = Field(
        min_length=1,
        max_length=300,
    )

    explanation: str = Field(
        min_length=1,
        max_length=500,
    )

    recommended_fix: str = Field(
        min_length=1,
        max_length=500,
    )


class VerificationGateAudit(
    BaseModel,
):
    passed: bool

    findings: list[
        VerificationGateFinding
    ] = Field(
        default_factory=list,
        max_length=10,
    )