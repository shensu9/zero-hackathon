from pathlib import Path

import walkthrough_final_semantic_critic_run as base
import walkthrough_plan_repair_run_02 as repair02_base
import walkthrough_semantic_critic_run as semantic_base
import walkthrough_verification_gate_run as gate_base


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

V5_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-closure-v5-"
    "verification-gate-after-repair-02.json"
)

V1_FINAL_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-final-semantic-critic.json"
)

V2_FINAL_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "final-semantic-critic.json"
)

V3_FINAL_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "final-semantic-critic.json"
)

V4_FINAL_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-accounting-v4-"
    "final-semantic-critic.json"
)

V5_FINAL_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-closure-v5-"
    "final-semantic-critic.json"
)


def main() -> None:
    protected_paths = {
        V1_FINAL_CACHE,
        V2_FINAL_CACHE,
        V3_FINAL_CACHE,
        V4_FINAL_CACHE,
    }

    if V5_FINAL_CACHE in protected_paths:
        raise RuntimeError(
            "V5 final-semantic cache unexpectedly overlaps "
            "an earlier experiment cache."
        )

    required_paths = (
        V2_REPAIR_01_CACHE,
        V5_SEMANTIC_01_CACHE,
        V5_REPAIR_02_CACHE,
        V5_GATE_CACHE,
    )

    for path in required_paths:
        if not path.exists():
            raise RuntimeError(
                "Required V5 input cache was not found: "
                f"{path}"
            )

    # Reconstruct the same repair-attempt-1 plan used by V5.
    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # Reconstruct V5 repair attempt 2 from the exact V5 critic.
    repair02_base.SEMANTIC_CACHE_PATH = (
        V5_SEMANTIC_01_CACHE
    )

    # Reconstruct the exact V5 final repaired plan.
    gate_base.REPAIR_02_CACHE_PATH = (
        V5_REPAIR_02_CACHE
    )

    # Reconstruct the exact V5 post-gate SOLVED outcome.
    base.GATE_CACHE_PATH = (
        V5_GATE_CACHE
    )

    # Keep the terminal semantic result isolated.
    base.CACHE_PATH = (
        V5_FINAL_CACHE
    )

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — FINAL SEMANTIC AUDIT"
    )
    print("=" * 72)

    print()
    print(
        "Plan-repair budget: 2 of 2 used"
    )

    print()
    print(
        "Repair closure: no definitely persisted "
        "MEDIUM/HIGH claim detected"
    )

    print()
    print(
        "Verification gate: passed with 0 model calls"
    )

    print()
    print(
        "V5 verification-gate input:"
    )
    print(
        V5_GATE_CACHE
    )

    print()
    print(
        "V5 final semantic output:"
    )
    print(
        V5_FINAL_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()