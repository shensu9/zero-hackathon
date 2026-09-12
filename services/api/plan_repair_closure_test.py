from critic_schemas import (
    PlanCriticFinding,
    PlanCriticResult,
)
from plan_repair_closure import (
    find_persisted_critic_findings,
)
from plan_schemas import (
    CapabilityUse,
    PhysicalPlan,
    PlanStep,
)


def build_before_plan() -> PhysicalPlan:
    """
    V4 plan before repair attempt 2.
    """

    return PhysicalPlan(
        title="Zero-Cost Product Photography Setup",

        summary=(
            "Use a wardrobe door to hang a blanket backdrop, "
            "window light for diffused illumination, a desk as "
            "product surface, and handheld smartphone/Insta360 "
            "for image capture."
        ),

        item_ids_used=[
            "blanket_f02_o02",
            "desk_f05_o08",
            "wardrobe_door_f01_o05",
            "window_f03_o10",
        ],

        steps=[
            PlanStep(
                order=1,
                action=(
                    "Drape blanket over wardrobe door "
                    "to create a hanging backdrop"
                ),
                item_ids=[
                    "wardrobe_door_f01_o05",
                    "blanket_f02_o02",
                ],
                capability_uses=[
                    CapabilityUse(
                        item_id=(
                            "wardrobe_door_f01_o05"
                        ),
                        capability="hang",
                        purpose=(
                            "Hold blanket in place"
                        ),
                    ),
                    CapabilityUse(
                        item_id=(
                            "blanket_f02_o02"
                        ),
                        capability="hang",
                        purpose=(
                            "Drape over door to create backdrop"
                        ),
                    ),
                ],
                why_it_helps=(
                    "Provides a uniform background "
                    "without modifying walls."
                ),
            ),

            PlanStep(
                order=2,
                action=(
                    "Position the setup near the window "
                    "to use its diffused natural light"
                ),
                item_ids=[
                    "window_f03_o10",
                ],
                capability_uses=[
                    CapabilityUse(
                        item_id=(
                            "window_f03_o10"
                        ),
                        capability="diffuse_light",
                        purpose=(
                            "Diffuse incoming light"
                        ),
                    ),
                ],
                why_it_helps=(
                    "Uses window light for illumination "
                    "without extra gear."
                ),
            ),

            PlanStep(
                order=3,
                action=(
                    "Place the product on the desk surface"
                ),
                item_ids=[
                    "desk_f05_o08",
                ],
                capability_uses=[
                    CapabilityUse(
                        item_id=(
                            "desk_f05_o08"
                        ),
                        capability="provide_surface",
                        purpose=(
                            "Provide surface for product"
                        ),
                    ),
                ],
                why_it_helps=(
                    "Offers a flat area to showcase "
                    "the product."
                ),
            ),

            PlanStep(
                order=4,
                action=(
                    "Hold the smartphone at eye level "
                    "to frame the shot"
                ),
                item_ids=[],
                capability_uses=[],
                why_it_helps=(
                    "Allows flexible framing and avoids "
                    "reliance on unverified load-bearing "
                    "surfaces."
                ),
            ),

            PlanStep(
                order=5,
                action=(
                    "Capture images with the smartphone "
                    "and Insta360 camera"
                ),
                item_ids=[],
                capability_uses=[],
                why_it_helps=(
                    "Records the product using "
                    "available devices."
                ),
            ),
        ],

        assumptions=[
            (
                "Product fits comfortably on the "
                "desk surface"
            ),
        ],

        unresolved_risks=[
            (
                "Blanket may slip if the door is moved"
            ),
            (
                "Handheld camera may introduce motion "
                "blur if shutter speed is low"
            ),
            (
                "Light intensity varies with time of "
                "day and weather"
            ),
        ],

        constraint_check=[],
    )


def build_repaired_plan() -> PhysicalPlan:
    """
    Actual V4 repair-attempt-2 result.

    Important:
    - uniform-background wording was removed
    - desk-fit assumption survived unchanged
    """

    plan = build_before_plan()

    payload = plan.model_dump(
        mode="json"
    )

    payload["steps"][0][
        "why_it_helps"
    ] = (
        "Provides a backdrop without modifying walls."
    )

    # Intentionally leave the rejected desk-fit assumption unchanged.
    payload["assumptions"] = [
        (
            "Product fits comfortably on the "
            "desk surface"
        )
    ]

    return PhysicalPlan.model_validate(
        payload
    )


def build_v4_critic() -> PlanCriticResult:
    return PlanCriticResult(
        passed=False,
        findings=[
            PlanCriticFinding(
                step_order=1,
                claim=(
                    "Provides a uniform background"
                ),
                issue_type=(
                    "unsupported_physical_claim"
                ),
                severity="medium",
                explanation=(
                    "The blanket's appearance is not "
                    "guaranteed to be uniform."
                ),
                recommended_fix=(
                    "Remove uniformity claim."
                ),
            ),

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
                    "Product dimensions are not "
                    "verified against the desk."
                ),
                recommended_fix=(
                    "Verify fit or remove the assumption."
                ),
            ),
        ],
    )


def test_exact_v4_failure_detected():
    result = find_persisted_critic_findings(
        before_plan=build_before_plan(),
        repaired_plan=build_repaired_plan(),
        critic=build_v4_critic(),
    )

    assert result is not None

    assert result.passed is False

    assert len(
        result.findings
    ) == 1

    assert result.findings[0].claim == (
        "Product fits comfortably on "
        "the desk surface"
    )


def test_removed_uniform_claim_not_reported():
    result = find_persisted_critic_findings(
        before_plan=build_before_plan(),
        repaired_plan=build_repaired_plan(),
        critic=build_v4_critic(),
    )

    assert result is not None

    claims = {
        finding.claim
        for finding in result.findings
    }

    assert (
        "Provides a uniform background"
        not in claims
    )


def test_all_removed_returns_none():
    before_plan = build_before_plan()

    repaired_plan = build_repaired_plan()

    payload = repaired_plan.model_dump(
        mode="json"
    )

    payload["assumptions"] = []

    fully_repaired = (
        PhysicalPlan.model_validate(
            payload
        )
    )

    result = find_persisted_critic_findings(
        before_plan=before_plan,
        repaired_plan=fully_repaired,
        critic=build_v4_critic(),
    )

    assert result is None


def test_low_severity_is_ignored():
    critic = PlanCriticResult(
        passed=True,
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
                severity="low",
                explanation=(
                    "Minor wording concern."
                ),
                recommended_fix=(
                    "Optional cleanup."
                ),
            ),
        ],
    )

    result = find_persisted_critic_findings(
        before_plan=build_before_plan(),
        repaired_plan=build_repaired_plan(),
        critic=critic,
    )

    assert result is None


def test_ambiguous_pre_repair_claim_is_not_used():
    before_plan = build_before_plan()

    payload = before_plan.model_dump(
        mode="json"
    )

    duplicated_claim = (
        "Product fits comfortably on "
        "the desk surface"
    )

    payload["summary"] = (
        "Photography setup. "
        + duplicated_claim
    )

    ambiguous_before = (
        PhysicalPlan.model_validate(
            payload
        )
    )

    critic = PlanCriticResult(
        passed=False,
        findings=[
            PlanCriticFinding(
                step_order=None,
                claim=duplicated_claim,
                issue_type=(
                    "hidden_assumption"
                ),
                severity="medium",
                explanation=(
                    "Fit is unverified."
                ),
                recommended_fix=(
                    "Remove the assumption."
                ),
            ),
        ],
    )

    result = find_persisted_critic_findings(
        before_plan=ambiguous_before,
        repaired_plan=build_repaired_plan(),
        critic=critic,
    )

    # The closure guard is intentionally conservative.
    # Two possible pre-repair sources means it does not make
    # a deterministic claim about closure.
    assert result is None


def run_tests():
    tests = [
        (
            "exact V4 persisted finding detected",
            test_exact_v4_failure_detected,
        ),
        (
            "removed uniform claim ignored",
            test_removed_uniform_claim_not_reported,
        ),
        (
            "fully removed findings return none",
            test_all_removed_returns_none,
        ),
        (
            "low severity ignored",
            test_low_severity_is_ignored,
        ),
        (
            "ambiguous source remains conservative",
            test_ambiguous_pre_repair_claim_is_not_used,
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