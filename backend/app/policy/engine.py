"""Runs every active rule over a claim and works out line and claim outcomes.

Line outcome  = most severe outcome among the rules it breached (none: AUTO_APPROVE).
Claim outcome = most severe of its lines and claim-level findings; an otherwise clean
claim is routed when its total is above the ``auto_approve_max_total`` setting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from fastapi import status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Claim, ClaimAttachment, PolicyOutcome, PolicyRule, PolicySetting
from app.policy.rules import REGISTRY, EvaluationContext, LineView, PolicyConfig, money, normalise

logger = logging.getLogger(__name__)

AUTO_APPROVE_LIMIT_CODE = "AUTO_APPROVE_LIMIT"


class PolicyNotConfigured(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "policy_not_configured"
    message = "Policy configuration is missing or invalid. Run backend/db/seed.sql."


@dataclass
class Finding:
    """The combined result for one line, or for the claim as a whole (position None)."""

    line_position: int | None
    outcome: PolicyOutcome = PolicyOutcome.AUTO_APPROVE
    rule_codes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    rule_snapshot: dict[str, Any] = field(default_factory=dict)

    def add(self, code: str, outcome: PolicyOutcome, reason: str, snapshot: Any) -> None:
        self.rule_codes.append(code)
        self.reasons.append(reason)
        self.rule_snapshot[code] = snapshot
        if outcome.severity > self.outcome.severity:
            self.outcome = outcome


@dataclass
class Evaluation:
    outcome: PolicyOutcome
    lines: list[Finding]
    claim_level: Finding


class _SafeValues(dict[str, Any]):
    """Leaves an unknown ``{placeholder}`` in place instead of failing."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(template: str, values: dict[str, Any]) -> str:
    return template.format_map(_SafeValues(values))


def load_config(db: Session) -> PolicyConfig:
    settings = {row.key: row.value for row in db.scalars(select(PolicySetting))}
    try:
        return PolicyConfig(
            tier1_cities=frozenset(normalise(city) for city in settings["tier1_cities"]),
            approval_thresholds={
                role: Decimal(str(amount))
                for role, amount in settings["approval_thresholds"].items()
            },
            auto_approve_max_total=Decimal(str(settings["auto_approve_max_total"])),
        )
    except (KeyError, TypeError, ArithmeticError, AttributeError) as exc:
        raise PolicyNotConfigured(details={"missing_or_invalid": str(exc)}) from exc


def parse_params(rule: PolicyRule) -> Any:
    """Validated params for ``rule``; a bad or unknown rule must never be skipped silently."""
    evaluator = REGISTRY.get(rule.rule_type)
    if evaluator is None:
        raise PolicyNotConfigured(f"Rule {rule.code} has unknown rule type {rule.rule_type}.")
    try:
        return evaluator.Params.model_validate(rule.params)
    except ValidationError as exc:
        raise PolicyNotConfigured(f"Rule {rule.code} has invalid params.") from exc


def evaluate(db: Session, claim: Claim) -> Evaluation:
    config = load_config(db)
    hashes = dict(
        db.execute(
            select(ClaimAttachment.id, ClaimAttachment.sha256).where(
                ClaimAttachment.claim_id == claim.id
            )
        ).all()
    )
    lines = [
        LineView(
            position=line.position,
            category=line.category,
            amount=line.amount,
            expense_date=line.expense_date,
            vendor=line.vendor,
            city=line.city,
            nights=line.nights,
            receipt_number=line.receipt_number,
            receipt_id=line.receipt_id,
            receipt_sha256=hashes.get(line.receipt_id) if line.receipt_id else None,
        )
        for line in claim.lines
    ]
    ctx = EvaluationContext(db=db, claim=claim, lines=lines, config=config)

    per_line = {line.position: Finding(line.position) for line in lines}
    claim_level = Finding(None)

    rules = db.scalars(select(PolicyRule).where(PolicyRule.active).order_by(PolicyRule.code))
    for rule in rules:
        params = parse_params(rule)
        outcome = PolicyOutcome(rule.outcome_on_breach)
        snapshot = {"params": rule.params, "outcome_on_breach": rule.outcome_on_breach}
        for breach in REGISTRY[rule.rule_type].evaluate(ctx, rule, params):
            target = claim_level if breach.line_position is None else per_line[breach.line_position]
            target.add(rule.code, outcome, render(rule.reason_template, breach.values), snapshot)

    findings = [*per_line.values(), claim_level]
    worst = max((f.outcome for f in findings), key=lambda o: o.severity)

    if worst == PolicyOutcome.AUTO_APPROVE and claim.total_amount > config.auto_approve_max_total:
        claim_level.add(
            AUTO_APPROVE_LIMIT_CODE,
            PolicyOutcome.ROUTE_FOR_APPROVAL,
            f"Claim total {money(claim.total_amount)} INR is above the auto-approve limit of "
            f"{money(config.auto_approve_max_total)} INR",
            {"auto_approve_max_total": str(config.auto_approve_max_total)},
        )
        worst = PolicyOutcome.ROUTE_FOR_APPROVAL

    return Evaluation(outcome=worst, lines=list(per_line.values()), claim_level=claim_level)


def receipt_required_above(db: Session) -> Decimal | None:
    """The amount above which submit demands a receipt, read from the active
    RECEIPT_REQUIRED rule(s); None when no such rule is active."""
    limits = [
        parse_params(rule).above
        for rule in db.scalars(
            select(PolicyRule).where(PolicyRule.active, PolicyRule.rule_type == "RECEIPT_REQUIRED")
        )
    ]
    return min(limits) if limits else None
