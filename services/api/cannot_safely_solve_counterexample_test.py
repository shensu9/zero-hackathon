from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)

from cannot_safely_solve_critic import (
    _build_blocker_critic_prompt,
)


def main() -> None:
    outcome = PlanOutcome(
        status=(
            PlanOutcomeStatus
            .CANNOT_SAFELY_SOLVE
        ),
        explanation=(
            "No grounded complete attachment path exists."
        ),
        plan=None,
        requirements=[],
        blocking_reasons=[
            (
                "No grounded attachment chain secures "
                "the target to the destination."
            )
        ],
    )

    prompt = (
        _build_blocker_critic_prompt(
            outcome=outcome,
            goal=(
                "Hang a mirror safely without drilling "
                "or adhesives."
            ),
            inventory_payload=[
                {
                    "id": "mirror",
                    "name": "mirror",
                    "description":
                        "Full-length mirror.",
                },
                {
                    "id": "hook",
                    "name": "clothes hook",
                    "description":
                        "Hook intended for clothing.",
                },
            ],
            compact_dna=[
                {
                    "item_id": "mirror",
                    "traits": ["rigid"],
                    "affordances": [
                        {
                            "capability":
                                "reflect_light",
                        }
                    ],
                    "unknown_properties": [],
                    "caution_notes": [],
                },
                {
                    "item_id": "hook",
                    "traits": ["rigid"],
                    "affordances": [
                        {
                            "capability": "hang",
                        },
                        {
                            "capability": "support",
                        },
                    ],
                    "unknown_properties": [
                        "load-bearing capacity",
                        "attachment method",
                    ],
                    "caution_notes": [],
                },
            ],
            external_resources=[],
            field_map={
                "explanation":
                    outcome.explanation,
                "blocking_reason:1":
                    outcome.blocking_reasons[0],
            },
        )
    )

    required_phrases = [
        "PARTIAL COUNTEREXAMPLE IS NOT ENOUGH",
        "target-object connection or attachment interface",
        "support-to-destination attachment or compatibility",
        "every OTHER required physical link",
        "COMPLETE candidate",
        "garments or another object",
    ]

    for phrase in required_phrases:
        assert phrase in prompt, (
            f"Missing complete-path critic rule: {phrase}"
        )

    print(
        "CANNOT_SAFELY_SOLVE COMPLETE-PATH "
        "PROMPT TEST: 6/6 passed"
    )
    print("Model calls: 0")


if __name__ == "__main__":
    main()
