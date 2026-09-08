from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Vision / perception
# ---------------------------------------------------------------------------


class ObjectObservation(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=300)
    location_hint: str = Field(min_length=1, max_length=200)
    potentially_useful: bool
    confidence: float = Field(ge=0.0, le=1.0)


class VisionObservationResponse(BaseModel):
    objects: list[ObjectObservation]


# ---------------------------------------------------------------------------
# Canonical inventory
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Goal-aware relevance
# ---------------------------------------------------------------------------


class RelevanceLabel(str, Enum):
    RELEVANT = "relevant"
    POSSIBLY_RELEVANT = "possibly_relevant"
    NOT_RELEVANT = "not_relevant"


class GoalInput(BaseModel):
    primary_goal: str = Field(min_length=1, max_length=300)
    budget_dollars: int = Field(ge=0)
    permanent_modifications_allowed: bool


class GoalAwareInventoryItem(BaseModel):
    item_id: str = Field(min_length=1, max_length=100)
    relevance: RelevanceLabel
    reason: str = Field(min_length=1, max_length=300)


class GoalAwareInventoryResponse(BaseModel):
    items: list[GoalAwareInventoryItem]


# ---------------------------------------------------------------------------
# Object DNA
# ---------------------------------------------------------------------------


class CapabilityType(str, Enum):
    SUPPORT = "support"
    ELEVATE = "elevate"
    CONTAIN = "contain"
    COVER = "cover"
    HANG = "hang"
    FASTEN = "fasten"
    ILLUMINATE = "illuminate"
    REFLECT_LIGHT = "reflect_light"
    DIFFUSE_LIGHT = "diffuse_light"
    BLOCK_LIGHT = "block_light"
    ABSORB_SOUND = "absorb_sound"
    DAMPEN_SOUND = "dampen_sound"
    CUSHION = "cushion"
    STACK = "stack"
    FOLD = "fold"
    CUT = "cut"
    ORGANIZE = "organize"
    STABILIZE = "stabilize"
    PROVIDE_WEIGHT = "provide_weight"
    PROVIDE_SURFACE = "provide_surface"
    PROVIDE_POWER_CONNECTION = "provide_power_connection"
    REPOSITION = "reposition"
    DISPENSE_LIQUID = "dispense_liquid"


class EvidenceBasis(str, Enum):
    VISUALLY_OBSERVED = "visually_observed"
    COMMON_PROPERTY = "common_property"
    UNCERTAIN = "uncertain"


class CertaintyLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PhysicalTraitType(str, Enum):
    FLEXIBLE = "flexible"
    RIGID = "rigid"
    SOFT = "soft"
    FLAT = "flat"
    HOLLOW = "hollow"
    FOLDABLE = "foldable"
    STACKABLE = "stackable"
    MOVABLE = "movable"
    WEIGHTED = "weighted"
    LARGE_SURFACE = "large_surface"
    SMALL_SURFACE = "small_surface"
    ELECTRICAL = "electrical"

    # Specific names are intentional.
    # "outlet" previously confused electrical outlets with spray nozzles.
    HAS_ELECTRICAL_OUTLETS = "has_electrical_outlets"
    HAS_NOZZLE = "has_nozzle"

    OPAQUE = "opaque"
    PORTABLE = "portable"

    CAN_HOLD_LIQUID = "can_hold_liquid"
    CAN_DISPENSE_LIQUID = "can_dispense_liquid"


class PhysicalTrait(BaseModel):
    trait: PhysicalTraitType
    evidence_basis: EvidenceBasis
    certainty: CertaintyLevel
    note: str = Field(
        min_length=1,
        max_length=160,
    )


class ObjectAffordance(BaseModel):
    capability: CapabilityType
    description: str = Field(
        min_length=1,
        max_length=200,
    )
    evidence_basis: EvidenceBasis
    certainty: CertaintyLevel


class ObjectDNA(BaseModel):
    item_id: str = Field(
        min_length=1,
        max_length=100,
    )

    physical_traits: list[PhysicalTrait] = Field(
        default_factory=list,
        max_length=6,
    )

    affordances: list[ObjectAffordance] = Field(
        default_factory=list,
        max_length=5,
    )

    unknown_properties: list[str] = Field(
        default_factory=list,
        max_length=4,
    )

    caution_notes: list[str] = Field(
        default_factory=list,
        max_length=3,
    )


class ObjectDNAResponse(BaseModel):
    objects: list[ObjectDNA]