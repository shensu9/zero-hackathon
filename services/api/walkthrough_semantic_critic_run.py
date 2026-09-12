import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from critic_schemas import (
    PlanCriticResult,
)
from plan_validator import (
    PlanValidationError,
    validate_zero_plan,
)
from semantic_critic import (
    audit_plan_semantics,
)
from walkthrough_goal_relevance_run import (
    GOAL,
)
from walkthrough_plan_repair_run import (
    CACHE_PATH as REPAIR_CACHE_PATH,
    PlanRepairCache,
    load_context,
    normalize_plan,
    repair_pipeline_fingerprint,
)


CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-critic-after-repair-01.json"
)


SEMANTIC_PIPELINE_FILES = (
    "semantic_critic.py",
    "critic_schemas.py",
    "plan_schemas.py",
    "schemas.py",
    "model_json.py",
)


class SemanticCriticCache(BaseModel):
    """
    Cache for the semantic physical audit of the deterministically validated
    repaired plan.

    This critic result is not, by itself, the final ZERO outcome.
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


def semantic_pipeline_fingerprint() -> str:
    """
    Bind the semantic-critic cache to the exact semantic-audit code and
    schemas.

    If the critic prompt/model/parsing/schema changes, the old audit becomes
    stale automatically.
    """

    digest = hashlib.sha256()

    base_dir = Path(__file__).resolve().parent

    for filename in SEMANTIC_PIPELINE_FILES:
        path = base_dir / filename

        if not path.exists():
            raise RuntimeError(
                "Required semantic-critic pipeline file was not found: "
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


def load_repaired_plan_context():
    """
    Load the current real planning world plus repair-attempt-1 cache.

    Re-run deterministic plan validation locally before allowing semantic
    auditing.

    No model calls occur here.
    """

    (
        active_items,
        object_dna,
        external_resources,
        active_item_ids,
        planning_input_sha256,
        _initial_outcome,
    ) = load_context()

    if not REPAIR_CACHE_PATH.exists():
        raise RuntimeError(
            "Plan-repair attempt-1 cache was not found: "
            f"{REPAIR_CACHE_PATH}"
        )

    try:
        payload = json.loads(
            REPAIR_CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        repair_cache = (
            PlanRepairCache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Plan-repair attempt-1 cache is invalid."
        ) from exc

    if repair_cache.goal != GOAL:
        raise RuntimeError(
            "Plan-repair cache belongs to a different goal."
        )

    if (
        repair_cache.planning_input_sha256
        != planning_input_sha256
    ):
        raise RuntimeError(
            "Plan-repair cache belongs to a different planning input."
        )

    current_repair_pipeline_sha256 = (
        repair_pipeline_fingerprint()
    )

    if (
        repair_cache.repair_pipeline_sha256
        != current_repair_pipeline_sha256
    ):
        raise RuntimeError(
            "Plan-repair cache was produced under a different "
            "repair pipeline."
        )

    normalized_repaired_plan = normalize_plan(
        plan=repair_cache.repaired_plan,
        external_resources=external_resources,
    )

    try:
        validated_plan = validate_zero_plan(
            normalized_repaired_plan,
            object_dna,
            set(active_item_ids),
        )

    except PlanValidationError as exc:
        raise RuntimeError(
            "Cached repaired plan no longer passes deterministic "
            f"validation: {exc}"
        ) from exc

    repaired_plan_sha256 = sha256_payload(
        validated_plan.model_dump(
            mode="json"
        )
    )

    return (
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        repaired_plan_sha256,
        validated_plan,
    )


def load_matching_cache(
    *,
    planning_input_sha256: str,
    repaired_plan_sha256: str,
    semantic_pipeline_sha256: str,
) -> PlanCriticResult | None:
    """
    Reuse the semantic critic only when its exact plan, world-input, and
    critic implementation fingerprints match.
    """

    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cache = SemanticCriticCache.model_validate(
            payload
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing semantic-critic cache is invalid. "
            "Refusing to overwrite it with another paid audit until "
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
        cache.repaired_plan_sha256
        != repaired_plan_sha256
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
    planning_input_sha256: str,
    repaired_plan_sha256: str,
    semantic_pipeline_sha256: str,
    critic: PlanCriticResult,
) -> None:
    """
    Persist one successful semantic-audit result atomically.
    """

    cache = SemanticCriticCache(
        goal=GOAL,
        planning_input_sha256=planning_input_sha256,
        repaired_plan_sha256=repaired_plan_sha256,
        semantic_pipeline_sha256=semantic_pipeline_sha256,
        critic=critic,
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


def print_critic(
    critic: PlanCriticResult,
) -> None:
    print()
    print("=" * 72)
    print("SEMANTIC PHYSICAL AUDIT RESULT")
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
            "The repaired plan passed the semantic physical audit."
        )

    else:
        print(
            "The repaired plan requires another bounded repair "
            "before it can continue."
        )

    print()

    print(
        "Verification-gate processing and final semantic recheck "
        "have NOT been run yet."
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the repaired-plan context and inspect critic-cache "
            "status without making a model call."
        ),
    )

    parser.add_argument(
        "--max-new-audits",
        type=int,
        default=0,
        choices=[0, 1],
        help=(
            "Maximum new semantic-audit invocations allowed. "
            "One audit normally uses one model call, but may use one "
            "additional formatting-only repair call if JSON is malformed. "
            "Default 0."
        ),
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and args.max_new_audits != 0
    ):
        parser.error(
            "--dry-run cannot authorize a semantic audit."
        )

    print("=" * 72)
    print("ZERO WALKTHROUGH SEMANTIC CRITIC — AFTER REPAIR 1")
    print("=" * 72)

    (
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        repaired_plan_sha256,
        validated_plan,
    ) = load_repaired_plan_context()

    semantic_sha256 = (
        semantic_pipeline_fingerprint()
    )

    cached_critic = load_matching_cache(
        planning_input_sha256=planning_input_sha256,
        repaired_plan_sha256=repaired_plan_sha256,
        semantic_pipeline_sha256=semantic_sha256,
    )

    print()
    print(
        f"Planning input SHA-256: "
        f"{planning_input_sha256}"
    )

    print(
        f"Validated repaired-plan SHA-256: "
        f"{repaired_plan_sha256}"
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

    if cached_critic is None:
        print(
            "Semantic-critic cache: missing/stale"
        )

    else:
        print(
            "Semantic-critic cache: valid"
        )

    if args.dry_run:
        print()
        print(
            "DRY RUN COMPLETE — NO MODEL CALL MADE"
        )

        if cached_critic is not None:
            print_critic(
                cached_critic
            )

        return

    if cached_critic is not None:
        print()
        print(
            "Reusing validated semantic-critic cache."
        )

        print(
            "New semantic audit invocations: 0"
        )

        print_critic(
            cached_critic
        )

        return

    if args.max_new_audits == 0:
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

    critic = audit_plan_semantics(
        plan=validated_plan,
        goal=GOAL,
        inventory=active_items,
        object_dna=object_dna,
        external_resources=external_resources,
    )

    save_cache(
        planning_input_sha256=planning_input_sha256,
        repaired_plan_sha256=repaired_plan_sha256,
        semantic_pipeline_sha256=semantic_sha256,
        critic=critic,
    )

    print()
    print(
        "Semantic critic schema-valid and cached."
    )

    print(
        "New semantic audit invocations: 1"
    )

    print(
        "Saved private semantic-critic cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_critic(
        critic
    )


if __name__ == "__main__":
    main()