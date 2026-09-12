from pathlib import Path

import walkthrough_final_semantic_critic_retry_run as retry_base
import walkthrough_final_semantic_critic_run as final_base
import walkthrough_plan_repair_run_02 as repair02_base
import walkthrough_semantic_critic_run as semantic_base
import walkthrough_verification_gate_run as gate_base


RUN_ID = "semantic-coverage-v3"

V1_RETRY_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-final-semantic-critic-"
    "truncation-retry-01.json"
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

V3_STANDARD_FINAL_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "final-semantic-critic.json"
)

V3_RETRY_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "final-semantic-critic-truncation-retry-01.json"
)


def main() -> None:
    if V3_RETRY_CACHE == V1_RETRY_CACHE:
        raise RuntimeError(
            "V3 retry cache unexpectedly overlaps "
            "the rejected V1 retry cache."
        )

    required_paths = (
        V2_REPAIR_01_CACHE,
        V3_SEMANTIC_01_CACHE,
        V3_REPAIR_02_CACHE,
        V3_GATE_CACHE,
    )

    for path in required_paths:
        if not path.exists():
            raise RuntimeError(
                "Required V3 input cache was not found: "
                f"{path}"
            )

    # V3 deliberately reuses repair attempt 1 from V2.
    semantic_base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # V3 repair attempt 2 was driven by the new exhaustive critic.
    repair02_base.SEMANTIC_CACHE_PATH = (
        V3_SEMANTIC_01_CACHE
    )

    # Reconstruct the exact V3 final repaired plan.
    gate_base.REPAIR_02_CACHE_PATH = (
        V3_REPAIR_02_CACHE
    )

    # Reconstruct the exact post-gate V3 SOLVED outcome.
    final_base.GATE_CACHE_PATH = (
        V3_GATE_CACHE
    )

    # The normal V3 final audit did not produce a valid cache because
    # the response was truncated. Keep its expected path isolated.
    final_base.CACHE_PATH = (
        V3_STANDARD_FINAL_CACHE
    )

    # The generic truncation-retry runner imported this path by value.
    # Patch the alias too so all cache reporting/checks refer to V3.
    retry_base.STANDARD_FINAL_CACHE_PATH = (
        V3_STANDARD_FINAL_CACHE
    )

    # Keep the V3 transport-retry result isolated from every earlier run.
    retry_base.CACHE_PATH = (
        V3_RETRY_CACHE
    )

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — FINAL SEMANTIC TRANSPORT RETRY"
    )
    print("=" * 72)

    print()
    print(
        "Plan-repair budget remains exhausted: "
        "2 of 2 used"
    )

    print()
    print(
        "V1 retry cache preserved:"
    )
    print(
        V1_RETRY_CACHE
    )

    print()
    print(
        "V3 normal final-semantic cache:"
    )
    print(
        V3_STANDARD_FINAL_CACHE
    )

    print()
    print(
        "V3 retry output cache:"
    )
    print(
        V3_RETRY_CACHE
    )

    print()
    print(
        "Transport policy only: "
        "main critic max_tokens 4500 -> 8000"
    )

    print()

    retry_base.main()


if __name__ == "__main__":
    main()