from pathlib import Path

import walkthrough_semantic_critic_run as base


RUN_ID = "semantic-coverage-v3"

V1_REPAIR_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-plan-repair-attempt-01.json"
)

V1_SEMANTIC_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-critic-after-repair-01.json"
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

V3_SEMANTIC_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "semantic-critic-after-repair-01.json"
)


def main() -> None:
    protected_paths = {
        V1_REPAIR_01_CACHE,
        V1_SEMANTIC_01_CACHE,
        V2_SEMANTIC_01_CACHE,
    }

    fresh_paths = {
        V3_SEMANTIC_01_CACHE,
    }

    if protected_paths & fresh_paths:
        raise RuntimeError(
            "V3 cache path unexpectedly overlaps "
            "an earlier experiment cache."
        )

    if not V2_REPAIR_01_CACHE.exists():
        raise RuntimeError(
            "Reusable V2 repair-attempt-1 cache was not found: "
            f"{V2_REPAIR_01_CACHE}"
        )

    # V3 deliberately reuses V2 repair attempt 1.
    #
    # That repair was generated under the current hardened plan_repair.py.
    # Only semantic_critic.py changed afterward, so purchasing repair
    # attempt 1 again would be unnecessary and would not reflect the
    # bounded production pipeline.
    base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # All semantic output for the new critic policy gets a fresh namespace.
    base.CACHE_PATH = (
        V3_SEMANTIC_01_CACHE
    )

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — SEMANTIC AUDIT AFTER REPAIR 1"
    )
    print("=" * 72)

    print()
    print(
        "Plan-repair budget entering V3: 1 of 2 already used"
    )

    print()
    print(
        "Reusing valid V2 repair-attempt-1 cache:"
    )
    print(
        V2_REPAIR_01_CACHE
    )

    print()
    print(
        "V1 semantic cache preserved:"
    )
    print(
        V1_SEMANTIC_01_CACHE
    )

    print()
    print(
        "V2 semantic cache preserved:"
    )
    print(
        V2_SEMANTIC_01_CACHE
    )

    print()
    print(
        "V3 semantic output cache:"
    )
    print(
        V3_SEMANTIC_01_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()