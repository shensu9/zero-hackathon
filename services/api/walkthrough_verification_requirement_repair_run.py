import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

import walkthrough_verification_gate_after_promotion_run as gate_run

from plan_outcome_pipeline import (
    _replace_requirements,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanRequirement,
)
from verification_gate_repair import (
    repair_verification_requirements,
)


DEFAULT_WALKTHROUGH_ID = (
    gate_run.DEFAULT_WALKTHROUGH_ID
)


CACHE_PATH = (
    gate_run.CACHE_PATH.with_name(
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-verification-requirement-repair-after-promotion.json"
    )
)


class VerificationRequirementRepairCache(
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

    gate_pipeline_sha256: str = Field(
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

    repair_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    repaired_requirements: list[
        PlanRequirement
    ] = Field(
        min_length=1,
        max_length=5,
    )

    output_outcome: PlanOutcome


def configure_walkthrough_context(
    walkthrough_id: str,
) -> str:
    global CACHE_PATH

    validated_id = (
        gate_run.configure_walkthrough_context(
            walkthrough_id
        )
    )

    CACHE_PATH = (
        gate_run.CACHE_PATH.with_name(
            f"{validated_id}"
            "-verification-requirement-repair-after-promotion.json"
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


def repair_pipeline_fingerprint() -> str:
    base = Path(__file__).resolve().parent

    filenames = (
        "verification_gate_repair.py",
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


def load_context(
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
        source_semantic_critic_sha256,
        semantic_pipeline_sha256,
        promotion_pipeline_sha256,
        promotion_cache_sha256,
        promoted_outcome_sha256,
        critic,
    ) = (
        gate_run.load_promoted_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    gate_pipeline_sha256 = (
        gate_run.gate_pipeline_fingerprint()
    )

    gate_cache = (
        gate_run.load_matching_cache(
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

    if gate_cache is None:
        raise RuntimeError(
            "Matching verification-gate audit cache "
            "was not found."
        )

    if gate_cache.audit.passed:
        raise RuntimeError(
            "Verification-gate audit already passes. "
            "Requirement repair is not justified."
        )

    if not gate_cache.audit.findings:
        raise RuntimeError(
            "Verification-gate audit failed without findings. "
            "Refusing unguided requirement repair."
        )

    source_gate_cache_sha256 = (
        sha256_file(
            gate_run.CACHE_PATH
        )
    )

    source_gate_audit_sha256 = (
        sha256_payload(
            gate_cache.audit.model_dump(
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
        promotion_cache_sha256,
        promoted_outcome_sha256,
        gate_pipeline_sha256,
        source_gate_cache_sha256,
        source_gate_audit_sha256,
        gate_cache.audit,
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
    gate_pipeline_sha256: str,
    source_gate_cache_sha256: str,
    source_gate_audit_sha256: str,
    repair_pipeline_sha256: str,
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
            VerificationRequirementRepairCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing verification-requirement-repair cache "
            "is invalid. Refusing another paid repair until "
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
            cache.gate_pipeline_sha256,
            gate_pipeline_sha256,
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
            cache.repair_pipeline_sha256,
            repair_pipeline_sha256,
        ),
    )

    for actual, expected in checks:
        if actual != expected:
            raise RuntimeError(
                "Existing verification-requirement-repair cache "
                "is stale for the current inputs. Preserve and "
                "inspect it before authorizing another paid repair."
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
    gate_pipeline_sha256: str,
    source_gate_cache_sha256: str,
    source_gate_audit_sha256: str,
    repair_pipeline_sha256: str,
    repaired_requirements,
    output_outcome: PlanOutcome,
) -> None:
    cache = (
        VerificationRequirementRepairCache(
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
                gate_pipeline_sha256
            ),
            source_gate_cache_sha256=(
                source_gate_cache_sha256
            ),
            source_gate_audit_sha256=(
                source_gate_audit_sha256
            ),
            repair_pipeline_sha256=(
                repair_pipeline_sha256
            ),
            repaired_requirements=(
                repaired_requirements
            ),
            output_outcome=(
                output_outcome
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


def validate_output(
    *,
    input_outcome: PlanOutcome,
    cache: VerificationRequirementRepairCache,
) -> None:
    output = cache.output_outcome

    if (
        output.status
        != input_outcome.status
    ):
        raise RuntimeError(
            "Requirement repair changed PlanOutcome status."
        )

    if (
        output.plan
        != input_outcome.plan
    ):
        raise RuntimeError(
            "Requirement repair modified the frozen PhysicalPlan."
        )

    if (
        output.explanation
        != input_outcome.explanation
    ):
        raise RuntimeError(
            "Requirement repair changed the outcome explanation."
        )

    if (
        output.blocking_reasons
        != input_outcome.blocking_reasons
    ):
        raise RuntimeError(
            "Requirement repair changed blocking reasons."
        )

    if (
        len(cache.repaired_requirements)
        != len(input_outcome.requirements)
    ):
        raise RuntimeError(
            "Requirement repair changed the requirement count."
        )

    if (
        output.requirements
        != cache.repaired_requirements
    ):
        raise RuntimeError(
            "Output requirements do not match cached "
            "repaired requirements."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Single bounded verification-requirement repair "
            "after failed gate audit."
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
        "--max-new-repairs",
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
        args.max_new_repairs != 0
    ):
        parser.error(
            "--dry-run cannot authorize a paid "
            "requirement repair."
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
        "ZERO VERIFICATION REQUIREMENT REPAIR - "
        "ATTEMPT 1 OF 1"
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
        promotion_cache_sha256,
        promoted_outcome_sha256,
        gate_pipeline_sha256,
        source_gate_cache_sha256,
        source_gate_audit_sha256,
        audit,
        _critic,
        _semantic_pipeline_sha256,
    ) = (
        load_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    repair_pipeline_sha256 = (
        repair_pipeline_fingerprint()
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
            gate_pipeline_sha256=(
                gate_pipeline_sha256
            ),
            source_gate_cache_sha256=(
                source_gate_cache_sha256
            ),
            source_gate_audit_sha256=(
                source_gate_audit_sha256
            ),
            repair_pipeline_sha256=(
                repair_pipeline_sha256
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
        f"{repair_pipeline_sha256}"
    )

    print()

    print(
        f"Outcome status: "
        f"{promoted_outcome.status.value}"
    )

    print(
        f"Requirements before repair: "
        f"{len(promoted_outcome.requirements)}"
    )

    print(
        f"Blocking gate findings: "
        f"{len(audit.findings)}"
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

    for index, finding in enumerate(
        audit.findings,
        start=1,
    ):
        print(
            f"{index}. "
            f"{finding.model_dump_json()}"
        )

    print()

    print(
        f"Requirement-repair cache: "
        f"{CACHE_PATH.resolve()}"
    )

    if cached is None:
        print(
            "Verification requirement repair cache: missing"
        )
    else:
        print(
            "Verification requirement repair cache: valid"
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
            "0 of 1 used."
        )

        print(
            "Maximum future repair calls from this runner: 1."
        )

        return

    if cached is None:
        if (
            args.max_new_repairs
            == 0
        ):
            print()

            print(
                "No paid verification requirement repair "
                "authorized (--max-new-repairs is 0)."
            )

            return

        print()

        print(
            "Running ONE verification requirement repair call..."
        )

        print(
            "This is requirement repair attempt 1 of 1."
        )

        print(
            "PhysicalPlan remains frozen."
        )

        repaired_requirements = (
            repair_verification_requirements(
                outcome=(
                    promoted_outcome
                ),
                audit=audit,
                inventory=(
                    active_items
                ),
                external_resources=(
                    external_resources
                ),
            )
        )

        output_outcome = (
            _replace_requirements(
                outcome=(
                    promoted_outcome
                ),
                requirements=(
                    repaired_requirements
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
            gate_pipeline_sha256=(
                gate_pipeline_sha256
            ),
            source_gate_cache_sha256=(
                source_gate_cache_sha256
            ),
            source_gate_audit_sha256=(
                source_gate_audit_sha256
            ),
            repair_pipeline_sha256=(
                repair_pipeline_sha256
            ),
            repaired_requirements=(
                repaired_requirements
            ),
            output_outcome=(
                output_outcome
            ),
        )

        cached = (
            VerificationRequirementRepairCache(
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
                    gate_pipeline_sha256
                ),
                source_gate_cache_sha256=(
                    source_gate_cache_sha256
                ),
                source_gate_audit_sha256=(
                    source_gate_audit_sha256
                ),
                repair_pipeline_sha256=(
                    repair_pipeline_sha256
                ),
                repaired_requirements=(
                    repaired_requirements
                ),
                output_outcome=(
                    output_outcome
                ),
            )
        )

        print()

        print(
            "Requirement repair schema-valid and cached."
        )

        print(
            "New verification requirement repair calls: 1"
        )

        print(
            "Saved private requirement-repair cache:"
        )

        print(
            CACHE_PATH.resolve()
        )

    else:
        print()

        print(
            "Reusing validated verification requirement "
            "repair cache."
        )

        print(
            "New verification requirement repair calls: 0"
        )

    validate_output(
        input_outcome=(
            promoted_outcome
        ),
        cache=cached,
    )

    print()
    print("=" * 72)
    print(
        "REPAIRED VERIFICATION REQUIREMENTS"
    )
    print("=" * 72)

    for index, requirement in enumerate(
        cached.repaired_requirements,
        start=1,
    ):
        print()

        print(
            f"{index}. requirement: "
            f"{requirement.requirement}"
        )

        print(
            f"   how_to_verify: "
            f"{requirement.how_to_verify}"
        )

        print(
            f"   if_not_met: "
            f"{requirement.if_not_met}"
        )

    print()

    print(
        f"Requirement count preserved: "
        f"{len(cached.repaired_requirements)}"
    )

    print(
        "Frozen PhysicalPlan unchanged: YES"
    )

    print(
        "Verification requirement repair budget: "
        "1 of 1 exhausted."
    )

    print()

    print(
        "A fresh post-repair verification-gate audit "
        "is still required."
    )

    print(
        "Final semantic recheck has NOT been run yet."
    )


if __name__ == "__main__":
    main()