from pydantic import ValidationError

from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
    PlanRequirement,
)
from plan_schemas import PhysicalPlan


def minimal_plan() -> PhysicalPlan:
    return PhysicalPlan.model_validate(
        {
            "title":
                "Minimal grounded plan",

            "summary":
                "A minimal physical plan.",

            "item_ids_used": [
                "books_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Place the books in the requested position.",

                    "item_ids": [
                        "books_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Uses the available books.",
                }
            ],

            "assumptions": [],
            "unresolved_risks": [],
            "constraint_check": [],
        }
    )


plan = minimal_plan()


# ---------------------------------------------------------------------------
# VALID: SOLVED
# ---------------------------------------------------------------------------


solved = PlanOutcome(
    status=PlanOutcomeStatus.SOLVED,
    explanation=(
        "A grounded solution is available now."
    ),
    plan=plan,
)

assert solved.plan is not None


# ---------------------------------------------------------------------------
# VALID: CONDITIONAL
# ---------------------------------------------------------------------------


conditional = PlanOutcome(
    status=PlanOutcomeStatus.CONDITIONAL,
    explanation=(
        "The solution is available only after verification."
    ),
    plan=plan,
    requirements=[
        PlanRequirement(
            requirement=(
                "The unknown bottle contents must be identified "
                "as appropriate."
            ),
            how_to_verify=(
                "Check the bottle label or otherwise identify "
                "the contents before use."
            ),
            if_not_met=(
                "Do not use the bottle."
            ),
        )
    ],
)

assert len(
    conditional.requirements
) == 1


# ---------------------------------------------------------------------------
# VALID: NEEDS_CONFIRMATION
# ---------------------------------------------------------------------------


needs_confirmation = PlanOutcome(
    status=(
        PlanOutcomeStatus.NEEDS_CONFIRMATION
    ),
    explanation=(
        "ZERO needs one environmental fact before selecting a plan."
    ),
    requirements=[
        PlanRequirement(
            requirement=(
                "Confirm whether the target surface may get wet."
            ),
            how_to_verify=(
                "Ask the user whether liquid contact is acceptable."
            ),
            if_not_met=(
                "Do not construct a liquid-based plan."
            ),
        )
    ],
)

assert (
    needs_confirmation.plan
    is None
)


# ---------------------------------------------------------------------------
# VALID: CANNOT SAFELY SOLVE
# ---------------------------------------------------------------------------


cannot_solve = PlanOutcome(
    status=(
        PlanOutcomeStatus.CANNOT_SAFELY_SOLVE
    ),
    explanation=(
        "No grounded solution exists with the available resources."
    ),
    blocking_reasons=[
        (
            "The required physical capability is absent from "
            "the available inventory."
        )
    ],
)

assert (
    cannot_solve.plan
    is None
)


# ---------------------------------------------------------------------------
# INVALID: SOLVED WITHOUT PLAN
# ---------------------------------------------------------------------------


try:
    PlanOutcome(
        status=PlanOutcomeStatus.SOLVED,
        explanation="Invalid solved outcome.",
    )

except ValidationError:
    pass

else:
    raise AssertionError(
        "SOLVED without a plan should fail."
    )


# ---------------------------------------------------------------------------
# INVALID: CONDITIONAL WITHOUT REQUIREMENT
# ---------------------------------------------------------------------------


try:
    PlanOutcome(
        status=PlanOutcomeStatus.CONDITIONAL,
        explanation="Invalid conditional outcome.",
        plan=plan,
    )

except ValidationError:
    pass

else:
    raise AssertionError(
        "CONDITIONAL without a requirement should fail."
    )


# ---------------------------------------------------------------------------
# INVALID: NEEDS CONFIRMATION WITH EXECUTABLE PLAN
# ---------------------------------------------------------------------------


try:
    PlanOutcome(
        status=(
            PlanOutcomeStatus.NEEDS_CONFIRMATION
        ),
        explanation="Invalid confirmation outcome.",
        plan=plan,
        requirements=[
            PlanRequirement(
                requirement="Need confirmation.",
                how_to_verify="Ask the user.",
                if_not_met="Do not proceed.",
            )
        ],
    )

except ValidationError:
    pass

else:
    raise AssertionError(
        "NEEDS_CONFIRMATION with a plan should fail."
    )


# ---------------------------------------------------------------------------
# INVALID: CANNOT SOLVE WITH PLAN
# ---------------------------------------------------------------------------


try:
    PlanOutcome(
        status=(
            PlanOutcomeStatus.CANNOT_SAFELY_SOLVE
        ),
        explanation="Invalid impossible outcome.",
        plan=plan,
        blocking_reasons=[
            "Missing capability.",
        ],
    )

except ValidationError:
    pass

else:
    raise AssertionError(
        "CANNOT_SAFELY_SOLVE with a plan should fail."
    )


print(
    "PLAN OUTCOME SCHEMA TEST: passed"
)