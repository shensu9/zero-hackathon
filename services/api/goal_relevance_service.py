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

# Bound semantic relevance work so one oversized model response cannot
# consume a paid call and then truncate before validation/caching.
MAX_PENDING_ITEMS_PER_CALL = 15


def _create_client() -> OpenAI:
    """
    Create the paid reasoning client lazily.

    Keeping client creation out of module import allows deterministic tests
    to run without making or requiring a paid model call.
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


def _resolve_pending_items(
    *,
    inventory: CanonicalInventory,
    pending_item_ids: list[str] | None,
) -> list[InventoryItem]:
    """
    Resolve a requested subset of pending canonical inventory.

    If pending_item_ids is None, all NEEDS_CONFIRMATION items are selected.

    Returned items always follow canonical inventory order, regardless of
    the order supplied by the caller.
    """

    _, pending_items = _partition_inventory(
        inventory
    )

    if pending_item_ids is None:
        return pending_items

    seen_requested_ids: set[str] = set()

    for item_id in pending_item_ids:
        if item_id in seen_requested_ids:
            raise ValueError(
                "Requested pending item IDs contain duplicate ID: "
                f"{item_id}"
            )

        seen_requested_ids.add(item_id)

    pending_ids = {
        item.id
        for item in pending_items
    }

    invalid_ids = sorted(
        item_id
        for item_id in seen_requested_ids
        if item_id not in pending_ids
    )

    if invalid_ids:
        raise ValueError(
            "Requested goal-relevance item IDs are not "
            "NEEDS_CONFIRMATION canonical inventory items: "
            f"{invalid_ids}"
        )

    requested_set = set(
        pending_item_ids
    )

    return [
        item
        for item in pending_items
        if item.id in requested_set
    ]


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
    pending_item_ids: list[str] | None = None,
) -> str:
    """
    Build a relevance prompt for a bounded subset of uncertain objects.

    Active inventory is supplied as context.

    The model must output decisions only for the selected pending inventory
    items.

    If pending_item_ids is None, all pending items are included. This is
    useful for deterministic prompt inspection, but paid generation is
    separately bounded by MAX_PENDING_ITEMS_PER_CALL.
    """

    cleaned_goal = goal.strip()

    if not cleaned_goal:
        raise ValueError(
            "Goal must contain non-whitespace text."
        )

    active_items, _ = _partition_inventory(
        inventory
    )

    selected_pending_items = (
        _resolve_pending_items(
            inventory=inventory,
            pending_item_ids=pending_item_ids,
        )
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
        for item in selected_pending_items
    ]

    return f"""
You are ZERO's goal-scoped confirmation relevance layer.

ZERO already has a canonical inventory from a walkthrough.

Some inventory items are trusted enough to use automatically.
Other items remain NEEDS_CONFIRMATION and cannot enter physical reasoning
until the user explicitly confirms them.

Your task is NOT to confirm objects.

Your task is only to decide which of the PROVIDED uncertain objects are
worth asking the user about for the current goal.

Return ONLY valid JSON in exactly this structure:

{{
  "items": [
    {{
      "item_id": "exact provided pending inventory item id",
      "relevance": "relevant | possibly_relevant | not_relevant",
      "reason": "short grounded reason"
    }}
  ]
}}

OUTPUT ACCOUNTING RULES

- Include EVERY provided pending inventory item exactly once.
- Include ONLY the provided pending inventory item IDs.
- Copy item_id exactly.
- Never invent an item.
- Never omit a provided pending item.
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
- Use active inventory only as context for deciding whether provided pending
  objects materially matter.
- Keep each reason concise.

USER GOAL

{cleaned_goal}

ACTIVE INVENTORY ALREADY ELIGIBLE FOR DOWNSTREAM REASONING

{json.dumps(active_context, indent=2)}

PROVIDED PENDING INVENTORY ITEMS TO CLASSIFY

{json.dumps(pending_context, indent=2)}
""".strip()


def validate_goal_relevance_response(
    *,
    inventory: CanonicalInventory,
    response: GoalAwareInventoryResponse,
    pending_item_ids: list[str] | None = None,
) -> GoalAwareInventoryResponse:
    """
    Deterministically validate exact accounting for one relevance scope.

    The schema validates field shapes and relevance enum values.

    This validator additionally guarantees:
    - no invented/non-pending IDs
    - no output for pending items outside this requested scope
    - no duplicate relevance decisions
    - no missing requested pending IDs
    - deterministic canonical ordering

    It does NOT alter inventory verification status.
    """

    expected_items = _resolve_pending_items(
        inventory=inventory,
        pending_item_ids=pending_item_ids,
    )

    expected_ids = [
        item.id
        for item in expected_items
    ]

    expected_set = set(
        expected_ids
    )

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
                "part of the requested NEEDS_CONFIRMATION scope: "
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
            "Goal relevance is missing requested "
            "NEEDS_CONFIRMATION inventory items: "
            f"{sorted(missing_ids)}"
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
    pending_item_ids: list[str] | None = None,
) -> GoalAwareInventoryResponse:
    """
    Parse model JSON through the existing Pydantic schema, then apply
    deterministic exact-accounting validation for the requested scope.
    """

    payload = load_model_json(
        raw_output
    )

    result = (
        GoalAwareInventoryResponse.model_validate(
            payload
        )
    )

    return validate_goal_relevance_response(
        inventory=inventory,
        response=result,
        pending_item_ids=pending_item_ids,
    )


def generate_goal_relevance_chunk(
    *,
    goal: str,
    inventory: CanonicalInventory,
    pending_item_ids: list[str],
) -> GoalAwareInventoryResponse:
    """
    Make ONE bounded paid relevance call.

    This function is deliberately limited to
    MAX_PENDING_ITEMS_PER_CALL uncertain objects.

    Chunk orchestration and per-chunk caching belong outside this function.
    """

    selected_pending_items = (
        _resolve_pending_items(
            inventory=inventory,
            pending_item_ids=pending_item_ids,
        )
    )

    if not selected_pending_items:
        return GoalAwareInventoryResponse(
            items=[]
        )

    if (
        len(selected_pending_items)
        > MAX_PENDING_ITEMS_PER_CALL
    ):
        raise ValueError(
            "Goal relevance chunk contains "
            f"{len(selected_pending_items)} pending items, "
            "exceeding the per-call limit of "
            f"{MAX_PENDING_ITEMS_PER_CALL}."
        )

    selected_ids = [
        item.id
        for item in selected_pending_items
    ]

    prompt = build_goal_relevance_prompt(
        goal=goal,
        inventory=inventory,
        pending_item_ids=selected_ids,
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

        max_tokens=5000,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Goal relevance chunk output was truncated "
            "because the output token limit was reached."
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
        pending_item_ids=selected_ids,
    )


def generate_goal_relevance(
    *,
    goal: str,
    inventory: CanonicalInventory,
) -> GoalAwareInventoryResponse:
    """
    Convenience boundary for inventories small enough for one bounded call.

    Large pending inventories deliberately fail BEFORE client creation.

    The walkthrough runner must orchestrate large inventories as cached
    bounded chunks instead of silently issuing another oversized paid call.
    """

    _, pending_items = _partition_inventory(
        inventory
    )

    if not pending_items:
        return GoalAwareInventoryResponse(
            items=[]
        )

    if (
        len(pending_items)
        > MAX_PENDING_ITEMS_PER_CALL
    ):
        raise RuntimeError(
            "Goal relevance requires bounded chunk orchestration. "
            f"Pending items: {len(pending_items)}; "
            "maximum per paid call: "
            f"{MAX_PENDING_ITEMS_PER_CALL}."
        )

    return generate_goal_relevance_chunk(
        goal=goal,
        inventory=inventory,
        pending_item_ids=[
            item.id
            for item in pending_items
        ],
    )