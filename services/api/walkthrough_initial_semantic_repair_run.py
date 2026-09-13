import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from plan_normalizer import (
    normalize_external_resource_ids,
)
from plan_schemas import (
    PhysicalPlan,
)
from plan_validator import (
    PlanValidationError,
    normalize_plan_item_ids,
    validate_zero_plan,
)
import walkthrough_initial_semantic_critic_run as semantic_run


DEFAULT_WALKTHROUGH_ID = (
    semantic_run.DEFAULT_WALKTHROUGH_ID
)


CACHE_PATH = (
    semantic_run
    .initial_plan_run
    .object_dna_run
    .PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-initial-semantic-repair-attempt-01.json"
    )
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


class InitialSemanticRepairCache(
    BaseModel
):
    """
    Cache for repair attempt 1 of a deterministically-valid
    initial plan that failed the semantic physical audit.

    The paid repaired plan is persisted before later validation
    so it never needs to be purchased again merely because a
    downstream check fails.
    """

    walkthrough_id: str = Field(
        min_length=1,
        max_length=128,
    )

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    planning_input_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    semantic_context_sha256: str = Field(
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


def configure_walkthrough_context(
    walkthrough_id: str,
) -> str:
    global CACHE_PATH

    validated_id = (
        semantic_run
        .configure_walkthrough_context(
            walkthrough_id
        )
    )

    CACHE_PATH = (
        semantic_run
        .initial_plan_run
        .object_dna_run
        .PRIVATE_DIR
        / (
            f"{validated_id}"
            "-initial-semantic-repair-attempt-01.json"
        )
    )

    return validated_id


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
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def repair_pipeline_fingerprint() -> str:
    """
    Bind the repair cache to the exact repair implementation,
    deterministic validator, schemas, and normalizer.

    No model calls occur here.
    """

    digest = hashlib.sha256()

    base_dir = (
        Path(__file__)
        .resolve()
        .parent
    )

    for filename in (
        REPAIR_PIPELINE_FILES
    ):
        path = (
            base_dir
            / filename
        )

        if not path.exists():
            raise RuntimeError(
                "Required repair pipeline file was not found: "
                f"{path}"
            )

        digest.update(
            filename.encode(
                "utf-8"
            )
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
    normalized = (
        normalize_external_resource_ids(
            plan,
            external_resources,
        )
    )

    normalized = (
        normalize_plan_item_ids(
            normalized
        )
    )

    return normalized


def semantic_context_fingerprint(
    *,
    goal: str,
    outcome,
) -> str:
    return sha256_payload(
        {
            "goal": goal,
            "status": (
                outcome.status.value
            ),
            "requirements": [
                requirement.model_dump(
                    mode="json"
                )
                for requirement
                in outcome.requirements
            ],
        }
    )


def load_semantic_failure_context(
    *,
    walkthrough_id: str,
    goal: str,
):
    """
    Load the exact initial plan and matching hardened semantic
    critic result.

    The source plan is revalidated deterministically before
    any repair is allowed.

    No model calls occur here.
    """

    (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        source_plan_sha256,
        validated_source_plan,
    ) = (
        semantic_run
        .load_initial_plan_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    semantic_context_sha256 = (
        semantic_context_fingerprint(
            goal=goal,
            outcome=(
                initial_outcome
            ),
        )
    )

    semantic_pipeline_sha256 = (
        semantic_run
        .semantic_pipeline_fingerprint()
    )

    critic = (
        semantic_run
        .load_matching_cache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            semantic_context_sha256=(
                semantic_context_sha256
            ),
            planning_input_sha256=(
                planning_input_sha256
            ),
            validated_plan_sha256=(
                source_plan_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
        )
    )

    if critic is None:
        raise RuntimeError(
            "Matching hardened semantic-critic cache was not found."
        )

    if critic.passed:
        raise RuntimeError(
            "Semantic critic already passes. "
            "A semantic repair is not justified."
        )

    blocking_findings = [
        finding
        for finding
        in critic.findings
        if (
            finding.severity.value
            in {
                "medium",
                "high",
            }
        )
    ]

    if not blocking_findings:
        raise RuntimeError(
            "Semantic critic failed but contains no MEDIUM/HIGH "
            "findings. Refusing an unguided repair call."
        )

    return (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        source_plan_sha256,
        validated_source_plan,
        semantic_pipeline_sha256,
        critic,
    )


def load_matching_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    source_plan_sha256: str,
    semantic_pipeline_sha256: str,
    semantic_critic_sha256: str,
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

        cache = (
            InitialSemanticRepairCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing initial semantic-repair cache is invalid. "
            "Refusing to overwrite it with another paid call until "
            f"inspected: {CACHE_PATH}"
        ) from exc

    if (
        cache.walkthrough_id
        != walkthrough_id
    ):
        return None

    if (
        cache.goal
        != goal
    ):
        return None

    if (
        cache.planning_input_sha256
        != planning_input_sha256
    ):
        return None

    if (
        cache.semantic_context_sha256
        != semantic_context_sha256
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
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    source_plan_sha256: str,
    semantic_pipeline_sha256: str,
    semantic_critic_sha256: str,
    repair_pipeline_sha256: str,
    repaired_plan: PhysicalPlan,
) -> None:
    """
    Persist the paid repair result immediately.

    Later deterministic or semantic failure must not cause the same
    repair result to be purchased again.
    """

    cache = (
        InitialSemanticRepairCache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            semantic_context_sha256=(
                semantic_context_sha256
            ),
            source_plan_sha256=(
                source_plan_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            semantic_critic_sha256=(
                semantic_critic_sha256
            ),
            repair_pipeline_sha256=(
                repair_pipeline_sha256
            ),
            repaired_plan=(
                repaired_plan
            ),
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


def validate_repaired_plan(
    *,
    repaired_plan: PhysicalPlan,
    object_dna,
    active_items,
    external_resources: list[str],
):
    normalized_plan = (
        normalize_plan(
            plan=repaired_plan,
            external_resources=(
                external_resources
            ),
        )
    )

    active_item_ids = {
        item.id
        for item
        in active_items
    }

    try:
        validated_plan = (
            validate_zero_plan(
                normalized_plan,
                object_dna,
                active_item_ids,
            )
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
    critic,
) -> None:
    print(
        "Blocking semantic findings:"
    )

    print()

    blocking = [
        finding
        for finding
        in critic.findings
        if (
            finding.severity.value
            in {
                "medium",
                "high",
            }
        )
    ]

    for index, finding in enumerate(
        blocking,
        start=1,
    ):
        print(
            f"{index}. "
            f"[{finding.severity.value}] "
            f"{finding.issue_type.value}"
        )

        print(
            f"   Step: "
            f"{finding.step_order}"
        )

        print(
            f"   Claim: "
            f"{finding.claim}"
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
    parser = argparse.ArgumentParser(
        description=(
            "Perform bounded semantic repair attempt 1 for a "
            "deterministically-valid initial ZERO plan."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=(
            DEFAULT_WALKTHROUGH_ID
        ),
        help=(
            "Artifact namespace such as walkthrough-02. "
            "Defaults to walkthrough-01."
        ),
    )

    parser.add_argument(
        "--goal",
        default=(
            semantic_run
            .initial_plan_run
            .DEFAULT_GOAL
        ),
        help=(
            "Goal whose failed semantic audit should be repaired."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate all source caches and inspect repair-cache "
            "status without creating the repair client."
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
            "Maximum new paid plan-repair calls allowed. "
            "Only 0 or 1 is valid. Default 0."
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

    goal = (
        args.goal.strip()
    )

    if not goal:
        parser.error(
            "--goal may not be empty."
        )

    walkthrough_id = (
        configure_walkthrough_context(
            args.walkthrough_id
        )
    )

    print("=" * 72)
    print(
        "ZERO INITIAL SEMANTIC PLAN REPAIR - ATTEMPT 1 OF 2"
    )
    print("=" * 72)

    print(
        f"Walkthrough: "
        f"{walkthrough_id}"
    )

    print(
        f"Goal: "
        f"{goal}"
    )

    (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        source_plan_sha256,
        source_plan,
        semantic_pipeline_sha256,
        critic,
    ) = (
        load_semantic_failure_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    semantic_critic_sha256 = (
        sha256_payload(
            critic.model_dump(
                mode="json"
            )
        )
    )

    current_repair_pipeline_sha256 = (
        repair_pipeline_fingerprint()
    )

    cached_repair = (
        load_matching_cache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            semantic_context_sha256=(
                semantic_context_sha256
            ),
            source_plan_sha256=(
                source_plan_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            semantic_critic_sha256=(
                semantic_critic_sha256
            ),
            repair_pipeline_sha256=(
                current_repair_pipeline_sha256
            ),
        )
    )

    print()

    print(
        f"Planning input SHA-256: "
        f"{planning_input_sha256}"
    )

    print(
        f"Semantic execution-context SHA-256: "
        f"{semantic_context_sha256}"
    )

    print(
        f"Source plan SHA-256: "
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

    print(
        f"Initial outcome status: "
        f"{initial_outcome.status.value}"
    )

    print(
        f"Conditional requirements: "
        f"{len(initial_outcome.requirements)}"
    )

    print(
        f"Active inventory items: "
        f"{len(active_items)}"
    )

    print(
        f"Object DNA items: "
        f"{len(object_dna.objects)}"
    )

    print(
        f"External resources: "
        f"{external_resources}"
    )

    print()

    print_critic(
        critic
    )

    print(
        "Semantic repair cache: "
        f"{CACHE_PATH.resolve()}"
    )

    print()

    if (
        cached_repair
        is None
    ):
        print(
            "Semantic repair cache: missing/stale"
        )

    else:
        print(
            "Semantic repair cache: valid"
        )

    if args.dry_run:
        print()

        print(
            "DRY RUN COMPLETE - NO MODEL CALL MADE"
        )

        print(
            "Model calls: 0"
        )

        return

    repaired_plan = (
        cached_repair
    )

    if (
        repaired_plan
        is None
    ):
        if (
            args.max_new_calls
            == 0
        ):
            print()

            print(
                "No paid semantic-repair call authorized "
                "(--max-new-calls is 0)."
            )

            return

        print()

        print(
            "Running ONE paid semantic plan-repair call..."
        )

        print(
            "This is repair attempt 1 of 2."
        )

        # Lazy imports keep dry-run/cache-only execution free of
        # planner client construction.
        from plan_outcome_pipeline import (
            _build_execution_aware_goal,
        )
        from plan_repair import (
            repair_plan,
        )

        execution_goal = (
            _build_execution_aware_goal(
                goal=goal,
                outcome=(
                    initial_outcome
                ),
            )
        )

        repaired_plan = (
            repair_plan(
                plan=source_plan,
                critic=critic,
                goal=execution_goal,
                inventory=(
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

        # Save the paid result BEFORE downstream validation.
        save_cache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            semantic_context_sha256=(
                semantic_context_sha256
            ),
            source_plan_sha256=(
                source_plan_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            semantic_critic_sha256=(
                semantic_critic_sha256
            ),
            repair_pipeline_sha256=(
                current_repair_pipeline_sha256
            ),
            repaired_plan=(
                repaired_plan
            ),
        )

        print()

        print(
            "Repaired PhysicalPlan schema-valid and cached."
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
            "Reusing validated semantic-repair cache."
        )

        print(
            "Nemotron plan-repair calls: 0"
        )

    (
        validated_plan,
        validation_error,
    ) = (
        validate_repaired_plan(
            repaired_plan=(
                repaired_plan
            ),
            object_dna=(
                object_dna
            ),
            active_items=(
                active_items
            ),
            external_resources=(
                external_resources
            ),
        )
    )

    print()
    print("=" * 72)

    if (
        validation_error
        is not None
    ):
        print(
            "SEMANTIC REPAIR 1 DETERMINISTIC VALIDATION: FAILED"
        )

        print("=" * 72)

        print()

        print(
            str(
                validation_error
            )
        )

        print()

        print(
            "The paid repair result remains cached."
        )

        print(
            "Do not rerun repair attempt 1 blindly."
        )

        return

    print(
        "SEMANTIC REPAIR 1 DETERMINISTIC VALIDATION: PASSED"
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

    # Free one-way closure guard. This can prove a rejected literal
    # claim survived; absence does NOT prove the repair is safe.
    from plan_repair_closure import (
        find_persisted_critic_findings,
    )

    persisted = (
        find_persisted_critic_findings(
            before_plan=(
                source_plan
            ),
            repaired_plan=(
                validated_plan
            ),
            critic=critic,
        )
    )

    print()

    if (
        persisted
        is None
    ):
        print(
            "Repair closure guard: no definitely persisted "
            "critic claim detected."
        )

    else:
        print(
            "Repair closure guard: FAILED"
        )

        print(
            persisted.model_dump_json(
                indent=2
            )
        )

    print()

    print(
        "Repair budget used: 1 of 2 attempts."
    )

    print(
        "A fresh semantic audit is still required before "
        "this plan can continue."
    )


if __name__ == "__main__":
    main()
