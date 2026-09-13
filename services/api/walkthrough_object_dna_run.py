from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from human_confirmation_state import (
    PersistedHumanConfirmationState,
    apply_confirmation_state,
    validate_confirmation_state,
)
from object_dna_validator import (
    validate_object_dna,
)
from schemas import (
    CanonicalInventory,
    InventoryItem,
    ObjectDNA,
    ObjectDNAResponse,
    VerificationStatus,
)


DEFAULT_WALKTHROUGH_ID = "walkthrough-01"

WALKTHROUGH_ID_PATTERN = re.compile(
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

INVENTORY_PATH = (
    PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-canonical-inventory.json"
    )
)

CONFIRMATION_STATE_PATH = (
    PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-human-confirmation-state.json"
    )
)

CACHE_DIR = (
    PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-object-dna-cache"
    )
)

AGGREGATE_PATH = (
    PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-session-object-dna.json"
    )
)


OBJECT_DNA_PIPELINE_FILES = (
    "object_dna_service.py",
    "object_dna_normalizer.py",
    "object_dna_sanitizer.py",
    "object_dna_validator.py",
    "schemas.py",
)


class ObjectDNAItemCache(BaseModel):
    """
    Private per-item Object DNA cache.

    A cache is reusable only when:
    - the session item payload is identical
    - the complete Object DNA generation/validation pipeline is identical
    - the returned ObjectDNA belongs to the exact item ID
    """

    item_id: str = Field(
        min_length=1,
        max_length=100,
    )

    item_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    object_dna: ObjectDNA


class ObjectDNAAggregateSnapshot(BaseModel):
    """
    Convenience snapshot assembled only after every eligible
    session item has a valid per-item cache.

    Per-item caches remain the authoritative paid-call cache.
    """

    session_inventory_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    eligible_item_ids: list[str]

    object_dna: ObjectDNAResponse


def validate_walkthrough_id(
    value: str,
) -> str:
    if not WALKTHROUGH_ID_PATTERN.fullmatch(
        value
    ):
        raise ValueError(
            "walkthrough id may contain only letters, "
            "numbers, hyphens, and underscores"
        )

    return value


def configure_walkthrough_paths(
    walkthrough_id: str,
) -> None:
    global INVENTORY_PATH
    global CONFIRMATION_STATE_PATH
    global CACHE_DIR
    global AGGREGATE_PATH

    walkthrough_id = (
        validate_walkthrough_id(
            walkthrough_id
        )
    )

    INVENTORY_PATH = (
        PRIVATE_DIR
        / (
            f"{walkthrough_id}"
            "-canonical-inventory.json"
        )
    )

    CONFIRMATION_STATE_PATH = (
        PRIVATE_DIR
        / (
            f"{walkthrough_id}"
            "-human-confirmation-state.json"
        )
    )

    CACHE_DIR = (
        PRIVATE_DIR
        / (
            f"{walkthrough_id}"
            "-object-dna-cache"
        )
    )

    AGGREGATE_PATH = (
        PRIVATE_DIR
        / (
            f"{walkthrough_id}"
            "-session-object-dna.json"
        )
    )


def sha256_text(
    text: str,
) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def inventory_fingerprint(
    inventory: CanonicalInventory,
) -> str:
    """
    Deterministic fingerprint of the exact inventory payload.

    Kept equivalent to the goal-relevance inventory fingerprint,
    without introducing a goal-dependent runner dependency here.
    """

    canonical_json = json.dumps(
        inventory.model_dump(
            mode="json"
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return sha256_text(
        canonical_json
    )


def item_fingerprint(
    item: InventoryItem,
) -> str:
    """
    Fingerprint the exact session representation supplied to
    Object DNA generation.
    """

    payload = json.dumps(
        item.model_dump(
            mode="json"
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return sha256_text(
        payload
    )


def object_dna_pipeline_fingerprint() -> str:
    """
    Bind caches to the complete local Object DNA implementation.

    If the model prompt, model name, normalizer, sanitizer, validator,
    or ObjectDNA schema changes, this fingerprint changes and old caches
    become stale instead of silently being reused.
    """

    digest = hashlib.sha256()

    base_dir = (
        Path(__file__)
        .resolve()
        .parent
    )

    for filename in (
        OBJECT_DNA_PIPELINE_FILES
    ):
        path = (
            base_dir
            / filename
        )

        if not path.exists():
            raise RuntimeError(
                "Required Object DNA pipeline file "
                f"was not found: {path}"
            )

        digest.update(
            filename.encode(
                "utf-8"
            )
        )

        digest.update(
            b"\0"
        )

        digest.update(
            path.read_bytes()
        )

        digest.update(
            b"\0"
        )

    return digest.hexdigest()


def load_inventory(
) -> CanonicalInventory:
    """
    Load CanonicalInventory from the deterministic walkthrough
    normalization wrapper.
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

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Walkthrough normalization output must be "
            "a JSON object."
        )

    inventory_payload = (
        payload.get(
            "inventory"
        )
    )

    if not isinstance(
        inventory_payload,
        dict,
    ):
        raise RuntimeError(
            "Walkthrough normalization output does not "
            "contain a valid 'inventory' object."
        )

    return (
        CanonicalInventory
        .model_validate(
            inventory_payload
        )
    )


def load_existing_confirmation_state(
    *,
    inventory: CanonicalInventory,
    fingerprint: str,
) -> (
    PersistedHumanConfirmationState
    | None
):
    """
    Load persisted human evidence for this exact canonical inventory.

    No goal-relevance dependency is needed here.
    """

    if not (
        CONFIRMATION_STATE_PATH.exists()
    ):
        return None

    try:
        payload = json.loads(
            CONFIRMATION_STATE_PATH
            .read_text(
                encoding="utf-8"
            )
        )

        state = (
            PersistedHumanConfirmationState
            .model_validate(
                payload
            )
        )

        return (
            validate_confirmation_state(
                inventory=inventory,
                inventory_sha256=(
                    fingerprint
                ),
                state=state,
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing human confirmation state "
            "is invalid. Refusing to ignore it: "
            f"{CONFIRMATION_STATE_PATH}"
        ) from exc


def load_session_inventory() -> tuple[
    CanonicalInventory,
    CanonicalInventory,
    str,
]:
    """
    Reconstruct the current real session inventory from immutable
    canonical inventory plus persisted human evidence.

    No AI/model calls occur here.
    """

    canonical_inventory = (
        load_inventory()
    )

    canonical_fingerprint = (
        inventory_fingerprint(
            canonical_inventory
        )
    )

    state = (
        load_existing_confirmation_state(
            inventory=(
                canonical_inventory
            ),
            fingerprint=(
                canonical_fingerprint
            ),
        )
    )

    if state is None:
        session_inventory = (
            canonical_inventory
            .model_copy(
                deep=True
            )
        )

    else:
        session_inventory = (
            apply_confirmation_state(
                inventory=(
                    canonical_inventory
                ),
                inventory_sha256=(
                    canonical_fingerprint
                ),
                state=state,
            )
        )

    return (
        canonical_inventory,
        session_inventory,
        canonical_fingerprint,
    )


def get_eligible_items(
    session_inventory: CanonicalInventory,
) -> list[InventoryItem]:
    """
    Return exactly the items allowed to reach Object DNA.

    NEEDS_CONFIRMATION remains excluded.
    """

    seen_ids: set[
        str
    ] = set()

    eligible_items: list[
        InventoryItem
    ] = []

    for item in (
        session_inventory.items
    ):
        if item.id in seen_ids:
            raise ValueError(
                "Session inventory contains duplicate "
                f"item ID: {item.id}"
            )

        seen_ids.add(
            item.id
        )

        if (
            item.verification_status
            ==
            VerificationStatus
            .NEEDS_CONFIRMATION
        ):
            continue

        eligible_items.append(
            item
        )

    return eligible_items


def cache_path_for_item(
    item_id: str,
) -> Path:
    """
    Use a readable ID plus short digest so unusual IDs cannot
    collide after filename normalization.
    """

    safe_id = "".join(
        character
        if (
            character.isalnum()
            or character
            in {"-", "_"}
        )
        else "_"
        for character
        in item_id
    )

    if not safe_id:
        raise ValueError(
            "Cannot construct cache filename "
            "for empty item ID."
        )

    id_digest = hashlib.sha256(
        item_id.encode(
            "utf-8"
        )
    ).hexdigest()[:12]

    return (
        CACHE_DIR
        / (
            f"{safe_id}-"
            f"{id_digest}.json"
        )
    )


def load_matching_item_cache(
    *,
    item: InventoryItem,
    pipeline_sha256: str,
) -> ObjectDNA | None:
    """
    Return a valid matching per-item cache or None when no
    reusable cache exists.

    Malformed cache files fail loudly rather than triggering
    a silent paid replacement.
    """

    path = cache_path_for_item(
        item.id
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
            ObjectDNAItemCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing Object DNA item cache is invalid. "
            "Refusing to overwrite it with another paid "
            f"call until inspected: {path}"
        ) from exc

    if (
        cached.item_id
        != item.id
    ):
        raise RuntimeError(
            "Object DNA cache item ID does not match "
            "its expected canonical item: "
            f"{item.id}"
        )

    if (
        cached.item_sha256
        != item_fingerprint(
            item
        )
    ):
        return None

    if (
        cached.pipeline_sha256
        != pipeline_sha256
    ):
        return None

    if (
        cached.object_dna.item_id
        != item.id
    ):
        raise RuntimeError(
            "Cached Object DNA payload item ID "
            f"mismatch for {item.id}."
        )

    return validate_object_dna(
        cached.object_dna
    )


def save_item_cache(
    *,
    item: InventoryItem,
    pipeline_sha256: str,
    object_dna: ObjectDNA,
) -> None:
    """
    Save one successful paid result immediately and atomically.
    """

    if (
        object_dna.item_id
        != item.id
    ):
        raise RuntimeError(
            "Cannot cache Object DNA under the wrong "
            f"item ID. Expected {item.id}, "
            f"received {object_dna.item_id}."
        )

    validated = (
        validate_object_dna(
            object_dna
        )
    )

    cache = ObjectDNAItemCache(
        item_id=item.id,
        item_sha256=(
            item_fingerprint(
                item
            )
        ),
        pipeline_sha256=(
            pipeline_sha256
        ),
        object_dna=validated,
    )

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = cache_path_for_item(
        item.id
    )

    temporary_path = (
        path.with_name(
            path.name
            + ".tmp"
        )
    )

    temporary_path.write_text(
        cache.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        path
    )


def resolve_requested_items(
    *,
    eligible_items: list[
        InventoryItem
    ],
    requested_item_ids: list[str],
) -> list[InventoryItem]:
    """
    Resolve optional CLI item selection while preserving canonical order.
    """

    if not requested_item_ids:
        return eligible_items

    seen_requested: set[
        str
    ] = set()

    for item_id in (
        requested_item_ids
    ):
        if (
            item_id
            in seen_requested
        ):
            raise ValueError(
                "Requested Object DNA item IDs "
                "contain duplicate ID: "
                f"{item_id}"
            )

        seen_requested.add(
            item_id
        )

    eligible_ids = {
        item.id
        for item
        in eligible_items
    }

    invalid_ids = sorted(
        item_id
        for item_id
        in seen_requested
        if (
            item_id
            not in eligible_ids
        )
    )

    if invalid_ids:
        raise ValueError(
            "Requested Object DNA IDs are not "
            "currently eligible session inventory "
            f"items: {invalid_ids}"
        )

    return [
        item
        for item
        in eligible_items
        if (
            item.id
            in seen_requested
        )
    ]


def inspect_cache_status(
    *,
    eligible_items: list[
        InventoryItem
    ],
    pipeline_sha256: str,
) -> tuple[
    dict[
        str,
        ObjectDNA,
    ],
    list[
        InventoryItem
    ],
]:
    """
    Inspect every eligible item without making model calls.
    """

    cached_by_id: dict[
        str,
        ObjectDNA,
    ] = {}

    missing_items: list[
        InventoryItem
    ] = []

    for item in (
        eligible_items
    ):
        cached = (
            load_matching_item_cache(
                item=item,
                pipeline_sha256=(
                    pipeline_sha256
                ),
            )
        )

        if cached is None:
            missing_items.append(
                item
            )

            continue

        cached_by_id[
            item.id
        ] = cached

    return (
        cached_by_id,
        missing_items,
    )


def build_complete_response(
    *,
    eligible_items: list[
        InventoryItem
    ],
    cached_by_id: dict[
        str,
        ObjectDNA,
    ],
) -> ObjectDNAResponse:
    """
    Assemble complete ObjectDNAResponse in canonical eligible-item order.
    """

    missing_ids = [
        item.id
        for item
        in eligible_items
        if (
            item.id
            not in cached_by_id
        )
    ]

    if missing_ids:
        raise ValueError(
            "Cannot build complete Object DNA response. "
            "Missing eligible item IDs: "
            f"{missing_ids}"
        )

    objects = [
        cached_by_id[
            item.id
        ]
        for item
        in eligible_items
    ]

    actual_ids = [
        object_dna.item_id
        for object_dna
        in objects
    ]

    expected_ids = [
        item.id
        for item
        in eligible_items
    ]

    if (
        actual_ids
        != expected_ids
    ):
        raise RuntimeError(
            "Complete Object DNA ordering/"
            "coverage mismatch."
        )

    return ObjectDNAResponse(
        objects=objects
    )


def save_aggregate_snapshot(
    *,
    session_inventory: CanonicalInventory,
    eligible_items: list[
        InventoryItem
    ],
    pipeline_sha256: str,
    object_dna: ObjectDNAResponse,
) -> None:
    """
    Save a convenience full-session snapshot after all
    per-item caches exist.

    Per-item caches remain authoritative.
    """

    snapshot = (
        ObjectDNAAggregateSnapshot(
            session_inventory_sha256=(
                inventory_fingerprint(
                    session_inventory
                )
            ),
            pipeline_sha256=(
                pipeline_sha256
            ),
            eligible_item_ids=[
                item.id
                for item
                in eligible_items
            ],
            object_dna=(
                object_dna
            ),
        )
    )

    AGGREGATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        AGGREGATE_PATH.with_name(
            AGGREGATE_PATH.name
            + ".tmp"
        )
    )

    temporary_path.write_text(
        snapshot.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        AGGREGATE_PATH
    )


def print_inventory_summary(
    *,
    session_inventory: CanonicalInventory,
    eligible_items: list[
        InventoryItem
    ],
) -> None:
    pending_count = sum(
        1
        for item
        in session_inventory.items
        if (
            item.verification_status
            ==
            VerificationStatus
            .NEEDS_CONFIRMATION
        )
    )

    auto_count = sum(
        1
        for item
        in session_inventory.items
        if (
            item.verification_status
            ==
            VerificationStatus
            .AUTO_ACCEPTED
        )
    )

    confirmed_count = sum(
        1
        for item
        in session_inventory.items
        if (
            item.verification_status
            ==
            VerificationStatus
            .USER_CONFIRMED
        )
    )

    print(
        "Session inventory items: "
        f"{len(session_inventory.items)}"
    )

    print(
        f"AUTO_ACCEPTED: "
        f"{auto_count}"
    )

    print(
        f"USER_CONFIRMED: "
        f"{confirmed_count}"
    )

    print(
        "NEEDS_CONFIRMATION: "
        f"{pending_count}"
    )

    print(
        "Eligible Object DNA items: "
        f"{len(eligible_items)}"
    )


def parse_args() -> (
    argparse.Namespace
):
    parser = argparse.ArgumentParser(
        description=(
            "Generate or inspect goal-independent "
            "Object DNA for a namespaced walkthrough."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=(
            DEFAULT_WALKTHROUGH_ID
        ),
        help=(
            "Artifact namespace such as walkthrough-02. "
            "Defaults to walkthrough-01."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Inspect eligible items and cache status "
            "without creating a paid Object DNA client."
        ),
    )

    parser.add_argument(
        "--max-new-calls",
        type=int,
        default=0,
        help=(
            "Maximum number of new paid Object DNA "
            "calls allowed during this run. Default 0."
        ),
    )

    parser.add_argument(
        "--item-id",
        action="append",
        default=[],
        help=(
            "Limit generation to one eligible item ID. "
            "May be supplied multiple times."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    walkthrough_id = (
        validate_walkthrough_id(
            args.walkthrough_id
        )
    )

    configure_walkthrough_paths(
        walkthrough_id
    )

    if (
        args.max_new_calls
        < 0
    ):
        raise ValueError(
            "--max-new-calls cannot be negative."
        )

    if (
        args.dry_run
        and args.max_new_calls
        != 0
    ):
        raise ValueError(
            "--dry-run cannot be combined "
            "with paid calls."
        )

    print("=" * 72)
    print(
        "ZERO WALKTHROUGH OBJECT DNA"
    )
    print("=" * 72)

    print()

    print(
        "Walkthrough:",
        walkthrough_id,
    )

    print(
        "Canonical inventory:",
        INVENTORY_PATH.resolve(),
    )

    print(
        "Human-evidence state:",
        CONFIRMATION_STATE_PATH.resolve(),
    )

    print(
        "Per-item cache directory:",
        CACHE_DIR.resolve(),
    )

    print(
        "Aggregate snapshot:",
        AGGREGATE_PATH.resolve(),
    )

    (
        canonical_inventory,
        session_inventory,
        canonical_sha256,
    ) = load_session_inventory()

    eligible_items = (
        get_eligible_items(
            session_inventory
        )
    )

    selected_items = (
        resolve_requested_items(
            eligible_items=(
                eligible_items
            ),
            requested_item_ids=(
                args.item_id
            ),
        )
    )

    pipeline_sha256 = (
        object_dna_pipeline_fingerprint()
    )

    (
        cached_by_id,
        missing_items,
    ) = inspect_cache_status(
        eligible_items=(
            eligible_items
        ),
        pipeline_sha256=(
            pipeline_sha256
        ),
    )

    print()

    print(
        "Canonical inventory SHA-256: "
        f"{canonical_sha256}"
    )

    print(
        "Object DNA pipeline SHA-256: "
        f"{pipeline_sha256}"
    )

    print()

    print_inventory_summary(
        session_inventory=(
            session_inventory
        ),
        eligible_items=(
            eligible_items
        ),
    )

    print()

    print(
        "Valid per-item cache hits: "
        f"{len(cached_by_id)}"
    )

    print(
        "Missing/stale per-item caches: "
        f"{len(missing_items)}"
    )

    print(
        "Expected new calls for complete "
        "eligible coverage: "
        f"{len(missing_items)}"
    )

    print(
        "Selected items this run: "
        f"{len(selected_items)}"
    )

    print()

    print("=" * 72)
    print(
        "SELECTED OBJECT DNA ITEMS"
    )
    print("=" * 72)

    for index, item in enumerate(
        selected_items,
        start=1,
    ):
        cached = (
            item.id
            in cached_by_id
        )

        print(
            f"{index}. {item.id}"
        )

        print(
            f"   name: {item.name}"
        )

        print(
            "   verification: "
            f"{item.verification_status.value}"
        )

        print(
            "   cache: "
            f"{'valid' if cached else 'missing/stale'}"
        )

    if args.dry_run:
        print()

        print(
            "DRY RUN COMPLETE - "
            "NO MODEL CALL MADE"
        )

        print(
            "Model calls executed by dry run: 0"
        )

        return

    if (
        args.max_new_calls
        == 0
    ):
        print()

        print(
            "No paid Object DNA calls authorized "
            "(--max-new-calls is 0)."
        )

        return

    new_calls = 0

    for item in selected_items:
        existing = (
            load_matching_item_cache(
                item=item,
                pipeline_sha256=(
                    pipeline_sha256
                ),
            )
        )

        if existing is not None:
            print()

            print(
                f"{item.id}: "
                "valid cache hit"
            )

            continue

        if (
            new_calls
            >= args.max_new_calls
        ):
            break

        print()

        print(
            f"{item.id}: running one "
            "paid Object DNA call..."
        )

        try:
            # Import lazily so dry runs and cache-only runs
            # do not even create the Nebius client.
            from object_dna_service import (
                generate_object_dna,
            )

            result = (
                generate_object_dna(
                    item
                )
            )

            save_item_cache(
                item=item,
                pipeline_sha256=(
                    pipeline_sha256
                ),
                object_dna=result,
            )

        except Exception:
            print()

            print(
                "Object DNA generation failed "
                f"for {item.id}."
            )

            print(
                "All earlier successful per-item "
                "caches remain saved."
            )

            print(
                "Do not rerun blindly before "
                "inspecting the failure."
            )

            raise

        new_calls += 1

        print(
            f"{item.id}: "
            "validated and cached"
        )

    (
        refreshed_cached_by_id,
        refreshed_missing_items,
    ) = inspect_cache_status(
        eligible_items=(
            eligible_items
        ),
        pipeline_sha256=(
            pipeline_sha256
        ),
    )

    print()

    print("=" * 72)
    print(
        "OBJECT DNA RUN SUMMARY"
    )
    print("=" * 72)

    print(
        "Paid calls made this run: "
        f"{new_calls}"
    )

    print(
        "Valid cached eligible items: "
        f"{len(refreshed_cached_by_id)}"
    )

    print(
        "Remaining uncached eligible items: "
        f"{len(refreshed_missing_items)}"
    )

    if refreshed_missing_items:
        print()

        print(
            "Remaining item IDs:"
        )

        for item in (
            refreshed_missing_items
        ):
            print(
                f"- {item.id}"
            )

        print()

        print(
            "Aggregate Object DNA snapshot was "
            "NOT written because coverage "
            "is incomplete."
        )

        return

    complete_response = (
        build_complete_response(
            eligible_items=(
                eligible_items
            ),
            cached_by_id=(
                refreshed_cached_by_id
            ),
        )
    )

    save_aggregate_snapshot(
        session_inventory=(
            session_inventory
        ),
        eligible_items=(
            eligible_items
        ),
        pipeline_sha256=(
            pipeline_sha256
        ),
        object_dna=(
            complete_response
        ),
    )

    print()

    print(
        "Complete Object DNA coverage: "
        f"{len(eligible_items)}/"
        f"{len(eligible_items)}"
    )

    print(
        "Saved private aggregate "
        "Object DNA snapshot:"
    )

    print(
        AGGREGATE_PATH.resolve()
    )


if __name__ == "__main__":
    main()