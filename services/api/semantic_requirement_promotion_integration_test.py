from unittest.mock import patch

import plan_outcome_pipeline as pipeline

from critic_schemas import (
    CriticIssueType,
    CriticSeverity,
    PlanCriticFinding,
    PlanCriticResult,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
    PlanRequirement,
)
from plan_schemas import PhysicalPlan


def build_plan() -> PhysicalPlan:
    return PhysicalPlan.model_validate(
        {
            "title": "Temporary curtain",
            "summary": "Use a blanket as a temporary curtain.",
            "item_ids_used": [
                "blanket_01",
            ],
            "steps": [
                {
                    "order": 1,
                    "action": "Position the blanket.",
                    "item_ids": [
                        "blanket_01",
                    ],
                    "capability_uses": [
                        {
                            "item_id": "blanket_01",
                            "capability": "reposition",
                            "purpose": "Position the blanket.",
                        }
                    ],
                    "why_it_helps": (
                        "Positions the blanket for the intended use."
                    ),
                }
            ],
            "assumptions": [],
            "unresolved_risks": [],
            "constraint_check": [],
        }
    )


def existing_requirement() -> PlanRequirement:
    return PlanRequirement(
        requirement=(
            "The support must be safe before execution."
        ),
        how_to_verify=(
            "Inspect the support before beginning the plan."
        ),
        if_not_met=(
            "Do not execute this plan path."
        ),
    )


def promoted_requirement() -> PlanRequirement:
    return PlanRequirement(
        requirement=(
            "The blanket must be large enough for the intended opening."
        ),
        how_to_verify=(
            "Compare the blanket size with the intended opening "
            "before beginning the plan."
        ),
        if_not_met=(
            "Do not use this blanket for this plan path."
        ),
    )


def build_outcome() -> PlanOutcome:
    return PlanOutcome(
        status=PlanOutcomeStatus.CONDITIONAL,
        explanation=(
            "The plan may execute only after its requirements pass."
        ),
        plan=build_plan(),
        requirements=[
            existing_requirement(),
        ],
        blocking_reasons=[],
    )


def blocking_critic() -> PlanCriticResult:
    return PlanCriticResult(
        passed=False,
        findings=[
            PlanCriticFinding(
                step_order=None,
                claim=(
                    "Blanket fit is not established."
                ),
                issue_type=(
                    CriticIssueType
                    .UNSUPPORTED_PHYSICAL_CLAIM
                ),
                severity=(
                    CriticSeverity.MEDIUM
                ),
                explanation=(
                    "Blanket dimensions are unknown."
                ),
                recommended_fix=(
                    "Verify fit before execution."
                ),
            )
        ],
    )


def passing_critic() -> PlanCriticResult:
    return PlanCriticResult(
        passed=True,
        findings=[],
    )


def run_case(
    *,
    semantic_results,
    promotion_reason,
    promoted_requirements,
):
    outcome = build_outcome()

    with (
        patch.object(
            pipeline,
            "_normalize_plan",
            side_effect=lambda **kwargs: kwargs["plan"],
        ) as normalize_mock,
        patch.object(
            pipeline,
            "_hard_validate_plan",
            side_effect=lambda **kwargs: kwargs["plan"],
        ) as validate_mock,
        patch.object(
            pipeline,
            "_audit_outcome_plan",
            side_effect=semantic_results,
        ) as semantic_mock,
        patch.object(
            pipeline,
            "repair_plan",
            side_effect=lambda **kwargs: kwargs["plan"],
        ) as repair_mock,
        patch.object(
            pipeline,
            "find_persisted_critic_findings",
            return_value=None,
        ) as closure_mock,
        patch.object(
            pipeline,
            "promotion_ineligibility_reason",
            return_value=promotion_reason,
        ) as eligibility_mock,
        patch.object(
            pipeline,
            "promote_semantic_findings_to_requirements",
            return_value=promoted_requirements,
        ) as promotion_mock,
    ):
        try:
            result = pipeline._make_outcome_plan_safe(
                outcome=outcome,
                goal="Create a temporary curtain.",
                inventory=[],
                object_dna=None,
                external_resources=[],
            )

            error = None

        except Exception as exc:
            result = None
            error = exc

    return {
        "result": result,
        "error": error,
        "normalize_mock": normalize_mock,
        "validate_mock": validate_mock,
        "semantic_mock": semantic_mock,
        "repair_mock": repair_mock,
        "closure_mock": closure_mock,
        "eligibility_mock": eligibility_mock,
        "promotion_mock": promotion_mock,
    }


def main() -> None:
    passed = 0

    # ------------------------------------------------------------
    # CASE 1
    #
    # Two PhysicalPlan repairs are exhausted.
    # Remaining eligible semantic uncertainty is promoted.
    # Expanded execution contract passes semantic re-audit.
    # ------------------------------------------------------------

    fail = blocking_critic()
    success = passing_critic()
    new_requirement = promoted_requirement()

    case = run_case(
        semantic_results=[
            fail,
            fail,
            fail,
            success,
        ],
        promotion_reason=None,
        promoted_requirements=[
            new_requirement,
        ],
    )

    assert case["error"] is None, case["error"]

    (
        output_outcome,
        output_critic,
        repair_attempts,
        validation_failures,
    ) = case["result"]

    assert repair_attempts == 2
    assert validation_failures == 0
    assert output_critic.passed

    assert (
        output_outcome.status
        == PlanOutcomeStatus.CONDITIONAL
    )

    assert len(
        output_outcome.requirements
    ) == 2

    assert (
        output_outcome.requirements[0]
        == existing_requirement()
    )

    assert (
        output_outcome.requirements[1]
        == new_requirement
    )

    assert (
        output_outcome.plan
        == build_plan()
    )

    assert (
        case["repair_mock"].call_count
        == 2
    )

    assert (
        case["promotion_mock"].call_count
        == 1
    )

    assert (
        case["semantic_mock"].call_count
        == 4
    )

    passed += 1

    # ------------------------------------------------------------
    # CASE 2
    #
    # Non-promotable semantic failure must fail closed after
    # exactly two PhysicalPlan repair attempts.
    # The promotion model must never be called.
    # ------------------------------------------------------------

    case = run_case(
        semantic_results=[
            fail,
            fail,
            fail,
        ],
        promotion_reason=(
            "Non-promotable semantic failure."
        ),
        promoted_requirements=[
            new_requirement,
        ],
    )

    assert isinstance(
        case["error"],
        pipeline.UnsafePhysicalPlanError,
    )

    assert (
        case["repair_mock"].call_count
        == 2
    )

    assert (
        case["promotion_mock"].call_count
        == 0
    )

    assert (
        case["semantic_mock"].call_count
        == 3
    )

    passed += 1

    # ------------------------------------------------------------
    # CASE 3
    #
    # Eligible promotion happens once, but semantic re-audit
    # still fails. ZERO must fail closed. No repair attempt 3
    # and no promotion attempt 2 are permitted.
    # ------------------------------------------------------------

    case = run_case(
        semantic_results=[
            fail,
            fail,
            fail,
            fail,
        ],
        promotion_reason=None,
        promoted_requirements=[
            new_requirement,
        ],
    )

    assert isinstance(
        case["error"],
        pipeline.UnsafePhysicalPlanError,
    )

    assert (
        case["repair_mock"].call_count
        == 2
    )

    assert (
        case["promotion_mock"].call_count
        == 1
    )

    assert (
        case["semantic_mock"].call_count
        == 4
    )

    passed += 1

    print()
    print(
        "SEMANTIC REQUIREMENT PROMOTION "
        f"PRODUCTION INTEGRATION TESTS: {passed}/3 passed"
    )
    print(
        "PhysicalPlan repair ceiling: 2"
    )
    print(
        "Requirement promotion ceiling after exhaustion: 1"
    )
    print(
        "Network/model calls: 0"
    )


if __name__ == "__main__":
    main()