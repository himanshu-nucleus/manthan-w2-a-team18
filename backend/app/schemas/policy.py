"""Request and response shapes for the expense policy settings."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Limit = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Threshold = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
CityName = Annotated[str, Field(min_length=1, max_length=100)]


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    receipt_required_above: Decimal = Field(
        description="A line needs a receipt number and an uploaded receipt when both the "
        "claim total and the line amount are above this (INR)."
    )
    meal_daily_limit: Decimal = Field(description="Meal spend allowed per employee per day.")
    hotel_tier1_nightly_limit: Decimal = Field(description="Hotel per night in a tier-1 city.")
    hotel_other_nightly_limit: Decimal = Field(description="Hotel per night in any other city.")
    local_trip_limit: Decimal = Field(description="Local conveyance per trip (one line).")
    tier1_cities: list[str]
    updated_by: int | None
    updated_at: datetime


class PolicyUpdate(BaseModel):
    """Send only the fields to change. Unknown fields and nulls are refused."""

    model_config = ConfigDict(extra="forbid")

    receipt_required_above: Threshold | None = None
    meal_daily_limit: Limit | None = None
    hotel_tier1_nightly_limit: Limit | None = None
    hotel_other_nightly_limit: Limit | None = None
    local_trip_limit: Limit | None = None
    tier1_cities: list[CityName] | None = Field(default=None, max_length=100)

    @field_validator("tier1_cities")
    @classmethod
    def tidy_cities(cls, value: list[str] | None) -> list[str] | None:
        """Trim names and drop case-insensitive repeats, keeping the first spelling."""
        if value is None:
            return None
        seen: set[str] = set()
        cities: list[str] = []
        for city in (name.strip() for name in value):
            if not city:
                raise ValueError("city names cannot be blank")
            if city.casefold() not in seen:
                seen.add(city.casefold())
                cities.append(city)
        return cities

    @model_validator(mode="after")
    def no_explicit_nulls(self) -> PolicyUpdate:
        nulls = [name for name in self.model_fields_set if getattr(self, name) is None]
        if nulls:
            raise ValueError(f"these fields cannot be null: {', '.join(sorted(nulls))}")
        return self

    def changes(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.model_fields_set}
