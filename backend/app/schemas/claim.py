"""Request and response shapes for claims, their attachments and audit trail.

Ownership, status and timestamps are never read from a request body: the write
models simply have no such fields, so anything sent for them is ignored.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.models.claim import ExpenseCategory


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _text(max_length: int) -> Any:
    return Annotated[str | None, BeforeValidator(_blank_to_none), Field(max_length=max_length)]


Text100 = _text(100)
Text200 = _text(200)
Text1000 = _text(1000)


Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class ClaimLineIn(BaseModel):
    """One line as sent by the client. Every field is optional so drafts can be partial;
    submission enforces the required ones."""

    category: ExpenseCategory | None = None
    amount: Money | None = None
    expense_date: date | None = None
    vendor: Text200 = None
    description: Text1000 = None
    city: Text100 = None
    nights: int | None = Field(default=None, ge=1, le=365)
    receipt_number: Text100 = None
    receipt_id: int | None = Field(
        default=None, description="Id of a receipt already uploaded to this claim."
    )

    @field_validator("expense_date")
    @classmethod
    def not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("expense date cannot be in the future")
        return value


class ClaimWrite(BaseModel):
    """Body for create and update. ``action`` decides draft vs submit."""

    action: Literal["draft", "submit"] = "draft"
    title: Text200 = None
    currency: Literal["INR"] = "INR"
    lines: list[ClaimLineIn] = Field(default_factory=list, max_length=50)


class ClaimLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    category: str | None
    amount: Decimal | None
    expense_date: date | None
    vendor: str | None
    description: str | None
    city: str | None
    nights: int | None
    receipt_number: str | None
    receipt_id: int | None


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str
    uploaded_by: int
    uploaded_at: datetime


class ClaimSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    title: str | None
    currency: str
    status: str
    total_amount: Decimal
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClaimOut(ClaimSummary):
    created_by: int
    updated_by: int
    lines: list[ClaimLineOut]
    attachments: list[AttachmentOut]


class ClaimPage(BaseModel):
    items: list[ClaimSummary]
    total: int
    limit: int
    offset: int


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    action: str
    changes: dict[str, Any]
    actor_id: int
    created_at: datetime
