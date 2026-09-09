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
    raise RuntimeError("NEBIUS_API_KEY was not found in .env")


client = OpenAI(
    base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
    api_key=api_key,
)


MODEL = "nvidia/nemotron-3-super-120b-a12b"


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
                        "item_id": use.item_id,
                        "capability": use.capability.value,
                        "purpose": use.purpose,
                    }
                    for use in step.capability_uses
                ],

                "why_it_helps": step.why_it_helps,
            }
            for step in plan.steps
        ],

        "assumptions": plan.assumptions,
        "unresolved_risks": plan.unresolved_risks,
    }


def _compact_critic(
    critic: PlanCriticResult,
) -> list[dict]:
    """
    Repair only meaningful blocking findings.
    Low-severity findings do not justify another model repair.
    """

    return [
        {
            "step_order": finding.step_order,
            "claim": finding.claim,
            "issue_type": finding.issue_type.value,
            "severity": finding.severity.value,
            "recommended_fix": finding.recommended_fix,
        }
        for finding in critic.findings
        if finding.severity in {
            CriticSeverity.MEDIUM,
            CriticSeverity.HIGH,
        }
    ]


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

    external_resources = external_resources or []

    inventory_payload = [
        {
            "id": item.id,
            "name": item.name,
        }
        for item in inventory
    ]

    capability_graph = []

    for dna in object_dna.objects:
        capability_graph.append(
            {
                "item_id": dna.item_id,

                "traits": [
                    trait.trait.value
                    for trait in dna.physical_traits
                    if trait.certainty != CertaintyLevel.LOW
                ],

                "capabilities": [
                    affordance.capability.value
                    for affordance in dna.affordances
                    if affordance.certainty != CertaintyLevel.LOW
                ],

                "unknowns": dna.unknown_properties,
                "cautions": dna.caution_notes,
            }
        )

    failed_plan = _compact_plan(
        plan
    )

    blocking_findings = _compact_critic(
        critic
    )

    if not blocking_findings:
        return plan

    response = client.chat.completions.create(
        model=MODEL,
        reasoning_effort="low",

        response_format={
            "type": "json_object"
        },

        messages=[
            {
                "role": "user",
                "content": f"""
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
- If a step depends on an unsupported condition, change the physical arrangement.
- Every item used must cite an exact capability from its capability graph.
- Do not invent capabilities.
- Do not invent physical resources.
- Do not use unknown properties as if they were known.
- Respect cautions.
- Budget remains $0.
- No purchases.
- No permanent modifications.
- No intentional damage.
- Phone camera is explicitly available.
- Maximum 5 steps.
- Maximum about 22 words per action.
- Maximum about 12 words per capability purpose.
- Maximum about 18 words per why_it_helps.
- Keep assumptions and risks short.
- Return JSON only.


GOAL:

{goal}


EXTERNAL RESOURCES:

{json.dumps(external_resources, indent=2)}


AVAILABLE INVENTORY:

{json.dumps(inventory_payload, indent=2)}


CAPABILITY GRAPH:

{json.dumps(capability_graph, indent=2)}


CURRENT PLAN:

{json.dumps(failed_plan, indent=2)}


BLOCKING CRITIC FINDINGS:

{json.dumps(blocking_findings, indent=2)}
""".strip(),
            }
        ],

        temperature=0,
        max_tokens=5000,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Plan repair output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            f"Plan repair refused request: "
            f"{choice.message.refusal}"
        )

    raw_output = choice.message.content

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