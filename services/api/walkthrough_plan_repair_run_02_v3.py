from pathlib import Path

import walkthrough_plan_repair_run_02 as base
import walkthrough_semantic_critic_run as semantic_base


RUN_ID = "semantic-coverage-v3"

V1_REPAIR_02_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-plan-repair-attempt-02.json"
)

V2_REPAIR_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-01.json"
)

V2_REPAIR_02_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-02.json"
)

V3_SEMANTIC_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "semantic-critic-after-repair-01.json"
)

V3_REPAIR_02_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "plan-repair-attempt-02.json"
)


def main() -> None:
    protected_paths = {
        V1_REPAIR_02_CACHE,
        V2_REPAIR_02_CACHE,
    }

    fresh_paths = {
        V3_REPAIR_02_CACHE,
    }

    if protected_paths & fresh_paths:
        raise RuntimeError(
            "V3 cache path unexpectedly overlaps "
            "an earlier experiment cache."
        )

    if not V2_REPAIR_01_CACHE.exists():
        raise RuntimeError(
            "Reusable repair-attempt-1 cache was not found: "
            f"{V2_REPAIR_01_CACHE}"
        )

    if not V3_SEMANTIC_01_CACHE.exists():
        raise RuntimeError(
            "V3 semantic-audit-1 cache was not found: "
            f"{V3_SEMANTIC_01_CACHE}"
        )

    # V3 begins after the valid repair attempt 1 that was produced
    # under the current hardened plan_repair.py.
    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # The second repair must use the NEW exhaustive V3 semantic critic.
    base.SEMANTIC_CACHE_PATH = (
        V3_SEMANTIC_01_CACHE
    )

    # Keep the final V3 repair isolated from V1 and V2.
    base.CACHE_PATH = (
        V3_REPAIR_02_CACHE
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
        "V3 exhaustive semantic-audit input:"
    )
    print(
        V3_SEMANTIC_01_CACHE
    )

    print()
    print(
        "V1 repair-attempt-2 cache preserved:"
    )
    print(
        V1_REPAIR_02_CACHE
    )

    print()
    print(
        "V2 repair-attempt-2 cache preserved:"
    )
    print(
        V2_REPAIR_02_CACHE
    )

    print()
    print(
        "V3 repair-attempt-2 output:"
    )
    print(
        V3_REPAIR_02_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()