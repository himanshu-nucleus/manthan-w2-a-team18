"""Rule types (strategy pattern). Each class checks one kind of rule against a claim.

An evaluator returns ``Breach`` objects carrying the values for the rule's
``reason_template``; it never decides the outcome, which comes from the rule row.
Limits come from the rule's ``params``, validated by the evaluator's ``Params`` model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Claim, ClaimAttachment, ClaimLine, ClaimStatus, PolicyRule

CENTS = Decimal("0.01")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# Other claims whose spend still counts against daily limits and split detection.
NOT_COUNTED = (
    ClaimStatus.DRAFT,
    ClaimStatus.REJECTED,
    ClaimStatus.AUTO_REJECTED,
    ClaimStatus.DUPLICATE,
)


def money(value: Decimal) -> str:
    return f"{value.quantize(CENTS):,}"


def day(value: date) -> str:
    return value.strftime("%d-%b-%Y")


def normalise(text: str | None) -> str:
    return " ".join((text or "").lower().split())


@dataclass(frozen=True)
class LineView:
    """A claim line as the rules see it, with the server-computed receipt hash."""

    position: int
    category: str | None
    amount: Decimal | None
    expense_date: date | None
    vendor: str | None
    city: str | None
    nights: int | None
    receipt_number: str | None
    receipt_id: int | None
    receipt_sha256: str | None


@dataclass(frozen=True)
class PolicyConfig:
    tier1_cities: frozenset[str]
    approval_thresholds: dict[str, Decimal]
    auto_approve_max_total: Decimal


@dataclass
class EvaluationContext:
    db: Session
    claim: Claim
    lines: list[LineView]
    config: PolicyConfig
    now: datetime = field(default_factory=lambda: datetime.now(UTC))

    def lines_for(self, category: str | None) -> list[LineView]:
        return [line for line in self.lines if category is None or line.category == category]


@dataclass(frozen=True)
class Breach:
    """``line_position`` None means the finding is about the whole claim."""

    line_position: int | None
    values: dict[str, Any]


class RuleType(ABC):
    rule_type: ClassVar[str]
    Params: ClassVar[type[BaseModel]]
    # Placeholders a reason_template may use for this rule type.
    placeholders: ClassVar[frozenset[str]]

    @abstractmethod
    def evaluate(self, ctx: EvaluationContext, rule: PolicyRule, params: Any) -> list[Breach]: ...


REGISTRY: dict[str, RuleType] = {}


def register(cls: type[RuleType]) -> type[RuleType]:
    REGISTRY[cls.rule_type] = cls()
    return cls


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LimitParams(_Params):
    limit: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


LINE_PLACEHOLDERS = frozenset({"line", "amount", "date"})


def _line_values(line: LineView) -> dict[str, Any]:
    return {
        "line": line.position,
        "amount": money(line.amount) if line.amount is not None else "",
        "date": day(line.expense_date) if line.expense_date else "",
    }


@register
class DailyCategoryLimit(RuleType):
    """Total of one category per calendar day, across this claim and the employee's
    other counted claims, must not exceed ``limit``."""

    rule_type = "DAILY_CATEGORY_LIMIT"
    Params = LimitParams
    placeholders = LINE_PLACEHOLDERS | {"total", "limit"}

    def evaluate(
        self, ctx: EvaluationContext, rule: PolicyRule, params: LimitParams
    ) -> list[Breach]:
        lines = [
            line
            for line in ctx.lines_for(rule.category)
            if line.amount is not None and line.expense_date is not None
        ]
        if not lines:
            return []
        by_date: dict[date, Decimal] = defaultdict(Decimal)
        for line in lines:
            by_date[line.expense_date] += line.amount  # type: ignore[index, operator]

        other = ctx.db.execute(
            select(ClaimLine.expense_date, func.sum(ClaimLine.amount))
            .join(Claim, Claim.id == ClaimLine.claim_id)
            .where(
                Claim.employee_id == ctx.claim.employee_id,
                Claim.id != ctx.claim.id,
                Claim.status.not_in([s.value for s in NOT_COUNTED]),
                ClaimLine.category == rule.category,
                ClaimLine.expense_date.in_(list(by_date)),
            )
            .group_by(ClaimLine.expense_date)
        )
        for expense_date, amount in other:
            by_date[expense_date] += Decimal(amount or 0)

        return [
            Breach(
                line.position,
                {
                    **_line_values(line),
                    "total": money(by_date[line.expense_date]),  # type: ignore[index]
                    "limit": money(params.limit),
                },
            )
            for line in lines
            if by_date[line.expense_date] > params.limit  # type: ignore[index]
        ]


class PerNightParams(LimitParams):
    city_tier: Literal["tier1", "other"]


@register
class PerNightLimit(RuleType):
    """Amount per night must not exceed ``limit`` for lines whose city is in ``city_tier``.
    The tier is derived from the configured tier-1 city list, never from the client."""

    rule_type = "PER_NIGHT_LIMIT"
    Params = PerNightParams
    placeholders = LINE_PLACEHOLDERS | {"per_night", "city", "nights", "limit"}

    def evaluate(
        self, ctx: EvaluationContext, rule: PolicyRule, params: PerNightParams
    ) -> list[Breach]:
        breaches = []
        for line in ctx.lines_for(rule.category):
            if line.amount is None or not line.nights or not line.city:
                continue
            tier = "tier1" if normalise(line.city) in ctx.config.tier1_cities else "other"
            if tier != params.city_tier:
                continue
            if line.amount > params.limit * line.nights:
                breaches.append(
                    Breach(
                        line.position,
                        {
                            **_line_values(line),
                            "per_night": money(line.amount / line.nights),
                            "city": line.city,
                            "nights": line.nights,
                            "limit": money(params.limit),
                        },
                    )
                )
        return breaches


@register
class PerLineLimit(RuleType):
    """A single line must not exceed ``limit`` (for example one cab trip)."""

    rule_type = "PER_LINE_LIMIT"
    Params = LimitParams
    placeholders = LINE_PLACEHOLDERS | {"limit"}

    def evaluate(
        self, ctx: EvaluationContext, rule: PolicyRule, params: LimitParams
    ) -> list[Breach]:
        return [
            Breach(line.position, {**_line_values(line), "limit": money(params.limit)})
            for line in ctx.lines_for(rule.category)
            if line.amount is not None and line.amount > params.limit
        ]


class ReceiptParams(_Params):
    above: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


@register
class ReceiptRequired(RuleType):
    """Above ``above``, a line needs an uploaded receipt and a receipt number.
    Submit validation already enforces this; the rule is a second line of defence."""

    rule_type = "RECEIPT_REQUIRED"
    Params = ReceiptParams
    placeholders = LINE_PLACEHOLDERS | {"above"}

    def evaluate(
        self, ctx: EvaluationContext, rule: PolicyRule, params: ReceiptParams
    ) -> list[Breach]:
        return [
            Breach(line.position, {**_line_values(line), "above": money(params.above)})
            for line in ctx.lines_for(rule.category)
            if line.amount is not None
            and line.amount > params.above
            and (not line.receipt_sha256 or not line.receipt_number)
        ]


class NoParams(_Params):
    pass


@register
class DuplicateLine(RuleType):
    """Same vendor + amount + date as an earlier line of this claim, or as any line of
    the same employee's other non-draft claims. Vendor is compared case- and space-insensitively."""

    rule_type = "DUPLICATE_LINE"
    Params = NoParams
    placeholders = LINE_PLACEHOLDERS | {"match"}

    def evaluate(self, ctx: EvaluationContext, rule: PolicyRule, params: NoParams) -> list[Breach]:
        lines = [
            line
            for line in ctx.lines_for(rule.category)
            if line.amount is not None and line.expense_date is not None and normalise(line.vendor)
        ]
        if not lines:
            return []

        earlier: dict[tuple[str, Decimal, date], str] = {}
        rows = ctx.db.execute(
            select(
                Claim.id,
                ClaimLine.position,
                ClaimLine.vendor,
                ClaimLine.amount,
                ClaimLine.expense_date,
            )
            .join(Claim, Claim.id == ClaimLine.claim_id)
            .where(
                Claim.employee_id == ctx.claim.employee_id,
                Claim.id != ctx.claim.id,
                Claim.status != ClaimStatus.DRAFT.value,
                ClaimLine.expense_date.in_({line.expense_date for line in lines}),
                ClaimLine.amount.in_({line.amount for line in lines}),
            )
            .order_by(Claim.id, ClaimLine.position)
        )
        for claim_id, position, vendor, amount, expense_date in rows:
            key = (normalise(vendor), Decimal(amount), expense_date)
            earlier.setdefault(key, f"line {position} of claim #{claim_id}")

        breaches = []
        for line in lines:
            key = (normalise(line.vendor), line.amount, line.expense_date)
            if key in earlier:
                breaches.append(
                    Breach(line.position, {**_line_values(line), "match": earlier[key]})
                )
            else:
                earlier[key] = f"line {line.position} of this claim"
        return breaches


@register
class DuplicateReceiptNumber(RuleType):
    """Same vendor + amount + receipt number as a line on any other counted claim (any
    employee), or as an earlier line of this claim. Vendor and receipt number are compared
    case- and space-insensitively. The team's duplicate rule: its outcome is MARK_DUPLICATE."""

    rule_type = "DUPLICATE_RECEIPT_NUMBER"
    Params = NoParams
    placeholders = LINE_PLACEHOLDERS | {"match"}

    def evaluate(self, ctx: EvaluationContext, rule: PolicyRule, params: NoParams) -> list[Breach]:
        lines = [
            line
            for line in ctx.lines_for(rule.category)
            if line.amount is not None and normalise(line.vendor) and normalise(line.receipt_number)
        ]
        if not lines:
            return []

        earlier: dict[tuple[str, Decimal, str], str] = {}
        rows = ctx.db.execute(
            select(
                Claim.id,
                ClaimLine.position,
                ClaimLine.vendor,
                ClaimLine.amount,
                ClaimLine.receipt_number,
            )
            .join(Claim, Claim.id == ClaimLine.claim_id)
            .where(
                Claim.id != ctx.claim.id,
                Claim.status.not_in([s.value for s in NOT_COUNTED]),
                ClaimLine.amount.in_({line.amount for line in lines}),
                ClaimLine.receipt_number.is_not(None),
            )
            .order_by(Claim.id, ClaimLine.position)
        )
        for claim_id, position, vendor, amount, number in rows:
            key = (normalise(vendor), Decimal(amount), normalise(number))
            earlier.setdefault(key, f"line {position} of claim #{claim_id}")

        breaches = []
        for line in lines:
            key = (normalise(line.vendor), line.amount, normalise(line.receipt_number))
            if key in earlier:
                breaches.append(
                    Breach(line.position, {**_line_values(line), "match": earlier[key]})
                )
            else:
                earlier[key] = f"line {line.position} of this claim"
        return breaches


@register
class DuplicateReceiptHash(RuleType):
    """Same receipt file (SHA-256) as a receipt on any other non-draft claim, from any
    employee, or as an earlier line of this claim."""

    rule_type = "DUPLICATE_RECEIPT_HASH"
    Params = NoParams
    placeholders = LINE_PLACEHOLDERS | {"match"}

    def evaluate(self, ctx: EvaluationContext, rule: PolicyRule, params: NoParams) -> list[Breach]:
        lines = [line for line in ctx.lines_for(rule.category) if line.receipt_sha256]
        if not lines:
            return []

        earlier: dict[str, str] = {}
        rows = ctx.db.execute(
            select(ClaimAttachment.sha256, Claim.id)
            .join(Claim, Claim.id == ClaimAttachment.claim_id)
            .where(
                ClaimAttachment.sha256.in_({line.receipt_sha256 for line in lines}),
                Claim.id != ctx.claim.id,
                Claim.status != ClaimStatus.DRAFT.value,
            )
            .order_by(Claim.id)
        )
        for sha256, claim_id in rows:
            earlier.setdefault(sha256, f"claim #{claim_id}")

        breaches = []
        for line in lines:
            sha = line.receipt_sha256
            if sha in earlier:
                breaches.append(
                    Breach(line.position, {**_line_values(line), "match": earlier[sha]})
                )
            else:
                earlier[sha] = f"line {line.position} of this claim"  # type: ignore[index]
        return breaches


class WeekendParams(_Params):
    days: list[int] = Field(min_length=1, max_length=7)


@register
class Weekend(RuleType):
    """Expense date on one of ``days`` (0 = Monday ... 6 = Sunday)."""

    rule_type = "WEEKEND"
    Params = WeekendParams
    placeholders = LINE_PLACEHOLDERS | {"weekday"}

    def evaluate(
        self, ctx: EvaluationContext, rule: PolicyRule, params: WeekendParams
    ) -> list[Breach]:
        return [
            Breach(
                line.position,
                {**_line_values(line), "weekday": WEEKDAYS[line.expense_date.weekday()]},
            )
            for line in ctx.lines_for(rule.category)
            if line.expense_date is not None and line.expense_date.weekday() in params.days
        ]


class SplitParams(_Params):
    window_days: int = Field(ge=1, le=90)
    threshold: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


@register
class SplitClaim(RuleType):
    """This claim is at or under ``threshold``, but together with the employee's other
    claims that were also at or under it, submitted in the last ``window_days``, it is
    above it. Larger claims already went through the higher approval steps, so they are
    not counted."""

    rule_type = "SPLIT_CLAIM"
    Params = SplitParams
    placeholders = frozenset({"window_days", "combined", "threshold", "claims"})

    def evaluate(
        self, ctx: EvaluationContext, rule: PolicyRule, params: SplitParams
    ) -> list[Breach]:
        total = ctx.claim.total_amount
        if total > params.threshold:
            return []
        since = ctx.now - timedelta(days=params.window_days)
        rows = ctx.db.execute(
            select(Claim.id, Claim.total_amount).where(
                Claim.employee_id == ctx.claim.employee_id,
                Claim.id != ctx.claim.id,
                Claim.status.not_in([s.value for s in NOT_COUNTED]),
                Claim.submitted_at >= since,
                Claim.total_amount <= params.threshold,
            )
        ).all()
        combined = total + sum((Decimal(amount) for _, amount in rows), Decimal("0"))
        if not rows or combined <= params.threshold:
            return []
        return [
            Breach(
                None,
                {
                    "window_days": params.window_days,
                    "combined": money(combined),
                    "threshold": money(params.threshold),
                    "claims": ", ".join(f"#{claim_id}" for claim_id, _ in rows),
                },
            )
        ]
