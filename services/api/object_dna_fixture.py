from schemas import (
    CanonicalInventory,
    InventoryItem,
    VerificationStatus,
)


OBJECT_DNA_FIXTURE = CanonicalInventory(
    items=[
        InventoryItem(
            id="office_chair_01",
            name="office chair",
            description="Black wheeled office chair with a high back and seat.",
            location_hint="test environment",
            source_confidence=1.0,
            verification_status=VerificationStatus.USER_CONFIRMED,
            uncertainty_reason=None,
        ),
        InventoryItem(
            id="blanket_01",
            name="blanket",
            description="Large thick beige comforter that can be folded.",
            location_hint="test environment",
            source_confidence=1.0,
            verification_status=VerificationStatus.USER_CONFIRMED,
            uncertainty_reason=None,
        ),
        InventoryItem(
            id="books_01",
            name="books",
            description="Several hardcover and paperback books arranged in a stack.",
            location_hint="test environment",
            source_confidence=1.0,
            verification_status=VerificationStatus.USER_CONFIRMED,
            uncertainty_reason=None,
        ),
        InventoryItem(
            id="power_strip_01",
            name="power strip",
            description="Electrical power strip with multiple outlet sockets.",
            location_hint="test environment",
            source_confidence=1.0,
            verification_status=VerificationStatus.USER_CONFIRMED,
            uncertainty_reason=None,
        ),
        InventoryItem(
            id="spray_bottles_01",
            name="spray bottles",
            description="Two handheld spray bottles with unknown liquid contents.",
            location_hint="test environment",
            source_confidence=1.0,
            verification_status=VerificationStatus.USER_CONFIRMED,
            uncertainty_reason=None,
        ),
    ]
)