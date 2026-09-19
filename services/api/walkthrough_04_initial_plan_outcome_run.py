import argparse
import json
from pathlib import Path

from pydantic import BaseModel, Field

from plan_outcome_schemas import (
    PlanOutcome,
)
from walkthrough_goal_relevance_run import (
    inventory_fingerprint,
)
import walkthrough_initial_plan_outcome_run as initial_run


WALKTHROUGH_ID = "walkthrough-04"
SOURCE_WORLD_ID = "walkthrough-03"

GOAL = (
    "Create one focal display in this room using either the guitar "
    "or the canvas artwork, using only what I already have and "
    "without damaging the wall. I only want one focal item, but "
    "I have not decided which one I want to feature."
)


EXPECTED_SOURCE_CANONICAL_SHA256 = (
    "6c3a4d47bfc46e59f666ef44fe1bc8ba"
    "989be527242160299d625e54bfc727df"
)

EXPECTED_SOURCE_SESSION_SHA256 = (
    "a27c535683216f4871d4855ee69803b85"
    "ca55d2f1de25f2637f2e98ec47752e5"
)

EXPECTED_SOURCE_OBJECT_DNA_SHA256 = (
    "24ee7c57b96f05518f47b0821932a4f4"
    "b77eccf2fe82ca257193828dc82bd6a2"
)

EXPECTED_ACTIVE_COUNT = 27

REQUIRED_CANDIDATE_IDS = {
    "canvas_artwork_f05_o01",
    "acoustic_guitar_f06_o05",
}


CACHE_PATH = (
    initial_run
    .object_dna_run
    .PRIVATE_DIR
    / (
        f"{WALKTHROUGH_ID}"
        "-initial-plan-outcome.json"
    )
)


class W4InitialPlanOutcomeCache(
    BaseModel
):
    source_world_walkthrough_id: str = Field(
        min_length=1,
        max_length=128,
    )

    walkthrough_id: str = Field(
        min_length=1,
        max_length=128,
    )

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    canonical_inventory_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    session_inventory_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    object_dna_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    planner_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    planning_input_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    active_item_ids: list[str]

    outcome: PlanOutcome


def load_context():
    """
    Load the exact frozen Walkthrough 03 world model and
    construct a new Walkthrough 04 planning input.

    No model calls occur here.
    """

    initial_run.configure_walkthrough_context(
        SOURCE_WORLD_ID
    )

    (
        canonical_inventory,
        session_inventory,
        active_items,
        object_dna,
        canonical_sha256,
    ) = (
        initial_run
        .load_real_planning_context()
    )

    session_sha256 = (
        inventory_fingerprint(
            session_inventory
        )
    )

    dna_sha256 = (
        initial_run
        .object_dna_fingerprint(
            object_dna
        )
    )

    if (
        canonical_sha256
        != EXPECTED_SOURCE_CANONICAL_SHA256
    ):
        raise RuntimeError(
            "Frozen W3 canonical inventory changed. "
            f"Expected {EXPECTED_SOURCE_CANONICAL_SHA256}, "
            f"got {canonical_sha256}."
        )

    if (
        session_sha256
        != EXPECTED_SOURCE_SESSION_SHA256
    ):
        raise RuntimeError(
            "Frozen W3 session inventory changed. "
            f"Expected {EXPECTED_SOURCE_SESSION_SHA256}, "
            f"got {session_sha256}."
        )

    if (
        dna_sha256
        != EXPECTED_SOURCE_OBJECT_DNA_SHA256
    ):
        raise RuntimeError(
            "Frozen W3 Object DNA changed. "
            f"Expected {EXPECTED_SOURCE_OBJECT_DNA_SHA256}, "
            f"got {dna_sha256}."
        )

    if (
        len(active_items)
        != EXPECTED_ACTIVE_COUNT
    ):
        raise RuntimeError(
            "Frozen W3 active-item count changed. "
            f"Expected {EXPECTED_ACTIVE_COUNT}, "
            f"got {len(active_items)}."
        )

    active_item_ids = [
        item.id
        for item
        in active_items
    ]

    missing_candidates = (
        REQUIRED_CANDIDATE_IDS
        - set(
            active_item_ids
        )
    )

    if missing_candidates:
        raise RuntimeError(
            "W4 candidate objects are missing from "
            "the frozen W3 planning world: "
            f"{sorted(missing_candidates)}"
        )

    external_resources: list[str] = []

    planner_sha256 = (
        initial_run
        .planner_pipeline_fingerprint()
    )

    planning_input_sha256 = (
        initial_run
        .planning_input_fingerprint(
            goal=GOAL,
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

    return {
        "canonical_inventory":
            canonical_inventory,

        "session_inventory":
            session_inventory,

        "active_items":
            active_items,

        "object_dna":
            object_dna,

        "external_resources":
            external_resources,

        "active_item_ids":
            active_item_ids,

        "canonical_sha256":
            canonical_sha256,

        "session_sha256":
            session_sha256,

        "dna_sha256":
            dna_sha256,

        "planner_sha256":
            planner_sha256,

        "planning_input_sha256":
            planning_input_sha256,
    }


def load_matching_cache(
    *,
    context,
) -> PlanOutcome | None:
    """
    Reuse only an exact W4 planning cache.

    Existing malformed or stale evidence is never silently
    overwritten.
    """

    if not CACHE_PATH.exists():
        return None

    try:
        cache = (
            W4InitialPlanOutcomeCache
            .model_validate_json(
                CACHE_PATH.read_text(
                    encoding="utf-8"
                )
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing W4 initial planning cache is "
            "malformed. Refusing to overwrite it: "
            f"{CACHE_PATH}"
        ) from exc

    expected = {
        "source_world_walkthrough_id":
            SOURCE_WORLD_ID,

        "walkthrough_id":
            WALKTHROUGH_ID,

        "goal":
            GOAL,

        "canonical_inventory_sha256":
            context[
                "canonical_sha256"
            ],

        "session_inventory_sha256":
            context[
                "session_sha256"
            ],

        "object_dna_sha256":
            context[
                "dna_sha256"
            ],

        "planner_pipeline_sha256":
            context[
                "planner_sha256"
            ],

        "planning_input_sha256":
            context[
                "planning_input_sha256"
            ],

        "active_item_ids":
            context[
                "active_item_ids"
            ],
    }

    actual = {
        "source_world_walkthrough_id":
            cache.source_world_walkthrough_id,

        "walkthrough_id":
            cache.walkthrough_id,

        "goal":
            cache.goal,

        "canonical_inventory_sha256":
            cache.canonical_inventory_sha256,

        "session_inventory_sha256":
            cache.session_inventory_sha256,

        "object_dna_sha256":
            cache.object_dna_sha256,

        "planner_pipeline_sha256":
            cache.planner_pipeline_sha256,

        "planning_input_sha256":
            cache.planning_input_sha256,

        "active_item_ids":
            cache.active_item_ids,
    }

    if actual != expected:
        raise RuntimeError(
            "Existing W4 initial planning cache "
            "does not match the current frozen world "
            "or planner fingerprint. Refusing to "
            "overwrite stale evidence."
        )

    return cache.outcome


def save_cache(
    *,
    context,
    outcome: PlanOutcome,
) -> None:
    cache = (
        W4InitialPlanOutcomeCache(
            source_world_walkthrough_id=(
                SOURCE_WORLD_ID
            ),

            walkthrough_id=(
                WALKTHROUGH_ID
            ),

            goal=GOAL,

            canonical_inventory_sha256=(
                context[
                    "canonical_sha256"
                ]
            ),

            session_inventory_sha256=(
                context[
                    "session_sha256"
                ]
            ),

            object_dna_sha256=(
                context[
                    "dna_sha256"
                ]
            ),

            planner_pipeline_sha256=(
                context[
                    "planner_sha256"
                ]
            ),

            planning_input_sha256=(
                context[
                    "planning_input_sha256"
                ]
            ),

            active_item_ids=(
                context[
                    "active_item_ids"
                ]
            ),

            outcome=outcome,
        )
    )

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        CACHE_PATH.with_name(
            CACHE_PATH.name
            + ".tmp"
        )
    )

    temporary_path.write_text(
        cache.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        CACHE_PATH
    )


def print_outcome(
    outcome: PlanOutcome,
) -> None:
    print()
    print("=" * 72)
    print(
        "WALKTHROUGH 04 INITIAL PLAN OUTCOME"
    )
    print(
        "NOT YET SAFETY APPROVED"
    )
    print("=" * 72)

    print()
    print(
        f"Status: "
        f"{outcome.status.value}"
    )

    print()
    print(
        f"Explanation: "
        f"{outcome.explanation}"
    )

    print()
    print(
        "PhysicalPlan: "
        f"{'present' if outcome.plan else 'none'}"
    )

    print(
        "Requirements: "
        f"{len(outcome.requirements)}"
    )

    for index, requirement in enumerate(
        outcome.requirements,
        start=1,
    ):
        print()
        print(
            f"Requirement {index}:"
        )

        print(
            f"  requirement: "
            f"{requirement.requirement}"
        )

        print(
            f"  how_to_verify: "
            f"{requirement.how_to_verify}"
        )

        print(
            f"  if_not_met: "
            f"{requirement.if_not_met}"
        )

    print()
    print(
        "Blocking reasons: "
        f"{len(outcome.blocking_reasons)}"
    )

    for index, reason in enumerate(
        outcome.blocking_reasons,
        start=1,
    ):
        print(
            f"  {index}. {reason}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or inspect Walkthrough 04's "
            "first PlanOutcome using the exact frozen "
            "Walkthrough 03 world model."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the frozen source world and W4 "
            "cache state without making a model call."
        ),
    )

    parser.add_argument(
        "--max-new-calls",
        type=int,
        default=0,
        choices=[
            0,
            1,
        ],
        help=(
            "Maximum newly authorized initial planner "
            "calls. Default 0."
        ),
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and
        args.max_new_calls
        != 0
    ):
        parser.error(
            "--dry-run cannot authorize a paid call."
        )

    context = load_context()

    cached_outcome = (
        load_matching_cache(
            context=context
        )
    )

    print("=" * 72)
    print(
        "ZERO WALKTHROUGH 04 INITIAL PLANNER"
    )
    print("=" * 72)

    print()
    print(
        f"Walkthrough: {WALKTHROUGH_ID}"
    )

    print(
        "Source frozen world: "
        f"{SOURCE_WORLD_ID}"
    )

    print()
    print(
        f"Goal: {GOAL}"
    )

    print()
    print(
        "Canonical inventory items: "
        f"{len(context['canonical_inventory'].items)}"
    )

    print(
        "Session inventory items: "
        f"{len(context['session_inventory'].items)}"
    )

    print(
        "Active eligible items: "
        f"{len(context['active_items'])}"
    )

    print(
        "Object DNA items: "
        f"{len(context['object_dna'].objects)}"
    )

    print(
        "External resources: "
        f"{len(context['external_resources'])}"
    )

    print()
    print(
        "Canvas candidate present: "
        f"{'canvas_artwork_f05_o01' in context['active_item_ids']}"
    )

    print(
        "Guitar candidate present: "
        f"{'acoustic_guitar_f06_o05' in context['active_item_ids']}"
    )

    print()
    print(
        "Source canonical SHA256: "
        f"{context['canonical_sha256']}"
    )

    print(
        "Source session SHA256: "
        f"{context['session_sha256']}"
    )

    print(
        "Source Object DNA SHA256: "
        f"{context['dna_sha256']}"
    )

    print(
        "Planner pipeline SHA256: "
        f"{context['planner_sha256']}"
    )

    print(
        "W4 planning input SHA256: "
        f"{context['planning_input_sha256']}"
    )

    print()
    print(
        "W4 initial planning cache: "
        f"{CACHE_PATH.resolve()}"
    )

    if cached_outcome is None:
        print(
            "W4 initial PlanOutcome cache: "
            "missing"
        )
    else:
        print(
            "W4 initial PlanOutcome cache: "
            "valid"
        )

    if args.dry_run:
        print()
        print(
            "DRY RUN COMPLETE - "
            "NO MODEL CALL MADE"
        )

        print(
            "Model calls: 0"
        )

        print(
            "Expected new initial planner calls "
            "if authorized: "
            f"{0 if cached_outcome else 1}"
        )

        if (
            cached_outcome
            is not None
        ):
            print_outcome(
                cached_outcome
            )

        return

    if (
        cached_outcome
        is not None
    ):
        print()
        print(
            "Reusing validated W4 initial "
            "PlanOutcome cache."
        )

        print(
            "Nemotron calls: 0"
        )

        print_outcome(
            cached_outcome
        )

        return

    if (
        args.max_new_calls
        < 1
    ):
        raise RuntimeError(
            "W4 initial planning cache is missing. "
            "No new planner call is authorized. "
            "Run with --max-new-calls 1 only after "
            "reviewing the dry-run output."
        )

    print()
    print(
        "Running ONE paid W4 initial "
        "PlanOutcome call..."
    )

    # Lazy import so dry-run/cache-only execution
    # cannot trigger planner execution.
    from plan_outcome_service import (
        generate_plan_outcome,
    )

    outcome = (
        generate_plan_outcome(
            goal=GOAL,

            inventory=(
                context[
                    "active_items"
                ]
            ),

            object_dna=(
                context[
                    "object_dna"
                ]
            ),

            external_resources=(
                context[
                    "external_resources"
                ]
            ),
        )
    )

    save_cache(
        context=context,
        outcome=outcome,
    )

    print()
    print(
        "Nemotron calls: 1"
    )

    print(
        "Saved private W4 initial planning cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_outcome(
        outcome
    )


if __name__ == "__main__":
    main()