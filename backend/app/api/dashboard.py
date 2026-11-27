"""Finance dashboard: one summary call for the F1 finance overview screen."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.database import get_db
from app.models import Role, User
from app.schemas.dashboard import DashboardSummary
from app.schemas.errors import error_responses
from app.services import dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

finance_only = require_role(Role.FINANCE_AUDITOR, Role.FINANCE_HEAD)


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Finance overview for one month: KPIs, my actions, spend charts, recent events "
    "(finance_auditor and finance_head only)",
    responses=error_responses(401, 403, 422),
)
def get_dashboard_summary(
    month: str | None = Query(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="YYYY-MM (India time); defaults to the current month.",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(finance_only),
) -> DashboardSummary:
    """Spend, claim counts and violations cover counted claims (not draft, rejected,
    auto-rejected or duplicate) submitted in the month. Each KPI carries the previous
    month for the "vs last month" figure. `ready_for_payout` is every approved or
    auto-approved claim, since payout batches do not exist yet. `spend_by_department` is
    always empty until users have a department."""
    selected = date(int(month[:4]), int(month[5:7]), 1) if month else dashboard.current_month()
    return dashboard.summary(db, user, selected)
