import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from critic_schemas import (
    CriticSeverity,
    PlanCriticResult,
)
from model_json import load_model_json
from plan_normalizer import normalize_plan_payload
from plan_schemas import PhysicalPlan
from schemas import (
    CertaintyLevel,
    InventoryItem,
    ObjectDNAResponse,
)


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

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


def _compact_plan(
    plan: PhysicalPlan,
) -> dict:
    """
    Keep only information needed to repair the plan.
    """

    return {
        "title": plan.title,
        "summary": plan.summary,

        "steps": [
            {
                "order": step.order,
                "action": step.action,
                "item_ids": step.item_ids,

                "capability_uses": [
                    {
                        "item_id":
                            use.item_id,

                        "capability":
                            use.capability.value,

                        "purpose":
                            use.purpose,
                    }
                    for use
                    in step.capability_uses
                ],

                "why_it_helps":
                    step.why_it_helps,
            }
            for step
            in plan.steps
        ],

        "assumptions":
            plan.assumptions,

        "unresolved_risks":
            plan.unresolved_risks,
    }


def _compact_critic(
    critic: PlanCriticResult,
) -> list[dict]:
    """
    Repair only meaningful blocking findings.

    Low-severity findings do not justify another model repair.

    Preserve the critic explanation so the repair model knows WHY the
    wording was rejected. This reduces the chance of replacing one
    unsupported claim with a differently worded unsupported claim.
    """

    return [
        {
            "step_order":
                finding.step_order,

            "claim":
                finding.claim,

            "issue_type":
                finding.issue_type.value,

            "severity":
                finding.severity.value,

            "explanation":
                finding.explanation,

            "recommended_fix":
                finding.recommended_fix,
        }
        for finding
        in critic.findings
        if finding.severity
        in {
            CriticSeverity.MEDIUM,
            CriticSeverity.HIGH,
        }
    ]


def _build_repair_prompt(
    *,
    goal: str,
    external_resources: list[str],
    inventory_payload: list[dict],
    capability_graph: list[dict],
    failed_plan: dict,
    blocking_findings: list[dict],
) -> str:
    """
    Build the semantic repair instruction.

    Important repair invariant:

    A repair may REMOVE or WEAKEN an unsupported claim, but it may not
    replace that claim with a new unsupported causal or certainty claim.

    Example:

        capability: fasten

    supports:

        "Fasten the blanket to the door."

    but does NOT itself prove:

        "prevent slipping"
        "reduce slip risk"
        "keep the blanket stable"
        "ensure the blanket stays in place"
        "make the setup safer"
    """

    return f"""
You are ZERO's plan repair layer.

The existing plan already passed ZERO's deterministic capability validator.

Do NOT redesign it from scratch.

Repair ONLY the MEDIUM/HIGH semantic critic findings.

Return ONLY valid JSON:

{{
  "title": "short title",
  "summary": "short grounded summary",
  "item_ids_used": [],
  "steps": [
    {{
      "order": 1,
      "action": "concise physical action",
      "item_ids": [],
      "capability_uses": [
        {{
          "item_id": "inventory id",
          "capability": "exact allowed capability",
          "purpose": "brief purpose"
        }}
      ],
      "why_it_helps": "brief grounded reason"
    }}
  ],
  "assumptions": [],
  "unresolved_risks": [],
  "constraint_check": []
}}


REPAIR RULES

- Preserve valid steps whenever possible.
- Fix every supplied critic finding.
- Remove unsupported wording rather than inventing evidence.
- A repair must NEVER replace one unsupported claim with a new unsupported claim.
- Do not strengthen certainty or causal language while repairing a finding.
- A capability proves only the direct physical affordance represented by that capability.
- Do not infer an unstated downstream effect merely because an item can perform a direct capability.
- Do not claim that an action prevents, eliminates, reduces, guarantees, ensures, stabilizes, protects, secures against, or makes something safer unless that exact effect is grounded by validated traits/capabilities or explicitly confirmed information.
- If a critic recommends weaker language such as "may", "could", "might", or "without asserting", preserve that uncertainty or make the wording even more conservative.
- If an unsupported effect is unnecessary to perform the action, remove the effect claim entirely.
- If uncertainty still matters after removing an unsupported claim, put it in unresolved_risks rather than presenting it as a fact or assumption.
- Do not convert an unresolved risk into an assumption that implies the risk has been solved.
- Capability purposes must describe the direct use of the capability, not an unverified result of that use.
- If a step depends on an unsupported condition, change the physical arrangement instead of pretending the condition is resolved.
- Every item used must cite an exact capability from its capability graph.
- Do not invent capabilities.
- Do not invent physical resources.
- Do not use unknown properties as if they were known.
- Respect cautions.
- Budget remains $0.
- No purchases.
- No permanent modifications.
- No intentional damage.
- Only the explicitly listed external resources may be treated as available without inventory IDs.
- Do not introduce fallback tools, lights, clips, fasteners, supports, or other materials unless they are present in AVAILABLE INVENTORY or EXTERNAL RESOURCES.
- Maximum 5 steps.
- Maximum about 22 words per action.
- Maximum about 12 words per capability purpose.
- Maximum about 18 words per why_it_helps.
- Keep assumptions and risks short.
- Return JSON only.


SEMANTIC-STRENGTHENING EXAMPLE

If the validated capability is:

"fasten"

Grounded wording includes:

"Fasten the blanket to the door."

or:

"Use the lanyard to fasten the blanket to the door."

The capability "fasten" alone does NOT establish any of these claims:

"prevent slipping"
"reduce slip risk"
"keep the blanket stable"
"ensure the blanket stays in place"
"guarantee the blanket will not move"
"make the setup safer"

If the critic rejected such an effect, remove the effect claim.

Do NOT replace it with another softer-sounding causal claim.

For example:

BAD REPAIR:
"secure the blanket to reduce slipping"

BAD REPAIR:
"fasten the blanket so it stays stable"

BAD REPAIR:
"fasten the blanket to help prevent movement"

GROUNDED REPAIR:
"fasten the blanket to the door"

If movement remains possible, keep that uncertainty in unresolved_risks.


GOAL:

{goal}


EXTERNAL RESOURCES:

{json.dumps(
    external_resources,
    indent=2,
)}


AVAILABLE INVENTORY:

{json.dumps(
    inventory_payload,
    indent=2,
)}


CAPABILITY GRAPH:

{json.dumps(
    capability_graph,
    indent=2,
)}


CURRENT PLAN:

{json.dumps(
    failed_plan,
    indent=2,
)}


BLOCKING CRITIC FINDINGS:

{json.dumps(
    blocking_findings,
    indent=2,
)}
""".strip()


def repair_plan(
    *,
    plan: PhysicalPlan,
    critic: PlanCriticResult,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources: list[str] | None = None,
) -> PhysicalPlan:
    """
    Repair only blocking semantic problems in an otherwise
    capability-valid ZERO plan.
    """

    external_resources = (
        external_resources
        or []
    )

    inventory_payload = [
        {
            "id": item.id,
            "name": item.name,
        }
        for item
        in inventory
    ]

    capability_graph = []

    for dna in object_dna.objects:
        capability_graph.append(
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

                "unknowns":
                    dna.unknown_properties,

                "cautions":
                    dna.caution_notes,
            }
        )

    failed_plan = _compact_plan(
        plan
    )

    blocking_findings = (
        _compact_critic(
            critic
        )
    )

    if not blocking_findings:
        return plan

    prompt = _build_repair_prompt(
        goal=goal,
        external_resources=(
            external_resources
        ),
        inventory_payload=(
            inventory_payload
        ),
        capability_graph=(
            capability_graph
        ),
        failed_plan=failed_plan,
        blocking_findings=(
            blocking_findings
        ),
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
            max_tokens=5000,
        )
    )

    choice = response.choices[0]

    if (
        choice.finish_reason
        == "length"
    ):
        raise RuntimeError(
            "Plan repair output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Plan repair refused request: "
            f"{choice.message.refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "Plan repair returned no final content."
        )

    payload = load_model_json(
        raw_output
    )

    payload = normalize_plan_payload(
        payload
    )

    return PhysicalPlan.model_validate(
        payload
    )