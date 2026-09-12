from pathlib import Path

import walkthrough_plan_repair_run_02 as repair02_base
import walkthrough_semantic_critic_run as semantic_base
import walkthrough_verification_gate_run as base


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

REJECTED_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-verification-gate-after-repair-02.json"
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

V2_GATE_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "verification-gate-after-repair-02.json"
)


def main() -> None:
    protected_paths = {
        REJECTED_REPAIR_01_CACHE,
        REJECTED_SEMANTIC_01_CACHE,
        REJECTED_REPAIR_02_CACHE,
        REJECTED_GATE_CACHE,
    }

    fresh_paths = {
        V2_REPAIR_01_CACHE,
        V2_SEMANTIC_01_CACHE,
        V2_REPAIR_02_CACHE,
        V2_GATE_CACHE,
    }

    if protected_paths & fresh_paths:
        raise RuntimeError(
            "A V2 cache path unexpectedly overlaps "
            "a rejected-run cache."
        )

    required_v2_paths = (
        V2_REPAIR_01_CACHE,
        V2_SEMANTIC_01_CACHE,
        V2_REPAIR_02_CACHE,
    )

    for path in required_v2_paths:
        if not path.exists():
            raise RuntimeError(
                "Required V2 cache was not found: "
                f"{path}"
            )

    # load_repaired_plan_context() belongs to
    # walkthrough_semantic_critic_run.py and reads this global.
    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # load_semantic_failure_context() belongs to
    # walkthrough_plan_repair_run_02.py and reads this global.
    repair02_base.SEMANTIC_CACHE_PATH = (
        V2_SEMANTIC_01_CACHE
    )

    # walkthrough_verification_gate_run.py loads repair attempt 2
    # through its module-local alias. Point it at the V2 result.
    base.REPAIR_02_CACHE_PATH = (
        V2_REPAIR_02_CACHE
    )

    # Keep gate output isolated from the rejected run.
    base.CACHE_PATH = (
        V2_GATE_CACHE
    )

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — VERIFICATION GATE"
    )
    print("=" * 72)

    print()
    print(
        "Rejected-run gate cache preserved:"
    )
    print(
        REJECTED_GATE_CACHE
    )

    print()
    print(
        "V2 repair-attempt-2 input:"
    )
    print(
        V2_REPAIR_02_CACHE
    )

    print()
    print(
        "V2 gate output cache:"
    )
    print(
        V2_GATE_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()