from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
    PlanRequirement,
)
from plan_schemas import PhysicalPlan
from verification_gate_auditor import (
    audit_verification_gates,
)


def build_plan() -> PhysicalPlan:
    return PhysicalPlan.model_validate(
        {
            "title":
                "Conditional spray",

            "summary":
                "Spray only after verification.",

            "item_ids_used": [
                "spray_bottles_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Dispense liquid from the spray bottle onto the test surface.",

                    "item_ids": [
                        "spray_bottles_01",
                    ],

                    "capability_uses": [
                        {
                            "item_id":
                                "spray_bottles_01",

                            "capability":
                                "dispense_liquid",

                            "purpose":
                                "Dispense the verified liquid.",
                        }
                    ],

                    "why_it_helps":
                        "Performs the requested spray action after verification.",
                }
            ],

            "assumptions": [],
            "unresolved_risks": [],
            "constraint_check": [],
        }
    )


plan = build_plan()


# ---------------------------------------------------------------------------
# GOOD GATE
# ---------------------------------------------------------------------------


good_outcome = PlanOutcome(
    status=PlanOutcomeStatus.CONDITIONAL,

    explanation=(
        "Contents must be identified before spraying."
    ),

    plan=plan,

    requirements=[
        PlanRequirement(
            requirement=(
                "Identify the bottle contents and confirm "
                "they are appropriate before spraying."
            ),

            how_to_verify=(
                "Read the bottle label or otherwise identify "
                "the contents without dispensing liquid."
            ),

            if_not_met=(
                "Do not spray."
            ),
        )
    ],
)


print(
    "Auditing good verification gate..."
)

good_audit = audit_verification_gates(
    good_outcome
)

print(
    good_audit.model_dump_json(
        indent=2
    )
)

assert good_audit.passed, (
    "Good verification gate should pass."
)


# ---------------------------------------------------------------------------
# BAD GATE
# ---------------------------------------------------------------------------


bad_outcome = PlanOutcome(
    status=PlanOutcomeStatus.CONDITIONAL,

    explanation=(
        "Contents must be verified before spraying."
    ),

    plan=plan,

    requirements=[
        PlanRequirement(
            requirement=(
                "Confirm the unknown liquid is appropriate "
                "before spraying."
            ),

            how_to_verify=(
                "Spray a small compatibility test area first "
                "to see whether the liquid is suitable."
            ),

            if_not_met=(
                "Do not perform the full spray."
            ),
        )
    ],
)


print()
print(
    "Auditing bad verification gate..."
)

bad_audit = audit_verification_gates(
    bad_outcome
)

print(
    bad_audit.model_dump_json(
        indent=2
    )
)

assert not bad_audit.passed, (
    "Bad verification gate should be rejected."
)


print()
print(
    "VERIFICATION GATE TEST: passed"
)