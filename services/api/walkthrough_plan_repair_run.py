import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from plan_normalizer import (
    normalize_external_resource_ids,
)
from plan_outcome_pipeline import (
    _validation_failure_to_critic,
)
from plan_repair import (
    repair_plan,
)
from plan_schemas import (
    PhysicalPlan,
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
    load_matching_cache as load_initial_outcome_cache,
    load_real_planning_context,
    object_dna_fingerprint,
    planner_pipeline_fingerprint,
    planning_input_fingerprint,
)


CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-plan-repair-attempt-01.json"
)


REPAIR_PIPELINE_FILES = (
    "plan_repair.py",
    "plan_validator.py",
    "plan_normalizer.py",
    "critic_schemas.py",
    "plan_schemas.py",
    "schemas.py",
    "model_json.py",
)


class PlanRepairCache(BaseModel):
    """
    Cache for exactly ONE paid plan-repair attempt.

    This repaired plan is NOT yet a final safe ZERO plan.

    It must still pass:
    - deterministic validation
    - semantic audit
    - any later bounded repair if required
    - verification-gate processing when CONDITIONAL
    - final semantic audit
    """

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    planning_input_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    initial_plan_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    critic_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    repair_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    repaired_plan: PhysicalPlan


def canonical_json(
    payload,
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_payload(
    payload,
) -> str:
    return hashlib.sha256(
        canonical_json(
            payload
        ).encode("utf-8")
    ).hexdigest()


def repair_pipeline_fingerprint() -> str:
    """
    Bind this cache to the exact repair + deterministic validation code.
    """

    digest = hashlib.sha256()

    base_dir = Path(__file__).resolve().parent

    for filename in REPAIR_PIPELINE_FILES:
        path = base_dir / filename

        if not path.exists():
            raise RuntimeError(
                "Required repair pipeline file was not found: "
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


def normalize_plan(
    *,
    plan: PhysicalPlan,
    external_resources: list[str],
) -> PhysicalPlan:
    normalized = normalize_external_resource_ids(
        plan,
        external_resources,
    )

    normalized = normalize_plan_item_ids(
        normalized
    )

    return normalized


def load_context():
    """
    Load the same real planning context and matching cached initial outcome.

    No model calls occur here.
    """

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

    outcome = load_initial_outcome_cache(
        goal=GOAL,
        session_inventory_sha256=session_sha256,
        object_dna_sha256=dna_sha256,
        planner_pipeline_sha256=planner_sha256,
        planning_input_sha256=input_sha256,
        active_item_ids=active_item_ids,
    )

    if outcome is None:
        raise RuntimeError(
            "Matching cached initial PlanOutcome was not found."
        )

    if outcome.plan is None:
        raise RuntimeError(
            "Cached initial PlanOutcome contains no PhysicalPlan."
        )

    return (
        active_items,
        object_dna,
        external_resources,
        active_item_ids,
        input_sha256,
        outcome,
    )


def reproduce_validation_failure(
    *,
    plan: PhysicalPlan,
    active_items,
    object_dna,
    active_item_ids: list[str],
    external_resources: list[str],
):
    """
    Reproduce the exact deterministic validation boundary used by production.

    Returns:
        normalized invalid plan
        production-style critic derived from PlanValidationError

    If the initial plan unexpectedly validates, repair should not run.
    """

    normalized_plan = normalize_plan(
        plan=plan,
        external_resources=external_resources,
    )

    try:
        validate_zero_plan(
            normalized_plan,
            object_dna,
            set(active_item_ids),
        )

    except PlanValidationError as exc:
        critic = _validation_failure_to_critic(
            exc
        )

        return (
            normalized_plan,
            critic,
            exc,
        )

    raise RuntimeError(
        "Initial plan now passes deterministic validation; "
        "a repair call is no longer justified."
    )


def load_matching_repair_cache(
    *,
    planning_input_sha256: str,
    initial_plan_sha256: str,
    critic_sha256: str,
    repair_pipeline_sha256: str,
) -> PhysicalPlan | None:
    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cache = PlanRepairCache.model_validate(
            payload
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing plan-repair cache is invalid. "
            "Refusing to overwrite it with another paid call until "
            f"inspected: {CACHE_PATH}"
        ) from exc

    if cache.goal != GOAL:
        return None

    if (
        cache.planning_input_sha256
        != planning_input_sha256
    ):
        return None

    if (
        cache.initial_plan_sha256
        != initial_plan_sha256
    ):
        return None

    if (
        cache.critic_sha256
        != critic_sha256
    ):
        return None

    if (
        cache.repair_pipeline_sha256
        != repair_pipeline_sha256
    ):
        return None

    return cache.repaired_plan


def save_repair_cache(
    *,
    planning_input_sha256: str,
    initial_plan_sha256: str,
    critic_sha256: str,
    repair_pipeline_sha256: str,
    repaired_plan: PhysicalPlan,
) -> None:
    """
    Save the paid repaired plan immediately, before later validation stages.

    This preserves the model result even if deterministic validation fails.
    """

    cache = PlanRepairCache(
        goal=GOAL,
        planning_input_sha256=planning_input_sha256,
        initial_plan_sha256=initial_plan_sha256,
        critic_sha256=critic_sha256,
        repair_pipeline_sha256=repair_pipeline_sha256,
        repaired_plan=repaired_plan,
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


def validate_repaired_plan(
    *,
    repaired_plan: PhysicalPlan,
    object_dna,
    active_item_ids: list[str],
    external_resources: list[str],
):
    """
    Run the repaired plan through the free deterministic validator.

    Returns:
        normalized validated plan on success
        None + error on deterministic failure
    """

    normalized = normalize_plan(
        plan=repaired_plan,
        external_resources=external_resources,
    )

    try:
        validated = validate_zero_plan(
            normalized,
            object_dna,
            set(active_item_ids),
        )

    except PlanValidationError as exc:
        return (
            None,
            exc,
        )

    return (
        validated,
        None,
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Reproduce the deterministic failure and inspect repair-cache "
            "status without making a model call."
        ),
    )

    parser.add_argument(
        "--max-new-calls",
        type=int,
        default=0,
        choices=[0, 1],
        help=(
            "Maximum new paid repair calls allowed. "
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
    print("ZERO WALKTHROUGH PLAN REPAIR — ATTEMPT 1")
    print("=" * 72)

    (
        active_items,
        object_dna,
        external_resources,
        active_item_ids,
        planning_input_sha256,
        outcome,
    ) = load_context()

    (
        normalized_initial_plan,
        critic,
        validation_error,
    ) = reproduce_validation_failure(
        plan=outcome.plan,
        active_items=active_items,
        object_dna=object_dna,
        active_item_ids=active_item_ids,
        external_resources=external_resources,
    )

    initial_plan_sha256 = sha256_payload(
        normalized_initial_plan.model_dump(
            mode="json"
        )
    )

    critic_sha256 = sha256_payload(
        critic.model_dump(
            mode="json"
        )
    )

    repair_sha256 = (
        repair_pipeline_fingerprint()
    )

    cached_repair = load_matching_repair_cache(
        planning_input_sha256=planning_input_sha256,
        initial_plan_sha256=initial_plan_sha256,
        critic_sha256=critic_sha256,
        repair_pipeline_sha256=repair_sha256,
    )

    print()
    print(
        f"Planning input SHA-256: "
        f"{planning_input_sha256}"
    )

    print(
        f"Initial normalized plan SHA-256: "
        f"{initial_plan_sha256}"
    )

    print(
        f"Validation critic SHA-256: "
        f"{critic_sha256}"
    )

    print(
        f"Repair pipeline SHA-256: "
        f"{repair_sha256}"
    )

    print()

    print(
        "Deterministic failure reproduced:"
    )

    print(
        str(validation_error)
    )

    print()

    print(
        "Production-style repair critic:"
    )

    print(
        critic.model_dump_json(
            indent=2
        )
    )

    print()

    if cached_repair is None:
        print(
            "Plan-repair cache: missing/stale"
        )

    else:
        print(
            "Plan-repair cache: valid"
        )

    if args.dry_run:
        print()
        print(
            "DRY RUN COMPLETE — NO MODEL CALL MADE"
        )

        return

    repaired_plan = cached_repair

    if repaired_plan is None:
        if args.max_new_calls == 0:
            print()
            print(
                "No paid repair call authorized "
                "(--max-new-calls is 0)."
            )

            return

        print()
        print(
            "Running ONE paid plan-repair call..."
        )

        repaired_plan = repair_plan(
            plan=normalized_initial_plan,
            critic=critic,
            goal=GOAL,
            inventory=active_items,
            object_dna=object_dna,
            external_resources=external_resources,
        )

        save_repair_cache(
            planning_input_sha256=planning_input_sha256,
            initial_plan_sha256=initial_plan_sha256,
            critic_sha256=critic_sha256,
            repair_pipeline_sha256=repair_sha256,
            repaired_plan=repaired_plan,
        )

        print()
        print(
            "Repaired PhysicalPlan schema-valid and cached."
        )

        print(
            "Nemotron calls: 1"
        )

        print(
            "Saved private repair cache:"
        )

        print(
            CACHE_PATH.resolve()
        )

    else:
        print()
        print(
            "Reusing validated repair cache."
        )

        print(
            "Nemotron calls: 0"
        )

    (
        validated_plan,
        repaired_error,
    ) = validate_repaired_plan(
        repaired_plan=repaired_plan,
        object_dna=object_dna,
        active_item_ids=active_item_ids,
        external_resources=external_resources,
    )

    print()
    print("=" * 72)

    if repaired_error is not None:
        print(
            "REPAIRED PLAN DETERMINISTIC VALIDATION: FAILED"
        )

        print("=" * 72)

        print()
        print(
            str(repaired_error)
        )

        print()

        print(
            "The paid repair result remains cached."
        )

        print(
            "Do not rerun attempt 1 blindly."
        )

        return

    print(
        "REPAIRED PLAN DETERMINISTIC VALIDATION: PASSED"
    )

    print("=" * 72)

    print()

    print(
        f"Plan title: "
        f"{validated_plan.title}"
    )

    print(
        f"Plan steps: "
        f"{len(validated_plan.steps)}"
    )

    print()

    print(
        validated_plan.model_dump_json(
            indent=2
        )
    )

    print()

    print(
        "Semantic critic has NOT been run yet."
    )


if __name__ == "__main__":
    main()