from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from goal_scoped_confirmation import (
    GoalScopedConfirmationSelection,
    select_goal_scoped_confirmation_candidates,
)
from human_confirmation import (
    apply_explicit_user_confirmations,
)
from human_confirmation_state import (
    HumanItemCorrection,
    PersistedHumanConfirmationState,
    apply_confirmation_state,
    merge_confirmation_state,
    validate_confirmation_state,
)
from schemas import (
    VerificationStatus,
)
import walkthrough_goal_relevance_run as goal_relevance_run


DEFAULT_WALKTHROUGH_ID = "walkthrough-01"
DEFAULT_GOAL_KEY = "product-photography"
DEFAULT_GOAL = (
    "Create a $0 product photography setup at home using only "
    "what I already have, without permanent modifications."
)

SCOPE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
)

REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

PRIVATE_DIR = (
    REPO_ROOT
    / "sample_data"
    / "private"
)

CONFIRMATION_STATE_PATH = (
    PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-human-confirmation-state.json"
    )
)


def validate_scope_component(
    value: str,
    *,
    label: str,
) -> str:
    if not SCOPE_PATTERN.fullmatch(
        value
    ):
        raise ValueError(
            f"{label} may contain only letters, "
            "numbers, hyphens, and underscores"
        )

    return value


def configure_scope(
    *,
    walkthrough_id: str,
    goal_key: str,
    goal: str,
) -> None:
    global CONFIRMATION_STATE_PATH

    walkthrough_id = (
        validate_scope_component(
            walkthrough_id,
            label="walkthrough id",
        )
    )

    goal_key = (
        validate_scope_component(
            goal_key,
            label="goal key",
        )
    )

    goal_relevance_run.configure_scope(
        walkthrough_id=walkthrough_id,
        goal_key=goal_key,
        goal=goal,
    )

    CONFIRMATION_STATE_PATH = (
        PRIVATE_DIR
        / (
            f"{walkthrough_id}"
            "-human-confirmation-state.json"
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or persist explicit human evidence "
            "for a namespaced ZERO walkthrough."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=DEFAULT_WALKTHROUGH_ID,
        help=(
            "Artifact namespace such as walkthrough-02. "
            "Defaults to walkthrough-01."
        ),
    )

    parser.add_argument(
        "--goal-key",
        default=DEFAULT_GOAL_KEY,
        help=(
            "Goal cache namespace such as temporary-curtain."
        ),
    )

    parser.add_argument(
        "--goal",
        default=DEFAULT_GOAL,
        help=(
            "Exact goal text used by the matching "
            "goal-relevance cache."
        ),
    )

    parser.add_argument(
        "--confirm-item-id",
        action="append",
        default=[],
        help=(
            "Explicitly confirm one currently presented "
            "candidate ID. May be supplied multiple times."
        ),
    )

    parser.add_argument(
        "--correction-json",
        action="append",
        default=[],
        help=(
            "JSON object describing one HumanItemCorrection. "
            "May be supplied multiple times."
        ),
    )

    parser.add_argument(
        "--persist",
        action="store_true",
        help=(
            "Persist successful explicit confirmations "
            "and/or identity corrections."
        ),
    )

    return parser.parse_args()


def parse_item_corrections(
    raw_values: list[str],
) -> list[
    HumanItemCorrection
]:
    corrections: list[
        HumanItemCorrection
    ] = []

    for index, raw_value in enumerate(
        raw_values,
        start=1,
    ):
        try:
            payload = json.loads(
                raw_value
            )

        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid --correction-json value "
                f"#{index}: {exc}"
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "--correction-json must decode to "
                "a JSON object."
            )

        try:
            correction = (
                HumanItemCorrection
                .model_validate(
                    payload
                )
            )

        except Exception as exc:
            raise ValueError(
                "Invalid human item correction "
                f"#{index}: {exc}"
            ) from exc

        corrections.append(
            correction
        )

    return corrections


def load_existing_confirmation_state(
    *,
    inventory,
    fingerprint: str,
) -> PersistedHumanConfirmationState | None:
    """
    Load persisted explicit human evidence for this exact inventory.

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
            PersistedHumanConfirmationState
            .model_validate(
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
    Persist human-evidence state atomically under sample_data/private/.
    """

    CONFIRMATION_STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        CONFIRMATION_STATE_PATH
        .with_name(
            CONFIRMATION_STATE_PATH.name
            + ".tmp"
        )
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
    Do not ask again about candidates whose explicit presence confirmation
    has already been persisted.

    Corrected-but-unconfirmed candidates remain eligible for questioning.
    """

    if state is None:
        return selection

    persisted_ids = set(
        state.confirmed_item_ids
    )

    remaining_candidates = [
        candidate
        for candidate
        in selection.candidates
        if (
            candidate.item.id
            not in persisted_ids
        )
    ]

    return GoalScopedConfirmationSelection(
        candidates=remaining_candidates,
        deferred_possible_item_ids=list(
            selection
            .deferred_possible_item_ids
        ),
        not_relevant_pending_item_ids=list(
            selection
            .not_relevant_pending_item_ids
        ),
    )


def load_real_confirmation_context():
    """
    Load:
    - immutable canonical walkthrough inventory
    - cached validated goal relevance
    - deterministic goal-scoped confirmation selection
    - persisted human-evidence state

    This function NEVER generates relevance output and therefore cannot
    make a paid model call.
    """

    inventory = (
        goal_relevance_run
        .load_inventory()
    )

    fingerprint = (
        goal_relevance_run
        .inventory_fingerprint(
            inventory
        )
    )

    relevance = (
        goal_relevance_run
        .load_matching_aggregate_cache(
            inventory=inventory,
            fingerprint=fingerprint,
        )
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


def correction_lookup(
    state: PersistedHumanConfirmationState | None,
) -> dict[
    str,
    HumanItemCorrection,
]:
    if state is None:
        return {}

    return {
        correction.item_id:
            correction
        for correction
        in state.item_corrections
    }


def print_existing_corrections(
    state: PersistedHumanConfirmationState | None,
) -> None:
    print()

    print(
        "Persisted identity corrections:"
    )

    if (
        state is None
        or not state.item_corrections
    ):
        print(
            "(none)"
        )

        return

    for correction in (
        state.item_corrections
    ):
        print(
            f"- {correction.item_id}"
        )

        if (
            correction.corrected_name
            is not None
        ):
            print(
                "    corrected name:",
                correction.corrected_name,
            )

        if (
            correction.corrected_description
            is not None
        ):
            print(
                "    corrected description:",
                correction.corrected_description,
            )

        if (
            correction.corrected_location_hint
            is not None
        ):
            print(
                "    corrected location:",
                correction.corrected_location_hint,
            )

        if (
            correction.user_note
            is not None
        ):
            print(
                "    user note:",
                correction.user_note,
            )


def print_confirmation_preview(
    *,
    selection,
    existing_state,
) -> None:
    print()

    print("=" * 72)
    print(
        "IMMEDIATE HUMAN CONFIRMATION QUESTIONS"
    )
    print("=" * 72)

    persisted_count = (
        0
        if existing_state is None
        else len(
            existing_state
            .confirmed_item_ids
        )
    )

    persisted_correction_count = (
        0
        if existing_state is None
        else len(
            existing_state
            .item_corrections
        )
    )

    print(
        "Already persisted confirmations: "
        f"{persisted_count}"
    )

    print(
        "Persisted identity corrections: "
        f"{persisted_correction_count}"
    )

    print(
        "Ask-now candidates: "
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

    existing_corrections = (
        correction_lookup(
            existing_state
        )
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
            f"{index}. item_id: "
            f"{candidate.item.id}"
        )

        print(
            "   canonical name: "
            f"{candidate.item.name}"
        )

        correction = (
            existing_corrections.get(
                candidate.item.id
            )
        )

        if correction is not None:
            if (
                correction.corrected_name
                is not None
            ):
                print(
                    "   user-corrected name: "
                    f"{correction.corrected_name}"
                )

        print(
            "   location: "
            f"{candidate.item.location_hint}"
        )

        print(
            "   description: "
            f"{candidate.item.description}"
        )

        print(
            "   current canonical status: "
            f"{candidate.item.verification_status.value}"
        )

        print(
            "   uncertainty: "
            f"{candidate.item.uncertainty_reason}"
        )

        print(
            "   why ZERO is asking: "
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
    print(
        "EXPLICIT HUMAN CONFIRMATION RESULT"
    )
    print("=" * 72)

    print(
        "Confirmed items this run: "
        f"{len(result.confirmed_item_ids)}"
    )

    print(
        "Unconfirmed immediate candidates: "
        f"{len(result.unconfirmed_candidate_item_ids)}"
    )

    print()

    if result.confirmed_item_ids:
        print(
            "Promoted to USER_CONFIRMED in "
            "reconstructed session inventory:"
        )

        for item_id in (
            result.confirmed_item_ids
        ):
            print(
                f"- {item_id}"
            )

    if (
        result
        .unconfirmed_candidate_item_ids
    ):
        print()

        print(
            "Still NEEDS_CONFIRMATION:"
        )

        for item_id in (
            result
            .unconfirmed_candidate_item_ids
        ):
            print(
                f"- {item_id}"
            )

    original_by_id = {
        item.id:
            item
        for item
        in original_inventory.items
    }

    updated_by_id = {
        item.id:
            item
        for item
        in result.inventory.items
    }

    for item_id in (
        result.confirmed_item_ids
    ):
        original_item = (
            original_by_id[
                item_id
            ]
        )

        updated_item = (
            updated_by_id[
                item_id
            ]
        )

        if (
            original_item
            .verification_status
            != VerificationStatus
            .NEEDS_CONFIRMATION
        ):
            raise RuntimeError(
                "Original confirmed item was unexpectedly "
                "not NEEDS_CONFIRMATION: "
                f"{item_id}"
            )

        if (
            updated_item
            .verification_status
            != VerificationStatus
            .USER_CONFIRMED
        ):
            raise RuntimeError(
                "Explicit confirmation failed to promote item: "
                f"{item_id}"
            )

    print()

    print(
        "Original CanonicalInventory remained unchanged."
    )


def print_requested_corrections(
    corrections: list[
        HumanItemCorrection
    ],
) -> None:
    if not corrections:
        return

    print()

    print("=" * 72)
    print(
        "REQUESTED HUMAN IDENTITY CORRECTIONS"
    )
    print("=" * 72)

    for correction in corrections:
        print(
            f"- {correction.item_id}"
        )

        if (
            correction.corrected_name
            is not None
        ):
            print(
                "    corrected name:",
                correction.corrected_name,
            )

        if (
            correction.corrected_description
            is not None
        ):
            print(
                "    corrected description:",
                correction.corrected_description,
            )

        if (
            correction.corrected_location_hint
            is not None
        ):
            print(
                "    corrected location:",
                correction.corrected_location_hint,
            )

        if (
            correction.user_note
            is not None
        ):
            print(
                "    user note:",
                correction.user_note,
            )


def print_session_evidence_result(
    *,
    inventory,
    fingerprint: str,
    state: PersistedHumanConfirmationState,
) -> None:
    session_inventory = (
        apply_confirmation_state(
            inventory=inventory,
            inventory_sha256=fingerprint,
            state=state,
        )
    )

    by_id = {
        item.id:
            item
        for item
        in session_inventory.items
    }

    print()

    print("=" * 72)
    print(
        "RECONSTRUCTED SESSION HUMAN EVIDENCE"
    )
    print("=" * 72)

    for item_id in (
        state.confirmed_item_ids
    ):
        item = by_id[
            item_id
        ]

        print(
            f"- {item_id}"
        )

        print(
            "    session name:",
            item.name,
        )

        print(
            "    status:",
            item.verification_status.value,
        )

    corrected_ids = {
        correction.item_id
        for correction
        in state.item_corrections
    }

    for item_id in corrected_ids:
        if (
            item_id
            in state.confirmed_item_ids
        ):
            continue

        item = by_id[
            item_id
        ]

        print(
            f"- {item_id}"
        )

        print(
            "    session name:",
            item.name,
        )

        print(
            "    status:",
            item.verification_status.value,
        )

        print(
            "    downstream eligibility:",
            (
                "blocked"
                if (
                    item.verification_status
                    ==
                    VerificationStatus
                    .NEEDS_CONFIRMATION
                )
                else "eligible"
            ),
        )


def main() -> None:
    args = parse_args()

    walkthrough_id = (
        validate_scope_component(
            args.walkthrough_id,
            label="walkthrough id",
        )
    )

    goal_key = (
        validate_scope_component(
            args.goal_key,
            label="goal key",
        )
    )

    configure_scope(
        walkthrough_id=walkthrough_id,
        goal_key=goal_key,
        goal=args.goal,
    )

    corrections = (
        parse_item_corrections(
            args.correction_json
        )
    )

    if (
        args.persist
        and not args.confirm_item_id
        and not corrections
    ):
        raise ValueError(
            "--persist requires at least one "
            "--confirm-item-id or --correction-json."
        )

    print("=" * 72)
    print(
        "ZERO REAL WALKTHROUGH HUMAN CONFIRMATION"
    )
    print("=" * 72)

    print()

    print(
        "Walkthrough:",
        walkthrough_id,
    )

    print(
        "Goal key:",
        goal_key,
    )

    print(
        "Goal:",
        goal_relevance_run.GOAL,
    )

    print(
        "Confirmation state:",
        CONFIRMATION_STATE_PATH.resolve(),
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
        "Inventory SHA-256:",
        fingerprint,
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
            "Persisted confirmed item IDs:",
            existing_state.confirmed_item_ids,
        )

    print_existing_corrections(
        existing_state
    )

    print_confirmation_preview(
        selection=selection,
        existing_state=existing_state,
    )

    print_requested_corrections(
        corrections
    )

    if (
        not args.confirm_item_id
        and not corrections
    ):
        print("=" * 72)
        print(
            "PREVIEW COMPLETE"
        )
        print("=" * 72)

        print()

        print(
            "No explicit user evidence was supplied."
        )

        print(
            "No inventory status or human-evidence "
            "state was changed."
        )

        return

    newly_confirmed_item_ids: list[
        str
    ] = []

    if args.confirm_item_id:
        if existing_state is not None:
            already_persisted_ids = set(
                existing_state
                .confirmed_item_ids
            )

            duplicate_persisted_requests = [
                item_id
                for item_id
                in args.confirm_item_id
                if (
                    item_id
                    in already_persisted_ids
                )
            ]

            if duplicate_persisted_requests:
                raise ValueError(
                    "Explicit confirmation request contains "
                    "item IDs that are already persisted: "
                    f"{sorted(duplicate_persisted_requests)}"
                )

        result = (
            apply_explicit_user_confirmations(
                inventory=inventory,
                selection=selection,
                confirmed_item_ids=(
                    args.confirm_item_id
                ),
            )
        )

        print_confirmation_result(
            original_inventory=inventory,
            result=result,
        )

        newly_confirmed_item_ids = list(
            result.confirmed_item_ids
        )

    if not args.persist:
        print()

        print(
            "Persistence was not requested."
        )

        print(
            "Validated human evidence exists only "
            "in memory in this run."
        )

        return

    updated_state = (
        merge_confirmation_state(
            inventory=inventory,
            inventory_sha256=fingerprint,
            existing_state=existing_state,
            newly_confirmed_item_ids=(
                newly_confirmed_item_ids
            ),
            new_item_corrections=(
                corrections
            ),
        )
    )

    save_confirmation_state(
        updated_state
    )

    print()

    print("=" * 72)
    print(
        "HUMAN EVIDENCE STATE PERSISTED"
    )
    print("=" * 72)

    print()

    print(
        "Persisted confirmed items:",
        len(
            updated_state
            .confirmed_item_ids
        ),
    )

    for item_id in (
        updated_state
        .confirmed_item_ids
    ):
        print(
            f"- {item_id}"
        )

    print()

    print(
        "Persisted identity corrections:",
        len(
            updated_state
            .item_corrections
        ),
    )

    for correction in (
        updated_state
        .item_corrections
    ):
        print(
            f"- {correction.item_id}"
        )

        if (
            correction.corrected_name
            is not None
        ):
            print(
                "    corrected name:",
                correction.corrected_name,
            )

    print()

    print(
        "Saved private human-evidence state:"
    )

    print(
        CONFIRMATION_STATE_PATH.resolve()
    )

    print()

    print(
        "Canonical walkthrough inventory "
        "was NOT overwritten."
    )

    print_session_evidence_result(
        inventory=inventory,
        fingerprint=fingerprint,
        state=updated_state,
    )


if __name__ == "__main__":
    main()