import argparse
import json
from pathlib import Path

from goal_scoped_confirmation import (
    GoalScopedConfirmationSelection,
    select_goal_scoped_confirmation_candidates,
)
from human_confirmation import (
    apply_explicit_user_confirmations,
)
from human_confirmation_state import (
    PersistedHumanConfirmationState,
    merge_confirmation_state,
    validate_confirmation_state,
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


CONFIRMATION_STATE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-human-confirmation-state.json"
)


def load_existing_confirmation_state(
    *,
    inventory,
    fingerprint: str,
) -> PersistedHumanConfirmationState | None:
    """
    Load persisted explicit user confirmations for this exact inventory.

    If the state file exists but is malformed or belongs to another
    canonical inventory fingerprint, fail rather than silently ignoring it.
    """

    if not CONFIRMATION_STATE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CONFIRMATION_STATE_PATH.read_text(
                encoding="utf-8"
            )
        )

        state = (
            PersistedHumanConfirmationState.model_validate(
                payload
            )
        )

        return validate_confirmation_state(
            inventory=inventory,
            inventory_sha256=fingerprint,
            state=state,
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing human confirmation state is invalid. "
            "Refusing to ignore or overwrite it until inspected: "
            f"{CONFIRMATION_STATE_PATH}"
        ) from exc


def save_confirmation_state(
    state: PersistedHumanConfirmationState,
) -> None:
    """
    Persist confirmation state atomically under sample_data/private/.
    """

    CONFIRMATION_STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = CONFIRMATION_STATE_PATH.with_name(
        CONFIRMATION_STATE_PATH.name + ".tmp"
    )

    temporary_path.write_text(
        state.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        CONFIRMATION_STATE_PATH
    )


def remove_already_persisted_candidates(
    *,
    selection: GoalScopedConfirmationSelection,
    state: PersistedHumanConfirmationState | None,
) -> GoalScopedConfirmationSelection:
    """
    Do not ask the user again about candidates whose explicit confirmation
    has already been persisted.

    Deferred and not-relevant groups remain unchanged.
    """

    if state is None:
        return selection

    persisted_ids = set(
        state.confirmed_item_ids
    )

    remaining_candidates = [
        candidate
        for candidate in selection.candidates
        if candidate.item.id not in persisted_ids
    ]

    return GoalScopedConfirmationSelection(
        candidates=remaining_candidates,
        deferred_possible_item_ids=(
            list(
                selection.deferred_possible_item_ids
            )
        ),
        not_relevant_pending_item_ids=(
            list(
                selection.not_relevant_pending_item_ids
            )
        ),
    )


def load_real_confirmation_context():
    """
    Load:
    - immutable canonical walkthrough inventory
    - cached validated goal relevance
    - deterministic goal-scoped confirmation selection
    - persisted human confirmation state

    This function NEVER generates relevance output and therefore cannot make
    a paid model call.
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

    full_selection = (
        select_goal_scoped_confirmation_candidates(
            inventory=inventory,
            relevance=relevance,
        )
    )

    existing_state = (
        load_existing_confirmation_state(
            inventory=inventory,
            fingerprint=fingerprint,
        )
    )

    active_selection = (
        remove_already_persisted_candidates(
            selection=full_selection,
            state=existing_state,
        )
    )

    return (
        inventory,
        active_selection,
        fingerprint,
        existing_state,
    )


def print_confirmation_preview(
    *,
    selection,
    existing_state,
) -> None:
    print()
    print("=" * 72)
    print("IMMEDIATE HUMAN CONFIRMATION QUESTIONS")
    print("=" * 72)

    persisted_count = (
        0
        if existing_state is None
        else len(
            existing_state.confirmed_item_ids
        )
    )

    print(
        f"Already persisted confirmations: "
        f"{persisted_count}"
    )

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
            "   current canonical status: "
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
        f"Confirmed items this run: "
        f"{len(result.confirmed_item_ids)}"
    )

    print(
        f"Unconfirmed immediate candidates: "
        f"{len(result.unconfirmed_candidate_item_ids)}"
    )

    print()

    if result.confirmed_item_ids:
        print(
            "Promoted to USER_CONFIRMED in reconstructed session inventory:"
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


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--confirm-item-id",
        action="append",
        default=[],
        help=(
            "Explicitly confirm one currently presented candidate ID. "
            "May be supplied multiple times."
        ),
    )

    parser.add_argument(
        "--persist",
        action="store_true",
        help=(
            "Persist successful explicit confirmations as a private "
            "confirmation-state delta."
        ),
    )

    args = parser.parse_args()

    if (
        args.persist
        and not args.confirm_item_id
    ):
        parser.error(
            "--persist requires at least one "
            "--confirm-item-id."
        )

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
        existing_state,
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

    if existing_state is None:
        print(
            "Persisted human confirmation state: none"
        )

    else:
        print(
            "Persisted human confirmation state: valid"
        )

        print(
            "Persisted confirmed item IDs: "
            f"{existing_state.confirmed_item_ids}"
        )

    print_confirmation_preview(
        selection=selection,
        existing_state=existing_state,
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
            "No inventory status or confirmation state was changed."
        )

        return

    if existing_state is not None:
        already_persisted_ids = set(
            existing_state.confirmed_item_ids
        )

        duplicate_persisted_requests = [
            item_id
            for item_id in args.confirm_item_id
            if item_id in already_persisted_ids
        ]

        if duplicate_persisted_requests:
            raise ValueError(
                "Explicit confirmation request contains item IDs "
                "that are already persisted: "
                f"{sorted(duplicate_persisted_requests)}"
            )

    result = apply_explicit_user_confirmations(
        inventory=inventory,
        selection=selection,
        confirmed_item_ids=args.confirm_item_id,
    )

    print_confirmation_result(
        original_inventory=inventory,
        result=result,
    )

    if not args.persist:
        print()
        print(
            "Persistence was not requested."
        )

        print(
            "Updated inventory exists only in memory in this run."
        )

        return

    updated_state = merge_confirmation_state(
        inventory=inventory,
        inventory_sha256=fingerprint,
        existing_state=existing_state,
        newly_confirmed_item_ids=(
            result.confirmed_item_ids
        ),
    )

    save_confirmation_state(
        updated_state
    )

    print()
    print("=" * 72)
    print("CONFIRMATION STATE PERSISTED")
    print("=" * 72)

    print()

    print(
        f"Persisted confirmed items: "
        f"{len(updated_state.confirmed_item_ids)}"
    )

    for item_id in (
        updated_state.confirmed_item_ids
    ):
        print(
            f"- {item_id}"
        )

    print()

    print(
        "Saved private confirmation state:"
    )

    print(
        CONFIRMATION_STATE_PATH.resolve()
    )

    print()

    print(
        "Canonical walkthrough inventory was NOT overwritten."
    )


if __name__ == "__main__":
    main()