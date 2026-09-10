from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from plan_schemas import PhysicalPlan


class PlanOutcomeStatus(str, Enum):
    SOLVED = "solved"
    CONDITIONAL = "conditional"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CANNOT_SAFELY_SOLVE = "cannot_safely_solve"


class PlanRequirement(BaseModel):
    """
    A condition that must be resolved before some or all of a
    physical plan may safely be executed.
    """

    requirement: str = Field(
        min_length=1,
        max_length=300,
    )

    how_to_verify: str = Field(
        min_length=1,
        max_length=300,
    )

    if_not_met: str = Field(
        min_length=1,
        max_length=300,
    )


class PlanOutcome(BaseModel):
    """
    ZERO's top-level planning decision.

    A PhysicalPlan is no longer assumed to always exist.
    """

    status: PlanOutcomeStatus

    explanation: str = Field(
        min_length=1,
        max_length=600,
    )

    plan: PhysicalPlan | None = None

    requirements: list[PlanRequirement] = Field(
        default_factory=list,
        max_length=5,
    )

    blocking_reasons: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    @model_validator(
        mode="after"
    )
    def validate_outcome(
        self,
    ):
        if (
            self.status
            == PlanOutcomeStatus.SOLVED
        ):
            if self.plan is None:
                raise ValueError(
                    "SOLVED requires a PhysicalPlan."
                )

            if self.requirements:
                raise ValueError(
                    "SOLVED cannot contain unresolved requirements."
                )

            if self.blocking_reasons:
                raise ValueError(
                    "SOLVED cannot contain blocking reasons."
                )

        elif (
            self.status
            == PlanOutcomeStatus.CONDITIONAL
        ):
            if self.plan is None:
                raise ValueError(
                    "CONDITIONAL requires a PhysicalPlan."
                )

            if not self.requirements:
                raise ValueError(
                    "CONDITIONAL requires at least one requirement."
                )

            if self.blocking_reasons:
                raise ValueError(
                    "CONDITIONAL should use requirements, "
                    "not blocking reasons."
                )

        elif (
            self.status
            == PlanOutcomeStatus.NEEDS_CONFIRMATION
        ):
            if self.plan is not None:
                raise ValueError(
                    "NEEDS_CONFIRMATION must not expose an executable plan."
                )

            if not self.requirements:
                raise ValueError(
                    "NEEDS_CONFIRMATION requires at least one requirement."
                )

            if self.blocking_reasons:
                raise ValueError(
                    "NEEDS_CONFIRMATION should use requirements, "
                    "not blocking reasons."
                )

        elif (
            self.status
            == PlanOutcomeStatus.CANNOT_SAFELY_SOLVE
        ):
            if self.plan is not None:
                raise ValueError(
                    "CANNOT_SAFELY_SOLVE must not contain a plan."
                )

            if self.requirements:
                raise ValueError(
                    "CANNOT_SAFELY_SOLVE cannot contain actionable "
                    "verification requirements."
                )

            if not self.blocking_reasons:
                raise ValueError(
                    "CANNOT_SAFELY_SOLVE requires at least one "
                    "blocking reason."
                )

        return self