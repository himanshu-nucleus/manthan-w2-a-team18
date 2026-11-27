"""Payout batches (finance head and finance auditor only). Rules: ``app.services.payouts``."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.database import get_db
from app.models import PayoutBatch, Role, User
from app.schemas.errors import error_responses
from app.schemas.payout import (
    BatchCreate,
    BatchDetail,
    BatchPage,
    BatchSummary,
    EligibleClaim,
    EligiblePreview,
)
from app.services import payouts

router = APIRouter(prefix="/payouts", tags=["payouts"])

finance_only = require_role(Role.FINANCE_HEAD, Role.FINANCE_AUDITOR)


@router.get(
    "/eligible-claims",
    response_model=EligiblePreview,
    summary="Preview the claims a batch would pay for a date range or TODAY; changes nothing "
    "(finance_head, finance_auditor)",
    responses=error_responses(400, 401, 403, 409, 422),
)
def preview_eligible_claims(
    range_name: Literal["TODAY"] | None = Query(default=None, alias="range"),
    from_date: date | None = Query(default=None, alias="fromDate"),
    to_date: date | None = Query(default=None, alias="toDate"),
    db: Session = Depends(get_db),
    _: User = Depends(finance_only),
) -> EligiblePreview:
    result = payouts.preview(db, range_name, from_date, to_date)
    employees = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_({c.employee_id for c in result.claims})))
    }
    return EligiblePreview(
        from_date=result.from_date,
        to_date=result.to_date,
        claim_count=len(result.claims),
        total_amount=result.total,
        claims=[
            EligibleClaim(
                claim_id=c.id,
                claim_code=payouts.claim_code(c.id),
                employee_id=c.employee_id,
                employee_code=payouts.employee_code(c.employee_id),
                beneficiary_name=employees[c.employee_id].full_name,
                department=employees[c.employee_id].department,
                status=c.status,
                approved_at=c.approved_at,  # type: ignore[arg-type]
                amount=payouts.payable_amount(c).quantize(payouts.CENTS),
            )
            for c in result.claims
        ],
    )


@router.post(
    "/batches",
    response_model=BatchSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a batch with every eligible claim in the range and mark them PAID "
    "(finance_head, finance_auditor)",
    responses=error_responses(400, 401, 403, 409, 422),
)
def create_payout_batch(
    body: BatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(finance_only),
) -> PayoutBatch:
    return payouts.create_batch(db, user, body.range, body.from_date, body.to_date)


@router.get(
    "/batches",
    response_model=BatchPage,
    summary="List payout batches, newest first (finance_head, finance_auditor)",
    responses=error_responses(401, 403, 422),
)
def list_payout_batches(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(finance_only),
) -> BatchPage:
    rows, total = payouts.list_batches(db, limit=limit, offset=offset)
    return BatchPage(
        items=[BatchSummary.model_validate(b) for b in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/batches/{batch_id}",
    response_model=BatchDetail,
    summary="One payout batch with its claims (finance_head, finance_auditor)",
    responses=error_responses(401, 403, 404, 422),
)
def get_payout_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(finance_only),
) -> PayoutBatch:
    return payouts.get_batch(db, batch_id)


@router.get(
    "/batches/{batch_id}/export",
    response_class=Response,
    summary="Download the batch's mock bank file as CSV; every download is audited "
    "(finance_head, finance_auditor)",
    responses={
        200: {"content": {"text/csv": {}}, "description": "The CSV file"},
        **error_responses(401, 403, 404, 422),
    },
)
def export_payout_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(finance_only),
) -> Response:
    batch, content = payouts.export_batch(db, user, batch_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{batch.file_name}"'},
    )
