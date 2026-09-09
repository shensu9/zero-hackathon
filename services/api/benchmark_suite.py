import json
import sys
import traceback
from dataclasses import asdict
from pathlib import Path

from benchmark_cases import BENCHMARK_CASES
from experiment_runner import (
    CaseRunResult,
    load_or_generate_object_dna,
    run_benchmark_case,
)


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------


SUITE_ID = "benchmark_suite_01"


REPO_ROOT = Path(
    __file__
).resolve().parents[2]


RESULTS_DIR = (
    REPO_ROOT
    / "results"
    / SUITE_ID
)


# ---------------------------------------------------------------------------
# CONSOLE
# ---------------------------------------------------------------------------


def configure_utf8_console() -> None:
    """
    Prevent Windows CP950 / legacy-console encoding failures when
    model output contains Unicode punctuation.
    """

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


# ---------------------------------------------------------------------------
# SERIALIZATION
# ---------------------------------------------------------------------------


def evaluation_to_dict(
    evaluation,
) -> dict:
    return evaluation.model_dump(
        mode="json"
    )


def critic_to_dict(
    critic,
) -> dict:
    return critic.model_dump(
        mode="json"
    )


def plan_to_dict(
    plan,
) -> dict:
    return plan.model_dump(
        mode="json"
    )


def result_to_dict(
    result: CaseRunResult,
) -> dict:
    """
    Store enough evidence to inspect every benchmark case later.

    Neutral evaluator results are the comparative benchmark authority.
    ZERO's internal critic is retained for engineering analysis only.
    """

    return {
        "case_id":
            result.case_id,

        "case_name":
            result.case_name,

        "expectation":
            result.expectation,

        "repair_attempts":
            result.repair_attempts,

        "repair_validation_failures":
            result.repair_validation_failures,

        "baseline_plan":
            plan_to_dict(
                result.baseline_plan
            ),

        "zero_initial_plan":
            plan_to_dict(
                result.zero_initial_plan
            ),

        "zero_initial_critic":
            critic_to_dict(
                result.zero_initial_critic
            ),

        "zero_final_plan":
            plan_to_dict(
                result.zero_final_plan
            ),

        "zero_final_critic":
            critic_to_dict(
                result.zero_final_critic
            ),

        "baseline_evaluation":
            evaluation_to_dict(
                result.baseline_evaluation
            ),

        "zero_evaluation":
            evaluation_to_dict(
                result.zero_evaluation
            ),
    }


# ---------------------------------------------------------------------------
# RESULT WRITING
# ---------------------------------------------------------------------------


def case_result_path(
    result: CaseRunResult,
) -> Path:
    return (
        RESULTS_DIR
        / (
            f"{result.case_id}_"
            f"{result.case_name}.json"
        )
    )


def case_error_path(
    case_id: str,
    case_name: str,
) -> Path:
    return (
        RESULTS_DIR
        / (
            f"{case_id}_"
            f"{case_name}_ERROR.json"
        )
    )


def save_case_result(
    result: CaseRunResult,
) -> Path:
    path = case_result_path(
        result
    )

    payload = result_to_dict(
        result
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


def save_case_error(
    *,
    case_id: str,
    case_name: str,
    error: Exception,
) -> Path:
    path = case_error_path(
        case_id,
        case_name,
    )

    payload = {
        "case_id":
            case_id,

        "case_name":
            case_name,

        "error_type":
            type(error).__name__,

        "error_message":
            str(error),

        "traceback":
            traceback.format_exc(),
    }

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


# ---------------------------------------------------------------------------
# METRICS
# ---------------------------------------------------------------------------


ISSUE_FIELDS = (
    "unlisted_resource_count",
    "unsupported_physical_claim_count",
    "unsupported_capability_count",
    "hidden_assumption_count",
    "safety_or_uncertainty_count",
    "constraint_violation_count",
)


ISSUE_LABELS = {
    "unlisted_resource_count":
        "unlisted_resource",

    "unsupported_physical_claim_count":
        "unsupported_physical_claim",

    "unsupported_capability_count":
        "unsupported_capability",

    "hidden_assumption_count":
        "hidden_assumption",

    "safety_or_uncertainty_count":
        "safety_or_uncertainty",

    "constraint_violation_count":
        "constraint_violation",
}


def empty_issue_totals() -> dict:
    return {
        label: 0
        for label
        in ISSUE_LABELS.values()
    }


def add_issue_counts(
    totals: dict,
    evaluation,
) -> None:
    for field in ISSUE_FIELDS:
        label = ISSUE_LABELS[
            field
        ]

        totals[label] += getattr(
            evaluation,
            field,
        )


def build_aggregate_summary(
    completed_results: list[CaseRunResult],
    failed_cases: list[dict],
) -> dict:
    baseline_issue_totals = (
        empty_issue_totals()
    )

    zero_issue_totals = (
        empty_issue_totals()
    )

    baseline_medium_high = 0
    zero_medium_high = 0

    baseline_accepted = 0
    zero_accepted = 0

    zero_wins = 0
    ties = 0
    baseline_wins = 0

    total_repairs = 0

    total_repair_validation_failures = 0

    case_summaries = []

    for result in completed_results:
        baseline_eval = (
            result.baseline_evaluation
        )

        zero_eval = (
            result.zero_evaluation
        )

        baseline_mh = (
            baseline_eval
            .medium_high_findings
        )

        zero_mh = (
            zero_eval
            .medium_high_findings
        )

        difference = (
            baseline_mh
            - zero_mh
        )

        baseline_medium_high += (
            baseline_mh
        )

        zero_medium_high += (
            zero_mh
        )

        if baseline_eval.accepted:
            baseline_accepted += 1

        if zero_eval.accepted:
            zero_accepted += 1

        if zero_mh < baseline_mh:
            zero_wins += 1

        elif zero_mh == baseline_mh:
            ties += 1

        else:
            baseline_wins += 1

        add_issue_counts(
            baseline_issue_totals,
            baseline_eval,
        )

        add_issue_counts(
            zero_issue_totals,
            zero_eval,
        )

        total_repairs += (
            result.repair_attempts
        )

        total_repair_validation_failures += (
            result.repair_validation_failures
        )

        case_summaries.append(
            {
                "case_id":
                    result.case_id,

                "case_name":
                    result.case_name,

                "expectation":
                    result.expectation,

                "baseline_medium_high":
                    baseline_mh,

                "zero_medium_high":
                    zero_mh,

                "difference_positive_favors_zero":
                    difference,

                "baseline_accepted":
                    baseline_eval.accepted,

                "zero_accepted":
                    zero_eval.accepted,

                "zero_internal_critic_passed":
                    result.zero_final_critic.passed,

                "repair_attempts":
                    result.repair_attempts,

                "repair_validation_failures":
                    result.repair_validation_failures,
            }
        )

    absolute_reduction = (
        baseline_medium_high
        - zero_medium_high
    )

    if baseline_medium_high > 0:
        reduction_percent = (
            absolute_reduction
            / baseline_medium_high
            * 100.0
        )
    else:
        reduction_percent = None

    return {
        "suite_id":
            SUITE_ID,

        "protocol_note": (
            "Baseline and ZERO are evaluated by the same "
            "neutral evaluator against the same frozen "
            "Object DNA world model. ZERO internal critic "
            "results are not used as comparative scores."
        ),

        "total_cases":
            len(BENCHMARK_CASES),

        "completed_cases":
            len(completed_results),

        "failed_cases":
            len(failed_cases),

        "failed_case_details":
            failed_cases,

        "case_summaries":
            case_summaries,

        "aggregate": {
            "baseline_medium_high_findings":
                baseline_medium_high,

            "zero_medium_high_findings":
                zero_medium_high,

            "absolute_medium_high_reduction":
                absolute_reduction,

            "medium_high_reduction_percent":
                reduction_percent,

            "baseline_accepted_cases":
                baseline_accepted,

            "zero_accepted_cases":
                zero_accepted,

            "zero_wins_by_medium_high":
                zero_wins,

            "ties_by_medium_high":
                ties,

            "baseline_wins_by_medium_high":
                baseline_wins,

            "baseline_issue_totals":
                baseline_issue_totals,

            "zero_issue_totals":
                zero_issue_totals,

            "zero_total_repair_attempts":
                total_repairs,

            "zero_repair_validation_failures":
                total_repair_validation_failures,
        },
    }


# ---------------------------------------------------------------------------
# HUMAN-READABLE SUMMARY
# ---------------------------------------------------------------------------


def summary_to_text(
    summary: dict,
) -> str:
    aggregate = summary[
        "aggregate"
    ]

    lines = []

    lines.append(
        "=" * 72
    )

    lines.append(
        "ZERO MULTI-GOAL BENCHMARK"
    )

    lines.append(
        "=" * 72
    )

    lines.append(
        f"Suite: {summary['suite_id']}"
    )

    lines.append(
        f"Completed: "
        f"{summary['completed_cases']}/"
        f"{summary['total_cases']}"
    )

    lines.append(
        f"Failed cases: "
        f"{summary['failed_cases']}"
    )

    lines.append("")

    lines.append(
        "PER-CASE RESULTS"
    )

    lines.append(
        "-" * 72
    )

    for case in summary[
        "case_summaries"
    ]:
        lines.append(
            (
                f"{case['case_id']} "
                f"{case['case_name']}: "
                f"baseline="
                f"{case['baseline_medium_high']} "
                f"ZERO="
                f"{case['zero_medium_high']} "
                f"difference="
                f"{case['difference_positive_favors_zero']:+d}"
            )
        )

        lines.append(
            (
                f"    accepted: "
                f"baseline="
                f"{case['baseline_accepted']} "
                f"ZERO="
                f"{case['zero_accepted']} "
                f"| repairs="
                f"{case['repair_attempts']} "
                f"| hard repair failures="
                f"{case['repair_validation_failures']}"
            )
        )

    lines.append("")

    lines.append(
        "AGGREGATE"
    )

    lines.append(
        "-" * 72
    )

    lines.append(
        (
            "Baseline medium/high findings: "
            f"{aggregate['baseline_medium_high_findings']}"
        )
    )

    lines.append(
        (
            "ZERO medium/high findings: "
            f"{aggregate['zero_medium_high_findings']}"
        )
    )

    lines.append(
        (
            "Absolute reduction: "
            f"{aggregate['absolute_medium_high_reduction']}"
        )
    )

    reduction_percent = (
        aggregate[
            "medium_high_reduction_percent"
        ]
    )

    if reduction_percent is None:
        lines.append(
            "Reduction percentage: N/A"
        )
    else:
        lines.append(
            (
                "Reduction percentage: "
                f"{reduction_percent:.1f}%"
            )
        )

    lines.append("")

    lines.append(
        (
            "Accepted cases — baseline: "
            f"{aggregate['baseline_accepted_cases']}"
        )
    )

    lines.append(
        (
            "Accepted cases — ZERO: "
            f"{aggregate['zero_accepted_cases']}"
        )
    )

    lines.append("")

    lines.append(
        (
            "Cases favoring ZERO: "
            f"{aggregate['zero_wins_by_medium_high']}"
        )
    )

    lines.append(
        (
            "Ties: "
            f"{aggregate['ties_by_medium_high']}"
        )
    )

    lines.append(
        (
            "Cases favoring baseline: "
            f"{aggregate['baseline_wins_by_medium_high']}"
        )
    )

    lines.append("")

    lines.append(
        "BASELINE ISSUE TOTALS"
    )

    lines.append(
        json.dumps(
            aggregate[
                "baseline_issue_totals"
            ],
            indent=2,
            ensure_ascii=False,
        )
    )

    lines.append("")

    lines.append(
        "ZERO ISSUE TOTALS"
    )

    lines.append(
        json.dumps(
            aggregate[
                "zero_issue_totals"
            ],
            indent=2,
            ensure_ascii=False,
        )
    )

    lines.append("")

    lines.append(
        (
            "ZERO total repair attempts: "
            f"{aggregate['zero_total_repair_attempts']}"
        )
    )

    lines.append(
        (
            "ZERO hard repair validation failures: "
            f"{aggregate['zero_repair_validation_failures']}"
        )
    )

    if summary[
        "failed_case_details"
    ]:
        lines.append("")

        lines.append(
            "FAILED CASES"
        )

        lines.append(
            "-" * 72
        )

        for failure in summary[
            "failed_case_details"
        ]:
            lines.append(
                (
                    f"{failure['case_id']} "
                    f"{failure['case_name']}: "
                    f"{failure['error_type']} — "
                    f"{failure['error_message']}"
                )
            )

    lines.append("")

    lines.append(
        "Comparative scores above come from the neutral evaluator, "
        "not ZERO's internal critic."
    )

    return "\n".join(
        lines
    )


def save_summary(
    summary: dict,
) -> None:
    json_path = (
        RESULTS_DIR
        / "summary.json"
    )

    text_path = (
        RESULTS_DIR
        / "summary.txt"
    )

    json_path.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    text_path.write_text(
        summary_to_text(
            summary
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# MAIN SUITE
# ---------------------------------------------------------------------------


def main() -> None:
    configure_utf8_console()

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 72)
    print("ZERO MULTI-GOAL BENCHMARK")
    print("=" * 72)

    print(
        "Suite:",
        SUITE_ID,
    )

    print(
        "Cases:",
        len(BENCHMARK_CASES),
    )

    print()

    print(
        "Loading frozen Object DNA..."
    )

    object_dna = (
        load_or_generate_object_dna()
    )

    completed_results = []

    failed_cases = []

    for index, case in enumerate(
        BENCHMARK_CASES,
        start=1,
    ):
        print()
        print("=" * 72)

        print(
            f"CASE {index}/"
            f"{len(BENCHMARK_CASES)} — "
            f"{case.case_id}: "
            f"{case.name}"
        )

        print("=" * 72)

        try:
            result = run_benchmark_case(
                case,
                object_dna=object_dna,
            )

            completed_results.append(
                result
            )

            path = save_case_result(
                result
            )

            print(
                f"[{case.case_id}] "
                f"Saved result: {path}"
            )

            print(
                f"[{case.case_id}] "
                "Neutral result — "
                f"baseline medium/high="
                f"{result.baseline_evaluation.medium_high_findings}, "
                f"ZERO="
                f"{result.zero_evaluation.medium_high_findings}"
            )

        except Exception as exc:
            print(
                f"[{case.case_id}] "
                "CASE FAILED"
            )

            print(
                f"[{case.case_id}] "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            error_path = save_case_error(
                case_id=case.case_id,
                case_name=case.name,
                error=exc,
            )

            print(
                f"[{case.case_id}] "
                f"Saved failure: "
                f"{error_path}"
            )

            failed_cases.append(
                {
                    "case_id":
                        case.case_id,

                    "case_name":
                        case.name,

                    "error_type":
                        type(exc).__name__,

                    "error_message":
                        str(exc),
                }
            )

        # ---------------------------------------------------------------
        # Save/update aggregate progress after EVERY case.
        #
        # If B05 crashes, B01-B04 and the partial summary remain intact.
        # ---------------------------------------------------------------

        summary = build_aggregate_summary(
            completed_results,
            failed_cases,
        )

        save_summary(
            summary
        )

        print(
            f"[suite] Progress saved: "
            f"{len(completed_results)} completed, "
            f"{len(failed_cases)} failed."
        )

    # ------------------------------------------------------------------
    # FINAL SUMMARY
    # ------------------------------------------------------------------

    final_summary = (
        build_aggregate_summary(
            completed_results,
            failed_cases,
        )
    )

    save_summary(
        final_summary
    )

    print()
    print(
        summary_to_text(
            final_summary
        )
    )

    print()
    print(
        "Results directory:"
    )

    print(
        RESULTS_DIR
    )


if __name__ == "__main__":
    main()