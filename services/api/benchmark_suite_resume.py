import json
import sys

from benchmark_cases import BENCHMARK_CASES
from benchmark_suite import (
    RESULTS_DIR,
    SUITE_ID,
    build_aggregate_summary,
    save_case_error,
    save_case_result,
    save_summary,
    summary_to_text,
)
from critic_schemas import PlanCriticResult
from evaluation_schemas import PlanEvaluation
from experiment_runner import (
    CaseRunResult,
    load_or_generate_object_dna,
    run_benchmark_case,
)
from plan_schemas import PhysicalPlan


def configure_utf8_console() -> None:
    """
    Avoid Windows legacy-console encoding failures.
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


def result_path(
    case,
):
    return (
        RESULTS_DIR
        / f"{case.case_id}_{case.name}.json"
    )


def error_path(
    case,
):
    return (
        RESULTS_DIR
        / (
            f"{case.case_id}_"
            f"{case.name}_ERROR.json"
        )
    )


def load_saved_result(
    case,
) -> CaseRunResult:
    """
    Reconstruct a validated CaseRunResult from a previously
    completed benchmark JSON file.
    """

    path = result_path(
        case
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if (
        payload.get("case_id")
        != case.case_id
    ):
        raise RuntimeError(
            f"Cached result case_id mismatch: "
            f"{path}"
        )

    if (
        payload.get("case_name")
        != case.name
    ):
        raise RuntimeError(
            f"Cached result case_name mismatch: "
            f"{path}"
        )

    return CaseRunResult(
        case_id=payload[
            "case_id"
        ],

        case_name=payload[
            "case_name"
        ],

        expectation=payload[
            "expectation"
        ],

        baseline_plan=(
            PhysicalPlan.model_validate(
                payload[
                    "baseline_plan"
                ]
            )
        ),

        zero_initial_plan=(
            PhysicalPlan.model_validate(
                payload[
                    "zero_initial_plan"
                ]
            )
        ),

        zero_initial_critic=(
            PlanCriticResult.model_validate(
                payload[
                    "zero_initial_critic"
                ]
            )
        ),

        zero_final_plan=(
            PhysicalPlan.model_validate(
                payload[
                    "zero_final_plan"
                ]
            )
        ),

        zero_final_critic=(
            PlanCriticResult.model_validate(
                payload[
                    "zero_final_critic"
                ]
            )
        ),

        repair_attempts=int(
            payload.get(
                "repair_attempts",
                0,
            )
        ),

        repair_validation_failures=int(
            payload.get(
                "repair_validation_failures",
                0,
            )
        ),

        baseline_evaluation=(
            PlanEvaluation.model_validate(
                payload[
                    "baseline_evaluation"
                ]
            )
        ),

        zero_evaluation=(
            PlanEvaluation.model_validate(
                payload[
                    "zero_evaluation"
                ]
            )
        ),
    )


def save_progress(
    completed_results,
    failed_cases,
) -> None:
    summary = build_aggregate_summary(
        completed_results,
        failed_cases,
    )

    save_summary(
        summary
    )


def main() -> None:
    configure_utf8_console()

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 72)
    print("ZERO MULTI-GOAL BENCHMARK — RESUME")
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

    reused_count = 0
    rerun_count = 0

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

        cached_path = result_path(
            case
        )

        stale_error_path = error_path(
            case
        )

        # ---------------------------------------------------------------
        # REUSE COMPLETED CASE
        # ---------------------------------------------------------------

        if cached_path.exists():
            try:
                result = load_saved_result(
                    case
                )

                completed_results.append(
                    result
                )

                reused_count += 1

                print(
                    f"[{case.case_id}] "
                    "Existing completed result found."
                )

                print(
                    f"[{case.case_id}] "
                    "Skipping model calls."
                )

                print(
                    f"[{case.case_id}] "
                    "Neutral result — "
                    f"baseline medium/high="
                    f"{result.baseline_evaluation.medium_high_findings}, "
                    f"ZERO="
                    f"{result.zero_evaluation.medium_high_findings}"
                )

                if stale_error_path.exists():
                    stale_error_path.unlink()

                    print(
                        f"[{case.case_id}] "
                        "Removed stale error file."
                    )

                save_progress(
                    completed_results,
                    failed_cases,
                )

                continue

            except Exception as exc:
                print(
                    f"[{case.case_id}] "
                    "Existing result could not be reused."
                )

                print(
                    f"[{case.case_id}] "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                print(
                    f"[{case.case_id}] "
                    "Rerunning this case."
                )

        # ---------------------------------------------------------------
        # RUN MISSING / PREVIOUSLY FAILED CASE
        # ---------------------------------------------------------------

        rerun_count += 1

        try:
            result = run_benchmark_case(
                case,
                object_dna=object_dna,
            )

            completed_results.append(
                result
            )

            saved_path = save_case_result(
                result
            )

            print(
                f"[{case.case_id}] "
                f"Saved result: "
                f"{saved_path}"
            )

            print(
                f"[{case.case_id}] "
                "Neutral result — "
                f"baseline medium/high="
                f"{result.baseline_evaluation.medium_high_findings}, "
                f"ZERO="
                f"{result.zero_evaluation.medium_high_findings}"
            )

            if stale_error_path.exists():
                stale_error_path.unlink()

                print(
                    f"[{case.case_id}] "
                    "Removed previous ERROR result."
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

            saved_error = save_case_error(
                case_id=case.case_id,
                case_name=case.name,
                error=exc,
            )

            print(
                f"[{case.case_id}] "
                f"Saved failure: "
                f"{saved_error}"
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

        # Save after every case.
        save_progress(
            completed_results,
            failed_cases,
        )

        print(
            "[suite] Progress saved: "
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
        "Resume statistics:"
    )

    print(
        "Existing cases reused:",
        reused_count,
    )

    print(
        "Cases rerun:",
        rerun_count,
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