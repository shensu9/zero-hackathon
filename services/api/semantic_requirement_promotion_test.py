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
from semantic_requirement_promotion import (
    _validate_promoted_requirements,
    promotion_ineligibility_reason,
    semantic_findings_are_promotable,
)


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
                        "Places the blanket where it may be used."
                    ),
                }
            ],
            "assumptions": [],
            "unresolved_risks": [],
            "constraint_check": [],
        }
    )


def requirement(
    text: str,
) -> PlanRequirement:
    return PlanRequirement(
        requirement=text,
        how_to_verify=(
            "Verify the fact safely before execution."
        ),
        if_not_met=(
            "Do not execute this plan path."
        ),
    )


def conditional_outcome(
    *,
    requirement_count: int = 1,
) -> PlanOutcome:
    return PlanOutcome(
        status=PlanOutcomeStatus.CONDITIONAL,
        explanation=(
            "The plan may execute only after verification."
        ),
        plan=build_plan(),
        requirements=[
            requirement(
                f"Existing requirement {index + 1}"
            )
            for index
            in range(
                requirement_count
            )
        ],
        blocking_reasons=[],
    )


def solved_outcome() -> PlanOutcome:
    return PlanOutcome(
        status=PlanOutcomeStatus.SOLVED,
        explanation="Plan is ready.",
        plan=build_plan(),
        requirements=[],
        blocking_reasons=[],
    )


def finding(
    *,
    issue_type: CriticIssueType,
    severity: CriticSeverity,
) -> PlanCriticFinding:
    return PlanCriticFinding(
        step_order=None,
        claim="A physical claim remains unresolved.",
        issue_type=issue_type,
        severity=severity,
        explanation=(
            "A physical fact is unknown before execution."
        ),
        recommended_fix=(
            "Verify the fact before execution."
        ),
    )


def critic_with(
    *findings: PlanCriticFinding,
) -> PlanCriticResult:
    return PlanCriticResult(
        passed=False,
        findings=list(
            findings
        ),
    )


def assert_raises(
    expected_exception,
    func,
    *,
    contains: str,
) -> None:
    try:
        func()
    except expected_exception as exc:
        assert (
            contains.lower()
            in str(exc).lower()
        ), (
            f"Expected error containing {contains!r}; "
            f"got: {exc}"
        )
    else:
        raise AssertionError(
            f"Expected {expected_exception.__name__}"
        )


def main() -> None:
    passed = 0

    outcome = conditional_outcome()

    # 1. MEDIUM unsupported physical claim is promotable.
    critic = critic_with(
        finding(
            issue_type=(
                CriticIssueType
                .UNSUPPORTED_PHYSICAL_CLAIM
            ),
            severity=CriticSeverity.MEDIUM,
        )
    )

    assert semantic_findings_are_promotable(
        outcome=outcome,
        critic=critic,
    )
    passed += 1

    # 2. MEDIUM hidden assumption is promotable.
    assert semantic_findings_are_promotable(
        outcome=outcome,
        critic=critic_with(
            finding(
                issue_type=(
                    CriticIssueType
                    .HIDDEN_ASSUMPTION
                ),
                severity=(
                    CriticSeverity.MEDIUM
                ),
            )
        ),
    )
    passed += 1

    # 3. MEDIUM safety/uncertainty is promotable.
    assert semantic_findings_are_promotable(
        outcome=outcome,
        critic=critic_with(
            finding(
                issue_type=(
                    CriticIssueType
                    .SAFETY_OR_UNCERTAINTY
                ),
                severity=(
                    CriticSeverity.MEDIUM
                ),
            )
        ),
    )
    passed += 1

    # 4. HIGH findings fail closed.
    high_critic = critic_with(
        finding(
            issue_type=(
                CriticIssueType
                .UNSUPPORTED_PHYSICAL_CLAIM
            ),
            severity=CriticSeverity.HIGH,
        )
    )

    assert not semantic_findings_are_promotable(
        outcome=outcome,
        critic=high_critic,
    )

    assert "high-severity" in (
        promotion_ineligibility_reason(
            outcome=outcome,
            critic=high_critic,
        )
        or ""
    ).lower()

    passed += 1

    # 5. Unlisted resources are never promotable.
    assert not semantic_findings_are_promotable(
        outcome=outcome,
        critic=critic_with(
            finding(
                issue_type=(
                    CriticIssueType
                    .UNLISTED_RESOURCE
                ),
                severity=(
                    CriticSeverity.MEDIUM
                ),
            )
        ),
    )
    passed += 1

    # 6. Unsupported capabilities are never promotable.
    assert not semantic_findings_are_promotable(
        outcome=outcome,
        critic=critic_with(
            finding(
                issue_type=(
                    CriticIssueType
                    .UNSUPPORTED_CAPABILITY
                ),
                severity=(
                    CriticSeverity.MEDIUM
                ),
            )
        ),
    )
    passed += 1

    # 7. Constraint violations are never promotable.
    assert not semantic_findings_are_promotable(
        outcome=outcome,
        critic=critic_with(
            finding(
                issue_type=(
                    CriticIssueType
                    .CONSTRAINT_VIOLATION
                ),
                severity=(
                    CriticSeverity.MEDIUM
                ),
            )
        ),
    )
    passed += 1

    # 8. SOLVED outcomes cannot be silently converted.
    assert not semantic_findings_are_promotable(
        outcome=solved_outcome(),
        critic=critic,
    )
    passed += 1

    # 9. No blocking findings means no promotion.
    empty_critic = PlanCriticResult(
        passed=True,
        findings=[],
    )

    assert not semantic_findings_are_promotable(
        outcome=outcome,
        critic=empty_critic,
    )
    passed += 1

    # 10. No remaining requirement capacity fails closed.
    full_outcome = conditional_outcome(
        requirement_count=5
    )

    assert not semantic_findings_are_promotable(
        outcome=full_outcome,
        critic=critic,
    )
    passed += 1

    # 11. Existing requirement duplication is rejected.
    duplicate = requirement(
        "Existing requirement 1"
    )

    assert_raises(
        RuntimeError,
        lambda: _validate_promoted_requirements(
            outcome=outcome,
            promoted_requirements=[
                duplicate,
            ],
        ),
        contains="duplicated an existing requirement",
    )
    passed += 1

    # 12. Duplicate newly promoted requirements are rejected.
    new_one = requirement(
        "Blanket must fit the doorway."
    )

    new_two = requirement(
        "  Blanket   must fit the doorway.  "
    )

    assert_raises(
        RuntimeError,
        lambda: _validate_promoted_requirements(
            outcome=outcome,
            promoted_requirements=[
                new_one,
                new_two,
            ],
        ),
        contains="duplicate new requirements",
    )
    passed += 1

    # 13. Remaining slot capacity is enforced.
    almost_full = conditional_outcome(
        requirement_count=4
    )

    assert_raises(
        RuntimeError,
        lambda: _validate_promoted_requirements(
            outcome=almost_full,
            promoted_requirements=[
                requirement(
                    "New fact A"
                ),
                requirement(
                    "New fact B"
                ),
            ],
        ),
        contains="exceeded remaining",
    )
    passed += 1

    print()
    print(
        "SEMANTIC REQUIREMENT PROMOTION "
        f"GUARDRAIL TESTS: {passed}/13 passed"
    )
    print(
        "Model calls: 0"
    )


if __name__ == "__main__":
    main()