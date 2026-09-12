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
from walkthrough_goal_relevance_run import (
    GOAL,
    inventory_fingerprint,
)
from walkthrough_initial_plan_outcome_run import (
    load_matching_cache,
    load_real_planning_context,
    object_dna_fingerprint,
    planner_pipeline_fingerprint,
    planning_input_fingerprint,
)


def main() -> None:
    print("=" * 72)
    print("ZERO INITIAL PLAN DETERMINISTIC VALIDATION")
    print("=" * 72)

    (
        _canonical_inventory,
        session_inventory,
        active_items,
        object_dna,
        _canonical_sha256,
    ) = load_real_planning_context()

    external_state = (
        load_external_resource_state()
    )

    if external_state is None:
        external_resources: list[str] = []

    else:
        if external_state.goal != GOAL:
            raise RuntimeError(
                "External-resource state belongs to a different goal."
            )

        external_resources = list(
            external_state.resources
        )

    session_sha256 = inventory_fingerprint(
        session_inventory
    )

    dna_sha256 = object_dna_fingerprint(
        object_dna
    )

    planner_sha256 = (
        planner_pipeline_fingerprint()
    )

    input_sha256 = (
        planning_input_fingerprint(
            goal=GOAL,
            active_inventory=active_items,
            object_dna=object_dna,
            external_resources=external_resources,
        )
    )

    active_item_ids = [
        item.id
        for item in active_items
    ]

    outcome = load_matching_cache(
        goal=GOAL,
        session_inventory_sha256=session_sha256,
        object_dna_sha256=dna_sha256,
        planner_pipeline_sha256=planner_sha256,
        planning_input_sha256=input_sha256,
        active_item_ids=active_item_ids,
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
        f"Cached outcome status: {outcome.status.value}"
    )

    print(
        f"Plan title: {outcome.plan.title}"
    )

    print(
        f"Plan steps: {len(outcome.plan.steps)}"
    )

    print(
        f"Active inventory IDs: {len(active_item_ids)}"
    )

    print(
        f"Object DNA IDs: {len(object_dna.objects)}"
    )

    print(
        f"External resources: {external_resources}"
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
        validated_plan = validate_zero_plan(
            normalized_plan,
            object_dna,
            set(active_item_ids),
        )

    except PlanValidationError as exc:
        print()
        print("=" * 72)
        print("DETERMINISTIC VALIDATION: FAILED")
        print("=" * 72)

        print()
        print(str(exc))

        print()
        print(
            "No semantic critic or planner-repair model call was made."
        )

        return

    print()
    print("=" * 72)
    print("DETERMINISTIC VALIDATION: PASSED")
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