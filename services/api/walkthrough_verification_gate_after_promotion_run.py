import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

import walkthrough_semantic_requirement_promotion_run as promotion_run

from verification_gate_auditor import (
    audit_verification_gates,
)
from verification_gate_schemas import (
    VerificationGateAudit,
)


DEFAULT_WALKTHROUGH_ID = (
    promotion_run.DEFAULT_WALKTHROUGH_ID
)


CACHE_PATH = (
    promotion_run.CACHE_PATH.with_name(
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-verification-gate-after-semantic-promotion.json"
    )
)


class VerificationGateAfterPromotionCache(
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

    source_semantic_critic_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    promotion_pipeline_sha256: str = Field(
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
        promotion_run
        .configure_walkthrough_context(
            walkthrough_id
        )
    )

    CACHE_PATH = (
        promotion_run.CACHE_PATH.with_name(
            f"{validated_id}"
            "-verification-gate-after-semantic-promotion.json"
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
        ).encode("utf-8")
    ).hexdigest()


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def gate_pipeline_fingerprint() -> str:
    base = Path(__file__).resolve().parent

    filenames = (
        "verification_gate_auditor.py",
        "verification_gate_schemas.py",
        "json_format_repair.py",
        "plan_outcome_schemas.py",
        "schemas.py",
    )

    payload = {}

    for filename in filenames:
        path = base / filename

        payload[filename] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

    return sha256_payload(
        payload
    )


def load_promoted_context(
    *,
    walkthrough_id: str,
    goal: str,
):
    (
        input_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        repaired_plan_sha256,
        source_semantic_critic_sha256,
        semantic_pipeline_sha256,
        input_outcome_sha256,
        critic,
    ) = (
        promotion_run.load_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    promotion_pipeline_sha256 = (
        promotion_run
        .promotion_pipeline_fingerprint()
    )

    promotion_cache = (
        promotion_run
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
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            promotion_pipeline_sha256=(
                promotion_pipeline_sha256
            ),
            input_outcome_sha256=(
                input_outcome_sha256
            ),
        )
    )

    if promotion_cache is None:
        raise RuntimeError(
            "Matching semantic requirement promotion cache "
            "was not found."
        )

    promotion_run.validate_output(
        input_outcome=(
            input_outcome
        ),
        cache=(
            promotion_cache
        ),
    )

    promoted_outcome = (
        promotion_cache.output_outcome
    )

    promotion_cache_sha256 = (
        sha256_file(
            promotion_run.CACHE_PATH
        )
    )

    promoted_outcome_sha256 = (
        sha256_payload(
            promoted_outcome.model_dump(
                mode="json"
            )
        )
    )

    return (
        promoted_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        repaired_plan_sha256,
        source_semantic_critic_sha256,
        semantic_pipeline_sha256,
        promotion_pipeline_sha256,
        promotion_cache_sha256,
        promoted_outcome_sha256,
        critic,
    )


def load_matching_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    repaired_plan_sha256: str,
    source_semantic_critic_sha256: str,
    promotion_pipeline_sha256: str,
    promotion_cache_sha256: str,
    promoted_outcome_sha256: str,
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
            VerificationGateAfterPromotionCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing verification-gate-after-promotion "
            "cache is invalid. Refusing another paid audit "
            f"until inspected: {CACHE_PATH}"
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
            cache.source_semantic_critic_sha256,
            source_semantic_critic_sha256,
        ),
        (
            cache.promotion_pipeline_sha256,
            promotion_pipeline_sha256,
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
            cache.gate_pipeline_sha256,
            gate_pipeline_sha256,
        ),
    )

    for actual, expected in checks:
        if actual != expected:
            raise RuntimeError(
                "Existing verification-gate-after-promotion "
                "cache is stale for the current inputs. "
                "Preserve and inspect it before authorizing "
                "another paid gate audit."
            )

    return cache


def save_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    repaired_plan_sha256: str,
    source_semantic_critic_sha256: str,
    promotion_pipeline_sha256: str,
    promotion_cache_sha256: str,
    promoted_outcome_sha256: str,
    gate_pipeline_sha256: str,
    audit: VerificationGateAudit,
) -> None:
    cache = (
        VerificationGateAfterPromotionCache(
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
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            promotion_pipeline_sha256=(
                promotion_pipeline_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            promoted_outcome_sha256=(
                promoted_outcome_sha256
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
        "VERIFICATION GATE AUDIT RESULT"
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
            "Promoted conditional requirements passed "
            "verification-gate auditing."
        )
    else:
        print(
            "Promoted conditional requirements still have "
            "blocking verification-gate findings."
        )

    print()

    print(
        "Verification requirement repair attempts used: 0 of 1."
    )

    print(
        "Final semantic recheck has NOT been run yet."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Initial verification-gate audit after "
            "semantic requirement promotion."
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
        "ZERO VERIFICATION GATE - "
        "AFTER SEMANTIC REQUIREMENT PROMOTION"
    )
    print("=" * 72)

    print(
        f"Walkthrough: {walkthrough_id}"
    )

    print(
        f"Goal: {goal}"
    )

    (
        promoted_outcome,
        active_items,
        _object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        repaired_plan_sha256,
        source_semantic_critic_sha256,
        _semantic_pipeline_sha256,
        promotion_pipeline_sha256,
        promotion_cache_sha256,
        promoted_outcome_sha256,
        _critic,
    ) = (
        load_promoted_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    gate_pipeline_sha256 = (
        gate_pipeline_fingerprint()
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
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            promotion_pipeline_sha256=(
                promotion_pipeline_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            promoted_outcome_sha256=(
                promoted_outcome_sha256
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
        f"Source semantic critic SHA-256: "
        f"{source_semantic_critic_sha256}"
    )

    print(
        f"Promotion pipeline SHA-256: "
        f"{promotion_pipeline_sha256}"
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
        f"Gate pipeline SHA-256: "
        f"{gate_pipeline_sha256}"
    )

    print()

    print(
        f"Outcome status: "
        f"{promoted_outcome.status.value}"
    )

    print(
        f"Requirements to audit: "
        f"{len(promoted_outcome.requirements)}"
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
        f"Gate cache: "
        f"{CACHE_PATH.resolve()}"
    )

    if cached is None:
        print(
            "Verification-gate cache: missing"
        )
    else:
        print(
            "Verification-gate cache: valid"
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
            "Verification requirement repair budget: 0 of 1 used."
        )

        return

    if cached is not None:
        print()

        print(
            "Reusing validated verification-gate cache."
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
            "No paid verification-gate audit authorized "
            "(--max-new-audits is 0)."
        )

        return

    print()

    print(
        "Running ONE fresh verification-gate audit..."
    )

    print(
        "Normally 1 Nemotron call; malformed JSON may "
        "trigger one formatting-only repair call."
    )

    audit = (
        audit_verification_gates(
            outcome=(
                promoted_outcome
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
        source_semantic_critic_sha256=(
            source_semantic_critic_sha256
        ),
        promotion_pipeline_sha256=(
            promotion_pipeline_sha256
        ),
        promotion_cache_sha256=(
            promotion_cache_sha256
        ),
        promoted_outcome_sha256=(
            promoted_outcome_sha256
        ),
        gate_pipeline_sha256=(
            gate_pipeline_sha256
        ),
        audit=audit,
    )

    cached = (
        VerificationGateAfterPromotionCache(
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
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            promotion_pipeline_sha256=(
                promotion_pipeline_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            promoted_outcome_sha256=(
                promoted_outcome_sha256
            ),
            gate_pipeline_sha256=(
                gate_pipeline_sha256
            ),
            audit=audit,
        )
    )

    print()

    print(
        "Verification-gate audit schema-valid and cached."
    )

    print(
        "New verification-gate audit calls: 1"
    )

    print(
        "Saved private verification-gate cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_audit(
        cached.audit
    )


if __name__ == "__main__":
    main()