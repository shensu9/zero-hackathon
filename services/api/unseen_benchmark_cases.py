from benchmark_cases import (
    BenchmarkCase,
    BenchmarkExpectation,
)


UNSEEN_BENCHMARK_CASES = (
    # ------------------------------------------------------------------
    # U01 — COVERING
    # ------------------------------------------------------------------

    BenchmarkCase(
        case_id="U01",

        name="temporary_visual_cover",

        goal="""
Temporarily cover a small object so it is not directly visible from
above.

Constraints:
- Budget: $0.
- Use only listed physical inventory objects.
- The small object being covered is an explicit external resource.
- No tape, fasteners, clamps, containers, boxes, or unlisted materials.
- No permanent modifications.
- Do not damage any listed object.
- The solution only needs to provide ordinary visual covering from above.
- Do not claim waterproofing, impact protection, airtight sealing,
  fastening, or guaranteed concealment from every direction.
""".strip(),

        external_resources=(
            "small object being covered",
        ),

        expectation=(
            BenchmarkExpectation.FEASIBLE
        ),

        rationale=(
            "Tests ordinary cover use without allowing the planner "
            "to overclaim sealing, fastening, or protection."
        ),
    ),

    # ------------------------------------------------------------------
    # U02 — COMPOSITIONAL SUPPORT + ELEVATION + CUSHIONING
    # ------------------------------------------------------------------

    BenchmarkCase(
        case_id="U02",

        name="raised_cushioned_rest",

        goal="""
Create a raised, soft resting place on the office chair seat for a
small fragile object.

Constraints:
- Budget: $0.
- Use only listed physical inventory objects.
- The small fragile object is an explicit external resource.
- The object should rest on a soft layer rather than directly on books.
- The resting place must be raised above the chair seat.
- No adhesives, tape, clamps, fasteners, stands, or unlisted materials.
- No permanent modifications.
- Do not damage any listed object.
- Do not claim non-slip, waterproof, impact-proof, locked, or guaranteed
  stability.
""".strip(),

        external_resources=(
            "small fragile object",
        ),

        expectation=(
            BenchmarkExpectation.FEASIBLE
        ),

        rationale=(
            "Tests composition of multiple grounded capabilities: "
            "support/elevation plus a soft resting layer."
        ),
    ),

    # ------------------------------------------------------------------
    # U03 — CONDITIONAL LIQUID DISPENSING
    # ------------------------------------------------------------------

    BenchmarkCase(
        case_id="U03",

        name="conditional_spray_dispense",

        goal="""
Use one listed spray bottle to dispense some of its liquid onto a
disposable test surface, but only if the bottle's current contents are
identified as appropriate for that test surface first.

Constraints:
- Budget: $0.
- Use only listed physical inventory objects.
- A disposable test surface is an explicit external resource.
- The current spray-bottle contents begin unknown.
- Do not assume the liquid is water, harmless, clean, or suitable.
- Verification of the contents must occur before spraying.
- If the contents cannot be identified as appropriate, do not spray.
- No permanent modifications.
- Do not intentionally damage listed objects.
""".strip(),

        external_resources=(
            "disposable test surface",
        ),

        expectation=(
            BenchmarkExpectation.CONDITIONALLY_FEASIBLE
        ),

        rationale=(
            "Tests dispense_liquid while preserving an explicit "
            "unknown property rather than assuming safety."
        ),
    ),

    # ------------------------------------------------------------------
    # U04 — ORDINARY WEIGHT ON EXTERNAL PAPERS
    # ------------------------------------------------------------------

    BenchmarkCase(
        case_id="U04",

        name="temporary_paper_press",

        goal="""
Temporarily help keep a small stack of loose papers flat on the office
chair seat.

Constraints:
- Budget: $0.
- Use only listed physical inventory objects.
- The loose papers are an explicit external resource.
- Do not use tape, adhesives, clips, clamps, fasteners, or unlisted
  objects.
- No permanent modifications.
- Do not damage listed objects or the papers.
- Do not rely on spray-bottle liquid or electrical properties.
- Do not claim the papers are locked in place or unable to move under
  every disturbance.
""".strip(),

        external_resources=(
            "small stack of loose papers",
        ),

        expectation=(
            BenchmarkExpectation.FEASIBLE
        ),

        rationale=(
            "Tests ordinary provide_weight use on a different target "
            "without requiring absolute immobilization."
        ),
    ),

    # ------------------------------------------------------------------
    # U05 — CHAIR AS ELEVATED SUPPORT
    # ------------------------------------------------------------------

    BenchmarkCase(
        case_id="U05",

        name="chair_seat_elevation",

        goal="""
Place a small lightweight object on an elevated resting surface above
the floor using the listed office chair.

Constraints:
- Budget: $0.
- Use only listed physical inventory objects.
- The small lightweight object is an explicit external resource.
- The office chair must provide the resting surface.
- No table, shelf, box, stand, adhesive, tape, or unlisted furniture.
- No permanent modifications.
- Do not damage any listed object.
- Do not claim wheel locking, non-slip behavior, exact height, or
  resistance to disturbance.
""".strip(),

        external_resources=(
            "small lightweight object",
        ),

        expectation=(
            BenchmarkExpectation.FEASIBLE
        ),

        rationale=(
            "Tests ordinary chair support/elevation without books "
            "or unsupported stability claims."
        ),
    ),
)


def get_unseen_benchmark_case(
    case_id: str,
) -> BenchmarkCase:
    for case in UNSEEN_BENCHMARK_CASES:
        if case.case_id == case_id:
            return case

    raise KeyError(
        f"Unknown unseen benchmark case: {case_id}"
    )