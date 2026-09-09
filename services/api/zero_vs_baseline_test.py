import sys

from benchmark_cases import get_benchmark_case
from experiment_runner import (
    load_or_generate_object_dna,
    run_benchmark_case,
)


def configure_utf8_console() -> None:
    """
    Prevent Windows legacy console encodings such as CP950 from
    failing when model output contains Unicode punctuation.
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


def print_section(
    title: str,
) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:
    configure_utf8_console()

    case = get_benchmark_case(
        "B01"
    )

    print_section(
        f"{case.case_id}: {case.name}"
    )

    print(
        "Human benchmark expectation:",
        case.expectation.value,
    )

    print(
        "Human benchmark rationale:",
        case.rationale,
    )

    # Freeze/reuse the same validated physical world model.
    object_dna = (
        load_or_generate_object_dna()
    )

    result = run_benchmark_case(
        case,
        object_dna=object_dna,
    )

    print_section(
        "GENERIC BASELINE"
    )

    print(
        result.baseline_plan.model_dump_json(
            indent=2
        )
    )

    print_section(
        "INITIAL ZERO PLAN"
    )

    print(
        result.zero_initial_plan.model_dump_json(
            indent=2
        )
    )

    print_section(
        "INITIAL ZERO SEMANTIC CRITIC"
    )

    print(
        result.zero_initial_critic.model_dump_json(
            indent=2
        )
    )

    print_section(
        "FINAL ZERO PLAN"
    )

    print(
        result.zero_final_plan.model_dump_json(
            indent=2
        )
    )

    print_section(
        "FINAL ZERO SEMANTIC CRITIC"
    )

    print(
        result.zero_final_critic.model_dump_json(
            indent=2
        )
    )

    print_section(
        "ZERO REPAIR SUMMARY"
    )

    print(
        "Repair attempts used:",
        result.repair_attempts,
    )

    print(
        "ZERO internal critic accepted:",
        result.zero_final_critic.passed,
    )

    print_section(
        "NEUTRAL BASELINE EVALUATION"
    )

    print(
        result.baseline_evaluation.model_dump_json(
            indent=2
        )
    )

    print_section(
        "NEUTRAL ZERO EVALUATION"
    )

    print(
        result.zero_evaluation.model_dump_json(
            indent=2
        )
    )

    print_section(
        "BASELINE VS ZERO SUMMARY"
    )

    print(
        "Case:",
        result.case_id,
        result.case_name,
    )

    print(
        "Expectation:",
        result.expectation,
    )

    print()

    print(
        "Baseline medium/high findings:",
        result.baseline_evaluation.medium_high_findings,
    )

    print(
        "ZERO medium/high findings:",
        result.zero_evaluation.medium_high_findings,
    )

    print()

    print(
        "Baseline accepted:",
        result.baseline_evaluation.accepted,
    )

    print(
        "ZERO accepted:",
        result.zero_evaluation.accepted,
    )

    print()

    baseline_issue_counts = {
        "unlisted_resource":
            result.baseline_evaluation.unlisted_resource_count,

        "unsupported_physical_claim":
            result.baseline_evaluation.unsupported_physical_claim_count,

        "unsupported_capability":
            result.baseline_evaluation.unsupported_capability_count,

        "hidden_assumption":
            result.baseline_evaluation.hidden_assumption_count,

        "safety_or_uncertainty":
            result.baseline_evaluation.safety_or_uncertainty_count,

        "constraint_violation":
            result.baseline_evaluation.constraint_violation_count,
    }

    zero_issue_counts = {
        "unlisted_resource":
            result.zero_evaluation.unlisted_resource_count,

        "unsupported_physical_claim":
            result.zero_evaluation.unsupported_physical_claim_count,

        "unsupported_capability":
            result.zero_evaluation.unsupported_capability_count,

        "hidden_assumption":
            result.zero_evaluation.hidden_assumption_count,

        "safety_or_uncertainty":
            result.zero_evaluation.safety_or_uncertainty_count,

        "constraint_violation":
            result.zero_evaluation.constraint_violation_count,
    }

    print(
        "Baseline issue counts:",
        baseline_issue_counts,
    )

    print(
        "ZERO issue counts:",
        zero_issue_counts,
    )

    print()

    difference = (
        result.baseline_evaluation.medium_high_findings
        - result.zero_evaluation.medium_high_findings
    )

    print(
        "Medium/high finding difference "
        "(positive favors ZERO):",
        difference,
    )


if __name__ == "__main__":
    main()