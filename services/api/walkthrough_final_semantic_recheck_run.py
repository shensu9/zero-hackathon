import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

import walkthrough_verification_gate_after_requirement_repair_run as gate_run

from critic_schemas import (
    PlanCriticResult,
)
from plan_outcome_pipeline import (
    _audit_outcome_plan,
    _build_execution_aware_goal,
)


DEFAULT_WALKTHROUGH_ID = (
    gate_run.DEFAULT_WALKTHROUGH_ID
)


CACHE_PATH = (
    gate_run.CACHE_PATH.with_name(
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-final-semantic-recheck-after-verification-gate.json"
    )
)


class FinalSemanticRecheckCache(
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

    passed_gate_cache_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    gate_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    final_execution_context_sha256: str = Field(
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
        gate_run.configure_walkthrough_context(
            walkthrough_id
        )
    )

    CACHE_PATH = (
        gate_run.CACHE_PATH.with_name(
            f"{validated_id}"
            "-final-semantic-recheck-after-verification-gate.json"
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


def semantic_pipeline_fingerprint() -> str:
    base = Path(__file__).resolve().parent

    filenames = (
        "semantic_critic.py",
        "critic_schemas.py",
        "plan_outcome_pipeline.py",
        "plan_outcome_schemas.py",
        "json_format_repair.py",
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


def load_final_context(
    *,
    walkthrough_id: str,
    goal: str,
):
    (
        repaired_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        _semantic_context_sha256,
        repaired_plan_sha256,
        promotion_cache_sha256,
        _promoted_outcome_sha256,
        _source_gate_cache_sha256,
        _source_gate_audit_sha256,
        _requirement_repair_pipeline_sha256,
        requirement_repair_cache_sha256,
        repaired_outcome_sha256,
        gate_pipeline_sha256,
        _source_gate_audit,
        _prior_critic,
        _prior_semantic_pipeline_sha256,
    ) = (
        gate_run.load_repaired_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    passed_gate_cache = (
        gate_run.load_matching_cache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            semantic_context_sha256=(
                _semantic_context_sha256
            ),
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            promoted_outcome_sha256=(
                _promoted_outcome_sha256
            ),
            source_gate_cache_sha256=(
                _source_gate_cache_sha256
            ),
            source_gate_audit_sha256=(
                _source_gate_audit_sha256
            ),
            requirement_repair_pipeline_sha256=(
                _requirement_repair_pipeline_sha256
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

    if passed_gate_cache is None:
        raise RuntimeError(
            "Matching passed post-repair verification-gate "
            "cache was not found."
        )

    if not passed_gate_cache.audit.passed:
        raise RuntimeError(
            "Post-repair verification gate does not pass. "
            "Final semantic recheck is blocked."
        )

    if passed_gate_cache.audit.findings:
        raise RuntimeError(
            "Passed verification gate unexpectedly contains findings."
        )

    passed_gate_cache_sha256 = (
        sha256_file(
            gate_run.CACHE_PATH
        )
    )

    execution_goal = (
        _build_execution_aware_goal(
            goal=goal,
            outcome=(
                repaired_outcome
            ),
        )
    )

    final_execution_context_sha256 = (
        hashlib.sha256(
            execution_goal.encode(
                "utf-8"
            )
        ).hexdigest()
    )

    return (
        repaired_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        repaired_plan_sha256,
        promotion_cache_sha256,
        requirement_repair_cache_sha256,
        repaired_outcome_sha256,
        passed_gate_cache_sha256,
        gate_pipeline_sha256,
        final_execution_context_sha256,
    )


def load_matching_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    repaired_plan_sha256: str,
    promotion_cache_sha256: str,
    requirement_repair_cache_sha256: str,
    repaired_outcome_sha256: str,
    passed_gate_cache_sha256: str,
    gate_pipeline_sha256: str,
    final_execution_context_sha256: str,
    semantic_pipeline_sha256: str,
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
            FinalSemanticRecheckCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing final semantic recheck cache is invalid. "
            "Refusing another paid audit until inspected: "
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
            cache.repaired_plan_sha256,
            repaired_plan_sha256,
        ),
        (
            cache.promotion_cache_sha256,
            promotion_cache_sha256,
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
            cache.passed_gate_cache_sha256,
            passed_gate_cache_sha256,
        ),
        (
            cache.gate_pipeline_sha256,
            gate_pipeline_sha256,
        ),
        (
            cache.final_execution_context_sha256,
            final_execution_context_sha256,
        ),
        (
            cache.semantic_pipeline_sha256,
            semantic_pipeline_sha256,
        ),
    )

    for actual, expected in checks:
        if actual != expected:
            raise RuntimeError(
                "Existing final semantic recheck cache is stale "
                "for the current inputs. Preserve and inspect it "
                "before authorizing another paid audit."
            )

    return cache


def save_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    repaired_plan_sha256: str,
    promotion_cache_sha256: str,
    requirement_repair_cache_sha256: str,
    repaired_outcome_sha256: str,
    passed_gate_cache_sha256: str,
    gate_pipeline_sha256: str,
    final_execution_context_sha256: str,
    semantic_pipeline_sha256: str,
    critic: PlanCriticResult,
) -> None:
    cache = (
        FinalSemanticRecheckCache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            requirement_repair_cache_sha256=(
                requirement_repair_cache_sha256
            ),
            repaired_outcome_sha256=(
                repaired_outcome_sha256
            ),
            passed_gate_cache_sha256=(
                passed_gate_cache_sha256
            ),
            gate_pipeline_sha256=(
                gate_pipeline_sha256
            ),
            final_execution_context_sha256=(
                final_execution_context_sha256
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
        "FINAL WALKTHROUGH 02 SEMANTIC RECHECK"
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
                f"{index}. "
                f"{finding.model_dump_json()}"
            )

    print()

    if critic.passed:
        print(
            "Walkthrough 02 passed the final semantic recheck."
        )

        print(
            "All bounded safety stages are complete."
        )

        print(
            "Walkthrough 02 is eligible for terminal freeze."
        )
    else:
        print(
            "Walkthrough 02 failed the final semantic recheck."
        )

        print(
            "All repair/promotion budgets are exhausted."
        )

        print(
            "Fail closed. No additional repair attempt is permitted."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Final production-style semantic recheck after "
            "passed verification-gate processing."
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
            "--dry-run cannot authorize a paid semantic audit."
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
        "ZERO FINAL SEMANTIC RECHECK - WALKTHROUGH 02"
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
        object_dna,
        external_resources,
        planning_input_sha256,
        repaired_plan_sha256,
        promotion_cache_sha256,
        requirement_repair_cache_sha256,
        repaired_outcome_sha256,
        passed_gate_cache_sha256,
        gate_pipeline_sha256,
        final_execution_context_sha256,
    ) = (
        load_final_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    semantic_pipeline_sha256 = (
        semantic_pipeline_fingerprint()
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
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            requirement_repair_cache_sha256=(
                requirement_repair_cache_sha256
            ),
            repaired_outcome_sha256=(
                repaired_outcome_sha256
            ),
            passed_gate_cache_sha256=(
                passed_gate_cache_sha256
            ),
            gate_pipeline_sha256=(
                gate_pipeline_sha256
            ),
            final_execution_context_sha256=(
                final_execution_context_sha256
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
        f"Final repaired-plan SHA-256: "
        f"{repaired_plan_sha256}"
    )

    print(
        f"Promotion cache SHA-256: "
        f"{promotion_cache_sha256}"
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
        f"Passed gate cache SHA-256: "
        f"{passed_gate_cache_sha256}"
    )

    print(
        f"Gate pipeline SHA-256: "
        f"{gate_pipeline_sha256}"
    )

    print(
        f"Final execution-context SHA-256: "
        f"{final_execution_context_sha256}"
    )

    print(
        f"Final semantic pipeline SHA-256: "
        f"{semantic_pipeline_sha256}"
    )

    print()

    print(
        f"Outcome status: "
        f"{repaired_outcome.status.value}"
    )

    print(
        f"Final requirements: "
        f"{len(repaired_outcome.requirements)}"
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

    print()

    print(
        f"Final semantic cache: "
        f"{CACHE_PATH.resolve()}"
    )

    if cached is None:
        print(
            "Final semantic recheck cache: missing"
        )
    else:
        print(
            "Final semantic recheck cache: valid"
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
            "PhysicalPlan repair budget: 2 of 2 exhausted."
        )

        print(
            "Semantic requirement promotion budget: 1 of 1 used."
        )

        print(
            "Verification requirement repair budget: 1 of 1 exhausted."
        )

        print(
            "Passed verification gate: YES"
        )

        return

    if cached is not None:
        print()

        print(
            "Reusing validated final semantic recheck cache."
        )

        print(
            "New semantic audit calls: 0"
        )

        print_critic(
            cached.critic
        )

        return

    if (
        args.max_new_audits
        == 0
    ):
        print()

        print(
            "No paid final semantic audit authorized "
            "(--max-new-audits is 0)."
        )

        return

    print()

    print(
        "Running ONE final production-style semantic recheck..."
    )

    print(
        "This uses the repaired two-requirement execution contract."
    )

    print(
        "Normally 1 Nemotron call; malformed JSON may "
        "trigger one formatting-only repair call."
    )

    critic = (
        _audit_outcome_plan(
            outcome=(
                repaired_outcome
            ),
            goal=goal,
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
        repaired_plan_sha256=(
            repaired_plan_sha256
        ),
        promotion_cache_sha256=(
            promotion_cache_sha256
        ),
        requirement_repair_cache_sha256=(
            requirement_repair_cache_sha256
        ),
        repaired_outcome_sha256=(
            repaired_outcome_sha256
        ),
        passed_gate_cache_sha256=(
            passed_gate_cache_sha256
        ),
        gate_pipeline_sha256=(
            gate_pipeline_sha256
        ),
        final_execution_context_sha256=(
            final_execution_context_sha256
        ),
        semantic_pipeline_sha256=(
            semantic_pipeline_sha256
        ),
        critic=critic,
    )

    cached = (
        FinalSemanticRecheckCache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            promotion_cache_sha256=(
                promotion_cache_sha256
            ),
            requirement_repair_cache_sha256=(
                requirement_repair_cache_sha256
            ),
            repaired_outcome_sha256=(
                repaired_outcome_sha256
            ),
            passed_gate_cache_sha256=(
                passed_gate_cache_sha256
            ),
            gate_pipeline_sha256=(
                gate_pipeline_sha256
            ),
            final_execution_context_sha256=(
                final_execution_context_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            critic=critic,
        )
    )

    print()

    print(
        "Final semantic critic schema-valid and cached."
    )

    print(
        "New semantic audit calls: 1"
    )

    print(
        "Saved private final semantic cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_critic(
        cached.critic
    )


if __name__ == "__main__":
    main()