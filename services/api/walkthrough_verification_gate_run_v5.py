from pathlib import Path

import walkthrough_plan_repair_run_02 as repair02_base
import walkthrough_semantic_critic_run as semantic_base
import walkthrough_verification_gate_run as base


RUN_ID = "repair-closure-v5"

V2_REPAIR_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-01.json"
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

V1_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-verification-gate-after-repair-02.json"
)

V2_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "verification-gate-after-repair-02.json"
)

V3_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "verification-gate-after-repair-02.json"
)

V5_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-closure-v5-"
    "verification-gate-after-repair-02.json"
)


def main() -> None:
    protected_paths = {
        V1_GATE_CACHE,
        V2_GATE_CACHE,
        V3_GATE_CACHE,
    }

    if V5_GATE_CACHE in protected_paths:
        raise RuntimeError(
            "V5 gate cache unexpectedly overlaps "
            "an earlier experiment cache."
        )

    required_paths = (
        V2_REPAIR_01_CACHE,
        V5_SEMANTIC_01_CACHE,
        V5_REPAIR_02_CACHE,
    )

    for path in required_paths:
        if not path.exists():
            raise RuntimeError(
                "Required V5 input cache was not found: "
                f"{path}"
            )

    # V5 reuses the valid repair-attempt-1 result from V2.
    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # Reconstruct V5 repair attempt 2 from the V5 semantic critic.
    repair02_base.SEMANTIC_CACHE_PATH = (
        V5_SEMANTIC_01_CACHE
    )

    # Point the generic gate runner at V5's final repaired plan.
    base.REPAIR_02_CACHE_PATH = (
        V5_REPAIR_02_CACHE
    )

    # Keep V5 gate output isolated.
    base.CACHE_PATH = (
        V5_GATE_CACHE
    )

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — VERIFICATION GATE"
    )
    print("=" * 72)

    print()
    print(
        "Plan-repair budget: 2 of 2 used"
    )

    print()
    print(
        "V5 repair closure: no definitely persisted "
        "MEDIUM/HIGH claim detected"
    )

    print()
    print(
        "V5 repair-attempt-2 input:"
    )
    print(
        V5_REPAIR_02_CACHE
    )

    print()
    print(
        "V5 gate output:"
    )
    print(
        V5_GATE_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()