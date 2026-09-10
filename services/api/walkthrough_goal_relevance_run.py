import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from goal_relevance_service import (
    MAX_PENDING_ITEMS_PER_CALL,
    build_goal_relevance_prompt,
    generate_goal_relevance_chunk,
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

CACHE_DIR = Path(
    "sample_data/private/"
    "walkthrough-01-goal-relevance-product-photography-cache"
)

AGGREGATE_CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-goal-relevance-product-photography.json"
)

GOAL = (
    "Create a $0 product photography setup at home using only "
    "what I already have, without permanent modifications."
)


class GoalRelevanceChunkCache(BaseModel):
    """
    Private cache for one bounded paid relevance call.

    A chunk cache is valid only for:
    - the exact goal
    - the exact canonical inventory fingerprint
    - the exact chunk index
    - the exact ordered pending item IDs
    """

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    inventory_sha256: str = Field(
        min_length=64,
        max_length=64,
    )

    chunk_index: int = Field(
        ge=1,
    )

    pending_item_ids: list[str] = Field(
        min_length=1,
        max_length=MAX_PENDING_ITEMS_PER_CALL,
    )

    relevance: GoalAwareInventoryResponse


class GoalRelevanceAggregateCache(BaseModel):
    """
    Fully assembled relevance result after every pending chunk has been
    validated.

    This gives later runs a zero-call fast path.
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
    Load CanonicalInventory from the saved walkthrough normalization wrapper.
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

    if not isinstance(
        inventory_payload,
        dict,
    ):
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


def get_pending_item_ids(
    inventory: CanonicalInventory,
) -> list[str]:
    """
    Return NEEDS_CONFIRMATION IDs in canonical inventory order.
    """

    return [
        item.id
        for item in inventory.items
        if (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        )
    ]


def build_chunk_plan(
    inventory: CanonicalInventory,
) -> list[list[str]]:
    """
    Deterministically split pending inventory into bounded relevance chunks.

    Chunk membership follows canonical inventory order.
    """

    pending_item_ids = get_pending_item_ids(
        inventory
    )

    return [
        pending_item_ids[
            start:
            start + MAX_PENDING_ITEMS_PER_CALL
        ]
        for start in range(
            0,
            len(pending_item_ids),
            MAX_PENDING_ITEMS_PER_CALL,
        )
    ]


def chunk_cache_path(
    chunk_index: int,
) -> Path:
    return CACHE_DIR / (
        f"chunk-{chunk_index:02d}.json"
    )


def load_matching_aggregate_cache(
    *,
    inventory: CanonicalInventory,
    fingerprint: str,
) -> GoalAwareInventoryResponse | None:
    """
    Reuse a complete aggregate cache only when both goal and inventory match.

    A matching cache is always revalidated against current CanonicalInventory.
    """

    if not AGGREGATE_CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            AGGREGATE_CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cached = (
            GoalRelevanceAggregateCache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing aggregate goal-relevance cache is invalid. "
            "Refusing to make paid calls until it is inspected."
        ) from exc

    if cached.goal != GOAL:
        return None

    if cached.inventory_sha256 != fingerprint:
        return None

    return validate_goal_relevance_response(
        inventory=inventory,
        response=cached.relevance,
    )


def save_aggregate_cache(
    *,
    fingerprint: str,
    relevance: GoalAwareInventoryResponse,
) -> None:
    """
    Save the fully validated all-pending relevance result.
    """

    AGGREGATE_CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache = GoalRelevanceAggregateCache(
        goal=GOAL,
        inventory_sha256=fingerprint,
        relevance=relevance,
    )

    AGGREGATE_CACHE_PATH.write_text(
        cache.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )


def load_matching_chunk_cache(
    *,
    inventory: CanonicalInventory,
    fingerprint: str,
    chunk_index: int,
    pending_item_ids: list[str],
) -> GoalAwareInventoryResponse | None:
    """
    Load one chunk cache when it exactly matches this experiment scope.

    If the cache file exists but is malformed, fail rather than silently
    making another paid call.

    A valid but stale cache is ignored.
    """

    path = chunk_cache_path(
        chunk_index
    )

    if not path.exists():
        return None

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        cached = (
            GoalRelevanceChunkCache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing goal-relevance chunk cache is invalid: "
            f"{path}. Refusing to make another paid call "
            "until the cache is inspected."
        ) from exc

    if cached.goal != GOAL:
        return None

    if cached.inventory_sha256 != fingerprint:
        return None

    if cached.chunk_index != chunk_index:
        return None

    if cached.pending_item_ids != pending_item_ids:
        return None

    return validate_goal_relevance_response(
        inventory=inventory,
        response=cached.relevance,
        pending_item_ids=pending_item_ids,
    )


def save_chunk_cache(
    *,
    fingerprint: str,
    chunk_index: int,
    pending_item_ids: list[str],
    relevance: GoalAwareInventoryResponse,
) -> None:
    """
    Save one successful validated paid call immediately.

    This happens before later chunks are attempted.
    """

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache = GoalRelevanceChunkCache(
        goal=GOAL,
        inventory_sha256=fingerprint,
        chunk_index=chunk_index,
        pending_item_ids=pending_item_ids,
        relevance=relevance,
    )

    path = chunk_cache_path(
        chunk_index
    )

    path.write_text(
        cache.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )


def combine_chunk_results(
    *,
    inventory: CanonicalInventory,
    chunk_results: list[
        GoalAwareInventoryResponse
    ],
) -> GoalAwareInventoryResponse:
    """
    Combine independently validated chunks and validate exact accounting
    across the complete NEEDS_CONFIRMATION inventory.

    Full validation catches any unexpected cross-chunk duplicate, omission,
    or ordering problem before an aggregate cache is accepted.
    """

    combined = GoalAwareInventoryResponse(
        items=[
            relevance_item
            for chunk_result in chunk_results
            for relevance_item in chunk_result.items
        ]
    )

    return validate_goal_relevance_response(
        inventory=inventory,
        response=combined,
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


def print_chunk_plan(
    *,
    inventory: CanonicalInventory,
    chunks: list[list[str]],
) -> None:
    """
    Build every chunk prompt locally and report its size.

    This doubles as a free validation that every requested chunk scope can
    produce a prompt before paid execution begins.
    """

    print()
    print("=" * 72)
    print("BOUNDED CHUNK PLAN")
    print("=" * 72)

    print(
        f"Maximum pending items per call: "
        f"{MAX_PENDING_ITEMS_PER_CALL}"
    )

    print(
        f"Chunk count: {len(chunks)}"
    )

    print()

    for chunk_index, pending_item_ids in enumerate(
        chunks,
        start=1,
    ):
        prompt = build_goal_relevance_prompt(
            goal=GOAL,
            inventory=inventory,
            pending_item_ids=pending_item_ids,
        )

        print(
            f"Chunk {chunk_index}: "
            f"{len(pending_item_ids)} items, "
            f"{len(prompt)} prompt characters"
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


def run_chunked_relevance(
    *,
    inventory: CanonicalInventory,
    fingerprint: str,
    chunks: list[list[str]],
) -> tuple[
    GoalAwareInventoryResponse,
    int,
    int,
]:
    """
    Execute or reuse each bounded relevance chunk.

    Returns:
        complete relevance response
        number of paid Nemotron calls made
        number of chunk cache hits

    Every newly generated chunk is cached immediately before proceeding.
    """

    chunk_results: list[
        GoalAwareInventoryResponse
    ] = []

    model_calls = 0
    cache_hits = 0

    for chunk_index, pending_item_ids in enumerate(
        chunks,
        start=1,
    ):
        print()
        print(
            f"Chunk {chunk_index}/{len(chunks)} "
            f"({len(pending_item_ids)} pending items)"
        )

        cached = load_matching_chunk_cache(
            inventory=inventory,
            fingerprint=fingerprint,
            chunk_index=chunk_index,
            pending_item_ids=pending_item_ids,
        )

        if cached is not None:
            print(
                "  Valid chunk cache found."
            )

            print(
                "  Nemotron calls: 0"
            )

            chunk_results.append(
                cached
            )

            cache_hits += 1

            continue

        print(
            "  No matching chunk cache found."
        )

        print(
            "  Running one bounded Nemotron call..."
        )

        try:
            result = generate_goal_relevance_chunk(
                goal=GOAL,
                inventory=inventory,
                pending_item_ids=pending_item_ids,
            )

        except Exception:
            print()
            print(
                f"Chunk {chunk_index} failed."
            )

            print(
                "Any earlier successful chunk caches remain saved."
            )

            print(
                "Do not delete them before investigating the failure."
            )

            raise

        save_chunk_cache(
            fingerprint=fingerprint,
            chunk_index=chunk_index,
            pending_item_ids=pending_item_ids,
            relevance=result,
        )

        print(
            "  Chunk validated and cached."
        )

        print(
            "  Nemotron calls: 1"
        )

        chunk_results.append(
            result
        )

        model_calls += 1

    complete_relevance = combine_chunk_results(
        inventory=inventory,
        chunk_results=chunk_results,
    )

    return (
        complete_relevance,
        model_calls,
        cache_hits,
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the real walkthrough inventory and every "
            "bounded chunk prompt without making paid model calls."
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

    chunks = build_chunk_plan(
        inventory
    )

    print_chunk_plan(
        inventory=inventory,
        chunks=chunks,
    )

    if args.dry_run:
        print()
        print(
            "DRY RUN COMPLETE — NO MODEL CALL MADE"
        )

        return

    aggregate_cache = (
        load_matching_aggregate_cache(
            inventory=inventory,
            fingerprint=fingerprint,
        )
    )

    if aggregate_cache is not None:
        print()
        print(
            "Valid complete aggregate cache found."
        )

        print(
            "Nemotron calls: 0"
        )

        relevance = aggregate_cache

    else:
        print()
        print(
            "No matching complete aggregate cache found."
        )

        (
            relevance,
            model_calls,
            chunk_cache_hits,
        ) = run_chunked_relevance(
            inventory=inventory,
            fingerprint=fingerprint,
            chunks=chunks,
        )

        save_aggregate_cache(
            fingerprint=fingerprint,
            relevance=relevance,
        )

        print()
        print("=" * 72)
        print("CHUNK EXECUTION COMPLETE")
        print("=" * 72)

        print(
            f"Nemotron calls made this run: "
            f"{model_calls}"
        )

        print(
            f"Chunk cache hits: "
            f"{chunk_cache_hits}"
        )

        print(
            f"Validated chunks: "
            f"{len(chunks)}"
        )

        print()
        print(
            "Saved complete private aggregate cache:"
        )

        print(
            AGGREGATE_CACHE_PATH.resolve()
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