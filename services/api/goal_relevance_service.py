import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from model_json import load_model_json
from schemas import (
    CanonicalInventory,
    GoalAwareInventoryResponse,
    InventoryItem,
    VerificationStatus,
)


MODEL = "nvidia/nemotron-3-super-120b-a12b"

BASE_URL = (
    "https://api.tokenfactory.us-central1.nebius.com/v1/"
)


def _create_client() -> OpenAI:
    """
    Create the paid reasoning client lazily.

    Keeping client creation out of module import allows deterministic
    validators/tests to run without making or requiring a paid model call.
    """

    load_dotenv()

    api_key = os.getenv("NEBIUS_API_KEY")

    if not api_key:
        raise RuntimeError(
            "NEBIUS_API_KEY was not found in .env"
        )

    return OpenAI(
        base_url=BASE_URL,
        api_key=api_key,
    )


def _partition_inventory(
    inventory: CanonicalInventory,
) -> tuple[
    list[InventoryItem],
    list[InventoryItem],
]:
    """
    Return active and pending inventory while enforcing unique canonical IDs.

    Active:
        AUTO_ACCEPTED or USER_CONFIRMED

    Pending:
        NEEDS_CONFIRMATION
    """

    seen_ids: set[str] = set()

    active_items: list[InventoryItem] = []
    pending_items: list[InventoryItem] = []

    for item in inventory.items:
        if item.id in seen_ids:
            raise ValueError(
                "Canonical inventory contains duplicate item ID: "
                f"{item.id}"
            )

        seen_ids.add(item.id)

        if (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        ):
            pending_items.append(item)
            continue

        active_items.append(item)

    return active_items, pending_items


def _item_context(
    item: InventoryItem,
    *,
    include_uncertainty: bool,
) -> dict:
    """
    Produce compact grounded model context without creating another
    inventory representation or changing the canonical contract.
    """

    context = {
        "item_id": item.id,
        "name": item.name,
        "description": item.description,
        "location_hint": item.location_hint,
    }

    if include_uncertainty:
        context["source_confidence"] = (
            item.source_confidence
        )
        context["uncertainty_reason"] = (
            item.uncertainty_reason
        )

    return context


def build_goal_relevance_prompt(
    *,
    goal: str,
    inventory: CanonicalInventory,
) -> str:
    """
    Build the model prompt used to judge which pending objects are worth
    asking the user about for one goal.

    Active inventory is supplied as context so the model can avoid treating
    obviously redundant uncertain objects as automatically important.

    The model must only return decisions for pending inventory IDs.
    """

    cleaned_goal = goal.strip()

    if not cleaned_goal:
        raise ValueError(
            "Goal must contain non-whitespace text."
        )

    active_items, pending_items = (
        _partition_inventory(inventory)
    )

    active_context = [
        _item_context(
            item,
            include_uncertainty=False,
        )
        for item in active_items
    ]

    pending_context = [
        _item_context(
            item,
            include_uncertainty=True,
        )
        for item in pending_items
    ]

    return f"""
You are ZERO's goal-scoped confirmation relevance layer.

ZERO already has a canonical inventory from a walkthrough.

Some inventory items are trusted enough to use automatically.
Other items remain NEEDS_CONFIRMATION and cannot enter physical reasoning
until the user explicitly confirms them.

Your task is NOT to confirm objects.

Your task is only to decide which uncertain objects are worth asking the
user about for the current goal.

Return ONLY valid JSON in exactly this structure:

{{
  "items": [
    {{
      "item_id": "exact pending inventory item id",
      "relevance": "relevant | possibly_relevant | not_relevant",
      "reason": "short grounded reason"
    }}
  ]
}}

OUTPUT ACCOUNTING RULES

- Include EVERY pending inventory item exactly once.
- Include ONLY pending inventory item IDs.
- Copy item_id exactly.
- Never invent an item.
- Never omit a pending item.
- Never output an active inventory item.

RELEVANCE RULES

"relevant":
The uncertain item has a realistic and material chance of helping accomplish
the goal, considering what is already available in active inventory.

"possibly_relevant":
The uncertain item could realistically matter, but usefulness depends on
details that are not established or it is a secondary/alternative resource.

"not_relevant":
The uncertain item is unlikely to materially affect accomplishing this goal,
especially when active inventory already provides what is needed.

Be selective.

Do NOT mark something possibly_relevant merely because an imaginative or
contrived use could exist.

Do NOT ask for confirmation merely because the object is uncertain.

The purpose of this stage is to avoid forcing the user to confirm dozens of
irrelevant observations.

SAFETY / SCOPE RULES

- Model relevance is NOT human confirmation.
- Do not change verification status.
- Do not claim the uncertain object definitely exists.
- Do not generate Object DNA.
- Do not output capabilities or physical-trait schemas.
- Do not construct a step-by-step solution.
- Do not recommend purchases.
- Do not invent hidden object properties.
- Use active inventory only as context for deciding whether pending objects
  materially matter.
- Keep each reason concise.

USER GOAL

{cleaned_goal}

ACTIVE INVENTORY ALREADY ELIGIBLE FOR DOWNSTREAM REASONING

{json.dumps(active_context, indent=2)}

PENDING INVENTORY REQUIRING EXPLICIT USER CONFIRMATION BEFORE USE

{json.dumps(pending_context, indent=2)}
""".strip()


def validate_goal_relevance_response(
    *,
    inventory: CanonicalInventory,
    response: GoalAwareInventoryResponse,
) -> GoalAwareInventoryResponse:
    """
    Deterministically validate exact accounting of model relevance output.

    The schema validates field shapes and relevance enum values.
    This validator additionally guarantees:

    - no invented/non-pending IDs
    - no duplicate relevance decisions
    - no missing pending IDs
    - deterministic canonical ordering

    It does NOT alter inventory verification status.
    """

    _, pending_items = _partition_inventory(
        inventory
    )

    expected_ids = [
        item.id
        for item in pending_items
    ]

    expected_set = set(expected_ids)

    response_by_id = {}

    for relevance_item in response.items:
        item_id = relevance_item.item_id

        if item_id in response_by_id:
            raise ValueError(
                "Goal relevance contains duplicate item ID: "
                f"{item_id}"
            )

        if item_id not in expected_set:
            raise ValueError(
                "Goal relevance contains an item ID that is not "
                "a NEEDS_CONFIRMATION inventory item: "
                f"{item_id}"
            )

        response_by_id[item_id] = relevance_item

    missing_ids = [
        item_id
        for item_id in expected_ids
        if item_id not in response_by_id
    ]

    if missing_ids:
        raise ValueError(
            "Goal relevance is missing NEEDS_CONFIRMATION "
            f"inventory items: {sorted(missing_ids)}"
        )

    ordered_items = [
        response_by_id[item_id]
        for item_id in expected_ids
    ]

    return GoalAwareInventoryResponse(
        items=ordered_items
    )


def parse_goal_relevance_output(
    *,
    inventory: CanonicalInventory,
    raw_output: str,
) -> GoalAwareInventoryResponse:
    """
    Parse model JSON through the existing Pydantic schema, then apply
    deterministic exact-accounting validation.
    """

    payload = load_model_json(
        raw_output
    )

    result = GoalAwareInventoryResponse.model_validate(
        payload
    )

    return validate_goal_relevance_response(
        inventory=inventory,
        response=result,
    )


def generate_goal_relevance(
    *,
    goal: str,
    inventory: CanonicalInventory,
) -> GoalAwareInventoryResponse:
    """
    Generate goal relevance decisions for pending confirmation items.

    If there are no pending items, return an empty validated response without
    creating a client or making a paid model call.
    """

    _, pending_items = _partition_inventory(
        inventory
    )

    if not pending_items:
        return GoalAwareInventoryResponse(
            items=[]
        )

    prompt = build_goal_relevance_prompt(
        goal=goal,
        inventory=inventory,
    )

    client = _create_client()

    response = client.chat.completions.create(
        model=MODEL,
        reasoning_effort="low",

        response_format={
            "type": "json_object"
        },

        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],

        temperature=0,
        max_tokens=6000,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Goal relevance output was truncated because "
            "the output token limit was reached."
        )

    message = choice.message

    if message.refusal:
        raise RuntimeError(
            "Goal relevance model refused the request: "
            f"{message.refusal}"
        )

    raw_output = message.content

    if not raw_output:
        raise RuntimeError(
            "Goal relevance model returned no final content."
        )

    return parse_goal_relevance_output(
        inventory=inventory,
        raw_output=raw_output,
    )