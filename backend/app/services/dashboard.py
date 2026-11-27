"""Finance dashboard summary, built only from existing claims, policy and approval data.

Rules:
- A claim's month is the India (IST, UTC+05:30) calendar month of ``submitted_at``.
- "Counted" claims are those the policy engine counts (``app.policy.rules.NOT_COUNTED``
  excluded: drafts, rejected, auto-rejected and duplicates). Spend, claim counts,
  violations and categories use counted claims only.
- Approval time: submit -> the last APPROVED step of the claim's current round, for
  claims whose final approval falls in the month. Auto-approved claims have no steps
  and are left out.
- Ready for payout: every APPROVED or AUTO_APPROVED claim (no payout batches exist yet).
- Spend by department is always empty until users get a department.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ApprovalStep,
    AuditAction,
    AuditEvent,
    Claim,
    ClaimLine,
    ClaimPolicyResult,
    ClaimStatus,
    Role,
    StepStatus,
    User,
)
from app.models.policy import BREACH_OUTCOMES
from app.policy import engine
from app.policy.rules import NOT_COUNTED
from app.schemas.dashboard import (
    AmountKpi,
    ApprovalTimeKpi,
    CategorySpend,
    CountKpi,
    DashboardSummary,
    FinanceEvent,
    HighValueClaim,
    HighValuePending,
    Kpis,
    MonthSpend,
    NeedsAction,
    PayoutKpi,
    ViolationsKpi,
)
from app.services import approvals

IST = timezone(timedelta(hours=5, minutes=30), "IST")
CENTS = Decimal("0.01")
NOT_COUNTED_VALUES = [status.value for status in NOT_COUNTED]
PAYABLE = (ClaimStatus.APPROVED.value, ClaimStatus.AUTO_APPROVED.value)
FINANCE_EVENT_ACTIONS = (
    AuditAction.APPROVED,
    AuditAction.REJECTED,
    AuditAction.SENT_BACK,
    AuditAction.STEP_APPROVED,
    AuditAction.POLICY_RULE_UPDATED,
)
RECENT_EVENTS = 10
HIGH_VALUE_SHOWN = 5


def current_month() -> date:
    return datetime.now(UTC).astimezone(IST).date().replace(day=1)


def summary(db: Session, user: User, month: date) -> DashboardSummary:
    """``month`` is the first day of the month to summarise."""
    previous = _add_months(month, -1)
    this_claims = _counted_claim_ids(db, month)
    previous_claims = _counted_claim_ids(db, previous)

    return DashboardSummary(
        month=month.strftime("%Y-%m"),
        generated_at=datetime.now(UTC),
        active_employees=db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.EMPLOYEE.value, User.is_active)
        )
        or 0,
        kpis=Kpis(
            claims=CountKpi(value=len(this_claims), previous=len(previous_claims)),
            total_spend=AmountKpi(
                value=_claims_total(db, this_claims), previous=_claims_total(db, previous_claims)
            ),
            policy_violations=_violations(db, this_claims, previous_claims),
            approval_time=_approval_time(db, month, previous),
            ready_for_payout=_ready_for_payout(db),
        ),
        needs_action=NeedsAction(
            my_pending_approvals=approvals.pending_for(db, user, limit=1, offset=0)[1],
            high_value_pending=_high_value_pending(db),
        ),
        monthly_spend=_monthly_spend(db, month.year),
        spend_by_category=_spend_by_category(db, this_claims),
        spend_by_department=[],
        recent_events=_recent_events(db),
    )


# --- months ------------------------------------------------------------------


def _add_months(month: date, delta: int) -> date:
    index = month.year * 12 + month.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


def _bounds(month: date) -> tuple[datetime, datetime]:
    """[start, end) of an IST calendar month, in UTC."""
    start = datetime(month.year, month.month, 1, tzinfo=IST)
    end_month = _add_months(month, 1)
    end = datetime(end_month.year, end_month.month, 1, tzinfo=IST)
    return start.astimezone(UTC), end.astimezone(UTC)


def _ist_month(moment: datetime) -> date:
    """IST month of a stored timestamp (SQLite returns naive values, stored as UTC)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(IST).date().replace(day=1)


def _money(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(CENTS)


# --- KPIs --------------------------------------------------------------------


def _counted_claim_ids(db: Session, month: date) -> list[int]:
    start, end = _bounds(month)
    return list(
        db.scalars(
            select(Claim.id).where(
                Claim.submitted_at >= start,
                Claim.submitted_at < end,
                Claim.status.not_in(NOT_COUNTED_VALUES),
            )
        )
    )


def _claims_total(db: Session, claim_ids: list[int]) -> Decimal:
    if not claim_ids:
        return _money(0)
    return _money(db.scalar(select(func.sum(Claim.total_amount)).where(Claim.id.in_(claim_ids))))


def _violating_lines(db: Session, claim_ids: list[int]) -> int:
    """Lines of the claims' current round with at least one breach finding."""
    if not claim_ids:
        return 0
    return (
        db.scalar(
            select(func.count())
            .select_from(ClaimPolicyResult)
            .join(Claim, Claim.id == ClaimPolicyResult.claim_id)
            .where(
                ClaimPolicyResult.claim_id.in_(claim_ids),
                ClaimPolicyResult.round == Claim.submission_round,
                ClaimPolicyResult.line_position.is_not(None),
                ClaimPolicyResult.outcome.in_(BREACH_OUTCOMES),
            )
        )
        or 0
    )


def _violations(db: Session, this_claims: list[int], previous_claims: list[int]) -> ViolationsKpi:
    lines = _violating_lines(db, this_claims)
    total_lines = (
        db.scalar(
            select(func.count()).select_from(ClaimLine).where(ClaimLine.claim_id.in_(this_claims))
        )
        if this_claims
        else 0
    ) or 0
    return ViolationsKpi(
        lines=lines,
        total_lines=total_lines,
        rate_percent=round(lines * 100 / total_lines, 1) if total_lines else 0.0,
        previous_lines=_violating_lines(db, previous_claims),
    )


def _approval_time(db: Session, month: date, previous: date) -> ApprovalTimeKpi:
    rows = db.execute(
        select(Claim.submitted_at, func.max(ApprovalStep.acted_at))
        .join(ApprovalStep, ApprovalStep.claim_id == Claim.id)
        .where(
            Claim.status == ClaimStatus.APPROVED.value,
            ApprovalStep.round == Claim.submission_round,
            ApprovalStep.status == StepStatus.APPROVED.value,
        )
        .group_by(Claim.id, Claim.submitted_at)
    ).all()

    hours: dict[date, list[float]] = defaultdict(list)
    for submitted_at, approved_at in rows:
        if submitted_at is None or approved_at is None:
            continue
        hours[_ist_month(approved_at)].append((approved_at - submitted_at).total_seconds() / 3600)

    def average(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 1) if values else None

    return ApprovalTimeKpi(
        average_hours=average(hours[month]),
        previous_average_hours=average(hours[previous]),
        approved_claims=len(hours[month]),
    )


def _ready_for_payout(db: Session) -> PayoutKpi:
    count, amount = db.execute(
        select(func.count(), func.sum(Claim.total_amount)).where(Claim.status.in_(PAYABLE))
    ).one()
    return PayoutKpi(claims=count or 0, amount=_money(amount))


# --- needs action ------------------------------------------------------------


def _high_value_pending(db: Session) -> HighValuePending:
    threshold = engine.load_config(db).approval_thresholds.get(
        Role.FINANCE_HEAD.value, Decimal("100000")
    )
    conditions = (
        Claim.status == ClaimStatus.PENDING_APPROVAL.value,
        Claim.total_amount > threshold,
    )
    count = db.scalar(select(func.count()).select_from(Claim).where(*conditions)) or 0
    rows = db.execute(
        select(Claim, User.full_name)
        .join(User, User.id == Claim.employee_id)
        .where(*conditions)
        .order_by(Claim.total_amount.desc(), Claim.id)
        .limit(HIGH_VALUE_SHOWN)
    ).all()
    return HighValuePending(
        threshold=_money(threshold),
        count=count,
        claims=[
            HighValueClaim(
                id=claim.id,
                title=claim.title,
                employee_id=claim.employee_id,
                employee_name=name,
                total_amount=_money(claim.total_amount),
            )
            for claim, name in rows
        ],
    )


# --- charts and events ---------------------------------------------------------


def _monthly_spend(db: Session, year: int) -> list[MonthSpend]:
    start, _ = _bounds(date(year, 1, 1))
    _, end = _bounds(date(year, 12, 1))
    totals: dict[date, list[Decimal]] = defaultdict(list)
    for submitted_at, amount in db.execute(
        select(Claim.submitted_at, Claim.total_amount).where(
            Claim.submitted_at >= start,
            Claim.submitted_at < end,
            Claim.status.not_in(NOT_COUNTED_VALUES),
        )
    ):
        totals[_ist_month(submitted_at)].append(Decimal(amount))

    months = [date(year, number, 1) for number in range(1, 13)]
    return [
        MonthSpend(
            month=month.strftime("%Y-%m"),
            claims=len(totals[month]),
            amount=_money(sum(totals[month], Decimal(0))),
        )
        for month in months
    ]


def _spend_by_category(db: Session, claim_ids: list[int]) -> list[CategorySpend]:
    if not claim_ids:
        return []
    rows = db.execute(
        select(ClaimLine.category, func.sum(ClaimLine.amount))
        .where(ClaimLine.claim_id.in_(claim_ids), ClaimLine.category.is_not(None))
        .group_by(ClaimLine.category)
    ).all()
    spend = [CategorySpend(category=category, amount=_money(total)) for category, total in rows]
    return sorted(spend, key=lambda item: (-item.amount, item.category))


def _recent_events(db: Session) -> list[FinanceEvent]:
    rows = db.execute(
        select(AuditEvent, User.full_name)
        .join(User, User.id == AuditEvent.actor_id)
        .where(AuditEvent.action.in_([action.value for action in FINANCE_EVENT_ACTIONS]))
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(RECENT_EVENTS)
    ).all()
    return [
        FinanceEvent(
            id=event.id,
            created_at=event.created_at,
            actor_id=event.actor_id,
            actor_name=name,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
        )
        for event, name in rows
    ]
