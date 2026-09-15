import argparse
import json

from pydantic import BaseModel, Field

import walkthrough_verification_requirement_repair_run as repair_run

from verification_gate_auditor import (
    audit_verification_gates,
)
from verification_gate_schemas import (
    VerificationGateAudit,
)


DEFAULT_WALKTHROUGH_ID = (
    repair_run.DEFAULT_WALKTHROUGH_ID
)


CACHE_PATH = (
    repair_run.CACHE_PATH.with_name(
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-verification-gate-after-requirement-repair.json"
    )
)


class VerificationGateAfterRequirementRepairCache(
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

    semantic_context_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    repaired_plan_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    promotion_cache_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    promoted_outcome_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    source_gate_cache_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    source_gate_audit_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    requirement_repair_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    requirement_repair_cache_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    repaired_outcome_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    gate_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    audit: VerificationGateAudit


def configure_walkthrough_context(
    walkthrough_id: str,
) -> str:
    global CACHE_PATH

    validated_id = (
        repair_run.configure_walkthrough_context(
            walkthrough_id
        )
    )

    CACHE_PATH = (
        repair_run.CACHE_PATH.with_name(
            f"{validated_id}"
            "-verification-gate-after-requirement-repair.json"
        )
    )

    return validated_id


def load_repaired_context(
    *,
    walkthrough_id: str,
    goal: str,
):
    (
        promoted_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        repaired_plan_sha256,
        promotion_cache_sha256,
        promoted_outcome_sha256,
        source_gate_pipeline_sha256,
        source_gate_cache_sha256,
        source_gate_audit_sha256,
        source_gate_audit,
        critic,
        semantic_pipeline_sha256,
    ) = (
        repair_run.load_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    requirement_repair_pipeline_sha256 = (
        repair_run.repair_pipeline_fingerprint()
    )

    repaired_cache = (
        repair_run.load_matching_cache(
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
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            promoted_outcome_sha256=(
                promoted_outcome_sha256
            ),
            gate_pipeline_sha256=(
                source_gate_pipeline_sha256
            ),
            source_gate_cache_sha256=(
                source_gate_cache_sha256
            ),
            source_gate_audit_sha256=(
                source_gate_audit_sha256
            ),
            repair_pipeline_sha256=(
                requirement_repair_pipeline_sha256
            ),
        )
    )

    if repaired_cache is None:
        raise RuntimeError(
            "Matching verification-requirement-repair "
            "cache was not found."
        )

    repair_run.validate_output(
        input_outcome=(
            promoted_outcome
        ),
        cache=(
            repaired_cache
        ),
    )

    repaired_outcome = (
        repaired_cache.output_outcome
    )

    requirement_repair_cache_sha256 = (
        repair_run.sha256_file(
            repair_run.CACHE_PATH
        )
    )

    repaired_outcome_sha256 = (
        repair_run.sha256_payload(
            repaired_outcome.model_dump(
                mode="json"
            )
        )
    )

    gate_pipeline_sha256 = (
        repair_run
        .gate_run
        .gate_pipeline_fingerprint()
    )

    return (
        repaired_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        repaired_plan_sha256,
        promotion_cache_sha256,
        promoted_outcome_sha256,
        source_gate_cache_sha256,
        source_gate_audit_sha256,
        requirement_repair_pipeline_sha256,
        requirement_repair_cache_sha256,
        repaired_outcome_sha256,
        gate_pipeline_sha256,
        source_gate_audit,
        critic,
        semantic_pipeline_sha256,
    )


def load_matching_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    repaired_plan_sha256: str,
    promotion_cache_sha256: str,
    promoted_outcome_sha256: str,
    source_gate_cache_sha256: str,
    source_gate_audit_sha256: str,
    requirement_repair_pipeline_sha256: str,
    requirement_repair_cache_sha256: str,
    repaired_outcome_sha256: str,
    gate_pipeline_sha256: str,
):
    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cache = (
            VerificationGateAfterRequirementRepairCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing post-requirement-repair gate cache "
            "is invalid. Refusing another paid audit until "
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
            cache.repaired_plan_sha256,
            repaired_plan_sha256,
        ),
        (
            cache.promotion_cache_sha256,
            promotion_cache_sha256,
        ),
        (
            cache.promoted_outcome_sha256,
            promoted_outcome_sha256,
        ),
        (
            cache.source_gate_cache_sha256,
            source_gate_cache_sha256,
        ),
        (
            cache.source_gate_audit_sha256,
            source_gate_audit_sha256,
        ),
        (
            cache.requirement_repair_pipeline_sha256,
            requirement_repair_pipeline_sha256,
        ),
        (
            cache.requirement_repair_cache_sha256,
            requirement_repair_cache_sha256,
        ),
        (
            cache.repaired_outcome_sha256,
            repaired_outcome_sha256,
        ),
        (
            cache.gate_pipeline_sha256,
            gate_pipeline_sha256,
        ),
    )

    for actual, expected in checks:
        if actual != expected:
            raise RuntimeError(
                "Existing post-requirement-repair gate "
                "cache is stale for the current inputs. "
                "Preserve and inspect it before authorizing "
                "another paid audit."
            )

    return cache


def save_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    repaired_plan_sha256: str,
    promotion_cache_sha256: str,
    promoted_outcome_sha256: str,
    source_gate_cache_sha256: str,
    source_gate_audit_sha256: str,
    requirement_repair_pipeline_sha256: str,
    requirement_repair_cache_sha256: str,
    repaired_outcome_sha256: str,
    gate_pipeline_sha256: str,
    audit: VerificationGateAudit,
) -> None:
    cache = (
        VerificationGateAfterRequirementRepairCache(
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
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            promoted_outcome_sha256=(
                promoted_outcome_sha256
            ),
            source_gate_cache_sha256=(
                source_gate_cache_sha256
            ),
            source_gate_audit_sha256=(
                source_gate_audit_sha256
            ),
            requirement_repair_pipeline_sha256=(
                requirement_repair_pipeline_sha256
            ),
            requirement_repair_cache_sha256=(
                requirement_repair_cache_sha256
            ),
            repaired_outcome_sha256=(
                repaired_outcome_sha256
            ),
            gate_pipeline_sha256=(
                gate_pipeline_sha256
            ),
            audit=audit,
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


def print_audit(
    audit: VerificationGateAudit,
) -> None:
    print()
    print("=" * 72)
    print(
        "POST-REPAIR VERIFICATION GATE AUDIT RESULT"
    )
    print("=" * 72)

    print()

    print(
        f"Passed: {audit.passed}"
    )

    print(
        f"Findings: {len(audit.findings)}"
    )

    if audit.findings:
        print()

        for index, finding in enumerate(
            audit.findings,
            start=1,
        ):
            print(
                f"{index}. "
                f"{finding.model_dump_json()}"
            )

    print()

    if audit.passed:
        print(
            "Repaired verification requirements passed "
            "the fresh gate audit."
        )
    else:
        print(
            "Repaired verification requirements still "
            "have blocking gate findings."
        )

    print()

    print(
        "Verification requirement repair budget: "
        "1 of 1 exhausted."
    )

    print(
        "NO second requirement repair is permitted."
    )

    print()

    print(
        "Final semantic recheck has NOT been run yet."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fresh verification-gate audit after the "
            "single bounded requirement repair."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=(
            DEFAULT_WALKTHROUGH_ID
        ),
    )

    parser.add_argument(
        "--goal",
        required=True,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "--max-new-audits",
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
        and
        args.max_new_audits != 0
    ):
        parser.error(
            "--dry-run cannot authorize a paid gate audit."
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
        "ZERO POST-REPAIR VERIFICATION GATE"
    )
    print("=" * 72)

    print(
        f"Walkthrough: {walkthrough_id}"
    )

    print(
        f"Goal: {goal}"
    )

    (
        repaired_outcome,
        active_items,
        _object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        repaired_plan_sha256,
        promotion_cache_sha256,
        promoted_outcome_sha256,
        source_gate_cache_sha256,
        source_gate_audit_sha256,
        requirement_repair_pipeline_sha256,
        requirement_repair_cache_sha256,
        repaired_outcome_sha256,
        gate_pipeline_sha256,
        _source_gate_audit,
        _critic,
        _semantic_pipeline_sha256,
    ) = (
        load_repaired_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    cached = (
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
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            promoted_outcome_sha256=(
                promoted_outcome_sha256
            ),
            source_gate_cache_sha256=(
                source_gate_cache_sha256
            ),
            source_gate_audit_sha256=(
                source_gate_audit_sha256
            ),
            requirement_repair_pipeline_sha256=(
                requirement_repair_pipeline_sha256
            ),
            requirement_repair_cache_sha256=(
                requirement_repair_cache_sha256
            ),
            repaired_outcome_sha256=(
                repaired_outcome_sha256
            ),
            gate_pipeline_sha256=(
                gate_pipeline_sha256
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
        f"Final repaired-plan SHA-256: "
        f"{repaired_plan_sha256}"
    )

    print(
        f"Promotion cache SHA-256: "
        f"{promotion_cache_sha256}"
    )

    print(
        f"Promoted outcome SHA-256: "
        f"{promoted_outcome_sha256}"
    )

    print(
        f"Source gate cache SHA-256: "
        f"{source_gate_cache_sha256}"
    )

    print(
        f"Source gate audit SHA-256: "
        f"{source_gate_audit_sha256}"
    )

    print(
        f"Requirement-repair pipeline SHA-256: "
        f"{requirement_repair_pipeline_sha256}"
    )

    print(
        f"Requirement-repair cache SHA-256: "
        f"{requirement_repair_cache_sha256}"
    )

    print(
        f"Repaired outcome SHA-256: "
        f"{repaired_outcome_sha256}"
    )

    print(
        f"Gate pipeline SHA-256: "
        f"{gate_pipeline_sha256}"
    )

    print()

    print(
        f"Outcome status: "
        f"{repaired_outcome.status.value}"
    )

    print(
        f"Requirements to re-audit: "
        f"{len(repaired_outcome.requirements)}"
    )

    print(
        f"Active inventory items: "
        f"{len(active_items)}"
    )

    print(
        f"External resources: "
        f"{external_resources}"
    )

    print()

    print(
        f"Post-repair gate cache: "
        f"{CACHE_PATH.resolve()}"
    )

    if cached is None:
        print(
            "Post-repair verification-gate cache: missing"
        )
    else:
        print(
            "Post-repair verification-gate cache: valid"
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
            "Verification requirement repair budget: "
            "1 of 1 exhausted."
        )

        print(
            "NO second requirement repair exists."
        )

        return

    if cached is not None:
        print()

        print(
            "Reusing validated post-repair "
            "verification-gate cache."
        )

        print(
            "New verification-gate audit calls: 0"
        )

        print_audit(
            cached.audit
        )

        return

    if (
        args.max_new_audits
        == 0
    ):
        print()

        print(
            "No paid post-repair verification-gate audit "
            "authorized (--max-new-audits is 0)."
        )

        return

    print()

    print(
        "Running ONE fresh post-repair "
        "verification-gate audit..."
    )

    print(
        "Normally 1 Nemotron call; malformed JSON may "
        "trigger one formatting-only repair call."
    )

    audit = (
        audit_verification_gates(
            outcome=(
                repaired_outcome
            ),
            inventory=(
                active_items
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
        repaired_plan_sha256=(
            repaired_plan_sha256
        ),
        promotion_cache_sha256=(
            promotion_cache_sha256
        ),
        promoted_outcome_sha256=(
            promoted_outcome_sha256
        ),
        source_gate_cache_sha256=(
            source_gate_cache_sha256
        ),
        source_gate_audit_sha256=(
            source_gate_audit_sha256
        ),
        requirement_repair_pipeline_sha256=(
            requirement_repair_pipeline_sha256
        ),
        requirement_repair_cache_sha256=(
            requirement_repair_cache_sha256
        ),
        repaired_outcome_sha256=(
            repaired_outcome_sha256
        ),
        gate_pipeline_sha256=(
            gate_pipeline_sha256
        ),
        audit=audit,
    )

    cached = (
        VerificationGateAfterRequirementRepairCache(
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
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            promoted_outcome_sha256=(
                promoted_outcome_sha256
            ),
            source_gate_cache_sha256=(
                source_gate_cache_sha256
            ),
            source_gate_audit_sha256=(
                source_gate_audit_sha256
            ),
            requirement_repair_pipeline_sha256=(
                requirement_repair_pipeline_sha256
            ),
            requirement_repair_cache_sha256=(
                requirement_repair_cache_sha256
            ),
            repaired_outcome_sha256=(
                repaired_outcome_sha256
            ),
            gate_pipeline_sha256=(
                gate_pipeline_sha256
            ),
            audit=audit,
        )
    )

    print()

    print(
        "Post-repair verification-gate audit "
        "schema-valid and cached."
    )

    print(
        "New verification-gate audit calls: 1"
    )

    print(
        "Saved private post-repair gate cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_audit(
        cached.audit
    )


if __name__ == "__main__":
    main()