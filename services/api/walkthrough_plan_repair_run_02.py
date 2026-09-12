import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from critic_schemas import (
    PlanCriticResult,
)
from plan_repair import (
    repair_plan,
)
from plan_schemas import (
    PhysicalPlan,
)
from plan_validator import (
    PlanValidationError,
    validate_zero_plan,
)
from walkthrough_goal_relevance_run import (
    GOAL,
)
from walkthrough_plan_repair_run import (
    normalize_plan,
    repair_pipeline_fingerprint,
)
from walkthrough_semantic_critic_run import (
    CACHE_PATH as SEMANTIC_CACHE_PATH,
    SemanticCriticCache,
    load_repaired_plan_context,
    semantic_pipeline_fingerprint,
)


CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-plan-repair-attempt-02.json"
)


class PlanRepairAttempt02Cache(BaseModel):
    """
    Cache for the second and FINAL bounded plan-repair attempt.

    ZERO permits at most two plan-repair attempts in the production
    safe-plan pipeline.

    A cached repaired plan is not yet final. It must still pass:
    - deterministic validation
    - final semantic physical audit
    - verification-gate processing if the outcome requires it
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

    source_plan_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    semantic_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    semantic_critic_sha256: str = Field(
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


def load_semantic_failure_context():
    """
    Reconstruct the exact current planning world, validate repair attempt 1,
    and load the matching semantic critic result.

    No model calls occur here.
    """

    (
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        source_plan_sha256,
        validated_source_plan,
    ) = load_repaired_plan_context()

    if not SEMANTIC_CACHE_PATH.exists():
        raise RuntimeError(
            "Semantic-critic cache was not found: "
            f"{SEMANTIC_CACHE_PATH}"
        )

    try:
        payload = json.loads(
            SEMANTIC_CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        semantic_cache = (
            SemanticCriticCache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Semantic-critic cache is invalid."
        ) from exc

    if semantic_cache.goal != GOAL:
        raise RuntimeError(
            "Semantic-critic cache belongs to a different goal."
        )

    if (
        semantic_cache.planning_input_sha256
        != planning_input_sha256
    ):
        raise RuntimeError(
            "Semantic-critic cache belongs to a different planning input."
        )

    if (
        semantic_cache.repaired_plan_sha256
        != source_plan_sha256
    ):
        raise RuntimeError(
            "Semantic-critic cache belongs to a different repaired plan."
        )

    current_semantic_pipeline_sha256 = (
        semantic_pipeline_fingerprint()
    )

    if (
        semantic_cache.semantic_pipeline_sha256
        != current_semantic_pipeline_sha256
    ):
        raise RuntimeError(
            "Semantic-critic cache was produced under a different "
            "semantic pipeline."
        )

    critic = semantic_cache.critic

    if critic.passed:
        raise RuntimeError(
            "Semantic critic already passes. "
            "Repair attempt 2 is not justified."
        )

    if not critic.findings:
        raise RuntimeError(
            "Semantic critic failed but contains no findings. "
            "Refusing to make an unguided repair call."
        )

    return (
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        source_plan_sha256,
        validated_source_plan,
        current_semantic_pipeline_sha256,
        critic,
    )


def load_matching_cache(
    *,
    planning_input_sha256: str,
    source_plan_sha256: str,
    semantic_pipeline_sha256: str,
    semantic_critic_sha256: str,
    repair_pipeline_sha256: str,
) -> PhysicalPlan | None:
    """
    Reuse repair attempt 2 only when every relevant input fingerprint
    matches exactly.
    """

    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cache = PlanRepairAttempt02Cache.model_validate(
            payload
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing repair-attempt-2 cache is invalid. "
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
        cache.source_plan_sha256
        != source_plan_sha256
    ):
        return None

    if (
        cache.semantic_pipeline_sha256
        != semantic_pipeline_sha256
    ):
        return None

    if (
        cache.semantic_critic_sha256
        != semantic_critic_sha256
    ):
        return None

    if (
        cache.repair_pipeline_sha256
        != repair_pipeline_sha256
    ):
        return None

    return cache.repaired_plan


def save_cache(
    *,
    planning_input_sha256: str,
    source_plan_sha256: str,
    semantic_pipeline_sha256: str,
    semantic_critic_sha256: str,
    repair_pipeline_sha256: str,
    repaired_plan: PhysicalPlan,
) -> None:
    """
    Persist the paid repair result immediately.

    Even if later deterministic validation fails, the exact paid result
    remains available and must not be purchased again.
    """

    cache = PlanRepairAttempt02Cache(
        goal=GOAL,
        planning_input_sha256=planning_input_sha256,
        source_plan_sha256=source_plan_sha256,
        semantic_pipeline_sha256=semantic_pipeline_sha256,
        semantic_critic_sha256=semantic_critic_sha256,
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
    active_items,
    external_resources: list[str],
):
    active_item_ids = {
        item.id
        for item in active_items
    }

    normalized_plan = normalize_plan(
        plan=repaired_plan,
        external_resources=external_resources,
    )

    try:
        validated_plan = validate_zero_plan(
            normalized_plan,
            object_dna,
            active_item_ids,
        )

    except PlanValidationError as exc:
        return (
            None,
            exc,
        )

    return (
        validated_plan,
        None,
    )


def print_critic(
    critic: PlanCriticResult,
) -> None:
    print(
        f"Semantic findings requiring final bounded repair: "
        f"{len(critic.findings)}"
    )

    print()

    for index, finding in enumerate(
        critic.findings,
        start=1,
    ):
        print(
            f"{index}. [{finding.severity.value}] "
            f"{finding.issue_type.value}"
        )

        print(
            f"   Step: {finding.step_order}"
        )

        print(
            f"   Claim: {finding.claim}"
        )

        print(
            f"   Explanation: "
            f"{finding.explanation}"
        )

        print(
            f"   Recommended fix: "
            f"{finding.recommended_fix}"
        )

        print()


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate all cached inputs and inspect repair-attempt-2 "
            "status without making a model call."
        ),
    )

    parser.add_argument(
        "--max-new-calls",
        type=int,
        default=0,
        choices=[0, 1],
        help=(
            "Maximum new paid plan-repair calls allowed. "
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
    print("ZERO WALKTHROUGH PLAN REPAIR — ATTEMPT 2 OF 2")
    print("=" * 72)

    (
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        source_plan_sha256,
        source_plan,
        semantic_pipeline_sha256,
        critic,
    ) = load_semantic_failure_context()

    semantic_critic_sha256 = sha256_payload(
        critic.model_dump(
            mode="json"
        )
    )

    current_repair_pipeline_sha256 = (
        repair_pipeline_fingerprint()
    )

    cached_repair = load_matching_cache(
        planning_input_sha256=planning_input_sha256,
        source_plan_sha256=source_plan_sha256,
        semantic_pipeline_sha256=semantic_pipeline_sha256,
        semantic_critic_sha256=semantic_critic_sha256,
        repair_pipeline_sha256=current_repair_pipeline_sha256,
    )

    print()
    print(
        f"Planning input SHA-256: "
        f"{planning_input_sha256}"
    )

    print(
        f"Source repaired-plan SHA-256: "
        f"{source_plan_sha256}"
    )

    print(
        f"Semantic pipeline SHA-256: "
        f"{semantic_pipeline_sha256}"
    )

    print(
        f"Semantic critic SHA-256: "
        f"{semantic_critic_sha256}"
    )

    print(
        f"Repair pipeline SHA-256: "
        f"{current_repair_pipeline_sha256}"
    )

    print()

    print_critic(
        critic
    )

    if cached_repair is None:
        print(
            "Repair-attempt-2 cache: missing/stale"
        )

    else:
        print(
            "Repair-attempt-2 cache: valid"
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

        print(
            "This is repair attempt 2 of 2. "
            "No further plan-repair attempt is permitted after this."
        )

        repaired_plan = repair_plan(
            plan=source_plan,
            critic=critic,
            goal=GOAL,
            inventory=active_items,
            object_dna=object_dna,
            external_resources=external_resources,
        )

        save_cache(
            planning_input_sha256=planning_input_sha256,
            source_plan_sha256=source_plan_sha256,
            semantic_pipeline_sha256=semantic_pipeline_sha256,
            semantic_critic_sha256=semantic_critic_sha256,
            repair_pipeline_sha256=current_repair_pipeline_sha256,
            repaired_plan=repaired_plan,
        )

        print()
        print(
            "Repair-attempt-2 PhysicalPlan schema-valid and cached."
        )

        print(
            "Nemotron plan-repair calls: 1"
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
            "Reusing validated repair-attempt-2 cache."
        )

        print(
            "Nemotron plan-repair calls: 0"
        )

    (
        validated_plan,
        validation_error,
    ) = validate_repaired_plan(
        repaired_plan=repaired_plan,
        object_dna=object_dna,
        active_items=active_items,
        external_resources=external_resources,
    )

    print()
    print("=" * 72)

    if validation_error is not None:
        print(
            "REPAIR ATTEMPT 2 DETERMINISTIC VALIDATION: FAILED"
        )

        print("=" * 72)

        print()
        print(
            str(validation_error)
        )

        print()

        print(
            "The paid repair result remains cached."
        )

        print(
            "The two-attempt plan-repair budget is exhausted."
        )

        print(
            "Do NOT run another plan-repair attempt."
        )

        return

    print(
        "REPAIR ATTEMPT 2 DETERMINISTIC VALIDATION: PASSED"
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
        "Repair budget exhausted: 2 of 2 attempts used."
    )

    print(
        "Final semantic physical audit has NOT been run yet."
    )

    print(
        "Do not accept this plan as final until that audit passes."
    )


if __name__ == "__main__":
    main()