import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel, Field

import semantic_critic

from critic_schemas import (
    PlanCriticResult,
)
from plan_outcome_pipeline import (
    _audit_outcome_plan,
)
from walkthrough_final_semantic_critic_run import (
    load_post_gate_context,
)
from walkthrough_goal_relevance_run import (
    GOAL,
)
from walkthrough_plan_repair_run_02 import (
    CACHE_PATH as _unused_repair_cache_alias,
)
from walkthrough_semantic_critic_run import (
    semantic_pipeline_fingerprint,
)

import walkthrough_final_semantic_critic_run as final_base
import walkthrough_plan_repair_run_02 as repair02_base
import walkthrough_semantic_critic_run as semantic_base
import walkthrough_verification_gate_run as gate_base


RUN_ID = "repair-closure-v5"

POLICY_VERSION = (
    "semantic-coverage-empty-group-compat-v1"
)

V2_REPAIR_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-01.json"
)

V5_SEMANTIC_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-closure-v5-"
    "semantic-critic-after-repair-01.json"
)

V5_REPAIR_02_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-closure-v5-"
    "plan-repair-attempt-02.json"
)

V5_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-closure-v5-"
    "verification-gate-after-repair-02.json"
)

STANDARD_V5_FINAL_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-closure-v5-"
    "final-semantic-critic.json"
)

CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-repair-closure-v5-"
    "final-semantic-critic-coverage-compat-retry-01.json"
)


# These are redundant GROUP labels only.
#
# They may be discarded only when:
# - every exact required field ID is already present, AND
# - the redundant key has no finding references.
#
# They never substitute for indexed exact fields such as:
# assumption:1
# risk:1
# constraint:1
ALLOWED_EMPTY_GROUP_KEYS = frozenset(
    {
        "assumption",
        "assumptions",
        "risk",
        "risks",
        "unresolved_risk",
        "unresolved_risks",
        "constraint_check",
        "constraint_checks",
    }
)


class CoverageCompatibilityRetryCache(
    BaseModel
):
    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    planning_input_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    gate_output_outcome_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    semantic_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    compatibility_policy_sha256: str = Field(
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


def compatibility_policy_fingerprint(
    *,
    semantic_pipeline_sha256: str,
) -> str:
    digest = hashlib.sha256()

    digest.update(
        POLICY_VERSION.encode(
            "utf-8"
        )
    )

    digest.update(
        b"\0"
    )

    digest.update(
        semantic_pipeline_sha256.encode(
            "utf-8"
        )
    )

    digest.update(
        b"\0"
    )

    for key in sorted(
        ALLOWED_EMPTY_GROUP_KEYS
    ):
        digest.update(
            key.encode(
                "utf-8"
            )
        )

        digest.update(
            b"\0"
        )

    digest.update(
        Path(__file__).read_bytes()
    )

    return digest.hexdigest()


def configure_v5_context() -> None:
    """
    Point the generic walkthrough loaders at the exact V5 cache chain.
    """

    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    repair02_base.SEMANTIC_CACHE_PATH = (
        V5_SEMANTIC_01_CACHE
    )

    gate_base.REPAIR_02_CACHE_PATH = (
        V5_REPAIR_02_CACHE
    )

    final_base.GATE_CACHE_PATH = (
        V5_GATE_CACHE
    )

    final_base.CACHE_PATH = (
        STANDARD_V5_FINAL_CACHE
    )


def load_matching_cache(
    *,
    planning_input_sha256: str,
    gate_output_outcome_sha256: str,
    semantic_pipeline_sha256: str,
    compatibility_policy_sha256: str,
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
            CoverageCompatibilityRetryCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing V5 coverage-compatibility "
            "retry cache is invalid. "
            f"Refusing to overwrite: {CACHE_PATH}"
        ) from exc

    if cache.goal != GOAL:
        return None

    if (
        cache.planning_input_sha256
        != planning_input_sha256
    ):
        return None

    if (
        cache.gate_output_outcome_sha256
        != gate_output_outcome_sha256
    ):
        return None

    if (
        cache.semantic_pipeline_sha256
        != semantic_pipeline_sha256
    ):
        return None

    if (
        cache.compatibility_policy_sha256
        != compatibility_policy_sha256
    ):
        return None

    return cache.critic


def save_cache(
    *,
    planning_input_sha256: str,
    gate_output_outcome_sha256: str,
    semantic_pipeline_sha256: str,
    compatibility_policy_sha256: str,
    critic: PlanCriticResult,
) -> None:
    cache = CoverageCompatibilityRetryCache(
        goal=GOAL,
        planning_input_sha256=(
            planning_input_sha256
        ),
        gate_output_outcome_sha256=(
            gate_output_outcome_sha256
        ),
        semantic_pipeline_sha256=(
            semantic_pipeline_sha256
        ),
        compatibility_policy_sha256=(
            compatibility_policy_sha256
        ),
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


def build_compatibility_validator():
    """
    Return a narrowly scoped wrapper around the production exact
    semantic-coverage validator.

    This does NOT relax missing-field checks.

    Compatibility is applied only when every exact required field
    already exists.

    Recognized redundant aggregate keys may then be removed only if
    their reference list is empty.

    Any:
    - missing required field
    - unknown extra key
    - non-empty redundant aggregate key
    still fails through the production validator.
    """

    original_validate = (
        semantic_critic
        ._validate_semantic_coverage
    )

    def compatibility_validate(
        *,
        envelope,
        required_field_ids,
    ):
        expected = set(
            required_field_ids
        )

        coverage = dict(
            envelope.coverage
        )

        actual = set(
            coverage.keys()
        )

        missing = (
            expected - actual
        )

        # If anything required is missing, do not normalize anything.
        # Let the production exact validator reject the response.
        if missing:
            return original_validate(
                envelope=envelope,
                required_field_ids=(
                    required_field_ids
                ),
            )

        extras = sorted(
            actual - expected
        )

        removed: list[str] = []

        for key in extras:
            if (
                key
                not in ALLOWED_EMPTY_GROUP_KEYS
            ):
                continue

            references = coverage[
                key
            ]

            if references:
                # Non-empty redundant key is semantically meaningful
                # and therefore must NOT be silently discarded.
                continue

            del coverage[
                key
            ]

            removed.append(
                key
            )

        if removed:
            print(
                "Coverage compatibility removed "
                "redundant empty aggregate key(s): "
                + ", ".join(
                    removed
                )
            )

        normalized_envelope = (
            envelope.model_copy(
                update={
                    "coverage":
                        coverage,
                }
            )
        )

        # Production validator remains authoritative.
        return original_validate(
            envelope=normalized_envelope,
            required_field_ids=(
                required_field_ids
            ),
        )

    return compatibility_validate


def run_compatibility_retry(
    *,
    outcome,
    active_items,
    object_dna,
    external_resources,
):
    """
    Run one normal semantic audit.

    The semantic prompt, model, token ceiling, findings schema, and
    grounding rules remain unchanged.

    Only the post-response deterministic coverage validator gets the
    narrow empty-aggregate compatibility rule.
    """

    original_create = (
        semantic_critic
        .client
        .chat
        .completions
        .create
    )

    model_call_count = 0

    def counted_create(
        *args,
        **kwargs,
    ):
        nonlocal model_call_count

        model_call_count += 1

        return original_create(
            *args,
            **kwargs,
        )

    compatibility_validate = (
        build_compatibility_validator()
    )

    with (
        patch.object(
            semantic_critic,
            "_validate_semantic_coverage",
            new=compatibility_validate,
        ),
        patch.object(
            semantic_critic
            .client
            .chat
            .completions,
            "create",
            side_effect=counted_create,
        ),
    ):
        critic = _audit_outcome_plan(
            outcome=outcome,
            goal=GOAL,
            inventory=active_items,
            object_dna=object_dna,
            external_resources=(
                external_resources
            ),
        )

    return (
        critic,
        model_call_count,
    )


def print_critic(
    critic: PlanCriticResult,
) -> None:
    print()
    print("=" * 72)
    print(
        "V5 FINAL SEMANTIC COVERAGE-COMPATIBILITY RESULT"
    )
    print("=" * 72)

    print()
    print(
        f"Passed: {critic.passed}"
    )

    print(
        f"Findings: {len(critic.findings)}"
    )

    for index, finding in enumerate(
        critic.findings,
        start=1,
    ):
        print()

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

    if critic.passed:
        print(
            "TERMINAL SEMANTIC BOUNDARY: PASSED"
        )
    else:
        print(
            "TERMINAL SEMANTIC BOUNDARY: FAILED"
        )

        print(
            "Repair budget remains exhausted at 2 of 2."
        )

        print(
            "No further plan repair is permitted."
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "--max-new-retries",
        type=int,
        default=0,
        choices=[
            0,
            1,
        ],
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and args.max_new_retries != 0
    ):
        parser.error(
            "--dry-run cannot authorize a paid retry."
        )

    configure_v5_context()

    print("=" * 72)
    print(
        "ZERO V5 FINAL SEMANTIC "
        "COVERAGE-COMPATIBILITY RETRY"
    )
    print("=" * 72)

    print()
    print(
        "Previous final-audit result:"
    )

    print(
        "all exact required fields were present, "
        "but redundant aggregate coverage keys "
        "'assumption' and 'constraint_check' "
        "caused exact-accounting rejection."
    )

    print()
    print(
        "Compatibility policy:"
    )

    print(
        "only recognized EMPTY aggregate keys may "
        "be removed, and only when no exact field is missing."
    )

    print()

    (
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        gate_output_outcome_sha256,
        outcome,
    ) = load_post_gate_context()

    semantic_sha256 = (
        semantic_pipeline_fingerprint()
    )

    policy_sha256 = (
        compatibility_policy_fingerprint(
            semantic_pipeline_sha256=(
                semantic_sha256
            ),
        )
    )

    cached_critic = (
        load_matching_cache(
            planning_input_sha256=(
                planning_input_sha256
            ),
            gate_output_outcome_sha256=(
                gate_output_outcome_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_sha256
            ),
            compatibility_policy_sha256=(
                policy_sha256
            ),
        )
    )

    print(
        f"Outcome status: "
        f"{outcome.status.value}"
    )

    print(
        f"Plan title: "
        f"{outcome.plan.title}"
    )

    print(
        f"Plan steps: "
        f"{len(outcome.plan.steps)}"
    )

    print(
        f"Planning input SHA-256: "
        f"{planning_input_sha256}"
    )

    print(
        f"Post-gate outcome SHA-256: "
        f"{gate_output_outcome_sha256}"
    )

    print(
        f"Semantic pipeline SHA-256: "
        f"{semantic_sha256}"
    )

    print(
        f"Compatibility policy SHA-256: "
        f"{policy_sha256}"
    )

    print()

    if STANDARD_V5_FINAL_CACHE.exists():
        print(
            "Standard V5 final cache exists."
        )
    else:
        print(
            "Standard V5 final cache: absent"
        )

    if cached_critic is None:
        print(
            "Compatibility-retry cache: missing/stale"
        )
    else:
        print(
            "Compatibility-retry cache: valid"
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
            "Reusing validated compatibility-retry cache."
        )

        print(
            "New model calls: 0"
        )

        print_critic(
            cached_critic
        )

        return

    if args.max_new_retries == 0:
        print()
        print(
            "No paid compatibility retry authorized "
            "(--max-new-retries is 0)."
        )

        return

    print()
    print(
        "Running ONE final semantic "
        "coverage-compatibility retry..."
    )

    print(
        "No plan repair is permitted."
    )

    (
        critic,
        model_call_count,
    ) = run_compatibility_retry(
        outcome=outcome,
        active_items=active_items,
        object_dna=object_dna,
        external_resources=(
            external_resources
        ),
    )

    save_cache(
        planning_input_sha256=(
            planning_input_sha256
        ),
        gate_output_outcome_sha256=(
            gate_output_outcome_sha256
        ),
        semantic_pipeline_sha256=(
            semantic_sha256
        ),
        compatibility_policy_sha256=(
            policy_sha256
        ),
        critic=critic,
    )

    print()
    print(
        "Coverage-compatibility result "
        "schema-valid and cached."
    )

    print(
        f"Model calls during retry: "
        f"{model_call_count}"
    )

    print(
        "Saved private retry cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_critic(
        critic
    )


if __name__ == "__main__":
    main()