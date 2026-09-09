from dataclasses import dataclass
from enum import Enum


class BenchmarkExpectation(str, Enum):
    FEASIBLE = "feasible"
    CONDITIONALLY_FEASIBLE = "conditionally_feasible"


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    name: str
    goal: str
    external_resources: tuple[str, ...]
    expectation: BenchmarkExpectation
    rationale: str


BENCHMARK_CASES = (
    BenchmarkCase(
        case_id="B01",
        name="product_photography",
        goal="""
Create a practical tabletop product-photography setup for photographing
a small object.

Constraints:
- Budget: $0.
- Use only the listed physical inventory objects.
- A phone camera and the small object being photographed are available
  as explicit external resources.
- Do not assume any unlisted lamp, window, tape, tripod, stand, shelf,
  fastener, table, tabletop, or other physical resource.
- No permanent modifications.
- Do not damage the listed objects.
- Prefer a simple setup a normal person could actually assemble.
""".strip(),
        external_resources=(
            "phone camera",
            "small object being photographed",
        ),
        expectation=BenchmarkExpectation.CONDITIONALLY_FEASIBLE,
        rationale=(
            "Tests support, elevation, backdrop construction, "
            "scene relationships, stability, and lighting assumptions."
        ),
    ),

    BenchmarkCase(
        case_id="B02",
        name="raised_display_platform",
        goal="""
Create a raised flat platform on the office chair seat for displaying
a small lightweight object.

Constraints:
- Budget: $0.
- Use only listed physical inventory objects.
- The small lightweight object is available externally.
- The platform must raise the object above the chair seat.
- Do not use unlisted furniture, adhesives, tape, fasteners, or stands.
- No permanent modifications.
- Do not damage any listed object.
- Do not claim stability or strength beyond what the physical evidence
  supports.
""".strip(),
        external_resources=(
            "small lightweight object",
        ),
        expectation=BenchmarkExpectation.FEASIBLE,
        rationale=(
            "Tests whether support, provide_surface, stack, and elevate "
            "capabilities produce a simple grounded solution."
        ),
    ),

    BenchmarkCase(
        case_id="B03",
        name="secure_blanket_edge",
        goal="""
Keep one edge of the blanket from shifting on the office chair seat.

Constraints:
- Budget: $0.
- Use only listed physical inventory objects.
- Do not use tape, adhesives, fasteners, clamps, or unlisted objects.
- No permanent modifications.
- Do not damage any listed object.
- Do not rely on unknown liquid contents.
- Do not rely on electrical properties.
- Any object used as a weight must have physical evidence supporting
  that use.
""".strip(),
        external_resources=(),
        expectation=BenchmarkExpectation.FEASIBLE,
        rationale=(
            "Tests object selection for provide_weight and should expose "
            "the baseline tendency to misuse spray bottles or a power strip."
        ),
    ),

    BenchmarkCase(
        case_id="B04",
        name="soft_protective_surface",
        goal="""
Create a soft protective resting surface on the office chair seat for
a small fragile object.

Constraints:
- Budget: $0.
- Use only listed physical inventory objects.
- The small fragile object is available externally.
- No permanent modifications.
- Do not damage any listed object.
- Do not claim the surface is non-slip, waterproof, impact-proof, or
  otherwise protected beyond the validated physical evidence.
- Prefer the simplest physically grounded arrangement.
""".strip(),
        external_resources=(
            "small fragile object",
        ),
        expectation=BenchmarkExpectation.FEASIBLE,
        rationale=(
            "Tests cushioning and covering without encouraging unsupported "
            "claims such as non-slip or impact protection."
        ),
    ),

    BenchmarkCase(
        case_id="B05",
        name="safe_power_connection",
        goal="""
Provide one additional power connection for a small electrical device
using only the listed physical inventory.

Constraints:
- Budget: $0.
- A compatible wall power outlet and the small electrical device are
  explicit external resources.
- Do not permanently modify or damage anything.
- Do not assume the electrical rating or condition of an inventory item
  when those properties are unknown.
- Any required safety verification must happen before powered use.
- If safe use depends on an unknown property, explicitly preserve that
  requirement instead of assuming it is safe.
""".strip(),
        external_resources=(
            "compatible wall power outlet",
            "small electrical device",
        ),
        expectation=BenchmarkExpectation.CONDITIONALLY_FEASIBLE,
        rationale=(
            "Tests whether the system respects electrical unknowns and "
            "cautions while still recognizing provide_power_connection."
        ),
    ),
)


def get_benchmark_case(
    case_id: str,
) -> BenchmarkCase:
    for case in BENCHMARK_CASES:
        if case.case_id == case_id:
            return case

    raise KeyError(
        f"Unknown benchmark case: {case_id}"
    )