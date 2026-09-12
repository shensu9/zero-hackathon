import argparse
import hashlib
import json
from pathlib import Path

from walkthrough_external_resource_state import (
    load_external_resource_state,
)

from pydantic import BaseModel, Field

from plan_outcome_schemas import (
    PlanOutcome,
)
from walkthrough_goal_relevance_run import (
    GOAL,
    inventory_fingerprint,
)
from walkthrough_object_dna_run import (
    get_eligible_items,
    load_session_inventory,
)
from walkthrough_real_object_dna_handoff_run import (
    load_validated_real_object_dna,
)


CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-initial-plan-outcome.json"
)


INITIAL_PLANNER_PIPELINE_FILES = (
    "plan_outcome_service.py",
    "plan_outcome_schemas.py",
    "plan_schemas.py",
    "plan_normalizer.py",
    "model_json.py",
    "schemas.py",
)


class InitialPlanOutcomeCache(BaseModel):
    """
    Cache for the FIRST paid planning stage only.

    This is NOT a safe/final ZERO outcome.

    The cached PlanOutcome still needs to pass:
    - deterministic plan validation
    - semantic critic
    - bounded repair if required
    - verification-gate audit when CONDITIONAL
    - final semantic recheck
    """

    goal: str = Field(
        min_length=1,
        max_length=2000,
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


def sha256_text(
    text: str,
) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def canonical_json(
    payload,
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def planner_pipeline_fingerprint() -> str:
    """
    Bind the initial-outcome cache to the exact code responsible for:
    - prompt construction
    - model selection
    - output normalization
    - PlanOutcome / PhysicalPlan schema parsing

    Later semantic-critic or gate code is intentionally NOT included here
    because this cache covers only the initial generation stage.
    """

    digest = hashlib.sha256()

    base_dir = Path(__file__).resolve().parent

    for filename in INITIAL_PLANNER_PIPELINE_FILES:
        path = base_dir / filename

        if not path.exists():
            raise RuntimeError(
                "Required initial planner file was not found: "
                f"{path}"
            )

        digest.update(
            filename.encode("utf-8")
        )

        digest.update(
            b"\0"
        )

        digest.update(
            path.read_bytes()
        )

        digest.update(
            b"\0"
        )

    return digest.hexdigest()


def object_dna_fingerprint(
    object_dna,
) -> str:
    payload = canonical_json(
        object_dna.model_dump(
            mode="json"
        )
    )

    return sha256_text(
        payload
    )


def planning_input_fingerprint(
    *,
    goal: str,
    active_inventory,
    object_dna,
    external_resources,
) -> str:
    payload = {
        "goal": goal,
        "inventory": [
            item.model_dump(
                mode="json"
            )
            for item in active_inventory
        ],
        "object_dna": (
            object_dna.model_dump(
                mode="json"
            )
        ),
        "external_resources": list(
            external_resources
        ),
    }

    return sha256_text(
        canonical_json(
            payload
        )
    )


def load_real_planning_context():
    """
    Load the validated real 33-item session world model.

    No model calls occur here.
    """

    (
        canonical_inventory,
        session_inventory,
        canonical_sha256,
    ) = load_session_inventory()

    active_items = get_eligible_items(
        session_inventory
    )

    snapshot = load_validated_real_object_dna(
        session_inventory=session_inventory,
        eligible_items=active_items,
    )

    if len(active_items) != 33:
        raise RuntimeError(
            "Expected exactly 33 active session items, received "
            f"{len(active_items)}."
        )

    if (
        len(snapshot.object_dna.objects)
        != 33
    ):
        raise RuntimeError(
            "Expected exactly 33 real Object DNA objects, received "
            f"{len(snapshot.object_dna.objects)}."
        )

    active_ids = [
        item.id
        for item in active_items
    ]

    dna_ids = [
        dna.item_id
        for dna in snapshot.object_dna.objects
    ]

    if active_ids != dna_ids:
        raise RuntimeError(
            "Real Object DNA IDs do not exactly match active session "
            "inventory IDs."
        )

    return (
        canonical_inventory,
        session_inventory,
        active_items,
        snapshot.object_dna,
        canonical_sha256,
    )


def load_matching_cache(
    *,
    goal: str,
    session_inventory_sha256: str,
    object_dna_sha256: str,
    planner_pipeline_sha256: str,
    planning_input_sha256: str,
    active_item_ids: list[str],
) -> PlanOutcome | None:
    """
    Reuse the first-stage model result only when every relevant input and
    generator fingerprint matches exactly.

    Malformed cache files fail loudly instead of triggering a silent paid
    replacement.
    """

    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cache = (
            InitialPlanOutcomeCache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing initial planning cache is invalid. "
            "Refusing to overwrite it with another paid call until "
            f"inspected: {CACHE_PATH}"
        ) from exc

    if cache.goal != goal:
        return None

    if (
        cache.session_inventory_sha256
        != session_inventory_sha256
    ):
        return None

    if (
        cache.object_dna_sha256
        != object_dna_sha256
    ):
        return None

    if (
        cache.planner_pipeline_sha256
        != planner_pipeline_sha256
    ):
        return None

    if (
        cache.planning_input_sha256
        != planning_input_sha256
    ):
        return None

    if (
        cache.active_item_ids
        != active_item_ids
    ):
        return None

    return cache.outcome


def save_cache(
    *,
    goal: str,
    session_inventory_sha256: str,
    object_dna_sha256: str,
    planner_pipeline_sha256: str,
    planning_input_sha256: str,
    active_item_ids: list[str],
    outcome: PlanOutcome,
) -> None:
    """
    Save one successful initial PlanOutcome atomically.
    """

    cache = InitialPlanOutcomeCache(
        goal=goal,
        session_inventory_sha256=(
            session_inventory_sha256
        ),
        object_dna_sha256=(
            object_dna_sha256
        ),
        planner_pipeline_sha256=(
            planner_pipeline_sha256
        ),
        planning_input_sha256=(
            planning_input_sha256
        ),
        active_item_ids=active_item_ids,
        outcome=outcome,
    )

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = CACHE_PATH.with_name(
        CACHE_PATH.name + ".tmp"
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


def print_outcome_summary(
    outcome: PlanOutcome,
) -> None:
    """
    Print the initial model decision without implying that it is safe/final.
    """

    print()
    print("=" * 72)
    print("INITIAL PLAN OUTCOME — NOT YET SAFETY APPROVED")
    print("=" * 72)

    print(
        f"Status: {outcome.status.value}"
    )

    print(
        f"Requirements: "
        f"{len(outcome.requirements)}"
    )

    print(
        f"Blocking reasons: "
        f"{len(outcome.blocking_reasons)}"
    )

    print(
        f"Physical plan present: "
        f"{outcome.plan is not None}"
    )

    if outcome.plan is not None:
        print(
            f"Plan title: "
            f"{outcome.plan.title}"
        )

        print(
            f"Plan steps: "
            f"{len(outcome.plan.steps)}"
        )

    if outcome.requirements:
        print()
        print("Requirements:")

        for index, requirement in enumerate(
            outcome.requirements,
            start=1,
        ):
            print(
                f"{index}. "
                f"{requirement.requirement}"
            )

            print(
                f"   if not met: "
                f"{requirement.if_not_met}"
            )

    if outcome.blocking_reasons:
        print()
        print("Blocking reasons:")

        for reason in outcome.blocking_reasons:
            print(
                f"- {reason}"
            )

    if outcome.plan is not None:
        print()
        print("Initial physical plan:")

        print(
            outcome.plan.model_dump_json(
                indent=2
            )
        )

    print()
    print(
        "IMPORTANT: This result has NOT yet passed deterministic "
        "plan validation, semantic audit, repair, or verification-gate "
        "processing."
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the real planning context and cache state "
            "without making a model call."
        ),
    )

    parser.add_argument(
        "--max-new-calls",
        type=int,
        default=0,
        choices=[0, 1],
        help=(
            "Maximum new paid initial-planner calls allowed. "
            "Only 0 or 1 is valid. Default 0."
        ),
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and args.max_new_calls != 0
    ):
        parser.error(
            "--dry-run cannot authorize a paid call."
        )

    print("=" * 72)
    print("ZERO WALKTHROUGH INITIAL PLAN OUTCOME")
    print("=" * 72)

    (
        canonical_inventory,
        session_inventory,
        active_items,
        object_dna,
        canonical_sha256,
    ) = load_real_planning_context()

    session_sha256 = inventory_fingerprint(
        session_inventory
    )

    dna_sha256 = object_dna_fingerprint(
        object_dna
    )

    planner_sha256 = (
        planner_pipeline_fingerprint()
    )

    external_resource_state = (
    load_external_resource_state()
)

    if external_resource_state is None:
        external_resources: list[str] = []

    else:
        if external_resource_state.goal != GOAL:
            raise RuntimeError(
                "Persisted external-resource state belongs to a "
                "different goal."
            )

        external_resources = list(
            external_resource_state.resources
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

    cached_outcome = load_matching_cache(
        goal=GOAL,
        session_inventory_sha256=session_sha256,
        object_dna_sha256=dna_sha256,
        planner_pipeline_sha256=planner_sha256,
        planning_input_sha256=input_sha256,
        active_item_ids=active_item_ids,
    )

    print()
    print(
        f"Goal: {GOAL}"
    )

    print()

    print(
        f"Canonical inventory SHA-256: "
        f"{canonical_sha256}"
    )

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

    print()

    print(
        f"Canonical items: "
        f"{len(canonical_inventory.items)}"
    )

    print(
        f"Session items: "
        f"{len(session_inventory.items)}"
    )

    print(
        f"Active planning items: "
        f"{len(active_items)}"
    )

    print(
        f"Real Object DNA items: "
        f"{len(object_dna.objects)}"
    )

    print(
        f"External resources: "
        f"{len(external_resources)}"
    )

    print()

    if cached_outcome is None:
        print(
            "Initial PlanOutcome cache: missing/stale"
        )

    else:
        print(
            "Initial PlanOutcome cache: valid"
        )

    if args.dry_run:
        print()
        print(
            "DRY RUN COMPLETE — NO MODEL CALL MADE"
        )

        if cached_outcome is not None:
            print_outcome_summary(
                cached_outcome
            )

        return

    if cached_outcome is not None:
        print()
        print(
            "Reusing validated initial PlanOutcome cache."
        )

        print(
            "Nemotron calls: 0"
        )

        print_outcome_summary(
            cached_outcome
        )

        return

    if args.max_new_calls == 0:
        print()
        print(
            "No paid initial-planner call authorized "
            "(--max-new-calls is 0)."
        )

        return

    print()
    print(
        "Running ONE paid initial PlanOutcome call..."
    )

    # Import lazily so dry runs and cache-only runs do not even
    # instantiate the planner's Nebius client in this runner.
    from plan_outcome_service import (
        generate_plan_outcome,
    )

    outcome = generate_plan_outcome(
        goal=GOAL,
        inventory=active_items,
        object_dna=object_dna,
        external_resources=external_resources,
    )

    save_cache(
        goal=GOAL,
        session_inventory_sha256=session_sha256,
        object_dna_sha256=dna_sha256,
        planner_pipeline_sha256=planner_sha256,
        planning_input_sha256=input_sha256,
        active_item_ids=active_item_ids,
        outcome=outcome,
    )

    print()
    print(
        "Initial PlanOutcome validated by schema and cached."
    )

    print(
        "Nemotron calls: 1"
    )

    print(
        "Saved private initial planning cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_outcome_summary(
        outcome
    )


if __name__ == "__main__":
    main()