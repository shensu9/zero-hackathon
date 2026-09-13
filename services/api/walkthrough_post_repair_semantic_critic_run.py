import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from critic_schemas import (
    PlanCriticResult,
)

import walkthrough_initial_semantic_critic_run as semantic_run
import walkthrough_initial_semantic_repair_run as repair_run


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
        "-semantic-critic-after-initial-semantic-repair-01.json"
    )
)


class PostRepairSemanticCriticCache(
    BaseModel
):
    """
    Semantic audit of validated semantic-repair attempt 1.

    This cache is separate from the initial-plan semantic audit.
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

    repaired_plan_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    semantic_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    critic: PlanCriticResult


def configure_walkthrough_context(
    walkthrough_id: str,
) -> str:
    global CACHE_PATH

    validated_id = (
        repair_run
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
            "-semantic-critic-after-initial-semantic-repair-01.json"
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


def load_repaired_plan_context(
    *,
    walkthrough_id: str,
    goal: str,
):
    """
    Reconstruct the exact semantic-failure context, load the
    matching paid repair-attempt-1 cache, and deterministically
    validate the repaired plan.

    No model calls occur here.
    """

    (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        source_plan_sha256,
        source_plan,
        source_semantic_pipeline_sha256,
        source_critic,
    ) = (
        repair_run
        .load_semantic_failure_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    source_semantic_critic_sha256 = (
        repair_run.sha256_payload(
            source_critic.model_dump(
                mode="json"
            )
        )
    )

    repair_pipeline_sha256 = (
        repair_run
        .repair_pipeline_fingerprint()
    )

    repaired_plan = (
        repair_run
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
            source_plan_sha256=(
                source_plan_sha256
            ),
            semantic_pipeline_sha256=(
                source_semantic_pipeline_sha256
            ),
            semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            repair_pipeline_sha256=(
                repair_pipeline_sha256
            ),
        )
    )

    if repaired_plan is None:
        raise RuntimeError(
            "Matching semantic-repair attempt-1 cache "
            "was not found."
        )

    (
        validated_plan,
        validation_error,
    ) = (
        repair_run
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

    if validation_error is not None:
        raise RuntimeError(
            "Cached semantic-repair attempt 1 no longer "
            "passes deterministic validation: "
            f"{validation_error}"
        )

    repaired_plan_sha256 = (
        sha256_payload(
            validated_plan.model_dump(
                mode="json"
            )
        )
    )

    current_semantic_pipeline_sha256 = (
        semantic_run
        .semantic_pipeline_fingerprint()
    )

    return (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        source_semantic_critic_sha256,
        repair_pipeline_sha256,
        repaired_plan_sha256,
        validated_plan,
        current_semantic_pipeline_sha256,
    )


def load_matching_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    source_semantic_critic_sha256: str,
    repair_pipeline_sha256: str,
    repaired_plan_sha256: str,
    semantic_pipeline_sha256: str,
) -> PlanCriticResult | None:
    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cache = (
            PostRepairSemanticCriticCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing post-repair semantic-critic cache "
            "is invalid. Refusing to overwrite it with "
            "another paid audit until inspected: "
            f"{CACHE_PATH}"
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
            cache.source_semantic_critic_sha256,
            source_semantic_critic_sha256,
        ),
        (
            cache.repair_pipeline_sha256,
            repair_pipeline_sha256,
        ),
        (
            cache.repaired_plan_sha256,
            repaired_plan_sha256,
        ),
        (
            cache.semantic_pipeline_sha256,
            semantic_pipeline_sha256,
        ),
    )

    for actual, expected in checks:
        if actual != expected:
            return None

    return cache.critic


def save_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    source_semantic_critic_sha256: str,
    repair_pipeline_sha256: str,
    repaired_plan_sha256: str,
    semantic_pipeline_sha256: str,
    critic: PlanCriticResult,
) -> None:
    cache = (
        PostRepairSemanticCriticCache(
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
                source_semantic_critic_sha256
            ),
            repair_pipeline_sha256=(
                repair_pipeline_sha256
            ),
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            critic=critic,
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
    critic: PlanCriticResult,
) -> None:
    print()
    print("=" * 72)
    print(
        "POST-REPAIR SEMANTIC PHYSICAL AUDIT RESULT"
    )
    print("=" * 72)

    print()
    print(
        f"Passed: {critic.passed}"
    )

    print(
        f"Findings: {len(critic.findings)}"
    )

    if critic.findings:
        print()

        for index, finding in enumerate(
            critic.findings,
            start=1,
        ):
            print(
                f"{index}. severity: "
                f"{finding.severity.value}"
            )

            print(
                f"   issue type: "
                f"{finding.issue_type.value}"
            )

            print(
                f"   step order: "
                f"{finding.step_order}"
            )

            print(
                f"   claim: "
                f"{finding.claim}"
            )

            print(
                f"   explanation: "
                f"{finding.explanation}"
            )

            print(
                f"   recommended fix: "
                f"{finding.recommended_fix}"
            )

    print()

    if critic.passed:
        print(
            "Semantic repair attempt 1 passed "
            "the fresh semantic audit."
        )

    else:
        print(
            "Semantic repair attempt 1 still has "
            "blocking semantic findings."
        )

    print()

    print(
        "Verification-gate processing and final semantic "
        "recheck have NOT been run yet."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fresh semantic audit after initial semantic "
            "repair attempt 1."
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
            "Goal whose repaired plan should be audited."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the repaired-plan context and inspect "
            "audit-cache status without making a model call."
        ),
    )

    parser.add_argument(
        "--max-new-audits",
        type=int,
        default=0,
        choices=[
            0,
            1,
        ],
        help=(
            "Maximum new semantic-audit invocations allowed. "
            "Normally one model call; malformed JSON may trigger "
            "one additional formatting-only repair call."
        ),
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and
        args.max_new_audits
        != 0
    ):
        parser.error(
            "--dry-run cannot authorize a semantic audit."
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
        "ZERO POST-REPAIR SEMANTIC CRITIC - "
        "AFTER REPAIR 1"
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
        source_semantic_critic_sha256,
        repair_pipeline_sha256,
        repaired_plan_sha256,
        validated_plan,
        semantic_pipeline_sha256,
    ) = (
        load_repaired_plan_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    cached_critic = (
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
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            repair_pipeline_sha256=(
                repair_pipeline_sha256
            ),
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
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
        f"Source semantic critic SHA-256: "
        f"{source_semantic_critic_sha256}"
    )

    print(
        f"Repair pipeline SHA-256: "
        f"{repair_pipeline_sha256}"
    )

    print(
        f"Validated repaired-plan SHA-256: "
        f"{repaired_plan_sha256}"
    )

    print(
        f"Semantic pipeline SHA-256: "
        f"{semantic_pipeline_sha256}"
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

    print(
        f"Validated repaired-plan steps: "
        f"{len(validated_plan.steps)}"
    )

    print()

    print(
        "Post-repair semantic cache: "
        f"{CACHE_PATH.resolve()}"
    )

    print()

    if cached_critic is None:
        print(
            "Post-repair semantic-critic cache: "
            "missing/stale"
        )
    else:
        print(
            "Post-repair semantic-critic cache: valid"
        )

    if args.dry_run:
        print()

        print(
            "DRY RUN COMPLETE - NO MODEL CALL MADE"
        )

        print(
            "Model calls: 0"
        )

        if cached_critic is not None:
            print_critic(
                cached_critic
            )

        return

    if cached_critic is not None:
        print()

        print(
            "Reusing validated post-repair "
            "semantic-critic cache."
        )

        print(
            "New semantic audit invocations: 0"
        )

        print_critic(
            cached_critic
        )

        return

    if (
        args.max_new_audits
        == 0
    ):
        print()

        print(
            "No paid semantic audit authorized "
            "(--max-new-audits is 0)."
        )

        return

    print()

    print(
        "Running ONE fresh semantic physical audit "
        "after repair attempt 1..."
    )

    print(
        "Normally 1 Nemotron call; malformed JSON may "
        "trigger one formatting-only repair call."
    )

    from plan_outcome_pipeline import (
        _build_execution_aware_goal,
    )
    from semantic_critic import (
        audit_plan_semantics,
    )

    execution_goal = (
        _build_execution_aware_goal(
            goal=goal,
            outcome=initial_outcome,
        )
    )

    critic = (
        audit_plan_semantics(
            plan=validated_plan,
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
        source_semantic_critic_sha256=(
            source_semantic_critic_sha256
        ),
        repair_pipeline_sha256=(
            repair_pipeline_sha256
        ),
        repaired_plan_sha256=(
            repaired_plan_sha256
        ),
        semantic_pipeline_sha256=(
            semantic_pipeline_sha256
        ),
        critic=critic,
    )

    print()

    print(
        "Post-repair semantic critic schema-valid "
        "and cached."
    )

    print(
        "New semantic audit invocations: 1"
    )

    print(
        "Saved private post-repair semantic cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_critic(
        critic
    )


if __name__ == "__main__":
    main()
