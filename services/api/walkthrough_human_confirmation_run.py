import argparse

from goal_scoped_confirmation import (
    select_goal_scoped_confirmation_candidates,
)
from human_confirmation import (
    apply_explicit_user_confirmations,
)
from schemas import (
    VerificationStatus,
)
from walkthrough_goal_relevance_run import (
    GOAL,
    inventory_fingerprint,
    load_inventory,
    load_matching_aggregate_cache,
)


def load_real_confirmation_context():
    """
    Load the real walkthrough inventory and its already-validated cached
    goal-relevance result.

    This function NEVER generates new relevance output and therefore cannot
    make a paid model call.
    """

    inventory = load_inventory()

    fingerprint = inventory_fingerprint(
        inventory
    )

    relevance = load_matching_aggregate_cache(
        inventory=inventory,
        fingerprint=fingerprint,
    )

    if relevance is None:
        raise RuntimeError(
            "No matching complete goal-relevance cache was found. "
            "Refusing to generate new model output from the human-"
            "confirmation runner."
        )

    selection = (
        select_goal_scoped_confirmation_candidates(
            inventory=inventory,
            relevance=relevance,
        )
    )

    return (
        inventory,
        selection,
        fingerprint,
    )


def print_confirmation_preview(
    *,
    selection,
) -> None:
    print()
    print("=" * 72)
    print("IMMEDIATE HUMAN CONFIRMATION QUESTIONS")
    print("=" * 72)

    print(
        f"Ask-now candidates: "
        f"{len(selection.candidates)}"
    )

    print(
        "Deferred possibly relevant items: "
        f"{len(selection.deferred_possible_item_ids)}"
    )

    print(
        "Not relevant for this goal: "
        f"{len(selection.not_relevant_pending_item_ids)}"
    )

    print()

    if not selection.candidates:
        print(
            "No immediate human confirmation is required."
        )

        return

    for index, candidate in enumerate(
        selection.candidates,
        start=1,
    ):
        print(
            f"{index}. item_id: {candidate.item.id}"
        )

        print(
            f"   name: {candidate.item.name}"
        )

        print(
            f"   location: {candidate.item.location_hint}"
        )

        print(
            f"   description: {candidate.item.description}"
        )

        print(
            "   current status: "
            f"{candidate.item.verification_status.value}"
        )

        print(
            f"   uncertainty: "
            f"{candidate.item.uncertainty_reason}"
        )

        print(
            f"   why ZERO is asking: "
            f"{candidate.relevance_reason}"
        )

        print()

        print(
            "   USER QUESTION:"
        )

        print(
            f'   Is "{candidate.item.name}" really present at '
            f'"{candidate.item.location_hint}"?'
        )

        print()


def print_confirmation_result(
    *,
    original_inventory,
    result,
) -> None:
    print()
    print("=" * 72)
    print("EXPLICIT HUMAN CONFIRMATION RESULT")
    print("=" * 72)

    print(
        f"Confirmed items: "
        f"{len(result.confirmed_item_ids)}"
    )

    print(
        f"Unconfirmed immediate candidates: "
        f"{len(result.unconfirmed_candidate_item_ids)}"
    )

    print()

    if result.confirmed_item_ids:
        print(
            "Promoted to USER_CONFIRMED:"
        )

        for item_id in result.confirmed_item_ids:
            print(
                f"- {item_id}"
            )

    if result.unconfirmed_candidate_item_ids:
        print()

        print(
            "Still NEEDS_CONFIRMATION:"
        )

        for item_id in (
            result.unconfirmed_candidate_item_ids
        ):
            print(
                f"- {item_id}"
            )

    original_by_id = {
        item.id: item
        for item in original_inventory.items
    }

    updated_by_id = {
        item.id: item
        for item in result.inventory.items
    }

    for item_id in result.confirmed_item_ids:
        original_item = original_by_id[
            item_id
        ]

        updated_item = updated_by_id[
            item_id
        ]

        if (
            original_item.verification_status
            != VerificationStatus.NEEDS_CONFIRMATION
        ):
            raise RuntimeError(
                "Original confirmed item was unexpectedly not "
                f"NEEDS_CONFIRMATION: {item_id}"
            )

        if (
            updated_item.verification_status
            != VerificationStatus.USER_CONFIRMED
        ):
            raise RuntimeError(
                "Explicit confirmation failed to promote item: "
                f"{item_id}"
            )

    print()

    print(
        "Original CanonicalInventory remained unchanged."
    )

    print(
        "Updated inventory exists only in memory in this test run."
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--confirm-item-id",
        action="append",
        default=[],
        help=(
            "Explicitly confirm one immediate candidate ID. "
            "May be supplied multiple times."
        ),
    )

    args = parser.parse_args()

    print("=" * 72)
    print("ZERO REAL WALKTHROUGH HUMAN CONFIRMATION")
    print("=" * 72)

    print()
    print(
        f"Goal: {GOAL}"
    )

    (
        inventory,
        selection,
        fingerprint,
    ) = load_real_confirmation_context()

    print()
    print(
        "Valid matching aggregate relevance cache found."
    )

    print(
        "Nemotron calls: 0"
    )

    print(
        f"Inventory SHA-256: {fingerprint}"
    )

    print_confirmation_preview(
        selection=selection,
    )

    if not args.confirm_item_id:
        print("=" * 72)
        print("PREVIEW COMPLETE")
        print("=" * 72)

        print()
        print(
            "No explicit user confirmation was supplied."
        )

        print(
            "No inventory status was changed."
        )

        return

    result = apply_explicit_user_confirmations(
        inventory=inventory,
        selection=selection,
        confirmed_item_ids=args.confirm_item_id,
    )

    print_confirmation_result(
        original_inventory=inventory,
        result=result,
    )


if __name__ == "__main__":
    main()