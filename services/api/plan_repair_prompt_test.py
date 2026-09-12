from types import SimpleNamespace

from critic_schemas import (
    CriticSeverity,
)
from plan_repair import (
    _build_repair_prompt,
    _compact_critic,
)


def fake_finding(
    *,
    severity,
    claim,
    explanation,
    recommended_fix,
):
    return SimpleNamespace(
        step_order=1,
        claim=claim,
        issue_type=SimpleNamespace(
            value="unsupported_physical_claim"
        ),
        severity=severity,
        explanation=explanation,
        recommended_fix=recommended_fix,
    )


def test_compact_critic_preserves_explanation():
    critic = SimpleNamespace(
        findings=[
            fake_finding(
                severity=CriticSeverity.MEDIUM,
                claim="to prevent slipping",
                explanation=(
                    "Fastening does not guarantee "
                    "slip resistance."
                ),
                recommended_fix=(
                    "State only that the lanyard "
                    "fastens the blanket."
                ),
            )
        ]
    )

    compact = _compact_critic(
        critic
    )

    assert len(compact) == 1

    assert compact[0]["claim"] == (
        "to prevent slipping"
    )

    assert compact[0]["explanation"] == (
        "Fastening does not guarantee "
        "slip resistance."
    )

    assert compact[0]["recommended_fix"] == (
        "State only that the lanyard "
        "fastens the blanket."
    )


def test_compact_critic_ignores_low_findings():
    critic = SimpleNamespace(
        findings=[
            fake_finding(
                severity=CriticSeverity.LOW,
                claim="minor wording",
                explanation="Minor issue.",
                recommended_fix="Optional cleanup.",
            )
        ]
    )

    compact = _compact_critic(
        critic
    )

    assert compact == []


def build_lanyard_regression_prompt():
    return _build_repair_prompt(
        goal=(
            "Create a $0 product photography setup "
            "at home using only what I already have, "
            "without permanent modifications."
        ),
        external_resources=[
            "smartphone",
            "insta360 camera",
        ],
        inventory_payload=[
            {
                "id": "blanket_f02_o02",
                "name": "blanket",
            },
            {
                "id": "lanyard_f06_o09",
                "name": "lanyard",
            },
            {
                "id": "wardrobe_door_f01_o05",
                "name": "wardrobe door",
            },
        ],
        capability_graph=[
            {
                "item_id": "lanyard_f06_o09",
                "traits": [
                    "flexible",
                ],
                "capabilities": [
                    "fasten",
                ],
                "unknowns": [],
                "cautions": [],
            }
        ],
        failed_plan={
            "title": (
                "Zero-Cost Product Photography Setup"
            ),
            "summary": (
                "Use a lanyard to secure the blanket."
            ),
            "steps": [
                {
                    "order": 1,
                    "action": (
                        "Secure blanket with lanyard "
                        "to prevent slipping"
                    ),
                    "item_ids": [
                        "blanket_f02_o02",
                        "lanyard_f06_o09",
                        "wardrobe_door_f01_o05",
                    ],
                    "capability_uses": [
                        {
                            "item_id":
                                "lanyard_f06_o09",
                            "capability":
                                "fasten",
                            "purpose":
                                "Secure blanket to door",
                        }
                    ],
                    "why_it_helps": (
                        "Reduces slip risk"
                    ),
                }
            ],
            "assumptions": [
                (
                    "Lanyard fastens blanket to door, "
                    "reducing slip risk"
                )
            ],
            "unresolved_risks": [
                (
                    "Blanket may still move"
                )
            ],
        },
        blocking_findings=[
            {
                "step_order": 1,
                "claim": "to prevent slipping",
                "issue_type": (
                    "unsupported_physical_claim"
                ),
                "severity": "medium",
                "explanation": (
                    "Fastening alone does not guarantee "
                    "slip resistance."
                ),
                "recommended_fix": (
                    "Say only that the lanyard fastens "
                    "the blanket."
                ),
            },
            {
                "step_order": None,
                "claim": (
                    "reducing slip risk"
                ),
                "issue_type": (
                    "unsupported_physical_claim"
                ),
                "severity": "medium",
                "explanation": (
                    "The fasten capability does not "
                    "establish reduced slip risk."
                ),
                "recommended_fix": (
                    "Do not assert slip-risk reduction."
                ),
            },
        ],
    )


def test_prompt_blocks_semantic_strengthening():
    prompt = build_lanyard_regression_prompt()

    required_phrases = [
        (
            "A repair must NEVER replace one unsupported "
            "claim with a new unsupported claim."
        ),
        (
            "Do not strengthen certainty or causal "
            "language while repairing a finding."
        ),
        (
            "Capability purposes must describe the direct "
            "use of the capability"
        ),
        "prevent slipping",
        "reduce slip risk",
        "ensure the blanket stays in place",
        "make the setup safer",
        (
            "fasten the blanket to the door"
        ),
        (
            "Do NOT replace it with another "
            "softer-sounding causal claim."
        ),
        (
            "keep that uncertainty in unresolved_risks"
        ),
    ]

    for phrase in required_phrases:
        assert phrase in prompt, (
            f"Missing repair guardrail: {phrase}"
        )


def test_prompt_contains_original_failure_context():
    prompt = build_lanyard_regression_prompt()

    assert (
        "Fastening alone does not guarantee "
        "slip resistance."
    ) in prompt

    assert (
        "The fasten capability does not "
        "establish reduced slip risk."
    ) in prompt

    assert (
        '"capabilities": ['
    ) in prompt

    assert (
        '"fasten"'
    ) in prompt


def run_tests():
    tests = [
        (
            "compact critic preserves explanation",
            test_compact_critic_preserves_explanation,
        ),
        (
            "low findings ignored",
            test_compact_critic_ignores_low_findings,
        ),
        (
            "semantic strengthening blocked",
            test_prompt_blocks_semantic_strengthening,
        ),
        (
            "original failure context preserved",
            test_prompt_contains_original_failure_context,
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