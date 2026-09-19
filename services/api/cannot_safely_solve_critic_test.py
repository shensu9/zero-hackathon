import json

from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from semantic_critic import (
    IncompleteSemanticCoverageError,
)
from cannot_safely_solve_critic import (
    _build_blocker_field_map,
    _parse_blocker_critic_output,
)


def build_outcome() -> PlanOutcome:
    return PlanOutcome(
        status=(
            PlanOutcomeStatus
            .CANNOT_SAFELY_SOLVE
        ),
        explanation=(
            "The available grounded resources do not "
            "establish a safe mounting method."
        ),
        plan=None,
        requirements=[],
        blocking_reasons=[
            (
                "No grounded attachment/load-bearing "
                "method is available."
            ),
        ],
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
        _build_blocker_field_map(
            outcome
        )
    )

    assert list(
        field_map.keys()
    ) == [
        "explanation",
        "blocking_reason:1",
    ]
    passed += 1

    clean_payload = {
        "findings": [],
        "coverage": {
            "explanation": [],
            "blocking_reason:1": [],
        },
    }

    clean = (
        _parse_blocker_critic_output(
            raw_output=json.dumps(
                clean_payload
            ),
            required_field_ids=[
                "explanation",
                "blocking_reason:1",
            ],
        )
    )

    assert clean.passed
    assert clean.findings == []
    passed += 1

    finding_payload = {
        "findings": [
            {
                "step_order": None,
                "claim": (
                    "Unknown load capacity is treated "
                    "as known absence."
                ),
                "issue_type":
                    "hidden_assumption",
                "severity":
                    "medium",
                "explanation": (
                    "The world model marks load capacity "
                    "unknown rather than absent."
                ),
                "recommended_fix": (
                    "Do not certify impossibility from "
                    "an unresolved property."
                ),
            }
        ],
        "coverage": {
            "explanation": [],
            "blocking_reason:1": [1],
        },
    }

    blocked = (
        _parse_blocker_critic_output(
            raw_output=json.dumps(
                finding_payload
            ),
            required_field_ids=[
                "explanation",
                "blocking_reason:1",
            ],
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
        },
    }

    assert_raises(
        IncompleteSemanticCoverageError,
        lambda: (
            _parse_blocker_critic_output(
                raw_output=json.dumps(
                    missing_coverage
                ),
                required_field_ids=[
                    "explanation",
                    "blocking_reason:1",
                ],
            )
        ),
    )
    passed += 1

    extra_coverage = {
        "findings": [],
        "coverage": {
            "explanation": [],
            "blocking_reason:1": [],
            "unexpected": [],
        },
    }

    assert_raises(
        IncompleteSemanticCoverageError,
        lambda: (
            _parse_blocker_critic_output(
                raw_output=json.dumps(
                    extra_coverage
                ),
                required_field_ids=[
                    "explanation",
                    "blocking_reason:1",
                ],
            )
        ),
    )
    passed += 1

    bad_step = {
        "findings": [
            {
                "step_order": 1,
                "claim":
                    "Invalid step-scoped blocker.",
                "issue_type":
                    "hidden_assumption",
                "severity":
                    "medium",
                "explanation":
                    "No plan exists.",
                "recommended_fix":
                    "Use null step_order.",
            }
        ],
        "coverage": {
            "explanation": [1],
            "blocking_reason:1": [],
        },
    }

    assert_raises(
        IncompleteSemanticCoverageError,
        lambda: (
            _parse_blocker_critic_output(
                raw_output=json.dumps(
                    bad_step
                ),
                required_field_ids=[
                    "explanation",
                    "blocking_reason:1",
                ],
            )
        ),
    )
    passed += 1

    wrong_status = PlanOutcome(
        status=(
            PlanOutcomeStatus
            .NEEDS_CONFIRMATION
        ),
        explanation=(
            "More information is needed."
        ),
        plan=None,
        requirements=[
            {
                "requirement":
                    "Verify the unknown.",
                "how_to_verify":
                    "Inspect it.",
                "if_not_met":
                    "Do not proceed.",
            }
        ],
        blocking_reasons=[],
    )

    assert_raises(
        ValueError,
        lambda: (
            _build_blocker_field_map(
                wrong_status
            )
        ),
    )
    passed += 1

    print(
        "CANNOT_SAFELY_SOLVE CRITIC TESTS: "
        f"{passed}/7 passed"
    )

    print(
        "Model calls: 0"
    )


if __name__ == "__main__":
    main()
