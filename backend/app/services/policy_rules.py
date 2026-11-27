"""Reading and changing policy rules. Changes are validated against the rule type and audited.

A change applies to evaluations from then on; earlier results keep the values they
were evaluated with (``claim_policy_results.rule_snapshot``).
"""

from __future__ import annotations

from string import Formatter

from fastapi import status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import AuditAction, PolicyRule, User
from app.policy.rules import REGISTRY
from app.schemas.policy import PolicyRuleUpdate
from app.services import audit

ENTITY_TYPE = "policy_rule"


class RuleNotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "policy_rule_not_found"
    message = "Policy rule not found."


class RuleInvalid(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"
    message = "The rule change is not valid."


def list_rules(db: Session, *, include_inactive: bool) -> list[PolicyRule]:
    query = select(PolicyRule).order_by(PolicyRule.code)
    if not include_inactive:
        query = query.where(PolicyRule.active)
    return list(db.scalars(query))


def update_rule(db: Session, user: User, code: str, body: PolicyRuleUpdate) -> PolicyRule:
    rule = db.scalar(select(PolicyRule).where(PolicyRule.code == code).with_for_update())
    if rule is None:
        raise RuleNotFound()
    evaluator = REGISTRY[rule.rule_type]
    changes = body.model_dump(exclude_unset=True)

    if "params" in changes:
        try:
            evaluator.Params.model_validate(changes["params"])
        except ValidationError as exc:
            raise RuleInvalid(
                "params do not fit this rule type.",
                details={
                    "rule_type": rule.rule_type,
                    "fields": [
                        {"field": ".".join(map(str, e["loc"])), "message": e["msg"]}
                        for e in exc.errors()
                    ],
                },
            ) from exc
    if "reason_template" in changes:
        used = {name for _, name, _, _ in Formatter().parse(changes["reason_template"]) if name}
        unknown = used - evaluator.placeholders
        if unknown:
            raise RuleInvalid(
                "reason_template uses placeholders this rule type does not provide.",
                details={"unknown": sorted(unknown), "allowed": sorted(evaluator.placeholders)},
            )

    before = {key: getattr(rule, key) for key in changes}
    for key, value in changes.items():
        setattr(rule, key, value)
    rule.updated_by = user.id
    diff = audit.diff(
        {k: audit.json_safe(v) for k, v in before.items()},
        {k: audit.json_safe(v) for k, v in changes.items()},
    )
    if diff:
        audit.record(
            db,
            entity_type=ENTITY_TYPE,
            entity_id=rule.id,
            action=AuditAction.RULE_UPDATED,
            changes={"code": {"old": rule.code, "new": rule.code}, **diff},
            actor=user,
        )
    db.commit()
    db.refresh(rule)
    return rule
