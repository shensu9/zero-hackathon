import json

import benchmark_suite as suite

from benchmark_cases import BENCHMARK_CASES
from plan_evaluator import EVALUATOR_VERSION


SUITE_ID = "benchmark_suite_02"

EXPECTED_EVALUATOR_VERSION = (
    "neutral_evaluator_v2"
)


def main() -> None:
    # ---------------------------------------------------------------
    # Freeze benchmark protocol
    # ---------------------------------------------------------------

    if (
        EVALUATOR_VERSION
        != EXPECTED_EVALUATOR_VERSION
    ):
        raise RuntimeError(
            "Benchmark Suite 02 requires "
            f"{EXPECTED_EVALUATOR_VERSION}, "
            f"but found {EVALUATOR_VERSION}."
        )

    suite.SUITE_ID = SUITE_ID

    suite.RESULTS_DIR = (
        suite.REPO_ROOT
        / "results"
        / SUITE_ID
    )

    # ---------------------------------------------------------------
    # Never silently overwrite an existing Suite 02.
    #
    # A benchmark run should remain immutable evidence.
    # ---------------------------------------------------------------

    if (
        suite.RESULTS_DIR.exists()
        and any(
            suite.RESULTS_DIR.iterdir()
        )
    ):
        raise RuntimeError(
            "Benchmark Suite 02 results already exist. "
            "Do not overwrite an existing benchmark run."
        )

    suite.RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------------
    # Record protocol before making any model calls.
    # ---------------------------------------------------------------

    protocol = {
        "suite_id":
            SUITE_ID,

        "evaluator_version":
            EVALUATOR_VERSION,

        "benchmark_case_ids": [
            case.case_id
            for case in BENCHMARK_CASES
        ],

        "benchmark_case_count":
            len(BENCHMARK_CASES),

        "object_dna_policy":
            "fixed validated fixture cache",

        "baseline_policy":
            "fresh generation for every case",

        "zero_policy":
            (
                "fresh capability-bound generation, "
                "deterministic validation, semantic critic, "
                "maximum two repair attempts"
            ),

        "comparative_scoring":
            (
                "neutral evaluator only; "
                "ZERO internal critic is not the benchmark judge"
            ),

        "suite_01_results_reused":
            False,

        "note":
            (
                "Post-calibration exploratory benchmark. "
                "Evaluator v2 is frozen before this run."
            ),
    }

    (
        suite.RESULTS_DIR
        / "protocol.json"
    ).write_text(
        json.dumps(
            protocol,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "Benchmark protocol:"
    )

    print(
        json.dumps(
            protocol,
            indent=2,
            ensure_ascii=False,
        )
    )

    print()

    # Run the existing persistent five-case suite.
    suite.main()


if __name__ == "__main__":
    main()