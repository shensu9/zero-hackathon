from pathlib import Path

import walkthrough_final_semantic_critic_run as base
import walkthrough_plan_repair_run_02 as repair02_base
import walkthrough_semantic_critic_run as semantic_base
import walkthrough_verification_gate_run as gate_base


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

REJECTED_FINAL_SEMANTIC_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-final-semantic-critic.json"
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

V2_FINAL_SEMANTIC_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "final-semantic-critic.json"
)


def main() -> None:
    protected_paths = {
        REJECTED_REPAIR_01_CACHE,
        REJECTED_SEMANTIC_01_CACHE,
        REJECTED_REPAIR_02_CACHE,
        REJECTED_GATE_CACHE,
        REJECTED_FINAL_SEMANTIC_CACHE,
    }

    fresh_paths = {
        V2_REPAIR_01_CACHE,
        V2_SEMANTIC_01_CACHE,
        V2_REPAIR_02_CACHE,
        V2_GATE_CACHE,
        V2_FINAL_SEMANTIC_CACHE,
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
        V2_GATE_CACHE,
    )

    for path in required_v2_paths:
        if not path.exists():
            raise RuntimeError(
                "Required V2 cache was not found: "
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
        V2_SEMANTIC_01_CACHE
    )

    # load_final_repaired_context() belongs to
    # walkthrough_verification_gate_run.py.
    gate_base.REPAIR_02_CACHE_PATH = (
        V2_REPAIR_02_CACHE
    )

    # load_post_gate_context() belongs to
    # walkthrough_final_semantic_critic_run.py.
    base.GATE_CACHE_PATH = (
        V2_GATE_CACHE
    )

    # Keep the terminal critic result isolated from
    # the rejected experiment.
    base.CACHE_PATH = (
        V2_FINAL_SEMANTIC_CACHE
    )

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — FINAL SEMANTIC AUDIT"
    )
    print("=" * 72)

    print()
    print(
        "Rejected-run final semantic cache preserved:"
    )
    print(
        REJECTED_FINAL_SEMANTIC_CACHE
    )

    print()
    print(
        "V2 gate input cache:"
    )
    print(
        V2_GATE_CACHE
    )

    print()
    print(
        "V2 final semantic output cache:"
    )
    print(
        V2_FINAL_SEMANTIC_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()