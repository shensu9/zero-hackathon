from object_dna_fixture import (
    OBJECT_DNA_FIXTURE,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
    PlanRequirement,
)
from plan_schemas import PhysicalPlan
from verification_gate_auditor import (
    audit_verification_gates,
)
from verification_gate_schemas import (
    VerificationGateIssueType,
)


EXTERNAL_RESOURCES = (
    "disposable test surface",
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
                        "Dispense liquid from the spray bottle onto the disposable test surface.",

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
                        "Performs the requested action after verification.",
                }
            ],

            "assumptions": [],
            "unresolved_risks": [],
            "constraint_check": [],
        }
    )


def audit(
    outcome: PlanOutcome,
):
    return audit_verification_gates(
        outcome=outcome,
        inventory=(
            OBJECT_DNA_FIXTURE.items
        ),
        external_resources=(
            EXTERNAL_RESOURCES
        ),
    )


def main() -> None:
    plan = build_plan()

    # ------------------------------------------------------------------
    # GOOD — EXISTING LABEL / USER INFORMATION
    # ------------------------------------------------------------------

    good_outcome = PlanOutcome(
        status=(
            PlanOutcomeStatus.CONDITIONAL
        ),

        explanation=(
            "Contents must be identified before spraying."
        ),

        plan=plan,

        requirements=[
            PlanRequirement(
                requirement=(
                    "Identify the bottle contents and "
                    "confirm they are appropriate."
                ),

                how_to_verify=(
                    "Read the bottle's existing label or "
                    "ask the user to identify the contents "
                    "without dispensing liquid."
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

    good_audit = audit(
        good_outcome
    )

    print(
        good_audit.model_dump_json(
            indent=2
        )
    )

    assert good_audit.passed, (
        "Grounded verification should pass."
    )

    # ------------------------------------------------------------------
    # BAD — EXECUTES GATED ACTION
    # ------------------------------------------------------------------

    executes_action = PlanOutcome(
        status=(
            PlanOutcomeStatus.CONDITIONAL
        ),

        explanation=(
            "Contents must be verified before spraying."
        ),

        plan=plan,

        requirements=[
            PlanRequirement(
                requirement=(
                    "Confirm the unknown liquid is "
                    "appropriate before spraying."
                ),

                how_to_verify=(
                    "Spray a small compatibility test "
                    "area first to see whether the liquid "
                    "is suitable."
                ),

                if_not_met=(
                    "Do not perform the full spray."
                ),
            )
        ],
    )

    print()
    print(
        "Auditing gate that executes "
        "the blocked action..."
    )

    action_audit = audit(
        executes_action
    )

    print(
        action_audit.model_dump_json(
            indent=2
        )
    )

    assert not action_audit.passed, (
        "Verification that sprays before authorization "
        "must fail."
    )

    action_issue_types = {
        finding.issue_type
        for finding
        in action_audit.findings
    }

    assert (
        VerificationGateIssueType
        .EXECUTES_GATED_ACTION
        in action_issue_types
    ), (
        "Test spraying should be classified as "
        "executes_gated_action."
    )

    # ------------------------------------------------------------------
    # BAD — INVENTS PHYSICAL VERIFICATION TOOL
    # ------------------------------------------------------------------

    invented_tool = PlanOutcome(
        status=(
            PlanOutcomeStatus.CONDITIONAL
        ),

        explanation=(
            "Contents must be identified before spraying."
        ),

        plan=plan,

        requirements=[
            PlanRequirement(
                requirement=(
                    "Identify the liquid and confirm "
                    "it is appropriate."
                ),

                how_to_verify=(
                    "Use a pH strip to test the liquid "
                    "before spraying."
                ),

                if_not_met=(
                    "Do not spray."
                ),
            )
        ],
    )

    print()
    print(
        "Auditing gate with invented "
        "verification resource..."
    )

    resource_audit = audit(
        invented_tool
    )

    print(
        resource_audit.model_dump_json(
            indent=2
        )
    )

    assert not resource_audit.passed, (
        "Verification requiring an unavailable pH strip "
        "must fail."
    )

    resource_issue_types = {
        finding.issue_type
        for finding
        in resource_audit.findings
    }

    assert (
        (
            VerificationGateIssueType
            .UNLISTED_VERIFICATION_RESOURCE
            in resource_issue_types
        )
        or
        (
            VerificationGateIssueType
            .NOT_ACTUALLY_VERIFIABLE
            in resource_issue_types
        )
    ), (
        "Invented pH strip must be recognized as "
        "an unavailable verification resource."
    )

    # ------------------------------------------------------------------
    # BAD — UNSAFE HUMAN EXPOSURE TO UNKNOWN LIQUID
    # ------------------------------------------------------------------

    unsafe_smell = PlanOutcome(
        status=(
            PlanOutcomeStatus.CONDITIONAL
        ),

        explanation=(
            "Contents must be identified before spraying."
        ),

        plan=plan,

        requirements=[
            PlanRequirement(
                requirement=(
                    "Identify the unknown liquid before spraying."
                ),

                how_to_verify=(
                    "Smell the contents of the bottle "
                    "to determine what the liquid is."
                ),

                if_not_met=(
                    "Do not spray."
                ),
            )
        ],
    )

    print()
    print(
        "Auditing unsafe unknown-liquid "
        "exposure verification..."
    )

    smell_audit = audit(
        unsafe_smell
    )

    print(
        smell_audit.model_dump_json(
            indent=2
        )
    )

    assert not smell_audit.passed, (
        "Smelling unknown liquid must fail "
        "verification-gate auditing."
    )

    smell_issue_types = {
        finding.issue_type
        for finding
        in smell_audit.findings
    }

    assert (
        VerificationGateIssueType
        .UNSAFE_VERIFICATION
        in smell_issue_types
    ), (
        "Unknown-liquid smelling must be classified "
        "as unsafe_verification."
    )

    print()
    print(
        "RESOURCE-AWARE VERIFICATION GATE TEST: passed"
    )


if __name__ == "__main__":
    main()