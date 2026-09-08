from pydantic import BaseModel, Field
from enum import Enum


class VerificationStatus(str, Enum):
    AUTO_ACCEPTED = "auto_accepted"
    NEEDS_CONFIRMATION = "needs_confirmation"
    USER_CONFIRMED = "user_confirmed"


class InventoryItem(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=300)
    location_hint: str = Field(min_length=1, max_length=200)

    source_confidence: float = Field(ge=0.0, le=1.0)

    verification_status: VerificationStatus

    uncertainty_reason: str | None = Field(
        default=None,
        max_length=300,
    )


class CanonicalInventory(BaseModel):
    items: list[InventoryItem]


class ObjectObservation(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=300)
    location_hint: str = Field(min_length=1, max_length=200)
    potentially_useful: bool
    confidence: float = Field(ge=0.0, le=1.0)


class VisionObservationResponse(BaseModel):
    objects: list[ObjectObservation]
