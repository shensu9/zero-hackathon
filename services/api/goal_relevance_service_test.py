from pydantic import ValidationError

import goal_relevance_service
from goal_relevance_service import (
    MAX_PENDING_ITEMS_PER_CALL,
    build_goal_relevance_prompt,
    generate_goal_relevance,
    generate_goal_relevance_chunk,
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


def test_prompt_separates_active_and_selected_pending() -> None:
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
                "power_strip_01",
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
        pending_item_ids=[
            "power_strip_01",
        ],
    )

    assert "desk_01" in prompt
    assert "lamp_01" in prompt
    assert "power_strip_01" in prompt

    # The unselected pending item must not enter this chunk.
    assert "blanket_01" not in prompt

    assert (
        '"source_confidence": 0.85'
        in prompt
    )

    assert (
        "Your task is NOT to confirm objects."
        in prompt
    )

    assert (
        "Include EVERY provided pending inventory item exactly once."
        in prompt
    )

    print(
        "CHUNK PROMPT PARTITION TEST: passed"
    )


def test_requested_scope_uses_canonical_order() -> None:
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
        pending_item_ids=[
            "power_strip_01",
            "blanket_01",
        ],
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
        "CANONICAL CHUNK ORDER TEST: passed"
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
        ]
    )

    try:
        validate_goal_relevance_response(
            inventory=inventory,
            response=response,
            pending_item_ids=[
                "blanket_01",
            ],
        )

    except ValueError as exc:
        assert (
            "requested NEEDS_CONFIRMATION scope"
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
            pending_item_ids=[
                "blanket_01",
            ],
        )

    except ValueError as exc:
        assert (
            "requested NEEDS_CONFIRMATION scope"
            in str(exc)
        )

        print(
            "INVENTED ITEM OUTPUT REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Invented item ID was not rejected."
    )


def test_rejects_output_outside_requested_chunk() -> None:
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
            ),
            make_relevance(
                "power_strip_01",
                RelevanceLabel.RELEVANT,
            ),
        ]
    )

    try:
        validate_goal_relevance_response(
            inventory=inventory,
            response=response,
            pending_item_ids=[
                "blanket_01",
            ],
        )

    except ValueError as exc:
        assert "power_strip_01" in str(exc)

        print(
            "OUT-OF-CHUNK OUTPUT REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Model output outside the requested chunk was not rejected."
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
            pending_item_ids=[
                "blanket_01",
            ],
        )

    except ValueError as exc:
        assert "duplicate item ID" in str(exc)

        print(
            "DUPLICATE MODEL ID TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate model item ID was not rejected."
    )


def test_rejects_missing_requested_pending_item() -> None:
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
            pending_item_ids=[
                "blanket_01",
                "power_strip_01",
            ],
        )

    except ValueError as exc:
        assert "power_strip_01" in str(exc)

        print(
            "MISSING CHUNK ITEM TEST: passed"
        )

        return

    raise AssertionError(
        "Missing requested pending item was not rejected."
    )


def test_rejects_invalid_requested_pending_id() -> None:
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

    try:
        build_goal_relevance_prompt(
            goal="Create a product photography setup",
            inventory=inventory,
            pending_item_ids=[
                "desk_01",
            ],
        )

    except ValueError as exc:
        assert (
            "not NEEDS_CONFIRMATION canonical inventory items"
            in str(exc)
        )

        print(
            "INVALID REQUESTED CHUNK ID TEST: passed"
        )

        return

    raise AssertionError(
        "Active item was accepted as requested pending scope."
    )


def test_rejects_duplicate_requested_pending_id() -> None:
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
            goal="Create a product photography setup",
            inventory=inventory,
            pending_item_ids=[
                "blanket_01",
                "blanket_01",
            ],
        )

    except ValueError as exc:
        assert (
            "duplicate ID"
            in str(exc)
        )

        print(
            "DUPLICATE REQUESTED CHUNK ID TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate requested pending ID was not rejected."
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
            pending_item_ids=[
                "blanket_01",
            ],
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


def test_oversized_inventory_stops_before_paid_client() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                f"pending_{index:02d}",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            )
            for index in range(
                MAX_PENDING_ITEMS_PER_CALL + 1
            )
        ]
    )

    original_create_client = (
        goal_relevance_service._create_client
    )

    def fail_if_called():
        raise AssertionError(
            "Paid client must not be created for an "
            "oversized unchunked inventory."
        )

    goal_relevance_service._create_client = (
        fail_if_called
    )

    try:
        try:
            generate_goal_relevance(
                goal="Create a product photography setup",
                inventory=inventory,
            )

        except RuntimeError as exc:
            assert (
                "bounded chunk orchestration"
                in str(exc)
            )

        else:
            raise AssertionError(
                "Oversized unchunked inventory was not rejected."
            )

    finally:
        goal_relevance_service._create_client = (
            original_create_client
        )

    print(
        "OVERSIZED INVENTORY NO-API-CALL TEST: passed"
    )


def test_oversized_chunk_stops_before_paid_client() -> None:
    pending_items = [
        make_item(
            f"pending_{index:02d}",
            status=VerificationStatus.NEEDS_CONFIRMATION,
        )
        for index in range(
            MAX_PENDING_ITEMS_PER_CALL + 1
        )
    ]

    inventory = CanonicalInventory(
        items=pending_items
    )

    original_create_client = (
        goal_relevance_service._create_client
    )

    def fail_if_called():
        raise AssertionError(
            "Paid client must not be created for an "
            "oversized relevance chunk."
        )

    goal_relevance_service._create_client = (
        fail_if_called
    )

    try:
        try:
            generate_goal_relevance_chunk(
                goal="Create a product photography setup",
                inventory=inventory,
                pending_item_ids=[
                    item.id
                    for item in pending_items
                ],
            )

        except ValueError as exc:
            assert (
                "exceeding the per-call limit"
                in str(exc)
            )

        else:
            raise AssertionError(
                "Oversized relevance chunk was not rejected."
            )

    finally:
        goal_relevance_service._create_client = (
            original_create_client
        )

    print(
        "OVERSIZED CHUNK NO-API-CALL TEST: passed"
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
        assert "non-whitespace" in str(exc)

        print(
            "EMPTY GOAL REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Whitespace-only goal was not rejected."
    )


def main() -> None:
    test_prompt_separates_active_and_selected_pending()

    test_requested_scope_uses_canonical_order()

    test_rejects_active_inventory_id()

    test_rejects_invented_item_id()

    test_rejects_output_outside_requested_chunk()

    test_rejects_duplicate_model_item_id()

    test_rejects_missing_requested_pending_item()

    test_rejects_invalid_requested_pending_id()

    test_rejects_duplicate_requested_pending_id()

    test_rejects_duplicate_canonical_inventory_id()

    test_parse_uses_schema_validation()

    test_no_pending_items_skips_paid_client()

    test_oversized_inventory_stops_before_paid_client()

    test_oversized_chunk_stops_before_paid_client()

    test_empty_goal_is_rejected_before_prompt()

    print()

    print(
        "GOAL RELEVANCE CHUNKED SERVICE TEST: passed"
    )


if __name__ == "__main__":
    main()