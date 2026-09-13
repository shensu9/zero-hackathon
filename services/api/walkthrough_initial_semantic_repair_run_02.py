import argparse
import json

from pydantic import BaseModel, Field

from plan_schemas import (
    PhysicalPlan,
)

import walkthrough_initial_semantic_repair_run as repair1_run
import walkthrough_post_repair_semantic_critic_run as post_semantic_run


DEFAULT_WALKTHROUGH_ID = (
    repair1_run.DEFAULT_WALKTHROUGH_ID
)


CACHE_PATH = (
    repair1_run
    .semantic_run
    .initial_plan_run
    .object_dna_run
    .PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-initial-semantic-repair-attempt-02.json"
    )
)


class InitialSemanticRepairAttempt02Cache(
    BaseModel
):
    """
    FINAL bounded semantic repair attempt.

    ZERO permits at most two plan-repair attempts.
    This paid result is cached before downstream validation.
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

    source_repair_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    source_semantic_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    source_semantic_critic_sha256: str = Field(
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
        post_semantic_run
        .configure_walkthrough_context(
            walkthrough_id
        )
    )

    CACHE_PATH = (
        repair1_run
        .semantic_run
        .initial_plan_run
        .object_dna_run
        .PRIVATE_DIR
        / (
            f"{validated_id}"
            "-initial-semantic-repair-attempt-02.json"
        )
    )

    return validated_id


def load_semantic_failure_context(
    *,
    walkthrough_id: str,
    goal: str,
):
    """
    Load validated repair attempt 1 plus its matching fresh
    semantic failure.

    No model calls occur here.
    """

    (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        repair1_source_critic_sha256,
        source_repair_pipeline_sha256,
        source_plan_sha256,
        source_plan,
        source_semantic_pipeline_sha256,
    ) = (
        post_semantic_run
        .load_repaired_plan_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    critic = (
        post_semantic_run
        .load_matching_cache(
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
            source_semantic_critic_sha256=(
                repair1_source_critic_sha256
            ),
            repair_pipeline_sha256=(
                source_repair_pipeline_sha256
            ),
            repaired_plan_sha256=(
                source_plan_sha256
            ),
            semantic_pipeline_sha256=(
                source_semantic_pipeline_sha256
            ),
        )
    )

    if critic is None:
        raise RuntimeError(
            "Matching post-repair semantic critic cache "
            "was not found."
        )

    if critic.passed:
        raise RuntimeError(
            "Post-repair semantic critic already passes. "
            "Repair attempt 2 is not justified."
        )

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

    if not blocking:
        raise RuntimeError(
            "Post-repair semantic critic failed without "
            "MEDIUM/HIGH findings. Refusing an unguided repair."
        )

    return (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        source_plan_sha256,
        source_plan,
        source_repair_pipeline_sha256,
        source_semantic_pipeline_sha256,
        critic,
    )


def load_matching_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    source_plan_sha256: str,
    source_repair_pipeline_sha256: str,
    source_semantic_pipeline_sha256: str,
    source_semantic_critic_sha256: str,
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
            InitialSemanticRepairAttempt02Cache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing semantic-repair-attempt-2 cache "
            "is invalid. Refusing another paid call until "
            f"inspected: {CACHE_PATH}"
        ) from exc

    checks = (
        (
            cache.walkthrough_id,
            walkthrough_id,
        ),
        (
            cache.goal,
            goal,
        ),
        (
            cache.planning_input_sha256,
            planning_input_sha256,
        ),
        (
            cache.semantic_context_sha256,
            semantic_context_sha256,
        ),
        (
            cache.source_plan_sha256,
            source_plan_sha256,
        ),
        (
            cache.source_repair_pipeline_sha256,
            source_repair_pipeline_sha256,
        ),
        (
            cache.source_semantic_pipeline_sha256,
            source_semantic_pipeline_sha256,
        ),
        (
            cache.source_semantic_critic_sha256,
            source_semantic_critic_sha256,
        ),
        (
            cache.repair_pipeline_sha256,
            repair_pipeline_sha256,
        ),
    )

    for actual, expected in checks:
        if actual != expected:
            return None

    return cache.repaired_plan


def save_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    source_plan_sha256: str,
    source_repair_pipeline_sha256: str,
    source_semantic_pipeline_sha256: str,
    source_semantic_critic_sha256: str,
    repair_pipeline_sha256: str,
    repaired_plan: PhysicalPlan,
) -> None:
    """
    Persist repair attempt 2 immediately.

    The repair budget is exhausted after this result exists.
    """

    cache = (
        InitialSemanticRepairAttempt02Cache(
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
            source_repair_pipeline_sha256=(
                source_repair_pipeline_sha256
            ),
            source_semantic_pipeline_sha256=(
                source_semantic_pipeline_sha256
            ),
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
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


def print_critic(
    critic,
) -> None:
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

    print(
        "Blocking semantic findings "
        "requiring FINAL bounded repair:"
    )

    print()

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
            "FINAL bounded semantic repair attempt 2 of 2."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=(
            DEFAULT_WALKTHROUGH_ID
        ),
        help=(
            "Artifact namespace such as walkthrough-02."
        ),
    )

    parser.add_argument(
        "--goal",
        default=(
            repair1_run
            .semantic_run
            .initial_plan_run
            .DEFAULT_GOAL
        ),
        help=(
            "Goal whose remaining semantic failure "
            "should be repaired."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate all source caches and inspect "
            "repair-attempt-2 cache status without a model call."
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
            "Maximum new paid repair calls allowed. "
            "Only 0 or 1 is valid."
        ),
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and
        args.max_new_calls != 0
    ):
        parser.error(
            "--dry-run cannot authorize a paid call."
        )

    goal = args.goal.strip()

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
        "ZERO INITIAL SEMANTIC PLAN REPAIR - "
        "ATTEMPT 2 OF 2"
    )
    print("=" * 72)

    print(
        f"Walkthrough: {walkthrough_id}"
    )

    print(
        f"Goal: {goal}"
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
        source_repair_pipeline_sha256,
        source_semantic_pipeline_sha256,
        critic,
    ) = (
        load_semantic_failure_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    source_semantic_critic_sha256 = (
        repair1_run.sha256_payload(
            critic.model_dump(
                mode="json"
            )
        )
    )

    current_repair_pipeline_sha256 = (
        repair1_run
        .repair_pipeline_fingerprint()
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
            source_repair_pipeline_sha256=(
                source_repair_pipeline_sha256
            ),
            source_semantic_pipeline_sha256=(
                source_semantic_pipeline_sha256
            ),
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
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
        f"Source repaired-plan SHA-256: "
        f"{source_plan_sha256}"
    )

    print(
        f"Source repair pipeline SHA-256: "
        f"{source_repair_pipeline_sha256}"
    )

    print(
        f"Source semantic pipeline SHA-256: "
        f"{source_semantic_pipeline_sha256}"
    )

    print(
        f"Source semantic critic SHA-256: "
        f"{source_semantic_critic_sha256}"
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
        "Semantic repair attempt-2 cache: "
        f"{CACHE_PATH.resolve()}"
    )

    print()

    if cached_repair is None:
        print(
            "Semantic repair attempt-2 cache: "
            "missing/stale"
        )
    else:
        print(
            "Semantic repair attempt-2 cache: valid"
        )

    if args.dry_run:
        print()

        print(
            "DRY RUN COMPLETE - NO MODEL CALL MADE"
        )

        print(
            "Model calls: 0"
        )

        print(
            "Repair budget if executed: "
            "2 of 2 attempts used."
        )

        return

    repaired_plan = cached_repair

    if repaired_plan is None:
        if (
            args.max_new_calls
            == 0
        ):
            print()

            print(
                "No paid repair-attempt-2 call authorized "
                "(--max-new-calls is 0)."
            )

            return

        print()

        print(
            "Running ONE paid semantic plan-repair call..."
        )

        print(
            "This is repair attempt 2 of 2. "
            "NO third repair is permitted."
        )

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

        # Persist BEFORE downstream validation.
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
            source_repair_pipeline_sha256=(
                source_repair_pipeline_sha256
            ),
            source_semantic_pipeline_sha256=(
                source_semantic_pipeline_sha256
            ),
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
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
            "Repair-attempt-2 PhysicalPlan "
            "schema-valid and cached."
        )

        print(
            "Nemotron plan-repair calls: 1"
        )

        print(
            "Saved private repair-attempt-2 cache:"
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
    ) = (
        repair1_run
        .validate_repaired_plan(
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

    if validation_error is not None:
        print(
            "SEMANTIC REPAIR 2 DETERMINISTIC "
            "VALIDATION: FAILED"
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
            "Repair budget exhausted: 2 of 2."
        )

        print(
            "DO NOT run another plan-repair attempt."
        )

        return

    print(
        "SEMANTIC REPAIR 2 DETERMINISTIC "
        "VALIDATION: PASSED"
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

    if persisted is None:
        print(
            "Repair closure guard: no definitely "
            "persisted critic claim detected."
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
        "Repair budget exhausted: 2 of 2 attempts used."
    )

    print(
        "NO third repair attempt is permitted."
    )

    print(
        "A final fresh semantic audit is still required."
    )


if __name__ == "__main__":
    main()
