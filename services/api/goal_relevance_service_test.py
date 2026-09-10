from pydantic import ValidationError

import goal_relevance_service
from goal_relevance_service import (
    build_goal_relevance_prompt,
    generate_goal_relevance,
    parse_goal_relevance_output,
    validate_goal_relevance_response,
)
from schemas import (
    CanonicalInventory,
    GoalAwareInventoryItem,
    GoalAwareInventoryResponse,
    InventoryItem,
    RelevanceLabel,
    VerificationStatus,
)


def make_item(
    item_id: str,
    *,
    status: VerificationStatus,
    confidence: float = 0.85,
) -> InventoryItem:
    return InventoryItem(
        id=item_id,
        name=item_id.replace("_", " "),
        description=f"Test object {item_id}.",
        location_hint="test location",
        source_confidence=confidence,
        verification_status=status,
        uncertainty_reason=(
            "Test uncertainty."
            if status == VerificationStatus.NEEDS_CONFIRMATION
            else None
        ),
    )


def make_relevance(
    item_id: str,
    label: RelevanceLabel,
) -> GoalAwareInventoryItem:
    return GoalAwareInventoryItem(
        item_id=item_id,
        relevance=label,
        reason=f"Reason for {item_id}.",
    )


def test_prompt_separates_active_and_pending_inventory() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "desk_01",
                status=VerificationStatus.AUTO_ACCEPTED,
                confidence=0.95,
            ),
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "lamp_01",
                status=VerificationStatus.USER_CONFIRMED,
                confidence=0.70,
            ),
        ]
    )

    prompt = build_goal_relevance_prompt(
        goal="Create a product photography setup",
        inventory=inventory,
    )

    assert "desk_01" in prompt
    assert "blanket_01" in prompt
    assert "lamp_01" in prompt

    assert (
        '"source_confidence": 0.85'
        in prompt
    )

    assert (
        "Your task is NOT to confirm objects."
        in prompt
    )

    assert (
        "Include EVERY pending inventory item exactly once."
        in prompt
    )

    print(
        "PROMPT INVENTORY PARTITION TEST: passed"
    )


def test_valid_response_is_reordered_to_canonical_order() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "power_strip_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "desk_01",
                status=VerificationStatus.AUTO_ACCEPTED,
            ),
        ]
    )

    response = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "power_strip_01",
                RelevanceLabel.POSSIBLY_RELEVANT,
            ),
            make_relevance(
                "blanket_01",
                RelevanceLabel.RELEVANT,
            ),
        ]
    )

    result = validate_goal_relevance_response(
        inventory=inventory,
        response=response,
    )

    result_ids = [
        item.item_id
        for item in result.items
    ]

    assert result_ids == [
        "blanket_01",
        "power_strip_01",
    ]

    print(
        "CANONICAL RESPONSE ORDER TEST: passed"
    )


def test_rejects_active_inventory_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "desk_01",
                status=VerificationStatus.AUTO_ACCEPTED,
            ),
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    response = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "desk_01",
                RelevanceLabel.RELEVANT,
            ),
            make_relevance(
                "blanket_01",
                RelevanceLabel.RELEVANT,
            ),
        ]
    )

    try:
        validate_goal_relevance_response(
            inventory=inventory,
            response=response,
        )

    except ValueError as exc:
        assert (
            "not a NEEDS_CONFIRMATION inventory item"
            in str(exc)
        )

        print(
            "ACTIVE ITEM OUTPUT REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Active inventory ID was not rejected."
    )


def test_rejects_invented_item_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            )
        ]
    )

    response = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "invented_item_99",
                RelevanceLabel.RELEVANT,
            )
        ]
    )

    try:
        validate_goal_relevance_response(
            inventory=inventory,
            response=response,
        )

    except ValueError as exc:
        assert (
            "not a NEEDS_CONFIRMATION inventory item"
            in str(exc)
        )

        print(
            "INVENTED ITEM OUTPUT REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Invented item ID was not rejected."
    )


def test_rejects_duplicate_model_item_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            )
        ]
    )

    response = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "blanket_01",
                RelevanceLabel.RELEVANT,
            ),
            make_relevance(
                "blanket_01",
                RelevanceLabel.POSSIBLY_RELEVANT,
            ),
        ]
    )

    try:
        validate_goal_relevance_response(
            inventory=inventory,
            response=response,
        )

    except ValueError as exc:
        assert (
            "duplicate item ID"
            in str(exc)
        )

        print(
            "DUPLICATE MODEL ID TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate model item ID was not rejected."
    )


def test_rejects_missing_pending_item() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "power_strip_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    response = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "blanket_01",
                RelevanceLabel.RELEVANT,
            )
        ]
    )

    try:
        validate_goal_relevance_response(
            inventory=inventory,
            response=response,
        )

    except ValueError as exc:
        assert "power_strip_01" in str(exc)

        print(
            "MISSING PENDING ITEM TEST: passed"
        )

        return

    raise AssertionError(
        "Missing pending item was not rejected."
    )


def test_rejects_duplicate_canonical_inventory_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    response = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "blanket_01",
                RelevanceLabel.RELEVANT,
            )
        ]
    )

    try:
        validate_goal_relevance_response(
            inventory=inventory,
            response=response,
        )

    except ValueError as exc:
        assert (
            "Canonical inventory contains duplicate item ID"
            in str(exc)
        )

        print(
            "DUPLICATE CANONICAL ID TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate canonical inventory ID was not rejected."
    )


def test_parse_uses_schema_validation() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            )
        ]
    )

    raw_output = """
{
  "items": [
    {
      "item_id": "blanket_01",
      "relevance": "definitely_useful",
      "reason": "Invalid enum value."
    }
  ]
}
""".strip()

    try:
        parse_goal_relevance_output(
            inventory=inventory,
            raw_output=raw_output,
        )

    except ValidationError:
        print(
            "PYDANTIC RELEVANCE ENUM TEST: passed"
        )

        return

    raise AssertionError(
        "Invalid relevance enum bypassed schema validation."
    )


def test_no_pending_items_skips_paid_client() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "desk_01",
                status=VerificationStatus.AUTO_ACCEPTED,
                confidence=0.95,
            ),
            make_item(
                "lamp_01",
                status=VerificationStatus.USER_CONFIRMED,
                confidence=0.80,
            ),
        ]
    )

    original_create_client = (
        goal_relevance_service._create_client
    )

    def fail_if_called():
        raise AssertionError(
            "Paid client should not be created when "
            "there are no pending items."
        )

    goal_relevance_service._create_client = (
        fail_if_called
    )

    try:
        result = generate_goal_relevance(
            goal="Create a product photography setup",
            inventory=inventory,
        )

    finally:
        goal_relevance_service._create_client = (
            original_create_client
        )

    assert result.items == []

    print(
        "ZERO-PENDING NO-API-CALL TEST: passed"
    )


def test_empty_goal_is_rejected_before_prompt() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            )
        ]
    )

    try:
        build_goal_relevance_prompt(
            goal="   ",
            inventory=inventory,
        )

    except ValueError as exc:
        assert (
            "non-whitespace"
            in str(exc)
        )

        print(
            "EMPTY GOAL REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Whitespace-only goal was not rejected."
    )


def main() -> None:
    test_prompt_separates_active_and_pending_inventory()

    test_valid_response_is_reordered_to_canonical_order()

    test_rejects_active_inventory_id()

    test_rejects_invented_item_id()

    test_rejects_duplicate_model_item_id()

    test_rejects_missing_pending_item()

    test_rejects_duplicate_canonical_inventory_id()

    test_parse_uses_schema_validation()

    test_no_pending_items_skips_paid_client()

    test_empty_goal_is_rejected_before_prompt()

    print()

    print(
        "GOAL RELEVANCE SERVICE TEST: passed"
    )


if __name__ == "__main__":
    main()