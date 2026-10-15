from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field


class ExtractedTemperature(BaseModel):
    temperature: float | None = Field(
        default=None,
        description="Temperature value mentioned by the user, null if none",
    )
    unit: Annotated[Literal["C", "F"], Field(description="Unit of the temperature")] = (
        "C"
    )


class PlaceMatch(BaseModel):
    country: str
    city: str = Field(description="City or region, '' if unknown")
    temperature_c: float = Field(description="Current temperature in Celsius")


class SearchOutcome(BaseModel):
    matches: list[PlaceMatch]


class PlaceRecommendation(BaseModel):
    place: str
    country: str
    why: str = Field(description="Why this place fits the requested temperature")


class BestPlacesOutcome(BaseModel):
    summary: str
    recommendations: list[PlaceRecommendation]


class AgentState(TypedDict):
    message: str
    temperature: float | None
    unit: str
    candidates: list[dict[str, Any]]
    exact_match: bool
    fallback_used: bool
    summary: str
    recommendations: list[dict[str, str]]
    answer: str
