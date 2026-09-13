import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from critic_schemas import (
    PlanCriticResult,
)
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


DEFAULT_WALKTHROUGH_ID = (
    initial_plan_run.DEFAULT_WALKTHROUGH_ID
)


CACHE_PATH = (
    initial_plan_run.object_dna_run.PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-initial-semantic-critic.json"
    )
)


SEMANTIC_PIPELINE_FILES = (
    "semantic_critic.py",
    "critic_schemas.py",
    "plan_schemas.py",
    "schemas.py",
    "model_json.py",
)


class InitialSemanticCriticCache(
    BaseModel
):
    """
    Cache for the semantic physical audit of an INITIAL plan
    that has already passed deterministic validation.

    This is still not a final ZERO outcome.
    """

    walkthrough_id: str = Field(
        min_length=1,
        max_length=128,
    )

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    # None preserves compatibility with older cache files.
    # Older audits will parse, but become stale because they lack
    # the current conditional-execution fingerprint.
    semantic_context_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    planning_input_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    validated_plan_sha256: str = Field(
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
        initial_plan_run
        .configure_walkthrough_context(
            walkthrough_id
        )
    )

    CACHE_PATH = (
        initial_plan_run
        .object_dna_run
        .PRIVATE_DIR
        / (
            f"{validated_id}"
            "-initial-semantic-critic.json"
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


def semantic_pipeline_fingerprint() -> str:
    """
    Bind the semantic cache to the exact critic implementation
    and schemas.

    No model call occurs here.
    """

    digest = hashlib.sha256()

    base_dir = (
        Path(__file__)
        .resolve()
        .parent
    )

    for filename in (
        SEMANTIC_PIPELINE_FILES
    ):
        path = (
            base_dir
            / filename
        )

        if not path.exists():
            raise RuntimeError(
                "Required semantic-critic pipeline file was not found: "
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


def load_initial_plan_context(
    *,
    walkthrough_id: str,
    goal: str,
):
    """
    Reconstruct the exact planning context used by the cached
    initial PlanOutcome and deterministically revalidate its plan.

    No model calls occur here.
    """

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

    object_dna_sha256 = (
        initial_plan_run
        .object_dna_fingerprint(
            object_dna
        )
    )

    planner_pipeline_sha256 = (
        initial_plan_run
        .planner_pipeline_fingerprint()
    )

    planning_input_sha256 = (
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
                object_dna_sha256
            ),
            planner_pipeline_sha256=(
                planner_pipeline_sha256
            ),
            planning_input_sha256=(
                planning_input_sha256
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
        raise RuntimeError(
            "Cached initial plan no longer passes deterministic "
            f"validation: {exc}"
        ) from exc

    validated_plan_sha256 = (
        sha256_payload(
            validated_plan.model_dump(
                mode="json"
            )
        )
    )

    return (
        outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        validated_plan_sha256,
        validated_plan,
    )


def load_matching_cache(
    *,
    walkthrough_id: str,
    goal: str,
    semantic_context_sha256: str,
    planning_input_sha256: str,
    validated_plan_sha256: str,
    semantic_pipeline_sha256: str,
) -> PlanCriticResult | None:
    """
    Reuse a semantic audit only when its exact walkthrough,
    goal, world input, validated plan, and critic implementation
    all match.
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
            InitialSemanticCriticCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing initial semantic-critic cache is invalid. "
            "Refusing to overwrite it with another paid audit until "
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
        cache.semantic_context_sha256
        != semantic_context_sha256
    ):
        return None

    if (
        cache.planning_input_sha256
        != planning_input_sha256
    ):
        return None

    if (
        cache.validated_plan_sha256
        != validated_plan_sha256
    ):
        return None

    if (
        cache.semantic_pipeline_sha256
        != semantic_pipeline_sha256
    ):
        return None

    return cache.critic


def save_cache(
    *,
    walkthrough_id: str,
    goal: str,
    semantic_context_sha256: str,
    planning_input_sha256: str,
    validated_plan_sha256: str,
    semantic_pipeline_sha256: str,
    critic: PlanCriticResult,
) -> None:
    """
    Persist one successful initial-plan semantic audit atomically.
    """

    cache = InitialSemanticCriticCache(
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
            validated_plan_sha256
        ),
        semantic_pipeline_sha256=(
            semantic_pipeline_sha256
        ),
        critic=critic,
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
        "INITIAL PLAN SEMANTIC PHYSICAL AUDIT RESULT"
    )
    print("=" * 72)

    print()

    print(
        f"Passed: "
        f"{critic.passed}"
    )

    print(
        f"Findings: "
        f"{len(critic.findings)}"
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
            "The initial plan passed the semantic physical audit."
        )

    else:
        print(
            "The initial plan requires a bounded repair or "
            "safe conditional fallback before it can continue."
        )

    print()

    print(
        "Verification-gate processing and final semantic recheck "
        "have NOT been run yet."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit a deterministically validated initial ZERO plan "
            "for semantic physical correctness."
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
            initial_plan_run.DEFAULT_GOAL
        ),
        help=(
            "Goal whose cached initial plan should be audited."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the initial-plan context and inspect critic-cache "
            "status without creating the semantic critic client."
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
            "One audit normally uses one model call. "
            "Malformed JSON may cause semantic_critic.py to make one "
            "additional formatting-only repair call. Default 0."
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
        "ZERO WALKTHROUGH INITIAL SEMANTIC CRITIC"
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
        validated_plan_sha256,
        validated_plan,
    ) = (
        load_initial_plan_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    # Bind the semantic audit to the exact outcome conditions that
    # determine how the plan is allowed to execute.
    semantic_context_sha256 = (
        sha256_payload(
            {
                "goal": goal,
                "status": (
                    initial_outcome.status.value
                ),
                "requirements": [
                    requirement.model_dump(
                        mode="json"
                    )
                    for requirement
                    in initial_outcome.requirements
                ],
            }
        )
    )

    semantic_sha256 = (
        semantic_pipeline_fingerprint()
    )

    cached_critic = (
        load_matching_cache(
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
                validated_plan_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_sha256
            ),
        )
    )

    print()

    print(
        f"Initial outcome status: "
        f"{initial_outcome.status.value}"
    )

    print(
        f"Planning input SHA-256: "
        f"{planning_input_sha256}"
    )

    print(
        f"Semantic execution-context SHA-256: "
        f"{semantic_context_sha256}"
    )

    print(
        f"Conditional requirements: "
        f"{len(initial_outcome.requirements)}"
    )

    print(
        f"Validated initial-plan SHA-256: "
        f"{validated_plan_sha256}"
    )

    print(
        f"Semantic pipeline SHA-256: "
        f"{semantic_sha256}"
    )

    print()

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
        f"Validated plan steps: "
        f"{len(validated_plan.steps)}"
    )

    print()

    print(
        "Initial semantic cache: "
        f"{CACHE_PATH.resolve()}"
    )

    print()

    if (
        cached_critic
        is None
    ):
        print(
            "Initial semantic-critic cache: missing/stale"
        )

    else:
        print(
            "Initial semantic-critic cache: valid"
        )

    if args.dry_run:
        print()

        print(
            "DRY RUN COMPLETE - NO MODEL CALL MADE"
        )

        print(
            "Model calls: 0"
        )

        if (
            cached_critic
            is not None
        ):
            print_critic(
                cached_critic
            )

        return

    if (
        cached_critic
        is not None
    ):
        print()

        print(
            "Reusing validated initial semantic-critic cache."
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
        "Running ONE semantic physical audit..."
    )

    print(
        "This normally uses 1 Nemotron call; malformed JSON may "
        "trigger 1 additional formatting-only repair call."
    )

    # Lazy imports:
    # dry runs and cache-only runs do not instantiate the Nebius client.
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
            inventory=active_items,
            object_dna=object_dna,
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
        semantic_context_sha256=(
            semantic_context_sha256
        ),
        planning_input_sha256=(
            planning_input_sha256
        ),
        validated_plan_sha256=(
            validated_plan_sha256
        ),
        semantic_pipeline_sha256=(
            semantic_sha256
        ),
        critic=critic,
    )

    print()

    print(
        "Initial semantic critic schema-valid and cached."
    )

    print(
        "New semantic audit invocations: 1"
    )

    print(
        "Saved private initial semantic-critic cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_critic(
        critic
    )


if __name__ == "__main__":
    main()
