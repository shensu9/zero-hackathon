import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel, Field

from plan_outcome_pipeline import (
    _make_verification_gate_safe,
    _replace_plan,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from plan_validator import (
    PlanValidationError,
    validate_zero_plan,
)
from verification_gate_schemas import (
    VerificationGateAudit,
)
from walkthrough_goal_relevance_run import (
    GOAL,
)
from walkthrough_plan_repair_run import (
    load_context,
    normalize_plan,
    repair_pipeline_fingerprint,
)
from walkthrough_plan_repair_run_02 import (
    CACHE_PATH as REPAIR_02_CACHE_PATH,
    PlanRepairAttempt02Cache,
    load_semantic_failure_context,
    sha256_payload,
)


CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-verification-gate-after-repair-02.json"
)


GATE_PIPELINE_FILES = (
    "plan_outcome_pipeline.py",
    "verification_gate_auditor.py",
    "verification_gate_repair.py",
    "verification_gate_schemas.py",
    "plan_outcome_schemas.py",
)


class VerificationGateStageCache(BaseModel):
    """
    Cached verification-gate result after the second and final plan repair.

    For this walkthrough the outcome is SOLVED, so production verification
    gating must short-circuit locally with:
        passed=True
        findings=[]
        gate_repair_attempts=0

    No model call is permitted in this stage.
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

    input_outcome_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    gate_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    output_outcome: PlanOutcome

    audit: VerificationGateAudit

    gate_repair_attempts: int = Field(
        ge=0,
        le=1,
    )


def canonical_json(
    payload,
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def fingerprint_payload(
    payload,
) -> str:
    return hashlib.sha256(
        canonical_json(
            payload
        ).encode("utf-8")
    ).hexdigest()


def gate_pipeline_fingerprint() -> str:
    """
    Bind the cache to the exact production verification-gate implementation.
    """

    digest = hashlib.sha256()

    base_dir = Path(__file__).resolve().parent

    for filename in GATE_PIPELINE_FILES:
        path = base_dir / filename

        if not path.exists():
            raise RuntimeError(
                "Required verification-gate pipeline file was not found: "
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


def load_final_repaired_context():
    """
    Reconstruct the exact current world and validate repair attempt 2.

    No model calls occur here.
    """

    (
        active_items,
        object_dna,
        external_resources,
        active_item_ids,
        planning_input_sha256,
        initial_outcome,
    ) = load_context()

    (
        _semantic_active_items,
        _semantic_object_dna,
        _semantic_external_resources,
        semantic_planning_input_sha256,
        source_plan_sha256,
        _source_plan,
        semantic_pipeline_sha256,
        semantic_critic,
    ) = load_semantic_failure_context()

    if (
        semantic_planning_input_sha256
        != planning_input_sha256
    ):
        raise RuntimeError(
            "Semantic-repair context planning input no longer matches "
            "the current planning context."
        )

    if not REPAIR_02_CACHE_PATH.exists():
        raise RuntimeError(
            "Repair-attempt-2 cache was not found: "
            f"{REPAIR_02_CACHE_PATH}"
        )

    try:
        payload = json.loads(
            REPAIR_02_CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        repair_cache = (
            PlanRepairAttempt02Cache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Repair-attempt-2 cache is invalid."
        ) from exc

    if repair_cache.goal != GOAL:
        raise RuntimeError(
            "Repair-attempt-2 cache belongs to a different goal."
        )

    if (
        repair_cache.planning_input_sha256
        != planning_input_sha256
    ):
        raise RuntimeError(
            "Repair-attempt-2 cache belongs to a different "
            "planning input."
        )

    if (
        repair_cache.source_plan_sha256
        != source_plan_sha256
    ):
        raise RuntimeError(
            "Repair-attempt-2 cache belongs to a different "
            "source plan."
        )

    if (
        repair_cache.semantic_pipeline_sha256
        != semantic_pipeline_sha256
    ):
        raise RuntimeError(
            "Repair-attempt-2 cache belongs to a different "
            "semantic pipeline."
        )

    current_semantic_critic_sha256 = (
        sha256_payload(
            semantic_critic.model_dump(
                mode="json"
            )
        )
    )

    if (
        repair_cache.semantic_critic_sha256
        != current_semantic_critic_sha256
    ):
        raise RuntimeError(
            "Repair-attempt-2 cache belongs to a different "
            "semantic critic."
        )

    current_repair_pipeline_sha256 = (
        repair_pipeline_fingerprint()
    )

    if (
        repair_cache.repair_pipeline_sha256
        != current_repair_pipeline_sha256
    ):
        raise RuntimeError(
            "Repair-attempt-2 cache was produced under a different "
            "repair pipeline."
        )

    normalized_plan = normalize_plan(
        plan=repair_cache.repaired_plan,
        external_resources=external_resources,
    )

    try:
        validated_plan = validate_zero_plan(
            normalized_plan,
            object_dna,
            set(active_item_ids),
        )

    except PlanValidationError as exc:
        raise RuntimeError(
            "Repair-attempt-2 plan no longer passes deterministic "
            f"validation: {exc}"
        ) from exc

    repaired_plan_sha256 = (
        sha256_payload(
            validated_plan.model_dump(
                mode="json"
            )
        )
    )

    outcome_with_final_plan = _replace_plan(
        outcome=initial_outcome,
        plan=validated_plan,
    )

    if (
        outcome_with_final_plan.status
        != PlanOutcomeStatus.SOLVED
    ):
        raise RuntimeError(
            "Current walkthrough outcome is no longer SOLVED. "
            "Refusing to invoke verification gating because a "
            "CONDITIONAL path could require a model call."
        )

    if outcome_with_final_plan.requirements:
        raise RuntimeError(
            "SOLVED walkthrough outcome unexpectedly contains "
            "verification requirements."
        )

    input_outcome_sha256 = (
        fingerprint_payload(
            outcome_with_final_plan.model_dump(
                mode="json"
            )
        )
    )

    return (
        active_items,
        external_resources,
        planning_input_sha256,
        repaired_plan_sha256,
        input_outcome_sha256,
        outcome_with_final_plan,
    )


def load_matching_cache(
    *,
    planning_input_sha256: str,
    repaired_plan_sha256: str,
    input_outcome_sha256: str,
    gate_pipeline_sha256: str,
) -> VerificationGateStageCache | None:
    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cache = (
            VerificationGateStageCache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing verification-gate cache is invalid: "
            f"{CACHE_PATH}"
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
        cache.input_outcome_sha256
        != input_outcome_sha256
    ):
        return None

    if (
        cache.gate_pipeline_sha256
        != gate_pipeline_sha256
    ):
        return None

    return cache


def save_cache(
    *,
    planning_input_sha256: str,
    repaired_plan_sha256: str,
    input_outcome_sha256: str,
    gate_pipeline_sha256: str,
    output_outcome: PlanOutcome,
    audit: VerificationGateAudit,
    gate_repair_attempts: int,
) -> None:
    cache = VerificationGateStageCache(
        goal=GOAL,
        planning_input_sha256=planning_input_sha256,
        repaired_plan_sha256=repaired_plan_sha256,
        input_outcome_sha256=input_outcome_sha256,
        gate_pipeline_sha256=gate_pipeline_sha256,
        output_outcome=output_outcome,
        audit=audit,
        gate_repair_attempts=gate_repair_attempts,
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


def run_production_gate_without_network(
    *,
    outcome: PlanOutcome,
    active_items,
    external_resources: list[str],
):
    """
    Invoke the exact production gate helper while physically blocking any
    model request.

    For a SOLVED outcome, audit_verification_gates() must return locally
    before touching the model client.

    If that behavior ever changes, this stage fails instead of spending
    credits.
    """

    with patch(
        "verification_gate_auditor.client.chat.completions.create",
        side_effect=RuntimeError(
            "NETWORK MODEL CALL BLOCKED: "
            "verification gate was expected to short-circuit locally."
        ),
    ):
        return _make_verification_gate_safe(
            outcome=outcome,
            inventory=active_items,
            external_resources=external_resources,
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the full gate input and cache state without "
            "invoking the production gate helper."
        ),
    )

    args = parser.parse_args()

    print("=" * 72)
    print("ZERO WALKTHROUGH VERIFICATION GATE — AFTER REPAIR 2")
    print("=" * 72)

    (
        active_items,
        external_resources,
        planning_input_sha256,
        repaired_plan_sha256,
        input_outcome_sha256,
        outcome,
    ) = load_final_repaired_context()

    gate_sha256 = (
        gate_pipeline_fingerprint()
    )

    cached = load_matching_cache(
        planning_input_sha256=planning_input_sha256,
        repaired_plan_sha256=repaired_plan_sha256,
        input_outcome_sha256=input_outcome_sha256,
        gate_pipeline_sha256=gate_sha256,
    )

    print()
    print(
        f"Outcome status: "
        f"{outcome.status.value}"
    )

    print(
        f"Requirements: "
        f"{len(outcome.requirements)}"
    )

    print(
        f"Planning input SHA-256: "
        f"{planning_input_sha256}"
    )

    print(
        f"Final repaired-plan SHA-256: "
        f"{repaired_plan_sha256}"
    )

    print(
        f"Gate input outcome SHA-256: "
        f"{input_outcome_sha256}"
    )

    print(
        f"Gate pipeline SHA-256: "
        f"{gate_sha256}"
    )

    print()

    if cached is None:
        print(
            "Verification-gate cache: missing/stale"
        )

    else:
        print(
            "Verification-gate cache: valid"
        )

    if args.dry_run:
        print()
        print(
            "DRY RUN COMPLETE — PRODUCTION GATE NOT INVOKED"
        )

        print(
            "Outcome is SOLVED, so the production gate is expected "
            "to short-circuit locally."
        )

        print(
            "Guaranteed model calls in dry run: 0"
        )

        return

    if cached is not None:
        print()
        print(
            "Reusing validated verification-gate cache."
        )

        print(
            "Model calls: 0"
        )

        print()
        print(
            cached.audit.model_dump_json(
                indent=2
            )
        )

        return

    print()
    print(
        "Invoking exact production verification-gate helper..."
    )

    print(
        "Model network access is forcibly blocked for this invocation."
    )

    (
        output_outcome,
        audit,
        gate_repair_attempts,
    ) = run_production_gate_without_network(
        outcome=outcome,
        active_items=active_items,
        external_resources=external_resources,
    )

    if output_outcome.status != PlanOutcomeStatus.SOLVED:
        raise RuntimeError(
            "Verification gate unexpectedly changed the SOLVED status."
        )

    if not audit.passed:
        raise RuntimeError(
            "SOLVED outcome unexpectedly failed verification gating."
        )

    if audit.findings:
        raise RuntimeError(
            "SOLVED outcome unexpectedly produced gate findings."
        )

    if gate_repair_attempts != 0:
        raise RuntimeError(
            "SOLVED outcome unexpectedly used a gate repair attempt."
        )

    output_outcome_sha256 = (
        fingerprint_payload(
            output_outcome.model_dump(
                mode="json"
            )
        )
    )

    if output_outcome_sha256 != input_outcome_sha256:
        raise RuntimeError(
            "Verification gate unexpectedly mutated the SOLVED outcome."
        )

    save_cache(
        planning_input_sha256=planning_input_sha256,
        repaired_plan_sha256=repaired_plan_sha256,
        input_outcome_sha256=input_outcome_sha256,
        gate_pipeline_sha256=gate_sha256,
        output_outcome=output_outcome,
        audit=audit,
        gate_repair_attempts=gate_repair_attempts,
    )

    print()
    print("=" * 72)
    print("VERIFICATION GATE: PASSED")
    print("=" * 72)

    print()
    print(
        f"Audit passed: "
        f"{audit.passed}"
    )

    print(
        f"Audit findings: "
        f"{len(audit.findings)}"
    )

    print(
        f"Gate repair attempts: "
        f"{gate_repair_attempts}"
    )

    print(
        "Model calls: 0"
    )

    print()

    print(
        "Saved private verification-gate cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print()

    print(
        "Final semantic physical audit has NOT been run yet."
    )


if __name__ == "__main__":
    main()