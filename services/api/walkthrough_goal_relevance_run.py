import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from goal_relevance_service import (
    build_goal_relevance_prompt,
    generate_goal_relevance,
    validate_goal_relevance_response,
)
from goal_scoped_confirmation import (
    select_goal_scoped_confirmation_candidates,
)
from schemas import (
    CanonicalInventory,
    GoalAwareInventoryResponse,
    RelevanceLabel,
    VerificationStatus,
)


INVENTORY_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-canonical-inventory.json"
)

CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-goal-relevance-product-photography.json"
)

GOAL = (
    "Create a $0 product photography setup at home using only "
    "what I already have, without permanent modifications."
)


class GoalRelevanceCache(BaseModel):
    """
    Private experiment cache.

    The cache is bound to both the exact goal and the exact canonical
    inventory content so stale relevance output cannot silently be reused.
    """

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    inventory_sha256: str = Field(
        min_length=64,
        max_length=64,
    )

    relevance: GoalAwareInventoryResponse


def load_inventory() -> CanonicalInventory:
    """
    Load CanonicalInventory from the saved walkthrough normalization result.

    The normalization artifact is a wrapper containing:
    - inventory
    - provenance
    - excluded_entities
    - potential_duplicate_groups

    Only the nested inventory object is the CanonicalInventory contract.
    """

    if not INVENTORY_PATH.exists():
        raise RuntimeError(
            "Canonical walkthrough inventory was not found: "
            f"{INVENTORY_PATH}"
        )

    payload = json.loads(
        INVENTORY_PATH.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, dict):
        raise RuntimeError(
            "Walkthrough normalization output must be a JSON object."
        )

    if "inventory" not in payload:
        raise RuntimeError(
            "Walkthrough normalization output does not contain "
            "the required 'inventory' field."
        )

    inventory_payload = payload["inventory"]

    if not isinstance(inventory_payload, dict):
        raise RuntimeError(
            "Walkthrough normalization 'inventory' field must "
            "contain a JSON object."
        )

    return CanonicalInventory.model_validate(
        inventory_payload
    )


def inventory_fingerprint(
    inventory: CanonicalInventory,
) -> str:
    """
    Produce a deterministic fingerprint of the exact canonical inventory.
    """

    canonical_json = json.dumps(
        inventory.model_dump(
            mode="json"
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()


def load_matching_cache(
    *,
    inventory: CanonicalInventory,
    fingerprint: str,
) -> GoalAwareInventoryResponse | None:
    """
    Reuse a cache only when both the goal and inventory fingerprint match.

    A matching cache is revalidated against the current canonical inventory.

    If an existing matching cache is malformed, fail rather than silently
    spending another paid model call.
    """

    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cached = GoalRelevanceCache.model_validate(
            payload
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing goal-relevance cache is invalid. "
            "Refusing to make another paid model call until "
            "the cache is inspected."
        ) from exc

    if cached.goal != GOAL:
        return None

    if cached.inventory_sha256 != fingerprint:
        return None

    return validate_goal_relevance_response(
        inventory=inventory,
        response=cached.relevance,
    )


def save_cache(
    *,
    fingerprint: str,
    relevance: GoalAwareInventoryResponse,
) -> None:
    """
    Save a validated paid model result under sample_data/private/.
    """

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache = GoalRelevanceCache(
        goal=GOAL,
        inventory_sha256=fingerprint,
        relevance=relevance,
    )

    CACHE_PATH.write_text(
        cache.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )


def print_inventory_summary(
    inventory: CanonicalInventory,
) -> None:
    auto_accepted = 0
    user_confirmed = 0
    needs_confirmation = 0

    for item in inventory.items:
        if (
            item.verification_status
            == VerificationStatus.AUTO_ACCEPTED
        ):
            auto_accepted += 1

        elif (
            item.verification_status
            == VerificationStatus.USER_CONFIRMED
        ):
            user_confirmed += 1

        elif (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        ):
            needs_confirmation += 1

    print(
        f"Canonical inventory items: "
        f"{len(inventory.items)}"
    )

    print(
        f"AUTO_ACCEPTED: {auto_accepted}"
    )

    print(
        f"USER_CONFIRMED: {user_confirmed}"
    )

    print(
        f"NEEDS_CONFIRMATION: {needs_confirmation}"
    )


def print_relevance_summary(
    relevance: GoalAwareInventoryResponse,
) -> None:
    relevant = 0
    possibly_relevant = 0
    not_relevant = 0

    for item in relevance.items:
        if (
            item.relevance
            == RelevanceLabel.RELEVANT
        ):
            relevant += 1

        elif (
            item.relevance
            == RelevanceLabel.POSSIBLY_RELEVANT
        ):
            possibly_relevant += 1

        elif (
            item.relevance
            == RelevanceLabel.NOT_RELEVANT
        ):
            not_relevant += 1

    print()
    print("=" * 72)
    print("GOAL RELEVANCE SUMMARY")
    print("=" * 72)

    print(
        f"RELEVANT: {relevant}"
    )

    print(
        f"POSSIBLY_RELEVANT: {possibly_relevant}"
    )

    print(
        f"NOT_RELEVANT: {not_relevant}"
    )

    print(
        f"Accounted pending items: "
        f"{len(relevance.items)}"
    )


def print_confirmation_candidates(
    *,
    inventory: CanonicalInventory,
    relevance: GoalAwareInventoryResponse,
) -> None:
    selection = (
        select_goal_scoped_confirmation_candidates(
            inventory=inventory,
            relevance=relevance,
        )
    )

    print()
    print("=" * 72)
    print("GOAL-SCOPED CONFIRMATION CANDIDATES")
    print("=" * 72)

    print(
        "Candidates requiring user question: "
        f"{len(selection.candidates)}"
    )

    print(
        "Pending but not selected for this goal: "
        f"{len(selection.not_selected_pending_item_ids)}"
    )

    print()

    for index, candidate in enumerate(
        selection.candidates,
        start=1,
    ):
        print(
            f"{index}. {candidate.item.id}"
        )

        print(
            f"   name: {candidate.item.name}"
        )

        print(
            "   relevance: "
            f"{candidate.relevance.value}"
        )

        print(
            "   location: "
            f"{candidate.item.location_hint}"
        )

        print(
            "   uncertainty: "
            f"{candidate.item.uncertainty_reason}"
        )

        print(
            "   relevance reason: "
            f"{candidate.relevance_reason}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the real walkthrough inventory and build "
            "the prompt without making a paid model call."
        ),
    )

    args = parser.parse_args()

    print("=" * 72)
    print("ZERO WALKTHROUGH GOAL-SCOPED RELEVANCE")
    print("=" * 72)

    print()
    print(f"Goal: {GOAL}")
    print()

    inventory = load_inventory()

    fingerprint = inventory_fingerprint(
        inventory
    )

    print_inventory_summary(
        inventory
    )

    print(
        "Inventory SHA-256: "
        f"{fingerprint}"
    )

    prompt = build_goal_relevance_prompt(
        goal=GOAL,
        inventory=inventory,
    )

    print(
        f"Prompt characters: {len(prompt)}"
    )

    if args.dry_run:
        print()
        print(
            "DRY RUN COMPLETE — NO MODEL CALL MADE"
        )

        return

    cached_relevance = load_matching_cache(
        inventory=inventory,
        fingerprint=fingerprint,
    )

    if cached_relevance is not None:
        print()
        print(
            "Valid matching cache found."
        )

        print(
            "Nemotron calls: 0"
        )

        relevance = cached_relevance

    else:
        print()
        print(
            "No matching cache found."
        )

        print(
            "Running one Nemotron goal-relevance call..."
        )

        relevance = generate_goal_relevance(
            goal=GOAL,
            inventory=inventory,
        )

        save_cache(
            fingerprint=fingerprint,
            relevance=relevance,
        )

        print(
            "Nemotron calls: 1"
        )

        print(
            "Saved private goal-relevance cache:"
        )

        print(
            CACHE_PATH.resolve()
        )

    print_relevance_summary(
        relevance
    )

    print_confirmation_candidates(
        inventory=inventory,
        relevance=relevance,
    )


if __name__ == "__main__":
    main()