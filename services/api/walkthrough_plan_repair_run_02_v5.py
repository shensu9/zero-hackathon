import json
from pathlib import Path

import walkthrough_plan_repair_run_02 as base
import walkthrough_semantic_critic_run as semantic_base

from plan_repair_closure import (
    find_persisted_critic_findings,
)


RUN_ID = "repair-closure-v5"

V2_REPAIR_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-01.json"
)

V4_REPAIR_02_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-accounting-v4-"
    "plan-repair-attempt-02.json"
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


def inspect_closure_if_available() -> None:
    """
    Run the same one-way deterministic closure check used by the
    production repair loop.

    This makes no model calls.

    If a rejected MEDIUM/HIGH claim persists literally after repair,
    V5 is already known to have failed and no terminal semantic model
    audit is needed.

    If no persisted literal claim is found, safety is NOT proven.
    Normal hard/gate/final-semantic validation must continue.
    """

    if not V5_REPAIR_02_CACHE.exists():
        print()
        print(
            "V5 repair-attempt-2 cache does not exist yet; "
            "closure check not run."
        )
        return

    (
        _active_items,
        _object_dna,
        _external_resources,
        _planning_input_sha256,
        _source_plan_sha256,
        source_plan,
        _semantic_pipeline_sha256,
        critic,
    ) = base.load_semantic_failure_context()

    try:
        payload = json.loads(
            V5_REPAIR_02_CACHE.read_text(
                encoding="utf-8"
            )
        )

        repair_cache = (
            base.PlanRepairAttempt02Cache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "V5 repair-attempt-2 cache is invalid."
        ) from exc

    closure_critic = (
        find_persisted_critic_findings(
            before_plan=source_plan,
            repaired_plan=(
                repair_cache.repaired_plan
            ),
            critic=critic,
        )
    )

    print()
    print("=" * 72)
    print("V5 DETERMINISTIC REPAIR CLOSURE CHECK")
    print("=" * 72)
    print()

    if closure_critic is None:
        print(
            "No definitely persisted MEDIUM/HIGH critic "
            "claim was detected."
        )

        print()
        print(
            "IMPORTANT: this does NOT prove the repair is "
            "semantically safe."
        )

        print(
            "Normal verification-gate and terminal semantic "
            "validation are still required."
        )

        return

    print(
        "REPAIR CLOSURE: FAILED"
    )

    print()

    print(
        f"Persisted findings: "
        f"{len(closure_critic.findings)}"
    )

    print()

    for index, finding in enumerate(
        closure_critic.findings,
        start=1,
    ):
        print(
            f"{index}. [{finding.severity.value}] "
            f"{finding.issue_type.value}"
        )

        print(
            f"   Claim: {finding.claim}"
        )

        print(
            f"   Explanation: "
            f"{finding.explanation}"
        )

        print()

    print(
        "V5 repair budget is exhausted at 2 of 2."
    )

    print(
        "ZERO must reject this candidate without spending "
        "another semantic-audit call."
    )


def main() -> None:
    if (
        V5_REPAIR_02_CACHE
        == V4_REPAIR_02_CACHE
    ):
        raise RuntimeError(
            "V5 repair cache unexpectedly overlaps "
            "the V4 cache."
        )

    if not V2_REPAIR_01_CACHE.exists():
        raise RuntimeError(
            "Reusable repair-attempt-1 cache was not found: "
            f"{V2_REPAIR_01_CACHE}"
        )

    if not V5_SEMANTIC_01_CACHE.exists():
        raise RuntimeError(
            "V5 semantic-audit cache was not found: "
            f"{V5_SEMANTIC_01_CACHE}"
        )

    # V5 begins after the valid repair attempt 1 produced under
    # the current hardened plan_repair.py.
    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # Repair attempt 2 must use the V5 deterministic-accounting
    # semantic critic containing all current findings.
    base.SEMANTIC_CACHE_PATH = (
        V5_SEMANTIC_01_CACHE
    )

    # Keep V5 repair attempt 2 isolated from earlier experiments.
    base.CACHE_PATH = (
        V5_REPAIR_02_CACHE
    )

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — REPAIR ATTEMPT 2 OF 2"
    )
    print("=" * 72)

    print()
    print(
        "Plan-repair budget before this stage: "
        "1 of 2 used"
    )

    print()
    print(
        "Reused repair-attempt-1 input:"
    )
    print(
        V2_REPAIR_01_CACHE
    )

    print()
    print(
        "V5 semantic-audit input:"
    )
    print(
        V5_SEMANTIC_01_CACHE
    )

    print()
    print(
        "V4 repair-attempt-2 cache preserved:"
    )
    print(
        V4_REPAIR_02_CACHE
    )

    print()
    print(
        "V5 repair-attempt-2 output:"
    )
    print(
        V5_REPAIR_02_CACHE
    )

    print()

    # Existing cached single-call repair machinery:
    # - dry-run remains 0 calls
    # - max-new-calls remains bounded to 0 or 1
    # - deterministic hard validation still runs
    base.main()

    # If a paid/cached repair result now exists, apply the production
    # one-way closure guard locally for immediate feedback.
    inspect_closure_if_available()


if __name__ == "__main__":
    main()