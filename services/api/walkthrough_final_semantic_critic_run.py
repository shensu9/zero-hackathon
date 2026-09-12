import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from critic_schemas import (
    PlanCriticResult,
)
from plan_outcome_pipeline import (
    _audit_outcome_plan,
)
from plan_outcome_schemas import (
    PlanOutcomeStatus,
)
from walkthrough_goal_relevance_run import (
    GOAL,
)
from walkthrough_plan_repair_run import (
    load_context,
)
from walkthrough_semantic_critic_run import (
    semantic_pipeline_fingerprint,
)
from walkthrough_verification_gate_run import (
    CACHE_PATH as GATE_CACHE_PATH,
    VerificationGateStageCache,
    fingerprint_payload,
    gate_pipeline_fingerprint,
    load_final_repaired_context,
)


CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-final-semantic-critic.json"
)


class FinalSemanticCriticCache(BaseModel):
    """
    Cache for the final semantic physical audit after verification-gate
    processing.

    This is the terminal semantic safety boundary.

    The plan-repair budget is already exhausted at 2 of 2.
    A failing final critic MUST NOT trigger another plan repair.
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


def load_post_gate_context():
    """
    Reconstruct the current real world and load the exact cached output of
    the production verification-gate stage.

    No model calls occur here.
    """

    (
        active_items,
        object_dna,
        external_resources,
        _active_item_ids,
        planning_input_sha256,
        _initial_outcome,
    ) = load_context()

    (
        gate_active_items,
        gate_external_resources,
        gate_planning_input_sha256,
        repaired_plan_sha256,
        gate_input_outcome_sha256,
        _pre_gate_outcome,
    ) = load_final_repaired_context()

    if (
        gate_planning_input_sha256
        != planning_input_sha256
    ):
        raise RuntimeError(
            "Verification-gate context planning input no longer matches "
            "the current planning context."
        )

    if [
        item.id
        for item in gate_active_items
    ] != [
        item.id
        for item in active_items
    ]:
        raise RuntimeError(
            "Verification-gate active inventory no longer matches "
            "the current planning inventory."
        )

    if (
        gate_external_resources
        != external_resources
    ):
        raise RuntimeError(
            "Verification-gate external resources no longer match "
            "the current planning context."
        )

    if not GATE_CACHE_PATH.exists():
        raise RuntimeError(
            "Verification-gate cache was not found: "
            f"{GATE_CACHE_PATH}"
        )

    try:
        payload = json.loads(
            GATE_CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        gate_cache = (
            VerificationGateStageCache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Verification-gate cache is invalid."
        ) from exc

    if gate_cache.goal != GOAL:
        raise RuntimeError(
            "Verification-gate cache belongs to a different goal."
        )

    if (
        gate_cache.planning_input_sha256
        != planning_input_sha256
    ):
        raise RuntimeError(
            "Verification-gate cache belongs to a different "
            "planning input."
        )

    if (
        gate_cache.repaired_plan_sha256
        != repaired_plan_sha256
    ):
        raise RuntimeError(
            "Verification-gate cache belongs to a different "
            "final repaired plan."
        )

    if (
        gate_cache.input_outcome_sha256
        != gate_input_outcome_sha256
    ):
        raise RuntimeError(
            "Verification-gate cache belongs to a different "
            "input outcome."
        )

    current_gate_pipeline_sha256 = (
        gate_pipeline_fingerprint()
    )

    if (
        gate_cache.gate_pipeline_sha256
        != current_gate_pipeline_sha256
    ):
        raise RuntimeError(
            "Verification-gate cache was produced under a different "
            "gate pipeline."
        )

    if not gate_cache.audit.passed:
        raise RuntimeError(
            "Verification gate did not pass."
        )

    if gate_cache.audit.findings:
        raise RuntimeError(
            "Passing verification-gate cache unexpectedly contains "
            "findings."
        )

    if gate_cache.gate_repair_attempts != 0:
        raise RuntimeError(
            "This SOLVED walkthrough unexpectedly used a verification-"
            "gate repair attempt."
        )

    outcome = gate_cache.output_outcome

    if outcome.status != PlanOutcomeStatus.SOLVED:
        raise RuntimeError(
            "Post-gate walkthrough outcome is no longer SOLVED."
        )

    if outcome.plan is None:
        raise RuntimeError(
            "Post-gate SOLVED outcome unexpectedly contains no plan."
        )

    if outcome.requirements:
        raise RuntimeError(
            "Post-gate SOLVED outcome unexpectedly contains "
            "verification requirements."
        )

    gate_output_outcome_sha256 = (
        fingerprint_payload(
            outcome.model_dump(
                mode="json"
            )
        )
    )

    if (
        gate_output_outcome_sha256
        != gate_input_outcome_sha256
    ):
        raise RuntimeError(
            "SOLVED verification-gate output differs from its input. "
            "The gate was expected to short-circuit without mutation."
        )

    return (
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        gate_output_outcome_sha256,
        outcome,
    )


def load_matching_cache(
    *,
    planning_input_sha256: str,
    gate_output_outcome_sha256: str,
    semantic_pipeline_sha256: str,
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
            FinalSemanticCriticCache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing final semantic-critic cache is invalid. "
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
        cache.gate_output_outcome_sha256
        != gate_output_outcome_sha256
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
    gate_output_outcome_sha256: str,
    semantic_pipeline_sha256: str,
    critic: PlanCriticResult,
) -> None:
    cache = FinalSemanticCriticCache(
        goal=GOAL,
        planning_input_sha256=planning_input_sha256,
        gate_output_outcome_sha256=gate_output_outcome_sha256,
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
    print("FINAL SEMANTIC PHYSICAL AUDIT RESULT")
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
            "FINAL SEMANTIC BOUNDARY: PASSED"
        )

        print(
            "The final repaired plan has passed deterministic "
            "validation, verification-gate processing, and the "
            "terminal semantic physical audit."
        )

    else:
        print(
            "FINAL SEMANTIC BOUNDARY: FAILED"
        )

        print(
            "The plan-repair budget is exhausted at 2 of 2."
        )

        print(
            "ZERO must reject this plan rather than perform "
            "another repair."
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the exact post-gate context and inspect final "
            "semantic-cache status without making a model call."
        ),
    )

    parser.add_argument(
        "--max-new-audits",
        type=int,
        default=0,
        choices=[0, 1],
        help=(
            "Maximum new final semantic-audit invocations allowed. "
            "One audit normally uses one model call, but malformed JSON "
            "may trigger one additional formatting-only repair call. "
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
    print("ZERO WALKTHROUGH FINAL SEMANTIC CRITIC")
    print("=" * 72)

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

    cached_critic = load_matching_cache(
        planning_input_sha256=planning_input_sha256,
        gate_output_outcome_sha256=gate_output_outcome_sha256,
        semantic_pipeline_sha256=semantic_sha256,
    )

    print()
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

    print()

    if cached_critic is None:
        print(
            "Final semantic-critic cache: missing/stale"
        )

    else:
        print(
            "Final semantic-critic cache: valid"
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
            "Reusing validated final semantic-critic cache."
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
            "No paid final semantic audit authorized "
            "(--max-new-audits is 0)."
        )

        return

    print()
    print(
        "Running ONE final semantic physical audit..."
    )

    print(
        "This normally uses 1 Nemotron call; malformed JSON may "
        "trigger 1 additional formatting-only repair call."
    )

    critic = _audit_outcome_plan(
        outcome=outcome,
        goal=GOAL,
        inventory=active_items,
        object_dna=object_dna,
        external_resources=external_resources,
    )

    save_cache(
        planning_input_sha256=planning_input_sha256,
        gate_output_outcome_sha256=gate_output_outcome_sha256,
        semantic_pipeline_sha256=semantic_sha256,
        critic=critic,
    )

    print()
    print(
        "Final semantic critic schema-valid and cached."
    )

    print(
        "New semantic audit invocations: 1"
    )

    print(
        "Saved private final semantic-critic cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_critic(
        critic
    )


if __name__ == "__main__":
    main()