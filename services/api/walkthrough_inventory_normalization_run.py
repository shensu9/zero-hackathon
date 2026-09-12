from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from schemas import (
    VerificationStatus,
)
from walkthrough_entity_resolution_schemas import (
    WalkthroughEntityResolution,
)
from walkthrough_inventory_normalizer import (
    WalkthroughInventoryNormalizationResult,
    normalize_walkthrough_inventory,
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

ENTITY_RESOLUTION_PATH = (
    PRIVATE_DIR
    / f"{DEFAULT_WALKTHROUGH_ID}-entity-resolution.json"
)

OUTPUT_PATH = (
    PRIVATE_DIR
    / f"{DEFAULT_WALKTHROUGH_ID}-canonical-inventory.json"
)


def configure_utf8_console() -> None:
    for stream in (
        sys.stdout,
        sys.stderr,
    ):
        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(reconfigure):
            try:
                reconfigure(
                    encoding="utf-8"
                )
            except Exception:
                pass


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
    global ENTITY_RESOLUTION_PATH
    global OUTPUT_PATH

    walkthrough_id = validate_walkthrough_id(
        walkthrough_id
    )

    ENTITY_RESOLUTION_PATH = (
        PRIVATE_DIR
        / f"{walkthrough_id}-entity-resolution.json"
    )

    OUTPUT_PATH = (
        PRIVATE_DIR
        / f"{walkthrough_id}-canonical-inventory.json"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize ZERO entity resolution into "
            "canonical inventory for a namespaced "
            "walkthrough."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=DEFAULT_WALKTHROUGH_ID,
        help=(
            "Artifact namespace such as walkthrough-02. "
            "Defaults to walkthrough-01 for backwards "
            "compatibility."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Run deterministic normalization and validation "
            "without writing the canonical inventory file."
        ),
    )

    return parser.parse_args()


def load_resolution(
) -> WalkthroughEntityResolution:
    if not ENTITY_RESOLUTION_PATH.exists():
        raise FileNotFoundError(
            "Entity-resolution output does not exist: "
            f"{ENTITY_RESOLUTION_PATH}"
        )

    envelope = json.loads(
        ENTITY_RESOLUTION_PATH.read_text(
            encoding="utf-8"
        )
    )

    payload = envelope.get(
        "resolution"
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Entity-resolution file does not contain "
            "a valid 'resolution' object."
        )

    return (
        WalkthroughEntityResolution
        .model_validate(
            payload
        )
    )


def validate_normalization_result(
    *,
    source_resolution: WalkthroughEntityResolution,
    result: WalkthroughInventoryNormalizationResult,
) -> None:
    """
    Deterministic accounting checks for the normalization boundary.
    """

    source_entity_count = len(
        source_resolution.entities
    )

    retained_count = len(
        result.inventory.items
    )

    excluded_count = len(
        result.excluded_entities
    )

    if (
        retained_count
        + excluded_count
        != source_entity_count
    ):
        raise RuntimeError(
            "Normalization accounting mismatch: "
            f"{source_entity_count} source entities, "
            f"{retained_count} retained, "
            f"{excluded_count} excluded."
        )

    inventory_ids = [
        item.id
        for item
        in result.inventory.items
    ]

    if (
        len(
            inventory_ids
        )
        != len(
            set(
                inventory_ids
            )
        )
    ):
        raise RuntimeError(
            "Canonical inventory contains duplicate item IDs."
        )

    provenance_ids = [
        record.item_id
        for record
        in result.provenance
    ]

    if (
        set(
            provenance_ids
        )
        != set(
            inventory_ids
        )
    ):
        raise RuntimeError(
            "Inventory/provenance item-ID coverage mismatch."
        )

    valid_inventory_ids = set(
        inventory_ids
    )

    for group in (
        result.potential_duplicate_groups
    ):
        unknown = (
            set(
                group.item_ids
            )
            - valid_inventory_ids
        )

        if unknown:
            raise RuntimeError(
                "Potential duplicate group references "
                "unknown inventory IDs: "
                f"{sorted(unknown)}"
            )


def save_result(
    result: WalkthroughInventoryNormalizationResult,
) -> None:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            result.model_dump(
                mode="json"
            ),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def print_result_summary(
    *,
    walkthrough_id: str,
    result: WalkthroughInventoryNormalizationResult,
    dry_run: bool,
) -> None:
    status_counts = Counter(
        item.verification_status
        for item
        in result.inventory.items
    )

    auto_accepted = status_counts[
        VerificationStatus
        .AUTO_ACCEPTED
    ]

    needs_confirmation = status_counts[
        VerificationStatus
        .NEEDS_CONFIRMATION
    ]

    user_confirmed = status_counts[
        VerificationStatus
        .USER_CONFIRMED
    ]

    print()
    print("=" * 72)

    if dry_run:
        print(
            "NORMALIZATION DRY RUN COMPLETE"
        )
    else:
        print(
            "NORMALIZATION COMPLETE"
        )

    print("=" * 72)

    print(
        "Walkthrough:",
        walkthrough_id,
    )

    print(
        "Canonical inventory items:",
        len(
            result.inventory.items
        ),
    )

    print(
        "AUTO_ACCEPTED:",
        auto_accepted,
    )

    print(
        "NEEDS_CONFIRMATION:",
        needs_confirmation,
    )

    print(
        "USER_CONFIRMED:",
        user_confirmed,
    )

    print(
        "Excluded entities:",
        len(
            result.excluded_entities
        ),
    )

    print(
        "Potential duplicate groups:",
        len(
            result.potential_duplicate_groups
        ),
    )

    print()

    print(
        "EXCLUDED ENTITIES"
    )

    print(
        "-" * 72
    )

    if not result.excluded_entities:
        print(
            "(none)"
        )

    for excluded in (
        result.excluded_entities
    ):
        print(
            f"- {excluded.name}: "
            f"{excluded.reason.value}"
        )

        print(
            "    sightings:",
            ", ".join(
                excluded.observation_ids
            ),
        )

        print(
            "    reason:",
            excluded.explanation,
        )

    print()

    print(
        "POTENTIAL DUPLICATE GROUPS"
    )

    print(
        "-" * 72
    )

    if not (
        result.potential_duplicate_groups
    ):
        print(
            "(none)"
        )

    item_lookup = {
        item.id:
            item
        for item
        in result.inventory.items
    }

    for group_index, group in enumerate(
        result.potential_duplicate_groups,
        start=1,
    ):
        print(
            f"Group {group_index}:"
        )

        for item_id in group.item_ids:
            item = (
                item_lookup[
                    item_id
                ]
            )

            print(
                f"    - {item_id}"
            )

            print(
                f"      name: "
                f"{item.name}"
            )

            print(
                f"      location: "
                f"{item.location_hint}"
            )

        print(
            "    reason:",
            group.reason,
        )

    print()

    print(
        "NEEDS CONFIRMATION"
    )

    print(
        "-" * 72
    )

    pending = [
        item
        for item
        in result.inventory.items
        if (
            item.verification_status
            ==
            VerificationStatus
            .NEEDS_CONFIRMATION
        )
    ]

    if not pending:
        print(
            "(none)"
        )

    for item in pending:
        print(
            f"- {item.id}"
        )

        print(
            "    name:",
            item.name,
        )

        print(
            "    confidence:",
            item.source_confidence,
        )

        print(
            "    location:",
            item.location_hint,
        )

        print(
            "    reason:",
            item.uncertainty_reason,
        )

    print()

    print(
        "AUTO-ACCEPTED INVENTORY"
    )

    print(
        "-" * 72
    )

    accepted = [
        item
        for item
        in result.inventory.items
        if (
            item.verification_status
            ==
            VerificationStatus
            .AUTO_ACCEPTED
        )
    ]

    for item in accepted:
        print(
            f"- {item.id}: "
            f"{item.name}"
        )

    print()

    if dry_run:
        print(
            "Dry run only — output not written."
        )
        print(
            "Would save:"
        )
    else:
        print(
            "Saved private canonical inventory:"
        )

    print(
        OUTPUT_PATH
    )

    print()

    print(
        "Model calls:",
        0,
    )


def main() -> None:
    configure_utf8_console()

    args = parse_args()

    walkthrough_id = validate_walkthrough_id(
        args.walkthrough_id
    )

    configure_walkthrough_paths(
        walkthrough_id
    )

    resolution = (
        load_resolution()
    )

    print()
    print("=" * 72)
    print(
        "ZERO WALKTHROUGH INVENTORY NORMALIZATION"
    )
    print("=" * 72)

    print(
        "Walkthrough:",
        walkthrough_id,
    )

    print(
        "Entity-resolution input:",
        ENTITY_RESOLUTION_PATH,
    )

    print(
        "Resolved candidate entities:",
        len(
            resolution.entities
        ),
    )

    print(
        "Model calls:",
        0,
    )

    result = (
        normalize_walkthrough_inventory(
            resolution
        )
    )

    validate_normalization_result(
        source_resolution=resolution,
        result=result,
    )

    if not args.dry_run:
        save_result(
            result
        )

    print_result_summary(
        walkthrough_id=walkthrough_id,
        result=result,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()