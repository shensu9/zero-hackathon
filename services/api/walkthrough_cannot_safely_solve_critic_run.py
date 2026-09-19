import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from critic_schemas import (
    PlanCriticResult,
)
from plan_outcome_schemas import (
    PlanOutcomeStatus,
)
from walkthrough_external_resource_state import (
    load_external_resource_state,
)
from walkthrough_goal_relevance_run import (
    inventory_fingerprint,
)
import walkthrough_initial_plan_outcome_run as initial_run


WALKTHROUGH_ID = "walkthrough-03"

GOAL = (
    "Hang a full-length mirror on this painted wall using only "
    "what I already have, without drilling, adhesives, or buying "
    "anything, while making sure it cannot fall."
)

CRITIC_PIPELINE_FILES = (
    "cannot_safely_solve_critic.py",
    "semantic_critic.py",
    "critic_schemas.py",
    "plan_outcome_schemas.py",
    "model_json.py",
    "schemas.py",
)


class CannotSafelySolveCriticCache(
    BaseModel
):
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

    initial_outcome_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    blocker_audit_input_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    critic_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    active_item_ids: list[str]

    critic: PlanCriticResult


def canonical_json(
    payload,
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_text(
    text: str,
) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def critic_pipeline_fingerprint(
) -> str:
    """
    Fingerprint only the semantic decision stack used by
    the CANNOT_SAFELY_SOLVE audit.

    No model/client import is required here.
    """

    base_dir = (
        Path(__file__)
        .resolve()
        .parent
    )

    digest = hashlib.sha256()

    for filename in (
        CRITIC_PIPELINE_FILES
    ):
        path = (
            base_dir
            / filename
        )

        if not path.exists():
            raise RuntimeError(
                "Missing blocker-critic pipeline file: "
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


def outcome_fingerprint(
    outcome,
) -> str:
    return sha256_text(
        canonical_json(
            outcome.model_dump(
                mode="json"
            )
        )
    )


def blocker_audit_input_fingerprint(
    *,
    goal: str,
    outcome,
    active_items,
    object_dna,
    external_resources,
) -> str:
    payload = {
        "goal":
            goal,

        "outcome":
            outcome.model_dump(
                mode="json"
            ),

        "inventory": [
            item.model_dump(
                mode="json"
            )
            for item
            in active_items
        ],

        "object_dna":
            object_dna.model_dump(
                mode="json"
            ),

        "external_resources":
            list(
                external_resources
            ),
    }

    return sha256_text(
        canonical_json(
            payload
        )
    )


def preserved_v1_cache_path(
) -> Path:
    return (
        initial_run
        .object_dna_run
        .PRIVATE_DIR
        / (
            f"{WALKTHROUGH_ID}"
            "-cannot-safely-solve-critic.json"
        )
    )


def cache_path(
) -> Path:
    return (
        initial_run
        .object_dna_run
        .PRIVATE_DIR
        / (
            f"{WALKTHROUGH_ID}"
            "-cannot-safely-solve-critic-v2.json"
        )
    )


def load_context():
    """
    Reconstruct the exact real W3 planning world and require the
    existing initial PlanOutcome cache to match it.

    This function performs zero model calls.
    """

    walkthrough_id = (
        initial_run
        .configure_walkthrough_context(
            WALKTHROUGH_ID
        )
    )

    (
        _canonical_inventory,
        session_inventory,
        active_items,
        object_dna,
        _canonical_sha256,
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

    planner_sha256 = (
        initial_run
        .planner_pipeline_fingerprint()
    )

    external_resource_state = (
        load_external_resource_state(
            path=(
                initial_run
                .EXTERNAL_RESOURCE_STATE_PATH
            )
        )
    )

    if (
        external_resource_state
        is None
    ):
        external_resources: list[
            str
        ] = []

    else:
        if (
            external_resource_state.goal
            != GOAL
        ):
            raise RuntimeError(
                "Persisted external-resource state "
                "belongs to a different goal."
            )

        external_resources = list(
            external_resource_state
            .resources
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

    active_item_ids = [
        item.id
        for item
        in active_items
    ]

    outcome = (
        initial_run
        .load_matching_cache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=GOAL,
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
                planning_input_sha256
            ),
            active_item_ids=(
                active_item_ids
            ),
        )
    )

    if outcome is None:
        raise RuntimeError(
            "Walkthrough 03 initial PlanOutcome cache "
            "is missing or stale. Refusing to regenerate "
            "the planner result."
        )

    if (
        outcome.status
        != PlanOutcomeStatus
        .CANNOT_SAFELY_SOLVE
    ):
        raise RuntimeError(
            "Walkthrough 03 cached initial outcome is "
            "not CANNOT_SAFELY_SOLVE. This runner must "
            "not be used for another outcome status."
        )

    if outcome.plan is not None:
        raise RuntimeError(
            "CANNOT_SAFELY_SOLVE cache unexpectedly "
            "contains a PhysicalPlan."
        )

    if outcome.requirements:
        raise RuntimeError(
            "CANNOT_SAFELY_SOLVE cache unexpectedly "
            "contains requirements."
        )

    if not outcome.blocking_reasons:
        raise RuntimeError(
            "CANNOT_SAFELY_SOLVE cache contains no "
            "blocking reasons."
        )

    initial_outcome_sha256 = (
        outcome_fingerprint(
            outcome
        )
    )

    audit_input_sha256 = (
        blocker_audit_input_fingerprint(
            goal=GOAL,
            outcome=outcome,
            active_items=(
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

    critic_pipeline_sha256 = (
        critic_pipeline_fingerprint()
    )

    return {
        "walkthrough_id":
            walkthrough_id,

        "active_items":
            active_items,

        "object_dna":
            object_dna,

        "external_resources":
            external_resources,

        "active_item_ids":
            active_item_ids,

        "outcome":
            outcome,

        "planning_input_sha256":
            planning_input_sha256,

        "initial_outcome_sha256":
            initial_outcome_sha256,

        "blocker_audit_input_sha256":
            audit_input_sha256,

        "critic_pipeline_sha256":
            critic_pipeline_sha256,
    }


def load_matching_critic_cache(
    *,
    context,
) -> PlanCriticResult | None:
    path = cache_path()

    if not path.exists():
        return None

    try:
        cache = (
            CannotSafelySolveCriticCache
            .model_validate_json(
                path.read_text(
                    encoding="utf-8"
                )
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing blocker-audit cache is malformed. "
            "Refusing to overwrite evidence until it is "
            f"inspected: {path}"
        ) from exc

    expected = {
        "walkthrough_id":
            context[
                "walkthrough_id"
            ],

        "goal":
            GOAL,

        "planning_input_sha256":
            context[
                "planning_input_sha256"
            ],

        "initial_outcome_sha256":
            context[
                "initial_outcome_sha256"
            ],

        "blocker_audit_input_sha256":
            context[
                "blocker_audit_input_sha256"
            ],

        "critic_pipeline_sha256":
            context[
                "critic_pipeline_sha256"
            ],

        "active_item_ids":
            context[
                "active_item_ids"
            ],
    }

    actual = {
        "walkthrough_id":
            cache.walkthrough_id,

        "goal":
            cache.goal,

        "planning_input_sha256":
            cache.planning_input_sha256,

        "initial_outcome_sha256":
            cache.initial_outcome_sha256,

        "blocker_audit_input_sha256":
            cache.blocker_audit_input_sha256,

        "critic_pipeline_sha256":
            cache.critic_pipeline_sha256,

        "active_item_ids":
            cache.active_item_ids,
    }

    if actual != expected:
        raise RuntimeError(
            "Existing blocker-audit cache does not match "
            "the current W3 evidence or critic pipeline. "
            "Refusing to overwrite stale evidence."
        )

    return cache.critic


def save_cache(
    *,
    context,
    critic: PlanCriticResult,
) -> None:
    path = cache_path()

    cache = (
        CannotSafelySolveCriticCache(
            walkthrough_id=(
                context[
                    "walkthrough_id"
                ]
            ),
            goal=GOAL,
            planning_input_sha256=(
                context[
                    "planning_input_sha256"
                ]
            ),
            initial_outcome_sha256=(
                context[
                    "initial_outcome_sha256"
                ]
            ),
            blocker_audit_input_sha256=(
                context[
                    "blocker_audit_input_sha256"
                ]
            ),
            critic_pipeline_sha256=(
                context[
                    "critic_pipeline_sha256"
                ]
            ),
            active_item_ids=(
                context[
                    "active_item_ids"
                ]
            ),
            critic=critic,
        )
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        path.with_name(
            path.name
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
        path
    )


def print_critic(
    critic: PlanCriticResult,
) -> None:
    print()
    print("=" * 72)
    print(
        "WALKTHROUGH 03 "
        "CANNOT_SAFELY_SOLVE BLOCKER AUDIT"
    )
    print("=" * 72)

    print()
    print(
        f"Passed: {critic.passed}"
    )

    print(
        f"Findings: "
        f"{len(critic.findings)}"
    )

    for index, finding in enumerate(
        critic.findings,
        start=1,
    ):
        print()
        print(
            f"Finding {index}:"
        )
        print(
            f"  severity: "
            f"{finding.severity.value}"
        )
        print(
            f"  issue_type: "
            f"{finding.issue_type.value}"
        )
        print(
            f"  claim: "
            f"{finding.claim}"
        )
        print(
            f"  explanation: "
            f"{finding.explanation}"
        )
        print(
            f"  recommended_fix: "
            f"{finding.recommended_fix}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the already-cached Walkthrough 03 "
            "CANNOT_SAFELY_SOLVE outcome without "
            "rerunning the planner."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate all W3 evidence/cache inputs "
            "without making a model call."
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
            "Maximum newly authorized blocker-critic "
            "model calls. Default 0."
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

    cached_critic = (
        load_matching_critic_cache(
            context=context
        )
    )

    outcome = (
        context[
            "outcome"
        ]
    )

    print("=" * 72)
    print(
        "ZERO WALKTHROUGH 03 "
        "NEGATIVE-OUTCOME AUDIT"
    )
    print("=" * 72)

    print()
    print(
        f"Goal: {GOAL}"
    )

    print()
    print(
        "Cached initial outcome status: "
        f"{outcome.status.value}"
    )

    print(
        "Cached initial outcome plan: "
        f"{'present' if outcome.plan else 'none'}"
    )

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

    print()
    print(
        "Active inventory items: "
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
        "Planning input SHA256: "
        f"{context['planning_input_sha256']}"
    )

    print(
        "Initial outcome SHA256: "
        f"{context['initial_outcome_sha256']}"
    )

    print(
        "Blocker audit input SHA256: "
        f"{context['blocker_audit_input_sha256']}"
    )

    print(
        "Blocker critic pipeline SHA256: "
        f"{context['critic_pipeline_sha256']}"
    )

    print()
    print(
        "Preserved V1 blocker audit: "
        f"{preserved_v1_cache_path().resolve()}"
    )

    print(
        "V2 blocker audit cache: "
        f"{cache_path().resolve()}"
    )

    if (
        cached_critic
        is None
    ):
        print(
            "Blocker audit cache: missing"
        )

    else:
        print(
            "Blocker audit cache: valid"
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
            "Expected new blocker-audit calls "
            "if authorized: "
            f"{0 if cached_critic else 1}"
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
            "Reusing validated blocker-audit cache."
        )

        print(
            "Nemotron calls: 0"
        )

        print_critic(
            cached_critic
        )

        return

    if (
        args.max_new_calls
        < 1
    ):
        raise RuntimeError(
            "Blocker-audit cache is missing. "
            "No new model call is authorized. "
            "Run with --max-new-calls 1 only after "
            "reviewing the dry-run output."
        )

    print()
    print(
        "Running ONE paid "
        "CANNOT_SAFELY_SOLVE blocker audit..."
    )

    # Import lazily so dry runs and cache-only runs
    # do not instantiate the semantic critic client.
    from cannot_safely_solve_critic import (
        audit_cannot_safely_solve_semantics,
    )

    critic = (
        audit_cannot_safely_solve_semantics(
            outcome=outcome,
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

    # Preserve BOTH favorable and unfavorable valid
    # audit results as evidence.
    save_cache(
        context=context,
        critic=critic,
    )

    print()
    print(
        "Nemotron calls: 1"
    )

    print(
        "Saved private blocker-audit cache:"
    )

    print(
        cache_path().resolve()
    )

    print_critic(
        critic
    )

    if not critic.passed:
        print()
        print(
            "RESULT: NEGATIVE OUTCOME NOT CERTIFIED. "
            "The failed critic has been preserved. "
            "Do not rerun or overwrite it."
        )

    else:
        print()
        print(
            "RESULT: CANNOT_SAFELY_SOLVE blockers "
            "passed semantic grounding."
        )


if __name__ == "__main__":
    main()