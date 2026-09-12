from unittest.mock import patch

import plan_outcome_pipeline as pipeline

from critic_schemas import (
    PlanCriticFinding,
    PlanCriticResult,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from plan_schemas import (
    PhysicalPlan,
    PlanStep,
)
from schemas import (
    ObjectDNAResponse,
)


def build_plan() -> PhysicalPlan:
    return PhysicalPlan(
        title="Desk Product Setup",

        summary=(
            "Use the desk as a product surface."
        ),

        item_ids_used=[],

        steps=[
            PlanStep(
                order=1,
                action=(
                    "Place the product on the desk."
                ),
                item_ids=[],
                capability_uses=[],
                why_it_helps=(
                    "Provides a place for the product."
                ),
            ),
        ],

        assumptions=[
            (
                "Product fits comfortably on "
                "the desk surface"
            ),
        ],

        unresolved_risks=[],

        constraint_check=[
            "Budget remains $0.",
        ],
    )


def build_outcome() -> PlanOutcome:
    return PlanOutcome(
        status=(
            PlanOutcomeStatus.SOLVED
        ),

        explanation=(
            "A desk-based product setup is available."
        ),

        plan=build_plan(),

        requirements=[],

        blocking_reasons=[],
    )


def build_critic() -> PlanCriticResult:
    return PlanCriticResult(
        passed=False,

        findings=[
            PlanCriticFinding(
                step_order=None,

                claim=(
                    "Product fits comfortably on "
                    "the desk surface"
                ),

                issue_type=(
                    "hidden_assumption"
                ),

                severity="medium",

                explanation=(
                    "Product dimensions are not verified "
                    "against the desk surface."
                ),

                recommended_fix=(
                    "Verify fit or remove the assumption."
                ),
            ),
        ],
    )


def unchanged_repair(
    *,
    plan,
    critic,
    goal,
    inventory,
    object_dna,
    external_resources,
):
    """
    Intentionally bad repair.

    It returns the rejected claim unchanged, reproducing the exact class
    of failure seen in V4.
    """

    return plan


def test_production_loop_skips_redundant_semantic_audit():
    outcome = build_outcome()

    critic = build_critic()

    hard_validation_calls = 0
    semantic_audit_calls = 0
    repair_calls = 0

    def fake_hard_validate_plan(
        *,
        plan,
        inventory,
        object_dna,
    ):
        nonlocal hard_validation_calls

        hard_validation_calls += 1

        # Hard validation is deliberately allowed to pass.
        #
        # The defect being tested is semantic repair closure,
        # not capability validation.
        return plan

    def fake_semantic_audit(
        *,
        outcome,
        goal,
        inventory,
        object_dna,
        external_resources,
    ):
        nonlocal semantic_audit_calls

        semantic_audit_calls += 1

        return critic

    def counted_repair(**kwargs):
        nonlocal repair_calls

        repair_calls += 1

        return unchanged_repair(
            **kwargs
        )

    with (
        patch.object(
            pipeline,
            "_hard_validate_plan",
            side_effect=(
                fake_hard_validate_plan
            ),
        ),
        patch.object(
            pipeline,
            "_audit_outcome_plan",
            side_effect=(
                fake_semantic_audit
            ),
        ),
        patch.object(
            pipeline,
            "repair_plan",
            side_effect=(
                counted_repair
            ),
        ),
    ):
        try:
            pipeline._make_outcome_plan_safe(
                outcome=outcome,

                goal=(
                    "Create a $0 product photography "
                    "setup."
                ),

                inventory=[],

                object_dna=(
                    ObjectDNAResponse(
                        objects=[]
                    )
                ),

                external_resources=[],
            )

        except pipeline.UnsafePhysicalPlanError as exc:
            error_text = str(
                exc
            )

        else:
            raise AssertionError(
                "Expected UnsafePhysicalPlanError "
                "after the bounded repair budget "
                "was exhausted."
            )

    # Initial plan + repaired plan after attempt 1 + repaired plan
    # after attempt 2 must all still pass through hard validation.
    assert hard_validation_calls == 3, (
        "Expected hard validation on initial plan "
        "and after both repairs, but observed "
        f"{hard_validation_calls} calls."
    )

    # The model-backed semantic audit should happen only once:
    #
    # initial semantic audit -> finding
    # repair 1 leaves claim unchanged
    # closure guard detects persistence
    # next semantic model audit is skipped
    # repair 2 leaves claim unchanged
    # closure guard detects persistence
    # final semantic model audit is skipped
    assert semantic_audit_calls == 1, (
        "Closure guard failed to eliminate redundant "
        "semantic audits. Expected 1 semantic audit, "
        f"observed {semantic_audit_calls}."
    )

    assert repair_calls == 2, (
        "Expected exactly the bounded 2 repair attempts, "
        f"observed {repair_calls}."
    )

    assert (
        "Product fits comfortably on "
        "the desk surface"
        in error_text
    ), (
        "Terminal UnsafePhysicalPlanError should preserve "
        "the persisted critic finding."
    )


def run_tests():
    tests = [
        (
            "production loop skips redundant semantic audit",
            test_production_loop_skips_redundant_semantic_audit,
        ),
    ]

    passed = 0

    for name, test in tests:
        test()

        passed += 1

        print(
            f"PASS: {name}"
        )

    print()
    print(
        f"{passed}/{len(tests)} tests passed."
    )

    print(
        "Model calls: 0"
    )


if __name__ == "__main__":
    run_tests()