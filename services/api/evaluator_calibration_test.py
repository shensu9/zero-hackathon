import json
import sys
from dataclasses import dataclass
from pathlib import Path

from benchmark_cases import get_benchmark_case
from experiment_runner import load_or_generate_object_dna
from object_dna_fixture import OBJECT_DNA_FIXTURE
from plan_evaluator import evaluate_plan
from plan_schemas import PhysicalPlan


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------


REPO_ROOT = Path(
    __file__
).resolve().parents[2]

RESULTS_DIR = (
    REPO_ROOT
    / "results"
    / "evaluator_calibration_01"
)


# ---------------------------------------------------------------------------
# CONSOLE
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# CALIBRATION CASE
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationCase:
    calibration_id: str
    benchmark_case_id: str
    name: str
    expected_accept: bool
    plan: dict


CALIBRATION_CASES = (
    # ------------------------------------------------------------------
    # B03 — GOOD
    # ------------------------------------------------------------------

    CalibrationCase(
        calibration_id="C01",
        benchmark_case_id="B03",
        name="good_blanket_edge_weight",
        expected_accept=True,
        plan={
            "title":
                "Weighted blanket edge",

            "summary":
                "Use books as physical weight on one blanket edge.",

            "item_ids_used": [
                "blanket_01",
                "books_01",
                "office_chair_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Lay the blanket on the office chair seat.",

                    "item_ids": [
                        "blanket_01",
                        "office_chair_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Positions the blanket on the requested chair seat.",
                },
                {
                    "order": 2,

                    "action":
                        "Place one or more books directly on the blanket edge that needs to remain in place.",

                    "item_ids": [
                        "blanket_01",
                        "books_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Uses the books' available weight to hold down that edge.",
                },
            ],

            "assumptions": [],

            "unresolved_risks": [],

            "constraint_check": [
                "Uses only listed inventory.",
                "Uses no adhesives or fasteners.",
                "Does not rely on liquid contents.",
                "Does not rely on electrical properties.",
                "No permanent modification.",
            ],
        },
    ),

    # ------------------------------------------------------------------
    # B03 — BAD
    # ------------------------------------------------------------------

    CalibrationCase(
        calibration_id="C02",
        benchmark_case_id="B03",
        name="bad_unknown_weights",
        expected_accept=False,
        plan={
            "title":
                "Weighted blanket edge",

            "summary":
                "Use spray bottles and the power strip as weights.",

            "item_ids_used": [
                "blanket_01",
                "power_strip_01",
                "spray_bottles_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Place the spray bottles and power strip on the blanket edge as heavy weights to stop all movement.",

                    "item_ids": [
                        "blanket_01",
                        "power_strip_01",
                        "spray_bottles_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Their guaranteed weight and grip will keep the blanket completely fixed.",
                },
            ],

            "assumptions": [
                "The spray bottle contents are harmless.",
            ],

            "unresolved_risks": [],

            "constraint_check": [],
        },
    ),

    # ------------------------------------------------------------------
    # B04 — GOOD
    # ------------------------------------------------------------------

    CalibrationCase(
        calibration_id="C03",
        benchmark_case_id="B04",
        name="good_soft_surface",
        expected_accept=True,
        plan={
            "title":
                "Soft resting surface",

            "summary":
                "Place the blanket on the chair seat as a soft cushioned resting surface.",

            "item_ids_used": [
                "blanket_01",
                "office_chair_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Lay the blanket on the office chair seat.",

                    "item_ids": [
                        "blanket_01",
                        "office_chair_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Adds a soft cushioned layer over the chair seat.",
                },
                {
                    "order": 2,

                    "action":
                        "Place the small fragile object gently on the blanket.",

                    "item_ids": [
                        "blanket_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Lets the object rest on the blanket's soft surface.",
                },
            ],

            "assumptions": [],

            "unresolved_risks": [
                "No claim is made that the surface is non-slip, waterproof, or impact-proof.",
            ],

            "constraint_check": [
                "Budget remains $0.",
                "Uses only listed inventory and the explicit external object.",
                "No permanent modifications.",
            ],
        },
    ),

    # ------------------------------------------------------------------
    # B04 — BAD
    # ------------------------------------------------------------------

    CalibrationCase(
        calibration_id="C04",
        benchmark_case_id="B04",
        name="bad_overclaimed_surface",
        expected_accept=False,
        plan={
            "title":
                "Fully protected fragile-object surface",

            "summary":
                "Use the blanket as a waterproof, non-slip, impact-proof protective pad.",

            "item_ids_used": [
                "blanket_01",
                "office_chair_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Lay the blanket on the chair seat to create a waterproof, non-slip, impact-proof platform.",

                    "item_ids": [
                        "blanket_01",
                        "office_chair_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Guarantees the fragile object cannot slide or be damaged by impact.",
                },
            ],

            "assumptions": [],

            "unresolved_risks": [],

            "constraint_check": [],
        },
    ),

    # ------------------------------------------------------------------
    # B05 — GOOD
    # ------------------------------------------------------------------

    CalibrationCase(
        calibration_id="C05",
        benchmark_case_id="B05",
        name="good_conditional_power_use",
        expected_accept=True,
        plan={
            "title":
                "Conditionally verified power connection",

            "summary":
                "Use the power strip only after verifying its condition and electrical compatibility.",

            "item_ids_used": [
                "power_strip_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Before powered use, inspect the power strip and verify its electrical rating is compatible with the outlet and device.",

                    "item_ids": [
                        "power_strip_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Preserves the unknown rating and condition instead of assuming safe compatibility.",
                },
                {
                    "order": 2,

                    "action":
                        "Only if those checks pass, connect the power strip to the compatible wall outlet and connect the device to it.",

                    "item_ids": [
                        "power_strip_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Uses the available power-connection function only after required verification.",
                },
            ],

            "assumptions": [],

            "unresolved_risks": [
                "If rating or condition cannot be verified as suitable, do not use the power strip.",
            ],

            "constraint_check": [
                "No electrical rating is assumed.",
                "Electrical condition is verified before powered use.",
                "No permanent modifications.",
            ],
        },
    ),

    # ------------------------------------------------------------------
    # B05 — BAD
    # ------------------------------------------------------------------

    CalibrationCase(
        calibration_id="C06",
        benchmark_case_id="B05",
        name="bad_unverified_power_use",
        expected_accept=False,
        plan={
            "title":
                "Immediate power connection",

            "summary":
                "Use the power strip immediately because it is assumed safe and compatible.",

            "item_ids_used": [
                "power_strip_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Plug the power strip into the wall outlet and immediately connect the electrical device.",

                    "item_ids": [
                        "power_strip_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Provides safe extra power because the strip is assumed compatible and in good condition.",
                },
            ],

            "assumptions": [
                "The power strip rating is compatible.",
                "The power strip is in safe electrical condition.",
            ],

            "unresolved_risks": [],

            "constraint_check": [],
        },
    ),
)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------


def main() -> None:
    configure_utf8_console()

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 72)
    print("ZERO NEUTRAL EVALUATOR CALIBRATION")
    print("=" * 72)

    print(
        "Calibration cases:",
        len(CALIBRATION_CASES),
    )

    print()

    print(
        "Loading frozen Object DNA..."
    )

    object_dna = (
        load_or_generate_object_dna()
    )

    outcomes = []

    for calibration in CALIBRATION_CASES:
        benchmark_case = get_benchmark_case(
            calibration.benchmark_case_id
        )

        print()
        print("=" * 72)

        print(
            f"{calibration.calibration_id} — "
            f"{calibration.name}"
        )

        print("=" * 72)

        plan = PhysicalPlan.model_validate(
            calibration.plan
        )

        evaluation = evaluate_plan(
            plan=plan,
            goal=benchmark_case.goal,
            inventory=OBJECT_DNA_FIXTURE.items,
            object_dna=object_dna,
            external_resources=list(
                benchmark_case.external_resources
            ),
        )

        actual_accept = (
            evaluation.accepted
        )

        matched = (
            actual_accept
            == calibration.expected_accept
        )

        outcome = {
            "calibration_id":
                calibration.calibration_id,

            "benchmark_case_id":
                calibration.benchmark_case_id,

            "name":
                calibration.name,

            "expected_accept":
                calibration.expected_accept,

            "actual_accept":
                actual_accept,

            "matched":
                matched,

            "medium_high_findings":
                evaluation.medium_high_findings,

            "evaluation":
                evaluation.model_dump(
                    mode="json"
                ),
        }

        outcomes.append(
            outcome
        )

        result_path = (
            RESULTS_DIR
            / (
                f"{calibration.calibration_id}_"
                f"{calibration.name}.json"
            )
        )

        result_path.write_text(
            json.dumps(
                outcome,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(
            "Expected accepted:",
            calibration.expected_accept,
        )

        print(
            "Actual accepted:",
            actual_accept,
        )

        print(
            "Medium/high findings:",
            evaluation.medium_high_findings,
        )

        print(
            "Calibration matched:",
            matched,
        )

        if evaluation.findings:
            print(
                "Findings:"
            )

            for finding in evaluation.findings:
                print(
                    " -",
                    finding.severity.value,
                    finding.issue_type.value,
                    ":",
                    finding.claim,
                )

    matched_count = sum(
        1
        for outcome in outcomes
        if outcome["matched"]
    )

    gold_cases = [
        outcome
        for outcome in outcomes
        if outcome["expected_accept"]
    ]

    bad_cases = [
        outcome
        for outcome in outcomes
        if not outcome["expected_accept"]
    ]

    gold_passed = sum(
        1
        for outcome in gold_cases
        if outcome["actual_accept"]
    )

    bad_rejected = sum(
        1
        for outcome in bad_cases
        if not outcome["actual_accept"]
    )

    summary = {
        "total_cases":
            len(outcomes),

        "matched_cases":
            matched_count,

        "accuracy_percent":
            (
                matched_count
                / len(outcomes)
                * 100.0
            ),

        "gold_cases":
            len(gold_cases),

        "gold_accepted":
            gold_passed,

        "bad_cases":
            len(bad_cases),

        "bad_rejected":
            bad_rejected,

        "outcomes":
            outcomes,
    }

    (
        RESULTS_DIR
        / "summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("CALIBRATION SUMMARY")
    print("=" * 72)

    print(
        "Matched:",
        f"{matched_count}/{len(outcomes)}",
    )

    print(
        "Accuracy:",
        f"{summary['accuracy_percent']:.1f}%",
    )

    print(
        "Known-good plans accepted:",
        f"{gold_passed}/{len(gold_cases)}",
    )

    print(
        "Known-bad plans rejected:",
        f"{bad_rejected}/{len(bad_cases)}",
    )

    print()

    if (
        gold_passed == len(gold_cases)
        and bad_rejected == len(bad_cases)
    ):
        print(
            "CALIBRATION STATUS: PASS"
        )
    else:
        print(
            "CALIBRATION STATUS: FAIL"
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