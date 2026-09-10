import json
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


REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

ENTITY_RESOLUTION_PATH = (
    REPO_ROOT
    / "sample_data"
    / "private"
    / "walkthrough-01-entity-resolution.json"
)

OUTPUT_PATH = (
    REPO_ROOT
    / "sample_data"
    / "private"
    / "walkthrough-01-canonical-inventory.json"
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


def main() -> None:
    configure_utf8_console()

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
        "Resolved candidate entities:",
        len(
            resolution.entities
        ),
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

    save_result(
        result
    )

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
    print(
        "NORMALIZATION COMPLETE"
    )
    print("=" * 72)

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

    print(
        "Saved private canonical inventory:"
    )

    print(
        OUTPUT_PATH
    )


if __name__ == "__main__":
    main()