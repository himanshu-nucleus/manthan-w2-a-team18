"""Shape of the finance dashboard summary (F1 finance overview screen)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AmountKpi(BaseModel):
    value: Decimal = Field(description="INR, this month.")
    previous: Decimal = Field(description="INR, the month before.")


class CountKpi(BaseModel):
    value: int
    previous: int


class ViolationsKpi(BaseModel):
    lines: int = Field(description="Claim lines with at least one policy breach this month.")
    total_lines: int = Field(description="All lines of this month's counted claims.")
    rate_percent: float = Field(description="lines / total_lines x 100, one decimal; 0 if none.")
    previous_lines: int


class ApprovalTimeKpi(BaseModel):
    average_hours: float | None = Field(
        description="Submit -> final approval, averaged over claims fully approved this month "
        "(by a person; auto-approved claims excluded). Null when there were none."
    )
    previous_average_hours: float | None
    approved_claims: int = Field(description="Claims the average is over.")


class PayoutKpi(BaseModel):
    claims: int = Field(description="APPROVED + AUTO_APPROVED claims (all months).")
    amount: Decimal = Field(description="Their total, INR. Payout batches do not exist yet.")


class Kpis(BaseModel):
    claims: CountKpi
    total_spend: AmountKpi
    policy_violations: ViolationsKpi
    approval_time: ApprovalTimeKpi
    ready_for_payout: PayoutKpi


class HighValueClaim(BaseModel):
    id: int
    title: str | None
    employee_id: int
    employee_name: str
    total_amount: Decimal


class HighValuePending(BaseModel):
    threshold: Decimal = Field(description="The finance_head approval threshold (INR).")
    count: int
    claims: list[HighValueClaim] = Field(description="Largest first, at most 5.")


class NeedsAction(BaseModel):
    my_pending_approvals: int = Field(
        description="Approval steps waiting on the caller (same rule as GET /approvals/pending)."
    )
    high_value_pending: HighValuePending = Field(
        description="Claims awaiting approval with a total above the finance_head threshold."
    )


class MonthSpend(BaseModel):
    month: str = Field(description="YYYY-MM")
    claims: int
    amount: Decimal


class CategorySpend(BaseModel):
    category: str
    amount: Decimal


class DepartmentSpend(BaseModel):
    department: str
    amount: Decimal


class FinanceEvent(BaseModel):
    id: int
    created_at: datetime
    actor_id: int
    actor_name: str
    action: str = Field(description="Audit action, e.g. APPROVED, REJECTED, POLICY_RULE_UPDATED.")
    entity_type: str
    entity_id: int


class DashboardSummary(BaseModel):
    month: str = Field(description="The month summarised, YYYY-MM (India time).")
    generated_at: datetime
    active_employees: int = Field(description="Active users with the employee role.")
    kpis: Kpis
    needs_action: NeedsAction
    monthly_spend: list[MonthSpend] = Field(description="January to December of the month's year.")
    spend_by_category: list[CategorySpend] = Field(description="This month, largest first.")
    spend_by_department: list[DepartmentSpend] = Field(
        description="Always empty for now: users have no department yet."
    )
    recent_events: list[FinanceEvent] = Field(description="Latest 10 finance events, newest first.")
