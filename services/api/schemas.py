from pydantic import BaseModel, Field


class ObjectObservation(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=300)
    location_hint: str = Field(min_length=1, max_length=200)
    potentially_useful: bool
    confidence: float = Field(ge=0.0, le=1.0)


class VisionObservationResponse(BaseModel):
    objects: list[ObjectObservation]
