"""System-wide audit search and hash-chain check. Read only: audit rows are written by the
system alone, so there is no create, update or delete endpoint."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.database import get_db
from app.models import Role, User
from app.schemas.claim import AuditEventOut
from app.schemas.errors import error_responses
from app.services import audit

router = APIRouter(prefix="/audit-logs", tags=["audit"])

finance_only = require_role(Role.FINANCE_HEAD, Role.FINANCE_AUDITOR)
finance_head_only = require_role(Role.FINANCE_HEAD)


class AuditPage(BaseModel):
    items: list[AuditEventOut]
    total: int
    limit: int
    offset: int


class ChainReportOut(BaseModel):
    checked: int
    valid: bool
    unchained_rows: int
    first_broken_id: int | None
    problem: str | None


@router.get(
    "",
    response_model=AuditPage,
    summary="Search the whole audit trail, newest first (finance_head, finance_auditor)",
    responses=error_responses(401, 403, 422),
)
def search_audit_logs(
    entity_type: str | None = Query(default=None, alias="entityType", max_length=32),
    action: str | None = Query(default=None, max_length=32),
    actor_id: int | None = Query(default=None, alias="actorId"),
    claim_id: int | None = Query(default=None, alias="claimId"),
    from_date: date | None = Query(default=None, alias="fromDate"),
    to_date: date | None = Query(default=None, alias="toDate"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(finance_only),
) -> AuditPage:
    """Dates are IST days, both inclusive. `entityType` and `action` match case-insensitively
    (`claim`, `approval_step`, `claim_attachment`, `delegation`, `policy_rule`, `payout_batch`,
    `user`, ...). Includes ACCESS_DENIED and LOGIN_FAILED rows."""
    rows, total = audit.search(
        db,
        entity_type=entity_type,
        action=action,
        actor_id=actor_id,
        claim_id=claim_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return AuditPage(
        items=[AuditEventOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/verify",
    response_model=ChainReportOut,
    summary="Recompute the audit hash chain and report the first broken row (finance_head)",
    responses=error_responses(401, 403),
)
def verify_audit_chain(
    db: Session = Depends(get_db),
    _: User = Depends(finance_head_only),
) -> ChainReportOut:
    report = audit.verify_chain(db)
    return ChainReportOut(**report.__dict__)
