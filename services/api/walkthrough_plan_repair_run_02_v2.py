from pathlib import Path

import walkthrough_plan_repair_run_02 as base
import walkthrough_semantic_critic_run as semantic_base


RUN_ID = "repair-policy-v2"

REJECTED_REPAIR_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-plan-repair-attempt-01.json"
)

REJECTED_SEMANTIC_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-critic-after-repair-01.json"
)

REJECTED_REPAIR_02_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-plan-repair-attempt-02.json"
)

V2_REPAIR_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-01.json"
)

V2_SEMANTIC_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "semantic-critic-after-repair-01.json"
)

V2_REPAIR_02_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-02.json"
)


def main() -> None:
    protected_paths = {
        REJECTED_REPAIR_01_CACHE,
        REJECTED_SEMANTIC_01_CACHE,
        REJECTED_REPAIR_02_CACHE,
    }

    fresh_paths = {
        V2_REPAIR_01_CACHE,
        V2_SEMANTIC_01_CACHE,
        V2_REPAIR_02_CACHE,
    }

    if protected_paths & fresh_paths:
        raise RuntimeError(
            "A V2 cache path unexpectedly overlaps a rejected-run cache."
        )

    if not V2_REPAIR_01_CACHE.exists():
        raise RuntimeError(
            "V2 repair-attempt-1 cache was not found: "
            f"{V2_REPAIR_01_CACHE}"
        )

    if not V2_SEMANTIC_01_CACHE.exists():
        raise RuntimeError(
            "V2 semantic-audit-1 cache was not found: "
            f"{V2_SEMANTIC_01_CACHE}"
        )

    # load_repaired_plan_context() is defined in
    # walkthrough_semantic_critic_run.py and reads that module's
    # REPAIR_CACHE_PATH global. Point it at V2 attempt 1.
    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # load_semantic_failure_context() is defined in
    # walkthrough_plan_repair_run_02.py and reads that module's
    # SEMANTIC_CACHE_PATH global. Point it at the V2 critic.
    base.SEMANTIC_CACHE_PATH = (
        V2_SEMANTIC_01_CACHE
    )

    # Keep repair attempt 2 isolated as well.
    base.CACHE_PATH = (
        V2_REPAIR_02_CACHE
    )

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — REPAIR ATTEMPT 2 OF 2"
    )
    print("=" * 72)

    print()
    print(
        "Rejected-run attempt-2 cache preserved:"
    )
    print(
        REJECTED_REPAIR_02_CACHE
    )

    print()
    print(
        "V2 repair-attempt-1 input:"
    )
    print(
        V2_REPAIR_01_CACHE
    )

    print()
    print(
        "V2 semantic-audit-1 input:"
    )
    print(
        V2_SEMANTIC_01_CACHE
    )

    print()
    print(
        "V2 repair-attempt-2 output:"
    )
    print(
        V2_REPAIR_02_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()