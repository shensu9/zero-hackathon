import argparse

from plan_normalizer import (
    normalize_external_resource_ids,
)
from plan_validator import (
    PlanValidationError,
    normalize_plan_item_ids,
    validate_zero_plan,
)
from walkthrough_external_resource_state import (
    load_external_resource_state,
)
import walkthrough_initial_plan_outcome_run as initial_plan_run


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministically validate a cached initial ZERO plan "
            "for a namespaced walkthrough."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=(
            initial_plan_run.DEFAULT_WALKTHROUGH_ID
        ),
        help=(
            "Artifact namespace such as walkthrough-02. "
            "Defaults to walkthrough-01."
        ),
    )

    parser.add_argument(
        "--goal",
        default=(
            initial_plan_run.DEFAULT_GOAL
        ),
        help=(
            "Goal whose cached initial PlanOutcome should be validated."
        ),
    )

    args = parser.parse_args()

    goal = args.goal.strip()

    if not goal:
        parser.error(
            "--goal may not be empty."
        )

    walkthrough_id = (
        initial_plan_run
        .configure_walkthrough_context(
            args.walkthrough_id
        )
    )

    print("=" * 72)
    print(
        "ZERO INITIAL PLAN DETERMINISTIC VALIDATION"
    )
    print("=" * 72)

    print(
        f"Walkthrough: {walkthrough_id}"
    )

    print(
        f"Goal: {goal}"
    )

    (
        _canonical_inventory,
        session_inventory,
        active_items,
        object_dna,
        _canonical_sha256,
    ) = (
        initial_plan_run
        .load_real_planning_context()
    )

    external_state = (
        load_external_resource_state(
            path=(
                initial_plan_run
                .EXTERNAL_RESOURCE_STATE_PATH
            )
        )
    )

    if (
        external_state
        is None
    ):
        external_resources: list[str] = []

    else:
        if (
            external_state.goal
            != goal
        ):
            raise RuntimeError(
                "External-resource state belongs to a different goal."
            )

        external_resources = list(
            external_state.resources
        )

    session_sha256 = (
        initial_plan_run
        .inventory_fingerprint(
            session_inventory
        )
    )

    dna_sha256 = (
        initial_plan_run
        .object_dna_fingerprint(
            object_dna
        )
    )

    planner_sha256 = (
        initial_plan_run
        .planner_pipeline_fingerprint()
    )

    input_sha256 = (
        initial_plan_run
        .planning_input_fingerprint(
            goal=goal,
            active_inventory=(
                active_items
            ),
            object_dna=(
                object_dna
            ),
            external_resources=(
                external_resources
            ),
        )
    )

    active_item_ids = [
        item.id
        for item
        in active_items
    ]

    outcome = (
        initial_plan_run
        .load_matching_cache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            session_inventory_sha256=(
                session_sha256
            ),
            object_dna_sha256=(
                dna_sha256
            ),
            planner_pipeline_sha256=(
                planner_sha256
            ),
            planning_input_sha256=(
                input_sha256
            ),
            active_item_ids=(
                active_item_ids
            ),
        )
    )

    if outcome is None:
        raise RuntimeError(
            "Matching initial PlanOutcome cache was not found."
        )

    if outcome.plan is None:
        raise RuntimeError(
            "Cached initial outcome contains no PhysicalPlan."
        )

    print()

    print(
        f"Cached outcome status: "
        f"{outcome.status.value}"
    )

    print(
        f"Plan title: "
        f"{outcome.plan.title}"
    )

    print(
        f"Plan steps: "
        f"{len(outcome.plan.steps)}"
    )

    print(
        f"Active inventory IDs: "
        f"{len(active_item_ids)}"
    )

    print(
        f"Object DNA IDs: "
        f"{len(object_dna.objects)}"
    )

    print(
        f"External resources: "
        f"{external_resources}"
    )

    print()

    print(
        f"Session inventory SHA-256: "
        f"{session_sha256}"
    )

    print(
        f"Object DNA SHA-256: "
        f"{dna_sha256}"
    )

    print(
        f"Initial planner pipeline SHA-256: "
        f"{planner_sha256}"
    )

    print(
        f"Planning input SHA-256: "
        f"{input_sha256}"
    )

    normalized_plan = (
        normalize_external_resource_ids(
            outcome.plan,
            external_resources,
        )
    )

    normalized_plan = (
        normalize_plan_item_ids(
            normalized_plan
        )
    )

    try:
        validated_plan = (
            validate_zero_plan(
                normalized_plan,
                object_dna,
                set(
                    active_item_ids
                ),
            )
        )

    except PlanValidationError as exc:
        print()
        print("=" * 72)
        print(
            "DETERMINISTIC VALIDATION: FAILED"
        )
        print("=" * 72)

        print()
        print(
            str(exc)
        )

        print()

        print(
            "No semantic critic or planner-repair model call was made."
        )

        print(
            "Model calls made: 0"
        )

        return

    print()
    print("=" * 72)
    print(
        "DETERMINISTIC VALIDATION: PASSED"
    )
    print("=" * 72)

    print()

    print(
        f"Validated plan steps: "
        f"{len(validated_plan.steps)}"
    )

    print(
        "All inventory IDs and capability citations are grounded in "
        "the current eligible session inventory and Object DNA."
    )

    print()

    print(
        "Model calls made: 0"
    )


if __name__ == "__main__":
    main()
