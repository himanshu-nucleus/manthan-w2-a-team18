"""Shapes for approver actions, approval steps, the pending queue, comments and delegations."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.claim import ClaimSummary


class _Action(BaseModel):
    step_id: int | None = Field(
        default=None,
        description="The step being decided. If it is no longer the current step, 409. "
        "Send it so a double click or retry can never decide a later step.",
    )


class ApproveRequest(_Action):
    comment: str | None = Field(default=None, max_length=2000)


class DecisionRequest(_Action):
    """Reject and send back: a comment is mandatory."""

    comment: str = Field(min_length=1, max_length=2000)


class ApprovalStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    round: int
    step_order: int
    approver_role: str
    assigned_approver_id: int | None = Field(
        description="Named approver; null means any active user with approver_role."
    )
    status: str
    acted_by_id: int | None
    on_behalf_of_id: int | None
    acted_at: datetime | None
    comment: str | None
    created_at: datetime


class PendingItem(BaseModel):
    step: ApprovalStepOut
    claim: ClaimSummary
    on_behalf_of_id: int | None = Field(
        description="Set when this item reaches you through a delegation."
    )


class PendingPage(BaseModel):
    items: list[PendingItem]
    total: int
    limit: int
    offset: int


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    author_id: int
    body: str
    created_at: datetime


class DelegationCreate(BaseModel):
    delegate_id: int
    from_date: date
    to_date: date
    reason: str | None = Field(default=None, max_length=500)


class DelegationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    delegator_id: int
    delegate_id: int
    from_date: date
    to_date: date
    reason: str | None
    active: bool
    created_at: datetime
    cancelled_at: datetime | None
