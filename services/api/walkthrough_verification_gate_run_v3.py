from pathlib import Path

import walkthrough_plan_repair_run_02 as repair02_base
import walkthrough_semantic_critic_run as semantic_base
import walkthrough_verification_gate_run as base


RUN_ID = "semantic-coverage-v3"

V1_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-verification-gate-after-repair-02.json"
)

V2_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "verification-gate-after-repair-02.json"
)

V2_REPAIR_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-01.json"
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

V3_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "verification-gate-after-repair-02.json"
)


def main() -> None:
    protected_paths = {
        V1_GATE_CACHE,
        V2_GATE_CACHE,
    }

    fresh_paths = {
        V3_GATE_CACHE,
    }

    if protected_paths & fresh_paths:
        raise RuntimeError(
            "V3 gate cache unexpectedly overlaps "
            "an earlier experiment cache."
        )

    required_paths = (
        V2_REPAIR_01_CACHE,
        V3_SEMANTIC_01_CACHE,
        V3_REPAIR_02_CACHE,
    )

    for path in required_paths:
        if not path.exists():
            raise RuntimeError(
                "Required V3 input cache was not found: "
                f"{path}"
            )

    # load_repaired_plan_context() belongs to
    # walkthrough_semantic_critic_run.py.
    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # load_semantic_failure_context() belongs to
    # walkthrough_plan_repair_run_02.py.
    repair02_base.SEMANTIC_CACHE_PATH = (
        V3_SEMANTIC_01_CACHE
    )

    # load_final_repaired_context() belongs to
    # walkthrough_verification_gate_run.py.
    base.REPAIR_02_CACHE_PATH = (
        V3_REPAIR_02_CACHE
    )

    # Keep the V3 gate result isolated.
    base.CACHE_PATH = (
        V3_GATE_CACHE
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
        "V1 gate cache preserved:"
    )
    print(
        V1_GATE_CACHE
    )

    print()
    print(
        "V2 gate cache preserved:"
    )
    print(
        V2_GATE_CACHE
    )

    print()
    print(
        "V3 repair-attempt-2 input:"
    )
    print(
        V3_REPAIR_02_CACHE
    )

    print()
    print(
        "V3 gate output:"
    )
    print(
        V3_GATE_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()