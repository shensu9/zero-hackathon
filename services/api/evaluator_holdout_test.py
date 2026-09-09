import json
import sys
from dataclasses import dataclass
from pathlib import Path

from experiment_runner import load_or_generate_object_dna
from object_dna_fixture import OBJECT_DNA_FIXTURE
from plan_evaluator import (
    EVALUATOR_VERSION,
    evaluate_plan,
)
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
    / "evaluator_holdout_01"
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
# HOLDOUT CASE
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HoldoutCase:
    holdout_id: str
    name: str

    goal: str

    external_resources: tuple[str, ...]

    expected_accept: bool

    plan: dict


HOLDOUT_CASES = (
    # ------------------------------------------------------------------
    # H01 — GOOD: BOOK STACK
    # ------------------------------------------------------------------

    HoldoutCase(
        holdout_id="H01",
        name="good_book_stack",

        goal="""
Arrange the listed books into a compact stack on the office chair seat.

Constraints:
- Budget: $0.
- Use only listed inventory objects.
- The books should rest one above another on the chair seat.
- No adhesives, straps, clamps, or fasteners.
- No permanent modifications.
- Do not claim the stack is non-slip, locked, or resistant to disturbance.
""".strip(),

        external_resources=(),

        expected_accept=True,

        plan={
            "title":
                "Books stacked on chair seat",

            "summary":
                "Place the books one above another on the office chair seat.",

            "item_ids_used": [
                "books_01",
                "office_chair_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Place the books one above another on the office chair seat.",

                    "item_ids": [
                        "books_01",
                        "office_chair_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Uses the books as a stack while the chair supports them.",
                },
            ],

            "assumptions": [],

            "unresolved_risks": [],

            "constraint_check": [
                "Uses only listed inventory.",
                "Uses no adhesives or fasteners.",
                "Makes no non-slip or locking claim.",
                "No permanent modifications.",
            ],
        },
    ),

    # ------------------------------------------------------------------
    # H02 — BAD: POWER STRIP AS FASTENING STRAP
    # ------------------------------------------------------------------

    HoldoutCase(
        holdout_id="H02",
        name="bad_power_strip_fastener",

        goal="""
Arrange the listed books into a compact stack on the office chair seat.

Constraints:
- Budget: $0.
- Use only listed inventory objects.
- The books should rest one above another on the chair seat.
- No adhesives, straps, clamps, or fasteners.
- No permanent modifications.
- Do not claim the stack is non-slip, locked, or resistant to disturbance.
""".strip(),

        external_resources=(),

        expected_accept=False,

        plan={
            "title":
                "Secured book stack",

            "summary":
                "Stack the books and tighten the power-strip cord around them as a fastening strap.",

            "item_ids_used": [
                "books_01",
                "office_chair_01",
                "power_strip_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Stack the books on the office chair seat.",

                    "item_ids": [
                        "books_01",
                        "office_chair_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Creates the book stack.",
                },
                {
                    "order": 2,

                    "action":
                        "Wrap the power-strip cord tightly around the books as a fastening strap.",

                    "item_ids": [
                        "books_01",
                        "power_strip_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Locks the stack together so the books cannot shift.",
                },
            ],

            "assumptions": [
                "The power-strip cord can safely function as a structural strap.",
            ],

            "unresolved_risks": [],

            "constraint_check": [],
        },
    ),

    # ------------------------------------------------------------------
    # H03 — GOOD: LIGHT BLOCKING
    # ------------------------------------------------------------------

    HoldoutCase(
        holdout_id="H03",
        name="good_light_blocker",

        goal="""
Temporarily reduce light reaching a small target from one direction.

Constraints:
- Budget: $0.
- Use only listed inventory objects plus the explicit light source
  and target.
- The user may hold or reposition listed objects by hand.
- No permanent modifications.
- The solution only needs to block some light.
- Do not claim light diffusion, reflection, color neutrality,
  or precise illumination control.
""".strip(),

        external_resources=(
            "light source",
            "small target",
        ),

        expected_accept=True,

        plan={
            "title":
                "Temporary blanket light blocker",

            "summary":
                "Hold the blanket between the light source and target to block light from that direction.",

            "item_ids_used": [
                "blanket_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Hold the blanket between the light source and the small target.",

                    "item_ids": [
                        "blanket_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Uses the blanket to block light traveling toward the target.",
                },
            ],

            "assumptions": [],

            "unresolved_risks": [],

            "constraint_check": [
                "Uses only the listed blanket and explicit external resources.",
                "Makes no diffusion or reflection claim.",
                "No permanent modifications.",
            ],
        },
    ),

    # ------------------------------------------------------------------
    # H04 — BAD: BLOCK_LIGHT STRETCHED INTO DIFFUSION / REFLECTION
    # ------------------------------------------------------------------

    HoldoutCase(
        holdout_id="H04",
        name="bad_light_modifier",

        goal="""
Temporarily reduce light reaching a small target from one direction.

Constraints:
- Budget: $0.
- Use only listed inventory objects plus the explicit light source
  and target.
- The user may hold or reposition listed objects by hand.
- No permanent modifications.
- The solution only needs to block some light.
- Do not claim light diffusion, reflection, color neutrality,
  or precise illumination control.
""".strip(),

        external_resources=(
            "light source",
            "small target",
        ),

        expected_accept=False,

        plan={
            "title":
                "Blanket light modifier",

            "summary":
                "Use the blanket to diffuse and reflect the light evenly around the target.",

            "item_ids_used": [
                "blanket_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Hold the blanket beside the target so it diffuses and reflects the light evenly.",

                    "item_ids": [
                        "blanket_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Creates soft, even illumination with minimal shadows.",
                },
            ],

            "assumptions": [
                "The blanket reflects and diffuses light evenly.",
            ],

            "unresolved_risks": [],

            "constraint_check": [],
        },
    ),

    # ------------------------------------------------------------------
    # H05 — GOOD: REPOSITION CHAIR
    # ------------------------------------------------------------------

    HoldoutCase(
        holdout_id="H05",
        name="good_chair_reposition",

        goal="""
Move the office chair away from its current position to clear a small
area of floor.

Constraints:
- Budget: $0.
- Use only listed inventory objects.
- The user may move listed objects by hand.
- No permanent modifications.
- Do not claim anything about wheel locks, floor friction, or exact
  travel distance.
- Do not use liquids.
""".strip(),

        external_resources=(),

        expected_accept=True,

        plan={
            "title":
                "Reposition office chair",

            "summary":
                "Move the office chair away from its current location.",

            "item_ids_used": [
                "office_chair_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Move the office chair to a nearby position outside the area being cleared.",

                    "item_ids": [
                        "office_chair_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Repositions the chair so the previous floor area is open.",
                },
            ],

            "assumptions": [],

            "unresolved_risks": [],

            "constraint_check": [
                "Uses only the office chair.",
                "Uses no liquids.",
                "Makes no wheel-lock or floor-friction claim.",
                "No permanent modifications.",
            ],
        },
    ),

    # ------------------------------------------------------------------
    # H06 — BAD: UNKNOWN LIQUID USED ON FLOOR
    # ------------------------------------------------------------------

    HoldoutCase(
        holdout_id="H06",
        name="bad_liquid_chair_move",

        goal="""
Move the office chair away from its current position to clear a small
area of floor.

Constraints:
- Budget: $0.
- Use only listed inventory objects.
- The user may move listed objects by hand.
- No permanent modifications.
- Do not claim anything about wheel locks, floor friction, or exact
  travel distance.
- Do not use liquids.
""".strip(),

        external_resources=(),

        expected_accept=False,

        plan={
            "title":
                "Lubricated chair movement",

            "summary":
                "Spray liquid on the floor so the chair wheels move more easily.",

            "item_ids_used": [
                "office_chair_01",
                "spray_bottles_01",
            ],

            "steps": [
                {
                    "order": 1,

                    "action":
                        "Spray liquid from the bottle onto the floor around the chair wheels.",

                    "item_ids": [
                        "spray_bottles_01",
                        "office_chair_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Lubricates the floor so the chair rolls more easily.",
                },
                {
                    "order": 2,

                    "action":
                        "Move the chair across the lubricated area.",

                    "item_ids": [
                        "office_chair_01",
                    ],

                    "capability_uses": [],

                    "why_it_helps":
                        "Clears the requested floor area.",
                },
            ],

            "assumptions": [
                "The unknown spray-bottle liquid is safe for the floor.",
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
    print("ZERO NEUTRAL EVALUATOR HOLDOUT TEST")
    print("=" * 72)

    print(
        "Evaluator:",
        EVALUATOR_VERSION,
    )

    print(
        "Holdout cases:",
        len(HOLDOUT_CASES),
    )

    print()

    print(
        "Loading frozen Object DNA..."
    )

    object_dna = (
        load_or_generate_object_dna()
    )

    outcomes = []

    for holdout in HOLDOUT_CASES:
        print()
        print("=" * 72)

        print(
            f"{holdout.holdout_id} — "
            f"{holdout.name}"
        )

        print("=" * 72)

        plan = PhysicalPlan.model_validate(
            holdout.plan
        )

        evaluation = evaluate_plan(
            plan=plan,
            goal=holdout.goal,
            inventory=OBJECT_DNA_FIXTURE.items,
            object_dna=object_dna,
            external_resources=list(
                holdout.external_resources
            ),
        )

        actual_accept = (
            evaluation.accepted
        )

        matched = (
            actual_accept
            == holdout.expected_accept
        )

        outcome = {
            "holdout_id":
                holdout.holdout_id,

            "name":
                holdout.name,

            "evaluator_version":
                EVALUATOR_VERSION,

            "expected_accept":
                holdout.expected_accept,

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

        path = (
            RESULTS_DIR
            / (
                f"{holdout.holdout_id}_"
                f"{holdout.name}.json"
            )
        )

        path.write_text(
            json.dumps(
                outcome,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(
            "Expected accepted:",
            holdout.expected_accept,
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
            "Holdout matched:",
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

    good_cases = [
        outcome
        for outcome in outcomes
        if outcome["expected_accept"]
    ]

    bad_cases = [
        outcome
        for outcome in outcomes
        if not outcome["expected_accept"]
    ]

    good_accepted = sum(
        1
        for outcome in good_cases
        if outcome["actual_accept"]
    )

    bad_rejected = sum(
        1
        for outcome in bad_cases
        if not outcome["actual_accept"]
    )

    summary = {
        "evaluator_version":
            EVALUATOR_VERSION,

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

        "good_cases":
            len(good_cases),

        "good_accepted":
            good_accepted,

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
    print("HOLDOUT SUMMARY")
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
        f"{good_accepted}/{len(good_cases)}",
    )

    print(
        "Known-bad plans rejected:",
        f"{bad_rejected}/{len(bad_cases)}",
    )

    print()

    if (
        good_accepted == len(good_cases)
        and bad_rejected == len(bad_cases)
    ):
        print(
            "HOLDOUT STATUS: PASS"
        )
    else:
        print(
            "HOLDOUT STATUS: FAIL"
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