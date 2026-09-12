from pathlib import Path

import walkthrough_semantic_critic_run as base


RUN_ID = "repair-policy-v2"

REJECTED_REPAIR_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-plan-repair-attempt-01.json"
)

V2_REPAIR_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-01.json"
)

REJECTED_SEMANTIC_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-semantic-critic-after-repair-01.json"
)

V2_SEMANTIC_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "semantic-critic-after-repair-01.json"
)


def main() -> None:
    if V2_REPAIR_CACHE == REJECTED_REPAIR_CACHE:
        raise RuntimeError(
            "V2 repair cache unexpectedly matches "
            "the rejected-run repair cache."
        )

    if V2_SEMANTIC_CACHE == REJECTED_SEMANTIC_CACHE:
        raise RuntimeError(
            "V2 semantic cache unexpectedly matches "
            "the rejected-run semantic cache."
        )

    if not V2_REPAIR_CACHE.exists():
        raise RuntimeError(
            "V2 repair-attempt-1 cache was not found: "
            f"{V2_REPAIR_CACHE}"
        )

    base.REPAIR_CACHE_PATH = V2_REPAIR_CACHE
    base.CACHE_PATH = V2_SEMANTIC_CACHE

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID} — SEMANTIC AUDIT 1"
    )
    print("=" * 72)

    print()
    print(
        "Rejected repair cache preserved:"
    )
    print(
        REJECTED_REPAIR_CACHE
    )

    print()
    print(
        "Rejected semantic cache preserved:"
    )
    print(
        REJECTED_SEMANTIC_CACHE
    )

    print()
    print(
        "V2 repair input cache:"
    )
    print(
        V2_REPAIR_CACHE
    )

    print()
    print(
        "V2 semantic output cache:"
    )
    print(
        V2_SEMANTIC_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()