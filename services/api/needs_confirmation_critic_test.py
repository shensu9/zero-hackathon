import json

from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from semantic_critic import (
    IncompleteSemanticCoverageError,
)
from needs_confirmation_critic import (
    _build_confirmation_critic_prompt,
    _build_confirmation_field_map,
    _parse_confirmation_critic_output,
)


def build_outcome() -> PlanOutcome:
    return PlanOutcome(
        status=(
            PlanOutcomeStatus
            .NEEDS_CONFIRMATION
        ),

        explanation=(
            "The user must choose which display item "
            "they want to feature before a physical "
            "arrangement can be selected."
        ),

        plan=None,

        requirements=[
            {
                "requirement": (
                    "Confirm whether the user wants "
                    "the guitar or canvas artwork "
                    "to be the focal display."
                ),

                "how_to_verify": (
                    "Ask the user to choose which "
                    "item they want to feature."
                ),

                "if_not_met": (
                    "Do not select or execute a "
                    "display plan."
                ),
            }
        ],

        blocking_reasons=[],
    )


def assert_raises(
    exception_type,
    func,
):
    try:
        func()

    except exception_type:
        return

    raise AssertionError(
        f"Expected {exception_type.__name__}"
    )


def main() -> None:
    passed = 0

    outcome = build_outcome()

    field_map = (
        _build_confirmation_field_map(
            outcome
        )
    )

    assert list(
        field_map.keys()
    ) == [
        "explanation",
        "requirement:1:requirement",
        "requirement:1:how_to_verify",
        "requirement:1:if_not_met",
    ]

    passed += 1

    clean_payload = {
        "findings": [],
        "coverage": {
            "explanation": [],
            "requirement:1:requirement": [],
            "requirement:1:how_to_verify": [],
            "requirement:1:if_not_met": [],
        },
    }

    clean = (
        _parse_confirmation_critic_output(
            raw_output=json.dumps(
                clean_payload
            ),

            required_field_ids=list(
                field_map.keys()
            ),
        )
    )

    assert clean.passed
    assert clean.findings == []

    passed += 1

    wrong_boundary_payload = {
        "findings": [
            {
                "step_order": None,

                "claim": (
                    "The requirement only gates "
                    "execution of an already-selected "
                    "physical plan."
                ),

                "issue_type":
                    "safety_or_uncertainty",

                "severity":
                    "medium",

                "explanation": (
                    "This uncertainty affects whether "
                    "the selected plan may execute, "
                    "not which plan should be chosen."
                ),

                "recommended_fix": (
                    "Use CONDITIONAL rather than "
                    "NEEDS_CONFIRMATION."
                ),
            }
        ],

        "coverage": {
            "explanation": [1],
            "requirement:1:requirement": [1],
            "requirement:1:how_to_verify": [],
            "requirement:1:if_not_met": [],
        },
    }

    blocked = (
        _parse_confirmation_critic_output(
            raw_output=json.dumps(
                wrong_boundary_payload
            ),

            required_field_ids=list(
                field_map.keys()
            ),
        )
    )

    assert not blocked.passed
    assert len(
        blocked.findings
    ) == 1

    passed += 1

    missing_coverage = {
        "findings": [],
        "coverage": {
            "explanation": [],
            "requirement:1:requirement": [],
            "requirement:1:how_to_verify": [],
        },
    }

    assert_raises(
        IncompleteSemanticCoverageError,

        lambda: (
            _parse_confirmation_critic_output(
                raw_output=json.dumps(
                    missing_coverage
                ),

                required_field_ids=list(
                    field_map.keys()
                ),
            )
        ),
    )

    passed += 1

    bad_step = {
        "findings": [
            {
                "step_order": 1,
                "claim":
                    "Invalid step-scoped finding.",
                "issue_type":
                    "hidden_assumption",
                "severity":
                    "medium",
                "explanation":
                    "There is no PhysicalPlan.",
                "recommended_fix":
                    "Use null step_order.",
            }
        ],

        "coverage": {
            "explanation": [1],
            "requirement:1:requirement": [],
            "requirement:1:how_to_verify": [],
            "requirement:1:if_not_met": [],
        },
    }

    assert_raises(
        IncompleteSemanticCoverageError,

        lambda: (
            _parse_confirmation_critic_output(
                raw_output=json.dumps(
                    bad_step
                ),

                required_field_ids=list(
                    field_map.keys()
                ),
            )
        ),
    )

    passed += 1

    wrong_status = PlanOutcome(
        status=(
            PlanOutcomeStatus
            .CANNOT_SAFELY_SOLVE
        ),

        explanation=(
            "No safe solution is available."
        ),

        plan=None,

        requirements=[],

        blocking_reasons=[
            "A required capability is absent."
        ],
    )

    assert_raises(
        ValueError,

        lambda: (
            _build_confirmation_field_map(
                wrong_status
            )
        ),
    )

    passed += 1

    prompt = (
        _build_confirmation_critic_prompt(
            outcome=outcome,

            goal=(
                "Create one focal display, but the "
                "preferred target is not specified."
            ),

            inventory_payload=[],

            compact_dna=[],

            external_resources=[],

            field_map=field_map,
        )
    )

    phrases = [
        "WHICH physical plan",
        "CONDITIONAL, not NEEDS_CONFIRMATION",
        "already established",
        "materially affect plan selection",
        "Do not manufacture ambiguity",
        "CANNOT_SAFELY_SOLVE",
    ]

    for phrase in phrases:
        assert phrase in prompt, (
            f"Missing confirmation-boundary rule: "
            f"{phrase}"
        )

    passed += 1

    print(
        "NEEDS_CONFIRMATION CRITIC TESTS: "
        f"{passed}/7 passed"
    )

    print(
        "Model calls: 0"
    )


if __name__ == "__main__":
    main()