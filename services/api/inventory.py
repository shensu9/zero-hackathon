import re

from schemas import (
    CanonicalInventory,
    InventoryItem,
    VerificationStatus,
    VisionObservationResponse,
)


CONFIRMATION_THRESHOLD = 0.90


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "object"


def build_canonical_inventory(
    observations: VisionObservationResponse,
) -> CanonicalInventory:
    counters: dict[str, int] = {}
    items: list[InventoryItem] = []

    for observation in observations.objects:
        base_id = slugify(observation.name)

        counters[base_id] = counters.get(base_id, 0) + 1

        object_id = f"{base_id}_{counters[base_id]:02d}"

        needs_confirmation = (
            observation.confidence < CONFIRMATION_THRESHOLD
            or " or " in observation.description.lower()
        )

        if needs_confirmation:
            verification_status = VerificationStatus.NEEDS_CONFIRMATION

            if " or " in observation.description.lower():
                uncertainty_reason = (
                    "The visual description contains an ambiguous identification."
                )
            else:
                uncertainty_reason = (
                    "The visual model reported lower confidence for this object."
                )
        else:
            verification_status = VerificationStatus.AUTO_ACCEPTED
            uncertainty_reason = None

        items.append(
            InventoryItem(
                id=object_id,
                name=observation.name,
                description=observation.description,
                location_hint=observation.location_hint,
                source_confidence=observation.confidence,
                verification_status=verification_status,
                uncertainty_reason=uncertainty_reason,
            )
        )

    return CanonicalInventory(items=items)