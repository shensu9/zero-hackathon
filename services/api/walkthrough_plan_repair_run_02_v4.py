from pathlib import Path

import walkthrough_plan_repair_run_02 as base
import walkthrough_semantic_critic_run as semantic_base


RUN_ID = "semantic-accounting-v4"

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

V3_REPAIR_02_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "plan-repair-attempt-02.json"
)

V4_SEMANTIC_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-accounting-v4-"
    "semantic-critic-after-repair-01.json"
)

V4_REPAIR_02_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-accounting-v4-"
    "plan-repair-attempt-02.json"
)


def main() -> None:
    protected_paths = {
        V1_REPAIR_02_CACHE,
        V2_REPAIR_02_CACHE,
        V3_REPAIR_02_CACHE,
    }

    if V4_REPAIR_02_CACHE in protected_paths:
        raise RuntimeError(
            "V4 repair cache unexpectedly overlaps "
            "an earlier experiment cache."
        )

    if not V2_REPAIR_01_CACHE.exists():
        raise RuntimeError(
            "Reusable repair-attempt-1 cache was not found: "
            f"{V2_REPAIR_01_CACHE}"
        )

    if not V4_SEMANTIC_01_CACHE.exists():
        raise RuntimeError(
            "V4 semantic-audit-1 cache was not found: "
            f"{V4_SEMANTIC_01_CACHE}"
        )

    # V4 begins after the same valid repair attempt 1 produced
    # under the current hardened plan_repair.py.
    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # Repair attempt 2 must use the deterministic-accounting
    # V4 semantic critic result.
    base.SEMANTIC_CACHE_PATH = (
        V4_SEMANTIC_01_CACHE
    )

    # Keep V4 repair attempt 2 isolated.
    base.CACHE_PATH = (
        V4_REPAIR_02_CACHE
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
        "V4 deterministic semantic-audit input:"
    )
    print(
        V4_SEMANTIC_01_CACHE
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
        "V3 repair-attempt-2 cache preserved:"
    )
    print(
        V3_REPAIR_02_CACHE
    )

    print()
    print(
        "V4 repair-attempt-2 output:"
    )
    print(
        V4_REPAIR_02_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()