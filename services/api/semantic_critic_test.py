from plan_schemas import (
    CapabilityUse,
    PhysicalPlan,
    PlanStep,
)
from semantic_critic import (
    _build_semantic_critic_prompt,
)


def build_regression_plan() -> PhysicalPlan:
    return PhysicalPlan(
        title="Zero-Cost Product Photography Setup",

        summary=(
            "Use a blanket backdrop and desk surface "
            "for product photography."
        ),

        item_ids_used=[
            "blanket_01",
            "desk_01",
        ],

        steps=[
            PlanStep(
                order=1,
                action=(
                    "Hang the blanket as a backdrop."
                ),
                item_ids=[
                    "blanket_01",
                ],
                capability_uses=[
                    CapabilityUse(
                        item_id="blanket_01",
                        capability="hang",
                        purpose=(
                            "Hang blanket as backdrop."
                        ),
                    )
                ],
                why_it_helps=(
                    "Provides a uniform background."
                ),
            ),

            PlanStep(
                order=2,
                action=(
                    "Place the product on the desk."
                ),
                item_ids=[
                    "desk_01",
                ],
                capability_uses=[
                    CapabilityUse(
                        item_id="desk_01",
                        capability="provide_surface",
                        purpose=(
                            "Provide surface for product."
                        ),
                    )
                ],
                why_it_helps=(
                    "Provides a clean stable surface."
                ),
            ),
        ],

        assumptions=[
            (
                "Product fits comfortably on the desk."
            )
        ],

        unresolved_risks=[
            (
                "Blanket may move during use."
            )
        ],

        constraint_check=[
            (
                "Budget remains $0."
            )
        ],
    )


def build_prompt() -> str:
    return _build_semantic_critic_prompt(
        plan=build_regression_plan(),

        goal=(
            "Create a $0 product photography setup "
            "using only existing resources."
        ),

        inventory_payload=[
            {
                "id": "blanket_01",
                "name": "blanket",
                "description": (
                    "Large blanket."
                ),
            },
            {
                "id": "desk_01",
                "name": "desk",
                "description": (
                    "Desk with flat top."
                ),
            },
        ],

        compact_dna=[
            {
                "item_id": "blanket_01",
                "traits": [
                    "soft",
                    "flexible",
                ],
                "capabilities": [
                    "cover",
                    "hang",
                ],
                "unknown_properties": [],
                "caution_notes": [],
            },
            {
                "item_id": "desk_01",
                "traits": [
                    "flat",
                    "large_surface",
                ],
                "capabilities": [
                    "provide_surface",
                ],
                "unknown_properties": [
                    (
                        "load-bearing capacity"
                    )
                ],
                "caution_notes": [],
            },
        ],

        external_resources=[
            "smartphone",
        ],
    )


def test_full_plan_coverage_contract():
    prompt = " ".join(build_prompt().split())

    required_coverage_phrases = [
        "FULL-PLAN COVERAGE CONTRACT",
        "title",
        "summary",
        "EVERY step.action",
        (
            "EVERY capability_uses[].purpose"
        ),
        "EVERY step.why_it_helps",
        "EVERY assumption",
        "EVERY unresolved_risk",
        "EVERY constraint_check entry",
        (
            "Do NOT stop auditing after "
            "finding the first problem."
        ),
        (
            "Before returning passed=true"
        ),
    ]

    for phrase in required_coverage_phrases:
        assert phrase in prompt, (
            f"Missing coverage rule: {phrase}"
        )


def test_blanket_direct_capability_does_not_imply_uniformity():
    prompt = " ".join(build_prompt().split())

    required_phrases = [
        (
            'A blanket that can "cover" '
            'or "hang" may be usable as a backdrop.'
        ),
        (
            '"Provides a uniform background."'
        ),
        (
            '"Provides a clean background."'
        ),
        (
            '"Provides a consistent color or texture."'
        ),
        (
            "Those appearance claims require "
            "supporting observed description"
        ),
        (
            "Do NOT use these words as a blind blacklist."
        ),
    ]

    for phrase in required_phrases:
        assert phrase in prompt, (
            f"Missing appearance grounding rule: {phrase}"
        )


def test_direct_capability_does_not_imply_downstream_effect():
    prompt = " ".join(build_prompt().split())

    required_phrases = [
        (
            "A direct capability does not "
            "automatically prove its hoped-for "
            "downstream effect."
        ),
        "prevents slipping",
        "reduces slip risk",
        "guarantees stability",
        "makes an arrangement safe",
        "enough light for exposure",
        "professional-quality lighting",
        "arbitrary product fits",
        "load capacity is sufficient",
    ]

    for phrase in required_phrases:
        assert phrase in prompt, (
            f"Missing causal grounding rule: {phrase}"
        )


def test_pass_requires_completed_full_sweep():
    prompt = " ".join(build_prompt().split())

    required_phrases = [
        (
            "passed should be true only when:"
        ),
        (
            "the FULL-PLAN COVERAGE CONTRACT "
            "has been completed"
        ),
        (
            "no meaningful unsupported physical "
            "claim remains anywhere in the plan"
        ),
        (
            "Do not return passed=true merely "
            "because one previously known finding "
            "has been fixed."
        ),
    ]

    for phrase in required_phrases:
        assert phrase in prompt, (
            f"Missing pass rule: {phrase}"
        )


def test_prompt_includes_actual_plan_fields():
    prompt = " ".join(build_prompt().split())

    actual_plan_content = [
        "Provides a uniform background.",
        "Provides a clean stable surface.",
        "Product fits comfortably on the desk.",
        "Blanket may move during use.",
        "Budget remains $0.",
    ]

    for text in actual_plan_content:
        assert text in prompt, (
            f"Plan field missing from audit prompt: {text}"
        )


def test_prompt_includes_grounding_context():
    prompt = " ".join(build_prompt().split())

    required_grounding = [
        '"item_id": "blanket_01"',
        '"cover"',
        '"hang"',
        '"item_id": "desk_01"',
        '"provide_surface"',
        '"load-bearing capacity"',
        '"smartphone"',
    ]

    for text in required_grounding:
        assert text in prompt, (
            f"Grounding context missing: {text}"
        )


def run_tests():
    tests = [
        (
            "full plan coverage contract",
            test_full_plan_coverage_contract,
        ),
        (
            "blanket capability does not imply uniformity",
            test_blanket_direct_capability_does_not_imply_uniformity,
        ),
        (
            "direct capability does not imply downstream effect",
            test_direct_capability_does_not_imply_downstream_effect,
        ),
        (
            "pass requires completed full sweep",
            test_pass_requires_completed_full_sweep,
        ),
        (
            "actual plan fields included",
            test_prompt_includes_actual_plan_fields,
        ),
        (
            "grounding context included",
            test_prompt_includes_grounding_context,
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