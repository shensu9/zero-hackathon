from pathlib import Path

import walkthrough_plan_repair_run as base


RUN_ID = "repair-policy-v2"

ORIGINAL_REJECTED_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-plan-repair-attempt-01.json"
)

FRESH_CACHE = Path(
    "sample_data/private/"
    "walkthrough-01-repair-policy-v2-"
    "plan-repair-attempt-01.json"
)


def main() -> None:
    if FRESH_CACHE == ORIGINAL_REJECTED_CACHE:
        raise RuntimeError(
            "Fresh-run cache path unexpectedly matches "
            "the rejected-run cache."
        )

    base.CACHE_PATH = FRESH_CACHE

    print("=" * 72)
    print(
        "ZERO FRESH BOUNDED RUN — "
        f"{RUN_ID}"
    )
    print("=" * 72)

    print()
    print(
        "Rejected-run cache preserved:"
    )
    print(
        ORIGINAL_REJECTED_CACHE
    )

    print()
    print(
        "Fresh attempt-1 cache:"
    )
    print(
        FRESH_CACHE
    )

    print()

    base.main()


if __name__ == "__main__":
    main()