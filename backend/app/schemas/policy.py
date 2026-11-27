"""Shapes for policy rules and policy results."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PolicyRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    category: str | None
    rule_type: str
    params: dict[str, Any]
    outcome_on_breach: str
    active: bool
    reason_template: str
    updated_at: datetime
    updated_by: int | None


class PolicyRuleUpdate(BaseModel):
    """Send only what changes. ``params`` replaces the whole params object."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    params: dict[str, Any] | None = None
    outcome_on_breach: Literal["ROUTE_FOR_APPROVAL", "AUTO_REJECT", "MARK_DUPLICATE"] | None = None
    active: bool | None = None
    reason_template: str | None = Field(default=None, min_length=1, max_length=500)


class PolicyFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_position: int | None = Field(
        description="1-based line position; null for a finding about the whole claim."
    )
    outcome: str
    rule_codes: list[str]
    reasons: list[str]
    rule_snapshot: dict[str, Any]
    evaluated_at: datetime


class PolicyResultsOut(BaseModel):
    claim_id: int
    round: int
    outcome: str | None
    evaluated_at: datetime | None
    lines: list[PolicyFindingOut]
    claim_level: list[PolicyFindingOut]
