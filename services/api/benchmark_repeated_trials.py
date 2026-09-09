import json
import sys
from pathlib import Path

import benchmark_suite as suite

from benchmark_cases import BENCHMARK_CASES
from plan_evaluator import EVALUATOR_VERSION


EXPECTED_EVALUATOR_VERSION = (
    "neutral_evaluator_v2"
)

EXISTING_TRIAL_ID = (
    "benchmark_suite_03"
)

NEW_TRIAL_IDS = (
    "benchmark_suite_04",
    "benchmark_suite_05",
)

ALL_TRIAL_IDS = (
    EXISTING_TRIAL_ID,
    *NEW_TRIAL_IDS,
)


REPO_ROOT = Path(
    __file__
).resolve().parents[2]

RESULTS_ROOT = (
    REPO_ROOT
    / "results"
)

REPEATED_RESULTS_DIR = (
    RESULTS_ROOT
    / "benchmark_repeated_01"
)


def configure_utf8_console() -> None:
    for stream in (
        sys.stdout,
        sys.stderr,
    ):
        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(reconfigure):
            try:
                reconfigure(
                    encoding="utf-8"
                )
            except Exception:
                pass


def trial_dir(
    trial_id: str,
) -> Path:
    return (
        RESULTS_ROOT
        / trial_id
    )


def trial_summary_path(
    trial_id: str,
) -> Path:
    return (
        trial_dir(trial_id)
        / "summary.json"
    )


def case_result_path(
    trial_id: str,
    case,
) -> Path:
    return (
        trial_dir(trial_id)
        / f"{case.case_id}_{case.name}.json"
    )


def verify_existing_suite_03() -> None:
    """
    Suite 03 is Trial 1.

    Require its complete saved result rather than silently
    regenerating or substituting another run.
    """

    summary_path = trial_summary_path(
        EXISTING_TRIAL_ID
    )

    if not summary_path.exists():
        raise RuntimeError(
            "Suite 03 summary is missing. "
            "Cannot use it as Trial 1."
        )

    payload = json.loads(
        summary_path.read_text(
            encoding="utf-8"
        )
    )

    if payload.get(
        "completed_cases"
    ) != len(BENCHMARK_CASES):
        raise RuntimeError(
            "Suite 03 is not a complete 5/5 benchmark."
        )

    if payload.get(
        "failed_cases"
    ) != 0:
        raise RuntimeError(
            "Suite 03 contains failed cases."
        )

    for case in BENCHMARK_CASES:
        path = case_result_path(
            EXISTING_TRIAL_ID,
            case,
        )

        if not path.exists():
            raise RuntimeError(
                f"Suite 03 is missing result: {path}"
            )


def write_trial_protocol(
    trial_id: str,
) -> None:
    destination = trial_dir(
        trial_id
    )

    protocol = {
        "trial_id":
            trial_id,

        "repeated_benchmark_id":
            "benchmark_repeated_01",

        "evaluator_version":
            EVALUATOR_VERSION,

        "evaluator_policy":
            (
                "frozen neutral evaluator v2; "
                "no evaluator changes between trials"
            ),

        "object_dna_policy":
            "same frozen validated fixture cache",

        "benchmark_cases": [
            case.case_id
            for case in BENCHMARK_CASES
        ],

        "generation_policy":
            (
                "fresh baseline and fresh ZERO generation "
                "for every benchmark case"
            ),

        "external_resource_normalization":
            "enabled",

        "comparative_scoring":
            "neutral evaluator only",

        "prior_trial_results_reused_for_generation":
            False,
    }

    (
        destination
        / "repeated_trial_protocol.json"
    ).write_text(
        json.dumps(
            protocol,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def run_fresh_trial(
    trial_id: str,
) -> None:
    destination = trial_dir(
        trial_id
    )

    if (
        destination.exists()
        and any(
            destination.iterdir()
        )
    ):
        raise RuntimeError(
            f"{trial_id} already contains results. "
            "Repeated benchmark trials are immutable."
        )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    suite.SUITE_ID = trial_id
    suite.RESULTS_DIR = destination

    write_trial_protocol(
        trial_id
    )

    print()
    print("=" * 72)
    print(
        f"STARTING FRESH TRIAL: {trial_id}"
    )
    print("=" * 72)

    suite.main()

    summary_path = trial_summary_path(
        trial_id
    )

    if not summary_path.exists():
        raise RuntimeError(
            f"{trial_id} did not produce summary.json."
        )

    payload = json.loads(
        summary_path.read_text(
            encoding="utf-8"
        )
    )

    if (
        payload.get("completed_cases")
        != len(BENCHMARK_CASES)
        or payload.get("failed_cases") != 0
    ):
        raise RuntimeError(
            f"{trial_id} did not finish cleanly 5/5. "
            "Do not include it in the repeated aggregate yet."
        )


def load_case_metrics(
    trial_id: str,
    case,
) -> dict:
    path = case_result_path(
        trial_id,
        case,
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    baseline = payload[
        "baseline_evaluation"
    ]

    zero = payload[
        "zero_evaluation"
    ]

    return {
        "trial_id":
            trial_id,

        "case_id":
            case.case_id,

        "case_name":
            case.name,

        "baseline_medium_high":
            baseline[
                "medium_high_findings"
            ],

        "zero_medium_high":
            zero[
                "medium_high_findings"
            ],

        "baseline_accepted":
            baseline[
                "accepted"
            ],

        "zero_accepted":
            zero[
                "accepted"
            ],
    }


def mean(
    values,
) -> float:
    return (
        sum(values)
        / len(values)
    )


def median(
    values,
) -> float:
    ordered = sorted(
        values
    )

    middle = len(ordered) // 2

    if len(ordered) % 2 == 1:
        return float(
            ordered[middle]
        )

    return (
        ordered[middle - 1]
        + ordered[middle]
    ) / 2.0


def build_repeated_summary() -> dict:
    rows = []

    for trial_id in ALL_TRIAL_IDS:
        for case in BENCHMARK_CASES:
            rows.append(
                load_case_metrics(
                    trial_id,
                    case,
                )
            )

    baseline_values = [
        row[
            "baseline_medium_high"
        ]
        for row in rows
    ]

    zero_values = [
        row[
            "zero_medium_high"
        ]
        for row in rows
    ]

    baseline_total = sum(
        baseline_values
    )

    zero_total = sum(
        zero_values
    )

    absolute_reduction = (
        baseline_total
        - zero_total
    )

    reduction_percent = None

    if baseline_total > 0:
        reduction_percent = (
            absolute_reduction
            / baseline_total
            * 100.0
        )

    zero_wins = sum(
        1
        for row in rows
        if (
            row["zero_medium_high"]
            < row["baseline_medium_high"]
        )
    )

    ties = sum(
        1
        for row in rows
        if (
            row["zero_medium_high"]
            == row["baseline_medium_high"]
        )
    )

    baseline_wins = sum(
        1
        for row in rows
        if (
            row["zero_medium_high"]
            > row["baseline_medium_high"]
        )
    )

    baseline_accepts = sum(
        1
        for row in rows
        if row[
            "baseline_accepted"
        ]
    )

    zero_accepts = sum(
        1
        for row in rows
        if row[
            "zero_accepted"
        ]
    )

    per_case = []

    for case in BENCHMARK_CASES:
        case_rows = [
            row
            for row in rows
            if (
                row["case_id"]
                == case.case_id
            )
        ]

        baseline_case_values = [
            row[
                "baseline_medium_high"
            ]
            for row in case_rows
        ]

        zero_case_values = [
            row[
                "zero_medium_high"
            ]
            for row in case_rows
        ]

        per_case.append(
            {
                "case_id":
                    case.case_id,

                "case_name":
                    case.name,

                "baseline_values":
                    baseline_case_values,

                "zero_values":
                    zero_case_values,

                "baseline_mean":
                    mean(
                        baseline_case_values
                    ),

                "zero_mean":
                    mean(
                        zero_case_values
                    ),

                "baseline_median":
                    median(
                        baseline_case_values
                    ),

                "zero_median":
                    median(
                        zero_case_values
                    ),

                "zero_wins":
                    sum(
                        1
                        for row in case_rows
                        if (
                            row[
                                "zero_medium_high"
                            ]
                            < row[
                                "baseline_medium_high"
                            ]
                        )
                    ),

                "ties":
                    sum(
                        1
                        for row in case_rows
                        if (
                            row[
                                "zero_medium_high"
                            ]
                            == row[
                                "baseline_medium_high"
                            ]
                        )
                    ),

                "baseline_wins":
                    sum(
                        1
                        for row in case_rows
                        if (
                            row[
                                "zero_medium_high"
                            ]
                            > row[
                                "baseline_medium_high"
                            ]
                        )
                    ),
            }
        )

    return {
        "repeated_benchmark_id":
            "benchmark_repeated_01",

        "evaluator_version":
            EVALUATOR_VERSION,

        "trial_ids":
            list(
                ALL_TRIAL_IDS
            ),

        "trials":
            len(ALL_TRIAL_IDS),

        "benchmark_cases_per_trial":
            len(BENCHMARK_CASES),

        "paired_case_runs":
            len(rows),

        "rows":
            rows,

        "aggregate": {
            "baseline_total_medium_high":
                baseline_total,

            "zero_total_medium_high":
                zero_total,

            "absolute_reduction":
                absolute_reduction,

            "reduction_percent":
                reduction_percent,

            "baseline_mean_per_case_run":
                mean(
                    baseline_values
                ),

            "zero_mean_per_case_run":
                mean(
                    zero_values
                ),

            "baseline_median_per_case_run":
                median(
                    baseline_values
                ),

            "zero_median_per_case_run":
                median(
                    zero_values
                ),

            "zero_wins":
                zero_wins,

            "ties":
                ties,

            "baseline_wins":
                baseline_wins,

            "baseline_accepted_runs":
                baseline_accepts,

            "zero_accepted_runs":
                zero_accepts,

            "baseline_acceptance_rate":
                (
                    baseline_accepts
                    / len(rows)
                    * 100.0
                ),

            "zero_acceptance_rate":
                (
                    zero_accepts
                    / len(rows)
                    * 100.0
                ),
        },

        "per_case":
            per_case,
    }


def summary_to_text(
    summary: dict,
) -> str:
    aggregate = summary[
        "aggregate"
    ]

    lines = [
        "=" * 72,
        "ZERO REPEATED BENCHMARK",
        "=" * 72,
        (
            f"Trials: "
            f"{summary['trials']}"
        ),
        (
            "Paired case runs: "
            f"{summary['paired_case_runs']}"
        ),
        "",
        "AGGREGATE",
        "-" * 72,
        (
            "Baseline total medium/high: "
            f"{aggregate['baseline_total_medium_high']}"
        ),
        (
            "ZERO total medium/high: "
            f"{aggregate['zero_total_medium_high']}"
        ),
        (
            "Absolute reduction: "
            f"{aggregate['absolute_reduction']}"
        ),
    ]

    reduction = aggregate[
        "reduction_percent"
    ]

    if reduction is None:
        lines.append(
            "Reduction percentage: N/A"
        )
    else:
        lines.append(
            f"Reduction percentage: "
            f"{reduction:.1f}%"
        )

    lines.extend(
        [
            "",
            (
                "Baseline mean findings/run: "
                f"{aggregate['baseline_mean_per_case_run']:.3f}"
            ),
            (
                "ZERO mean findings/run: "
                f"{aggregate['zero_mean_per_case_run']:.3f}"
            ),
            (
                "Baseline median findings/run: "
                f"{aggregate['baseline_median_per_case_run']:.3f}"
            ),
            (
                "ZERO median findings/run: "
                f"{aggregate['zero_median_per_case_run']:.3f}"
            ),
            "",
            (
                "ZERO wins: "
                f"{aggregate['zero_wins']}"
            ),
            (
                "Ties: "
                f"{aggregate['ties']}"
            ),
            (
                "Baseline wins: "
                f"{aggregate['baseline_wins']}"
            ),
            "",
            (
                "Baseline accepted runs: "
                f"{aggregate['baseline_accepted_runs']}/"
                f"{summary['paired_case_runs']} "
                f"({aggregate['baseline_acceptance_rate']:.1f}%)"
            ),
            (
                "ZERO accepted runs: "
                f"{aggregate['zero_accepted_runs']}/"
                f"{summary['paired_case_runs']} "
                f"({aggregate['zero_acceptance_rate']:.1f}%)"
            ),
            "",
            "PER-CASE ACROSS THREE TRIALS",
            "-" * 72,
        ]
    )

    for case in summary[
        "per_case"
    ]:
        lines.append(
            (
                f"{case['case_id']} "
                f"{case['case_name']}"
            )
        )

        lines.append(
            (
                "    baseline: "
                f"{case['baseline_values']} "
                f"mean={case['baseline_mean']:.2f} "
                f"median={case['baseline_median']:.2f}"
            )
        )

        lines.append(
            (
                "    ZERO:     "
                f"{case['zero_values']} "
                f"mean={case['zero_mean']:.2f} "
                f"median={case['zero_median']:.2f}"
            )
        )

        lines.append(
            (
                "    outcomes: "
                f"ZERO wins={case['zero_wins']} "
                f"ties={case['ties']} "
                f"baseline wins={case['baseline_wins']}"
            )
        )

    return "\n".join(
        lines
    )


def save_repeated_summary(
    summary: dict,
) -> None:
    REPEATED_RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        REPEATED_RESULTS_DIR
        / "summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (
        REPEATED_RESULTS_DIR
        / "summary.txt"
    ).write_text(
        summary_to_text(
            summary
        ),
        encoding="utf-8",
    )


def main() -> None:
    configure_utf8_console()

    if (
        EVALUATOR_VERSION
        != EXPECTED_EVALUATOR_VERSION
    ):
        raise RuntimeError(
            "Repeated benchmark requires "
            f"{EXPECTED_EVALUATOR_VERSION}, "
            f"but found {EVALUATOR_VERSION}."
        )

    verify_existing_suite_03()

    print()
    print(
        "Suite 03 verified as Trial 1."
    )

    for trial_id in NEW_TRIAL_IDS:
        run_fresh_trial(
            trial_id
        )

    summary = build_repeated_summary()

    save_repeated_summary(
        summary
    )

    print()
    print(
        summary_to_text(
            summary
        )
    )

    print()
    print(
        "Repeated benchmark results:"
    )

    print(
        REPEATED_RESULTS_DIR
    )


if __name__ == "__main__":
    main()