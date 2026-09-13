import json
import os
from json import JSONDecodeError

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from critic_schemas import (
    CriticSeverity,
    PlanCriticFinding,
    PlanCriticResult,
)
from model_json import load_model_json
from plan_schemas import PhysicalPlan
from schemas import (
    CertaintyLevel,
    InventoryItem,
    ObjectDNAResponse,
)


load_dotenv()

api_key = os.getenv(
    "NEBIUS_API_KEY"
)

if not api_key:
    raise RuntimeError(
        "NEBIUS_API_KEY was not found in .env"
    )


client = OpenAI(
    base_url=(
        "https://api.tokenfactory."
        "us-central1.nebius.com/v1/"
    ),
    api_key=api_key,
)


MODEL = (
    "nvidia/nemotron-3-super-120b-a12b"
)

SEMANTIC_CRITIC_MAX_TOKENS = 8000
JSON_REPAIR_MAX_TOKENS = 2500


# Compatibility for harmless redundant GROUP labels occasionally emitted
# by Nemotron in addition to every exact indexed semantic field.
#
# These keys never replace exact fields such as assumption:1,
# risk:1, or constraint:1.
#
# They may be ignored only when:
# - every exact required field is already present, and
# - the redundant group key contains zero finding references.
ALLOWED_EMPTY_COVERAGE_GROUP_KEYS = frozenset(
    {
        "assumption",
        "assumptions",
        "risk",
        "risks",
        "unresolved_risk",
        "unresolved_risks",
        "constraint_check",
        "constraint_checks",
    }
)


class IncompleteSemanticCoverageError(
    RuntimeError
):
    """
    Raised when the semantic critic does not provide exact
    field-by-field coverage for the PhysicalPlan.
    """

    pass


class SemanticAuditEnvelope(BaseModel):
    """
    Private model-output contract.

    This is intentionally NOT the public PlanCriticResult consumed by
    the rest of ZERO.

    coverage maps every required semantic field ID to the 1-based finding
    numbers that apply to that field.

    Example:

        "step:1:why_it_helps": [1]

    An empty list means the field was audited and no finding applies.
    """

    findings: list[
        PlanCriticFinding
    ] = Field(
        default_factory=list,
        max_length=8,
    )

    coverage: dict[
        str,
        list[int],
    ]


def _build_compact_dna(
    object_dna: ObjectDNAResponse,
) -> list[dict]:
    result = []

    for dna in object_dna.objects:
        result.append(
            {
                "item_id":
                    dna.item_id,

                "traits": [
                    trait.trait.value
                    for trait
                    in dna.physical_traits
                    if trait.certainty
                    != CertaintyLevel.LOW
                ],

                "capabilities": [
                    affordance.capability.value
                    for affordance
                    in dna.affordances
                    if affordance.certainty
                    != CertaintyLevel.LOW
                ],

                "unknown_properties":
                    dna.unknown_properties,

                "caution_notes":
                    dna.caution_notes,
            }
        )

    return result


def _build_semantic_field_map(
    plan: PhysicalPlan,
) -> dict[str, str]:
    """
    Deterministically enumerate every natural-language field that the
    semantic critic is required to inspect.

    item_ids and capability enum values are already covered by the hard
    deterministic validator, so they are not semantic audit fields.

    The returned IDs are compact, stable, and suitable for exact
    accounting in model output.
    """

    fields: dict[
        str,
        str,
    ] = {
        "title":
            plan.title,

        "summary":
            plan.summary,
    }

    for step in plan.steps:
        step_prefix = (
            f"step:{step.order}"
        )

        fields[
            f"{step_prefix}:action"
        ] = step.action

        for index, use in enumerate(
            step.capability_uses,
            start=1,
        ):
            fields[
                (
                    f"{step_prefix}:"
                    f"capability:{index}:purpose"
                )
            ] = use.purpose

        fields[
            f"{step_prefix}:why_it_helps"
        ] = step.why_it_helps

    for index, assumption in enumerate(
        plan.assumptions,
        start=1,
    ):
        fields[
            f"assumption:{index}"
        ] = assumption

    for index, risk in enumerate(
        plan.unresolved_risks,
        start=1,
    ):
        fields[
            f"risk:{index}"
        ] = risk

    for index, check in enumerate(
        plan.constraint_check,
        start=1,
    ):
        fields[
            f"constraint:{index}"
        ] = check

    return fields


def _normalize_critic_payload(
    payload: dict,
) -> dict:
    findings = payload.get(
        "findings",
        [],
    )

    if isinstance(
        findings,
        list,
    ):
        for finding in findings:
            if not isinstance(
                finding,
                dict,
            ):
                continue

            # Nemotron occasionally uses 0 to mean "plan-level".
            if finding.get(
                "step_order"
            ) == 0:
                finding[
                    "step_order"
                ] = None

    return payload


def _validate_semantic_coverage(
    *,
    envelope: SemanticAuditEnvelope,
    required_field_ids: list[str],
) -> None:
    """
    Deterministically prove exact audit-field accounting.

    Rules:
    - every required field ID must appear
    - no unknown field ID may appear
    - each finding reference is a valid 1-based finding index
    - duplicate references within one field are rejected
    - every finding must be attached to at least one audited field

    This does not decide whether a semantic judgment is correct.
    It guarantees that the critic response cannot silently omit a
    PhysicalPlan field and still be trusted by ZERO.
    """

    expected = set(
        required_field_ids
    )

    coverage = dict(
        envelope.coverage
    )

    actual = set(
        coverage.keys()
    )

    missing = sorted(
        expected - actual
    )

    initial_extra = sorted(
        actual - expected
    )

    # Never normalize extras when an exact required field is missing.
    #
    # Redundant aggregate keys are not substitutes for assumption:1,
    # risk:1, constraint:1, etc.
    if missing:
        raise IncompleteSemanticCoverageError(
            "Semantic critic coverage does not exactly match "
            "the required PhysicalPlan fields. "
            f"Missing: {missing}. "
            f"Unexpected: {initial_extra}."
        )

    # Narrow compatibility rule:
    #
    # If every exact required field is already present, Nemotron may
    # occasionally add harmless aggregate labels such as "assumption"
    # or "constraint_check".
    #
    # Ignore only known aggregate keys whose finding-reference list is
    # completely empty.
    #
    # Any non-empty aggregate key remains semantically meaningful and
    # therefore must still fail exact accounting.
    for key in initial_extra:
        if (
            key
            in ALLOWED_EMPTY_COVERAGE_GROUP_KEYS
            and coverage[key] == []
        ):
            del coverage[key]

    actual = set(
        coverage.keys()
    )

    extra = sorted(
        actual - expected
    )

    if extra:
        raise IncompleteSemanticCoverageError(
            "Semantic critic coverage does not exactly match "
            "the required PhysicalPlan fields. "
            "Missing: []. "
            f"Unexpected: {extra}."
        )

    finding_count = len(
        envelope.findings
    )

    referenced_findings: set[
        int
    ] = set()

    for field_id in required_field_ids:
        references = (
            coverage[
                field_id
            ]
        )

        if len(references) != len(
            set(references)
        ):
            raise IncompleteSemanticCoverageError(
                "Semantic critic coverage contains duplicate "
                f"finding references for field {field_id!r}: "
                f"{references}"
            )

        for finding_index in references:
            if finding_index < 1:
                raise IncompleteSemanticCoverageError(
                    "Semantic critic coverage uses a finding "
                    "index below 1 for field "
                    f"{field_id!r}: {finding_index}"
                )

            if (
                finding_index
                > finding_count
            ):
                raise IncompleteSemanticCoverageError(
                    "Semantic critic coverage references "
                    "a finding that does not exist. "
                    f"Field: {field_id!r}. "
                    f"Finding index: {finding_index}. "
                    f"Finding count: {finding_count}."
                )

            referenced_findings.add(
                finding_index
            )

    expected_findings = set(
        range(
            1,
            finding_count + 1,
        )
    )

    unreferenced = sorted(
        expected_findings
        - referenced_findings
    )

    if unreferenced:
        raise IncompleteSemanticCoverageError(
            "Semantic critic returned findings that were not "
            "attached to any audited PhysicalPlan field: "
            f"{unreferenced}"
        )


def _repair_malformed_critic_json(
    *,
    raw_output: str,
    required_field_ids: list[str],
) -> dict:
    """
    Repair formatting only.

    This call may not invent, remove, or reinterpret findings or coverage.

    If the original response omitted semantic coverage, the formatting
    repair must not fabricate it. The deterministic coverage validator
    will reject the incomplete result afterward.
    """

    response = (
        client.chat.completions.create(
            model=MODEL,
            reasoning_effort="low",

            response_format={
                "type":
                    "json_object"
            },

            messages=[
                {
                    "role":
                        "user",

                    "content":
                        f"""
You are a JSON formatting repair tool.

The following text was intended to be ZERO semantic-audit JSON,
but it is malformed.

Convert the existing content into valid JSON with this structure:

{{
  "findings": [
    {{
      "step_order": 1,
      "claim": "short claim",
      "issue_type": "unlisted_resource | unsupported_physical_claim | unsupported_capability | hidden_assumption | safety_or_uncertainty | constraint_violation",
      "severity": "low | medium | high",
      "explanation": "brief explanation",
      "recommended_fix": "brief fix"
    }}
  ],
  "coverage": {{
    "field-id": []
  }}
}}

Formatting-repair rules:

- Preserve the original findings and meaning.
- Preserve the original coverage decisions.
- Do NOT invent new findings.
- Do NOT remove findings.
- Do NOT invent missing coverage decisions.
- Do NOT add a required field merely because it appears in the list below
  if it was absent from the malformed input.
- Do NOT change severity except when necessary to recover malformed syntax.
- Use null for plan-level step_order.
- Never use step_order 0.
- coverage values are lists of 1-based finding numbers.
- Return JSON only.

The complete expected field-ID set is shown only so you can preserve
field-ID spelling when the malformed input clearly contains that field.
It is NOT permission to fabricate missing coverage.

EXPECTED FIELD IDS:

{json.dumps(
    required_field_ids,
    indent=2,
)}

MALFORMED INPUT:

{raw_output}
""".strip(),
                }
            ],

            temperature=0,
            max_tokens=(
                JSON_REPAIR_MAX_TOKENS
            ),
        )
    )

    choice = response.choices[0]

    if (
        choice.finish_reason
        == "length"
    ):
        raise RuntimeError(
            "Critic JSON-repair output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Critic JSON repair refused request: "
            f"{choice.message.refusal}"
        )

    repaired_output = (
        choice.message.content
    )

    if not repaired_output:
        raise RuntimeError(
            "Critic JSON repair returned no output."
        )

    return load_model_json(
        repaired_output
    )


def _parse_critic_output(
    *,
    raw_output: str,
    required_field_ids: list[str],
) -> PlanCriticResult:
    """
    Parse and validate the private semantic-audit envelope.

    Only after exact deterministic coverage succeeds is the response
    converted into ZERO's existing public PlanCriticResult.
    """

    try:
        payload = load_model_json(
            raw_output
        )

    except JSONDecodeError:
        print(
            "Semantic critic returned malformed JSON; "
            "attempting one formatting repair..."
        )

        payload = (
            _repair_malformed_critic_json(
                raw_output=raw_output,
                required_field_ids=(
                    required_field_ids
                ),
            )
        )

    payload = (
        _normalize_critic_payload(
            payload
        )
    )

    envelope = (
        SemanticAuditEnvelope.model_validate(
            payload
        )
    )

    _validate_semantic_coverage(
        envelope=envelope,
        required_field_ids=(
            required_field_ids
        ),
    )

    has_blocking_findings = any(
        finding.severity
        in {
            CriticSeverity.MEDIUM,
            CriticSeverity.HIGH,
        }
        for finding
        in envelope.findings
    )

    return PlanCriticResult(
        passed=(
            not has_blocking_findings
        ),
        findings=(
            envelope.findings
        ),
    )


def _build_semantic_critic_prompt(
    *,
    plan: PhysicalPlan,
    goal: str,
    inventory_payload: list[dict],
    compact_dna: list[dict],
    external_resources: list[str],
    semantic_field_map: dict[str, str],
) -> str:
    """
    Build ZERO's semantic physical-plan audit prompt.

    The model must explicitly account for every required field.
    Deterministic code validates that accounting before findings are trusted.
    """

    return f"""
You are ZERO's semantic physical-plan critic.

The plan has ALREADY passed deterministic validation:

- every inventory item ID exists
- every physical item use cites a capability
- every cited capability exists in validated Object DNA

Do NOT repeat those checks unless natural-language wording stretches a
capability beyond its actual meaning.

Your job is to detect unsupported physical claims that remain anywhere
in the plan's natural language.


======================================================================
MANDATORY FIELD-BY-FIELD AUDIT
======================================================================

ZERO has deterministically enumerated every natural-language PhysicalPlan
field that you must audit.

You MUST evaluate EVERY field ID in SEMANTIC FIELD CHECKLIST.

Do NOT stop after finding one problem.

For every field ID, decide whether one or more semantic findings apply.

Your output MUST contain a "coverage" object with EXACTLY the same field
IDs as SEMANTIC FIELD CHECKLIST.

Coverage values are lists of 1-based finding numbers.

Example:

{{
  "findings": [
    {{
      "step_order": 1,
      "claim": "Provides a uniform background",
      "issue_type": "unsupported_physical_claim",
      "severity": "medium",
      "explanation": "Uniform appearance is not established.",
      "recommended_fix": "Remove the uniformity claim."
    }}
  ],
  "coverage": {{
    "title": [],
    "summary": [],
    "step:1:action": [],
    "step:1:capability:1:purpose": [],
    "step:1:why_it_helps": [1]
  }}
}}

Meaning:

- [] means you audited that field and found no semantic issue.
- [1] means finding #1 applies to that field.
- A finding may be referenced by more than one field when genuinely needed.
- Every finding must be referenced by at least one field.
- Do not reference a finding number that does not exist.
- Do not omit a checklist field.
- Do not add a field that is not in the checklist.

ZERO will deterministically reject your entire response if coverage is
missing, incomplete, contains unknown fields, references invalid findings,
or leaves a finding unattached.

The model's own "passed" judgment is NOT requested and will NOT be trusted.
ZERO derives pass/fail deterministically from validated finding severity.


======================================================================
FULL SEMANTIC SWEEP
======================================================================

Audit:

- title
- summary
- every step action
- every capability-use purpose
- every why_it_helps
- every assumption
- every unresolved risk
- every constraint check

Treat each materially different physical property, outcome, causal effect,
resource dependency, safety claim, or required condition as something that
must be grounded.

A field is not automatically safe merely because it appears in summary,
why_it_helps, assumptions, risks, or constraint checks.


======================================================================
APPEARANCE / QUALITY CLAIMS
======================================================================

Direct capabilities such as:

- cover
- hang
- support
- provide_surface
- fasten

do NOT automatically establish:

- clean
- uniform
- plain
- seamless
- wrinkle-free
- smooth
- consistent color
- consistent texture
- professional-looking
- visually neutral

Example:

A blanket that can cover or hang may be usable as a backdrop.

That does NOT by itself prove:

"Provides a uniform background."

or:

"Provides a clean background."

or:

"Provides a consistent color or texture."

These terms are not a blind blacklist.

If validated evidence genuinely establishes the property, the claim may
be supported.


======================================================================
CAUSAL / CERTAINTY CLAIMS
======================================================================

A direct capability does not automatically prove a hoped-for downstream
effect.

"fasten" does not by itself prove:
- prevents slipping
- reduces slip risk
- guarantees stability
- ensures an object stays in place
- makes an arrangement safe

"diffuse_light" does not by itself prove:
- the window produces light
- enough ambient illumination exists
- exposure will be sufficient
- the image will be well-lit
- professional-quality lighting

"provide_surface" does not by itself prove:
- an arbitrary product fits
- unknown load capacity is sufficient
- the surface is clean
- an unknown load will be stable

Distinguish carefully between:

"The window diffuses available light."

and the stronger claim:

"The window provides illumination."

A window may transmit or diffuse available light without proving that an
adequate external light source exists.


======================================================================
TARGET FIT / COVERAGE / ATTACHMENT UNCERTAINTY
======================================================================

Unknown properties remain unresolved even when a related generic capability
exists.

Audit every natural-language field that relies on an unknown property.

In particular:

- "cover" does NOT establish that an object's dimensions are large enough
  for a particular target, doorway, opening, person, or surface.

- "large_surface" does NOT establish exact dimensions, target fit, or
  sufficient coverage area.

- If "dimensions" or "coverage area" are listed as unknown, claims such as
  "covers the doorway", "covers the opening", "fits across the window",
  "provides full coverage", or equivalent target-fit claims require
  verification or must remain explicitly conditional.

- "hang" does NOT by itself establish that a safe attachment method exists
  for the specific arrangement.

- If "attachment method" is unknown, claims that an object can be securely,
  safely, or non-damagingly attached must remain conditional on verification.

- "support" or "hang" does NOT establish sufficient load-bearing capacity
  when "load-bearing capacity" is unknown.

- Do not infer that a mounting surface, frame, hook, shelf, or other support
  can safely carry a particular object's weight merely from a generic
  support/hang capability.

CONDITIONAL EXECUTION RULE:

The USER GOAL may include a CONDITIONAL EXECUTION CONTRACT.

When an explicit requirement says a condition must be verified BEFORE
execution, do not flag the mere existence of that unknown as an immediate
failure.

Instead audit whether the plan preserves that condition correctly.

A plan is still problematic if it:

- states the unknown condition as already true,
- promises a result that depends on a different unresolved unknown,
- omits a required verification from the execution logic,
- or makes a stronger unconditional fit, coverage, stability, attachment,
  safety, privacy, or light-blocking claim than the evidence supports.


======================================================================
TARGET FIT / COVERAGE / ATTACHMENT UNCERTAINTY
======================================================================

Unknown properties remain unresolved even when a related generic capability
exists.

Audit every natural-language field that relies on an unknown property.

In particular:

- "cover" does NOT establish that an object's dimensions are large enough
  for a particular target, doorway, opening, person, or surface.

- "large_surface" does NOT establish exact dimensions, target fit, or
  sufficient coverage area.

- If "dimensions" or "coverage area" are listed as unknown, claims such as
  "covers the doorway", "covers the opening", "fits across the window",
  "provides full coverage", or equivalent target-fit claims require
  verification or must remain explicitly conditional.

- "hang" does NOT by itself establish that a safe attachment method exists
  for the specific arrangement.

- If "attachment method" is unknown, claims that an object can be securely,
  safely, or non-damagingly attached must remain conditional on verification.

- "support" or "hang" does NOT establish sufficient load-bearing capacity
  when "load-bearing capacity" is unknown.

- Do not infer that a mounting surface, frame, hook, shelf, or other support
  can safely carry a particular object's weight merely from a generic
  support/hang capability.

CONDITIONAL EXECUTION RULE:

The USER GOAL may include a CONDITIONAL EXECUTION CONTRACT.

When an explicit requirement says a condition must be verified BEFORE
execution, do not flag the mere existence of that unknown as an immediate
failure.

Instead audit whether the plan preserves that condition correctly.

A plan is still problematic if it:

- states the unknown condition as already true,
- promises a result that depends on a different unresolved unknown,
- omits a required verification from the execution logic,
- or makes a stronger unconditional fit, coverage, stability, attachment,
  safety, privacy, or light-blocking claim than the evidence supports.


======================================================================
RETURN FORMAT
======================================================================

Return ONLY valid JSON:

{{
  "findings": [
    {{
      "step_order": 1,
      "claim": "short problematic claim",
      "issue_type": "unlisted_resource | unsupported_physical_claim | unsupported_capability | hidden_assumption | safety_or_uncertainty | constraint_violation",
      "severity": "low | medium | high",
      "explanation": "brief explanation",
      "recommended_fix": "brief specific fix"
    }}
  ],
  "coverage": {{
    "exact-field-id": []
  }}
}}

OUTPUT LIMITS

- Maximum 8 findings.
- Prefer MEDIUM/HIGH issues.
- Include LOW issues only when materially useful.
- claim: maximum about 15 words.
- explanation: maximum about 35 words.
- recommended_fix: maximum about 30 words.
- Do not duplicate the same issue unnecessarily.


STEP ORDER RULE

- Use the real step number for a step-specific issue.
- Use null for title, summary, assumptions, risks, constraint checks,
  or plan-wide issues.
- Never use 0.


ISSUE TYPES

unlisted_resource:
The plan relies on a physical resource not present in canonical inventory
or explicit external resources.

unsupported_physical_claim:
The plan states a physical property or outcome not established by
validated evidence.

unsupported_capability:
A real capability is stretched beyond its actual meaning.

hidden_assumption:
The plan requires an unstated or unverified physical condition.

safety_or_uncertainty:
The plan ignores an unknown property or caution that matters to the use.

constraint_violation:
The plan conflicts with the user's stated constraints.


GROUNDING RULES

- Medium/high validated traits and capabilities may support claims.
- Low-certainty properties do not establish claims.
- Unknown properties remain unknown.
- Caution notes remain active.
- Object names alone do not establish extra physical properties.
- Generic category expectations do not override explicit unknowns.
- Do not require laboratory-level certainty for ordinary physical use.
- Do reject specific claims that exceed available evidence.
- A capability supports its direct affordance, not every desirable
  consequence that might follow from using it.


AVAILABLE INVENTORY

{json.dumps(
    inventory_payload,
    indent=2,
)}


EXPLICIT EXTERNAL RESOURCES

{json.dumps(
    external_resources,
    indent=2,
)}

No other physical resources are confirmed.


VALIDATED COMPACT OBJECT DNA

{json.dumps(
    compact_dna,
    indent=2,
)}


SEMANTIC FIELD CHECKLIST

The keys below are the EXACT field IDs required in your coverage object.

{json.dumps(
    semantic_field_map,
    indent=2,
)}


USER GOAL

{goal}


FULL PLAN CONTEXT

{plan.model_dump_json(
    indent=2
)}
""".strip()


def audit_plan_semantics(
    *,
    plan: PhysicalPlan,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources: list[str] | None = None,
) -> PlanCriticResult:
    external_resources = (
        external_resources
        or []
    )

    inventory_payload = [
        {
            "id":
                item.id,

            "name":
                item.name,

            "description":
                item.description,
        }
        for item
        in inventory
    ]

    compact_dna = (
        _build_compact_dna(
            object_dna
        )
    )

    semantic_field_map = (
        _build_semantic_field_map(
            plan
        )
    )

    required_field_ids = list(
        semantic_field_map.keys()
    )

    prompt = (
        _build_semantic_critic_prompt(
            plan=plan,
            goal=goal,
            inventory_payload=(
                inventory_payload
            ),
            compact_dna=(
                compact_dna
            ),
            external_resources=(
                external_resources
            ),
            semantic_field_map=(
                semantic_field_map
            ),
        )
    )

    response = (
        client.chat.completions.create(
            model=MODEL,
            reasoning_effort="low",

            response_format={
                "type":
                    "json_object"
            },

            messages=[
                {
                    "role":
                        "user",

                    "content":
                        prompt,
                }
            ],

            temperature=0,
            max_tokens=(
                SEMANTIC_CRITIC_MAX_TOKENS
            ),
        )
    )

    choice = response.choices[0]

    if (
        choice.finish_reason
        == "length"
    ):
        raise RuntimeError(
            "Semantic critic output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Semantic critic refused request: "
            f"{choice.message.refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "Semantic critic returned no final content."
        )

    return _parse_critic_output(
        raw_output=raw_output,
        required_field_ids=(
            required_field_ids
        ),
    )