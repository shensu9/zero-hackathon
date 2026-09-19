from critic_schemas import (
    CriticIssueType,
    CriticSeverity,
    PlanCriticFinding,
    PlanCriticResult,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from verification_gate_schemas import (
    VerificationGateAudit,
)

import plan_outcome_pipeline as pipeline


def passing_critic() -> PlanCriticResult:
    return PlanCriticResult(
        passed=True,
        findings=[],
    )


def failing_critic() -> PlanCriticResult:
    return PlanCriticResult(
        passed=False,
        findings=[
            PlanCriticFinding(
                step_order=None,
                claim=(
                    "The missing fact only gates an "
                    "already-selected plan."
                ),
                issue_type=(
                    CriticIssueType
                    .SAFETY_OR_UNCERTAINTY
                ),
                severity=(
                    CriticSeverity.MEDIUM
                ),
                explanation=(
                    "The uncertainty affects execution, "
                    "not plan selection."
                ),
                recommended_fix=(
                    "Use CONDITIONAL instead."
                ),
            )
        ],
    )


def needs_confirmation_outcome() -> PlanOutcome:
    return PlanOutcome(
        status=(
            PlanOutcomeStatus
            .NEEDS_CONFIRMATION
        ),
        explanation=(
            "The user must choose which item "
            "to feature before a plan can be selected."
        ),
        plan=None,
        requirements=[
            {
                "requirement": (
                    "Confirm whether the user wants "
                    "the guitar or canvas artwork."
                ),
                "how_to_verify": (
                    "Ask the user to choose one."
                ),
                "if_not_met": (
                    "Do not select a display plan."
                ),
            }
        ],
        blocking_reasons=[],
    )


def cannot_outcome() -> PlanOutcome:
    return PlanOutcome(
        status=(
            PlanOutcomeStatus
            .CANNOT_SAFELY_SOLVE
        ),
        explanation=(
            "No grounded safe solution exists."
        ),
        plan=None,
        requirements=[],
        blocking_reasons=[
            "A required capability is absent."
        ],
    )


def run_case(
    *,
    outcome: PlanOutcome,
    confirmation_result: PlanCriticResult,
    expect_error: bool,
):
    calls = {
        "plan_safety": 0,
        "gate": 0,
        "confirmation": 0,
        "blocker": 0,
        "plan_semantic": 0,
    }

    originals = {
        "generate":
            pipeline.generate_plan_outcome,
        "plan_safety":
            pipeline._make_outcome_plan_safe,
        "gate":
            pipeline._make_verification_gate_safe,
        "confirmation":
            pipeline.audit_needs_confirmation_semantics,
        "blocker":
            pipeline.audit_cannot_safely_solve_semantics,
        "plan_semantic":
            pipeline._audit_outcome_plan,
    }

    def fake_generate(**_kwargs):
        return outcome

    def fake_plan_safety(**kwargs):
        calls["plan_safety"] += 1
        return (
            kwargs["outcome"],
            passing_critic(),
            0,
            0,
        )

    def fake_gate(**kwargs):
        calls["gate"] += 1
        return (
            kwargs["outcome"],
            VerificationGateAudit(
                passed=True,
                findings=[],
            ),
            0,
        )

    def fake_confirmation(**_kwargs):
        calls["confirmation"] += 1
        return confirmation_result

    def fake_blocker(**_kwargs):
        calls["blocker"] += 1
        return passing_critic()

    def fake_plan_semantic(**_kwargs):
        calls["plan_semantic"] += 1
        return passing_critic()

    pipeline.generate_plan_outcome = (
        fake_generate
    )
    pipeline._make_outcome_plan_safe = (
        fake_plan_safety
    )
    pipeline._make_verification_gate_safe = (
        fake_gate
    )
    pipeline.audit_needs_confirmation_semantics = (
        fake_confirmation
    )
    pipeline.audit_cannot_safely_solve_semantics = (
        fake_blocker
    )
    pipeline._audit_outcome_plan = (
        fake_plan_semantic
    )

    try:
        if expect_error:
            try:
                pipeline.generate_safe_plan_outcome(
                    goal="Test goal",
                    inventory=[],
                    object_dna=None,
                    external_resources=[],
                )
            except pipeline.UnsafePhysicalPlanError:
                result = None
            else:
                raise AssertionError(
                    "Expected UnsafePhysicalPlanError."
                )

        else:
            result = (
                pipeline.generate_safe_plan_outcome(
                    goal="Test goal",
                    inventory=[],
                    object_dna=None,
                    external_resources=[],
                )
            )

    finally:
        pipeline.generate_plan_outcome = (
            originals["generate"]
        )
        pipeline._make_outcome_plan_safe = (
            originals["plan_safety"]
        )
        pipeline._make_verification_gate_safe = (
            originals["gate"]
        )
        pipeline.audit_needs_confirmation_semantics = (
            originals["confirmation"]
        )
        pipeline.audit_cannot_safely_solve_semantics = (
            originals["blocker"]
        )
        pipeline._audit_outcome_plan = (
            originals["plan_semantic"]
        )

    return result, calls


def main() -> None:
    passed = 0

    result, calls = run_case(
        outcome=needs_confirmation_outcome(),
        confirmation_result=passing_critic(),
        expect_error=False,
    )

    assert result is not None
    assert (
        result.outcome.status
        == PlanOutcomeStatus.NEEDS_CONFIRMATION
    )
    assert result.semantic_critic.passed
    assert calls == {
        "plan_safety": 1,
        "gate": 1,
        "confirmation": 1,
        "blocker": 0,
        "plan_semantic": 0,
    }
    passed += 1

    result, calls = run_case(
        outcome=needs_confirmation_outcome(),
        confirmation_result=failing_critic(),
        expect_error=True,
    )

    assert result is None
    assert calls == {
        "plan_safety": 1,
        "gate": 1,
        "confirmation": 1,
        "blocker": 0,
        "plan_semantic": 0,
    }
    passed += 1

    result, calls = run_case(
        outcome=cannot_outcome(),
        confirmation_result=failing_critic(),
        expect_error=False,
    )

    assert result is not None
    assert (
        result.outcome.status
        == PlanOutcomeStatus.CANNOT_SAFELY_SOLVE
    )
    assert calls == {
        "plan_safety": 1,
        "gate": 1,
        "confirmation": 0,
        "blocker": 1,
        "plan_semantic": 0,
    }
    passed += 1

    print(
        "NEEDS_CONFIRMATION PIPELINE "
        f"INTEGRATION TESTS: {passed}/3 passed"
    )

    print(
        "Model calls: 0"
    )


if __name__ == "__main__":
    main()
