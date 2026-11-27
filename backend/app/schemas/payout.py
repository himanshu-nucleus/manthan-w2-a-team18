"""Shapes for payout previews, batches and their items."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BatchCreate(BaseModel):
    """Either ``{"range": "TODAY"}`` or ``{"fromDate": ..., "toDate": ...}`` (IST days,
    inclusive, on the claim's approval date)."""

    model_config = ConfigDict(populate_by_name=True)

    range: Literal["TODAY"] | None = None
    from_date: date | None = Field(default=None, alias="fromDate")
    to_date: date | None = Field(default=None, alias="toDate")


class EligibleClaim(BaseModel):
    claim_id: int
    claim_code: str
    employee_id: int
    employee_code: str
    beneficiary_name: str
    department: str | None
    status: str
    approved_at: datetime
    amount: Decimal


class EligiblePreview(BaseModel):
    from_date: date
    to_date: date
    claim_count: int
    total_amount: Decimal
    claims: list[EligibleClaim]


class BatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_reference: str
    from_date: date
    to_date: date
    value_date: date
    claim_count: int
    total_amount: Decimal
    currency: str
    status: str
    file_name: str
    export_count: int
    first_exported_at: datetime | None
    created_by: int
    created_at: datetime


class BatchItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_reference: str
    claim_id: int
    claim_code: str
    employee_id: int
    employee_code: str
    beneficiary_name: str
    department: str | None
    amount: Decimal
    narration: str


class BatchDetail(BatchSummary):
    items: list[BatchItemOut]


class BatchPage(BaseModel):
    items: list[BatchSummary]
    total: int
    limit: int
    offset: int
