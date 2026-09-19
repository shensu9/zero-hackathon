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
import walkthrough_04_initial_plan_outcome_run as w4_run


WALKTHROUGH_ID = "walkthrough-04"

EXPECTED_INITIAL_CACHE_SHA256 = (
    "1e1a9c8fa6b8f544f6d29f28477bbe48"
    "2f448e4db3c00f1e22f2d357dbe37886"
)

EXPECTED_PLANNING_INPUT_SHA256 = (
    "4b8c0d7b0e328693644432f13430d3a5"
    "122331a9852080900a4b1e7701b86a67"
)

EXPECTED_INITIAL_OUTCOME_SHA256 = (
    "59500a819fa3c0a09e459470d09c5821"
    "2794826b1a12be1266e60a038ecf4e0e"
)

CRITIC_PIPELINE_FILES = (
    "needs_confirmation_critic.py",
    "semantic_critic.py",
    "critic_schemas.py",
    "plan_outcome_schemas.py",
    "model_json.py",
    "schemas.py",
)


CACHE_PATH = (
    w4_run
    .initial_run
    .object_dna_run
    .PRIVATE_DIR
    / (
        f"{WALKTHROUGH_ID}"
        "-needs-confirmation-critic.json"
    )
)


class W4NeedsConfirmationCriticCache(
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

    initial_cache_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    initial_outcome_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    confirmation_audit_input_sha256: str = Field(
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


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
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


def confirmation_audit_input_fingerprint(
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


def critic_pipeline_fingerprint(
) -> str:
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
                "Missing NEEDS_CONFIRMATION critic "
                f"pipeline file: {path}"
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


def load_context():
    """
    Reconstruct the exact W4 planning context and require
    the preserved initial NEEDS_CONFIRMATION result.

    Zero model calls occur here.
    """

    context = (
        w4_run.load_context()
    )

    initial_cache_path = (
        w4_run.CACHE_PATH
    )

    if not initial_cache_path.exists():
        raise RuntimeError(
            "W4 initial planning cache is missing. "
            "Refusing to rerun the planner."
        )

    initial_cache_sha256 = (
        sha256_file(
            initial_cache_path
        )
    )

    if (
        initial_cache_sha256
        != EXPECTED_INITIAL_CACHE_SHA256
    ):
        raise RuntimeError(
            "W4 initial planning cache changed. "
            f"Expected {EXPECTED_INITIAL_CACHE_SHA256}, "
            f"got {initial_cache_sha256}."
        )

    outcome = (
        w4_run.load_matching_cache(
            context=context
        )
    )

    if outcome is None:
        raise RuntimeError(
            "W4 initial PlanOutcome cache is stale "
            "or does not match the frozen source world."
        )

    if (
        context[
            "planning_input_sha256"
        ]
        != EXPECTED_PLANNING_INPUT_SHA256
    ):
        raise RuntimeError(
            "W4 planning input changed. "
            f"Expected {EXPECTED_PLANNING_INPUT_SHA256}, "
            f"got {context['planning_input_sha256']}."
        )

    if (
        outcome.status
        != PlanOutcomeStatus
        .NEEDS_CONFIRMATION
    ):
        raise RuntimeError(
            "W4 cached initial outcome is not "
            "NEEDS_CONFIRMATION."
        )

    if outcome.plan is not None:
        raise RuntimeError(
            "W4 NEEDS_CONFIRMATION outcome "
            "unexpectedly contains a plan."
        )

    if not outcome.requirements:
        raise RuntimeError(
            "W4 NEEDS_CONFIRMATION outcome "
            "contains no requirements."
        )

    if outcome.blocking_reasons:
        raise RuntimeError(
            "W4 NEEDS_CONFIRMATION outcome "
            "unexpectedly contains blocking reasons."
        )

    initial_outcome_sha256 = (
        outcome_fingerprint(
            outcome
        )
    )

    if (
        initial_outcome_sha256
        != EXPECTED_INITIAL_OUTCOME_SHA256
    ):
        raise RuntimeError(
            "W4 initial outcome changed. "
            f"Expected {EXPECTED_INITIAL_OUTCOME_SHA256}, "
            f"got {initial_outcome_sha256}."
        )

    audit_input_sha256 = (
        confirmation_audit_input_fingerprint(
            goal=w4_run.GOAL,
            outcome=outcome,
            active_items=(
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

    critic_pipeline_sha256 = (
        critic_pipeline_fingerprint()
    )

    return {
        **context,

        "outcome":
            outcome,

        "initial_cache_sha256":
            initial_cache_sha256,

        "initial_outcome_sha256":
            initial_outcome_sha256,

        "confirmation_audit_input_sha256":
            audit_input_sha256,

        "critic_pipeline_sha256":
            critic_pipeline_sha256,
    }


def load_matching_cache(
    *,
    context,
) -> PlanCriticResult | None:
    if not CACHE_PATH.exists():
        return None

    try:
        cache = (
            W4NeedsConfirmationCriticCache
            .model_validate_json(
                CACHE_PATH.read_text(
                    encoding="utf-8"
                )
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing W4 confirmation-audit cache "
            "is malformed. Refusing to overwrite "
            f"evidence until inspected: {CACHE_PATH}"
        ) from exc

    expected = {
        "walkthrough_id":
            WALKTHROUGH_ID,

        "goal":
            w4_run.GOAL,

        "planning_input_sha256":
            context[
                "planning_input_sha256"
            ],

        "initial_cache_sha256":
            context[
                "initial_cache_sha256"
            ],

        "initial_outcome_sha256":
            context[
                "initial_outcome_sha256"
            ],

        "confirmation_audit_input_sha256":
            context[
                "confirmation_audit_input_sha256"
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

        "initial_cache_sha256":
            cache.initial_cache_sha256,

        "initial_outcome_sha256":
            cache.initial_outcome_sha256,

        "confirmation_audit_input_sha256":
            cache.confirmation_audit_input_sha256,

        "critic_pipeline_sha256":
            cache.critic_pipeline_sha256,

        "active_item_ids":
            cache.active_item_ids,
    }

    if actual != expected:
        raise RuntimeError(
            "Existing W4 confirmation-audit cache "
            "does not match the current frozen evidence "
            "or critic pipeline. Refusing to overwrite it."
        )

    return cache.critic


def save_cache(
    *,
    context,
    critic: PlanCriticResult,
) -> None:
    cache = (
        W4NeedsConfirmationCriticCache(
            walkthrough_id=(
                WALKTHROUGH_ID
            ),

            goal=(
                w4_run.GOAL
            ),

            planning_input_sha256=(
                context[
                    "planning_input_sha256"
                ]
            ),

            initial_cache_sha256=(
                context[
                    "initial_cache_sha256"
                ]
            ),

            initial_outcome_sha256=(
                context[
                    "initial_outcome_sha256"
                ]
            ),

            confirmation_audit_input_sha256=(
                context[
                    "confirmation_audit_input_sha256"
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
        "WALKTHROUGH 04 "
        "NEEDS_CONFIRMATION AUDIT"
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
            "Audit the preserved Walkthrough 04 "
            "NEEDS_CONFIRMATION outcome without "
            "rerunning its planner."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",

        help=(
            "Validate W4 evidence and cache state "
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
            "Maximum newly authorized confirmation-"
            "critic calls. Default 0."
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
        load_matching_cache(
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
        "ZERO WALKTHROUGH 04 "
        "CONFIRMATION-OUTCOME AUDIT"
    )

    print("=" * 72)

    print()
    print(
        f"Goal: {w4_run.GOAL}"
    )

    print()
    print(
        "Cached initial status: "
        f"{outcome.status.value}"
    )

    print(
        "Cached initial plan: "
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
        "Initial cache SHA256: "
        f"{context['initial_cache_sha256']}"
    )

    print(
        "Initial outcome SHA256: "
        f"{context['initial_outcome_sha256']}"
    )

    print(
        "Confirmation audit input SHA256: "
        f"{context['confirmation_audit_input_sha256']}"
    )

    print(
        "Confirmation critic pipeline SHA256: "
        f"{context['critic_pipeline_sha256']}"
    )

    print()
    print(
        "Confirmation audit cache: "
        f"{CACHE_PATH.resolve()}"
    )

    if cached_critic is None:
        print(
            "Confirmation audit cache: missing"
        )
    else:
        print(
            "Confirmation audit cache: valid"
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
            "Expected new confirmation-audit "
            "calls if authorized: "
            f"{0 if cached_critic else 1}"
        )

        if cached_critic is not None:
            print_critic(
                cached_critic
            )

        return

    if cached_critic is not None:
        print()
        print(
            "Reusing validated W4 "
            "confirmation-audit cache."
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
            "W4 confirmation-audit cache is missing. "
            "No new model call is authorized. "
            "Run with --max-new-calls 1 only after "
            "reviewing the dry-run output."
        )

    print()
    print(
        "Running ONE paid NEEDS_CONFIRMATION "
        "semantic audit..."
    )

    # Lazy import so dry-run/cache-only execution
    # cannot instantiate the semantic critic client.
    from needs_confirmation_critic import (
        audit_needs_confirmation_semantics,
    )

    critic = (
        audit_needs_confirmation_semantics(
            outcome=outcome,

            goal=(
                w4_run.GOAL
            ),

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

    # Preserve favorable and unfavorable valid
    # audit results equally.
    save_cache(
        context=context,
        critic=critic,
    )

    print()
    print(
        "Nemotron calls: 1"
    )

    print(
        "Saved private W4 confirmation-audit cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_critic(
        critic
    )

    if critic.passed:
        print()
        print(
            "RESULT: NEEDS_CONFIRMATION "
            "passed semantic grounding."
        )

    else:
        print()
        print(
            "RESULT: NEEDS_CONFIRMATION NOT CERTIFIED. "
            "The failed critic has been preserved. "
            "Do not rerun or overwrite it."
        )


if __name__ == "__main__":
    main()