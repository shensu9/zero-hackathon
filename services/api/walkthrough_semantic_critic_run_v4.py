from pathlib import Path

import walkthrough_semantic_critic_run as base


RUN_ID = "semantic-accounting-v4"

V1_SEMANTIC_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-critic-after-repair-01.json"
)

V2_REPAIR_01_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-01.json"
)

V2_SEMANTIC_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "semantic-critic-after-repair-01.json"
)

V3_SEMANTIC_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-coverage-v3-"
    "semantic-critic-after-repair-01.json"
)

V4_SEMANTIC_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-accounting-v4-"
    "semantic-critic-after-repair-01.json"
)


def main() -> None:
    protected_paths = {
        V1_SEMANTIC_CACHE,
        V2_SEMANTIC_CACHE,
        V3_SEMANTIC_CACHE,
    }

    if V4_SEMANTIC_CACHE in protected_paths:
        raise RuntimeError(
            "V4 semantic cache unexpectedly overlaps "
            "an earlier experiment cache."
        )

    if not V2_REPAIR_01_CACHE.exists():
        raise RuntimeError(
            "Reusable repair-attempt-1 cache was not found: "
            f"{V2_REPAIR_01_CACHE}"
        )

    # The repair pipeline has not changed since V2.
    # Reuse repair attempt 1 rather than buying it again.
    base.REPAIR_CACHE_PATH = (
        V2_REPAIR_01_CACHE
    )

    # The deterministic semantic-accounting critic gets
    # a completely new experiment namespace.
    base.CACHE_PATH = (
        V4_SEMANTIC_CACHE
    )

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — SEMANTIC AUDIT AFTER REPAIR 1"
    )
    print("=" * 72)

    print()
    print(
        "Plan-repair budget entering V4: "
        "1 of 2 already used"
    )

    print()
    print(
        "Reusing valid repair-attempt-1 cache:"
    )
    print(
        V2_REPAIR_01_CACHE
    )

    print()
    print(
        "V1 semantic cache preserved:"
    )
    print(
        V1_SEMANTIC_CACHE
    )

    print()
    print(
        "V2 semantic cache preserved:"
    )
    print(
        V2_SEMANTIC_CACHE
    )

    print()
    print(
        "V3 semantic cache preserved:"
    )
    print(
        V3_SEMANTIC_CACHE
    )

    print()
    print(
        "V4 semantic output cache:"
    )
    print(
        V4_SEMANTIC_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()