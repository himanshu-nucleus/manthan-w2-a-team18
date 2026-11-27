"""Default policy rules and settings, inserted at startup when missing.

This is the single place the default values live (``db/seed.sql`` no longer inserts
them). A row is inserted only if its ``code`` (rule) or ``key`` (setting) is missing;
existing rows are never overwritten, so finance-head changes made through
``PUT /policy-rules/{code}`` survive restarts. Every database gets the rules this
way, including the SQLite test database, which never runs the seed.

Amounts are INR strings so they stay exact. Template placeholders are filled by the
rule type; see ``app/policy/rules.py``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AuditAction, PolicyRule, PolicySetting

logger = logging.getLogger(__name__)

DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "code": "MEAL_DAILY_LIMIT",
        "name": "Meals up to 1,500 INR per day",
        "category": "meal",
        "rule_type": "DAILY_CATEGORY_LIMIT",
        "params": {"limit": "1500"},
        "outcome_on_breach": "ROUTE_FOR_APPROVAL",
        "reason_template": "Meal spend {total} INR on {date} exceeds daily limit of {limit} INR",
        "active": True,
    },
    {
        "code": "HOTEL_NIGHTLY_LIMIT_T1",
        "name": "Hotel up to 6,000 INR per night in tier-1 cities",
        "category": "hotel",
        "rule_type": "PER_NIGHT_LIMIT",
        "params": {"limit": "6000", "city_tier": "tier1"},
        "outcome_on_breach": "ROUTE_FOR_APPROVAL",
        "reason_template": (
            "Hotel {per_night} INR per night in {city} exceeds tier-1 limit of {limit} INR"
        ),
        "active": True,
    },
    {
        "code": "HOTEL_NIGHTLY_LIMIT_OTHER",
        "name": "Hotel up to 4,000 INR per night in other cities",
        "category": "hotel",
        "rule_type": "PER_NIGHT_LIMIT",
        "params": {"limit": "4000", "city_tier": "other"},
        "outcome_on_breach": "ROUTE_FOR_APPROVAL",
        "reason_template": (
            "Hotel {per_night} INR per night in {city} exceeds limit of {limit} INR "
            "for non-tier-1 cities"
        ),
        "active": True,
    },
    {
        "code": "LOCAL_TRIP_LIMIT",
        "name": "Local conveyance up to 2,000 INR per trip",
        "category": "local",
        "rule_type": "PER_LINE_LIMIT",
        "params": {"limit": "2000"},
        "outcome_on_breach": "ROUTE_FOR_APPROVAL",
        "reason_template": (
            "Local conveyance {amount} INR on {date} exceeds per-trip limit of {limit} INR"
        ),
        "active": True,
    },
    {
        # Replaced by LOCAL_TRIP_LIMIT (team decision): cab has no limit, like airfare.
        "code": "CAB_TRIP_LIMIT",
        "name": "Local cab up to 2,000 INR per trip",
        "category": "cab",
        "rule_type": "PER_LINE_LIMIT",
        "params": {"limit": "2000"},
        "outcome_on_breach": "ROUTE_FOR_APPROVAL",
        "reason_template": "Cab fare {amount} INR on {date} exceeds per-trip limit of {limit} INR",
        "active": False,
    },
    {
        "code": "RECEIPT_MANDATORY",
        "name": "Receipt mandatory above 500 INR",
        "category": None,
        "rule_type": "RECEIPT_REQUIRED",
        "params": {"above": "500"},
        "outcome_on_breach": "AUTO_REJECT",
        "reason_template": (
            "Receipt is mandatory above {above} INR; line {line} ({amount} INR) has none"
        ),
        "active": True,
    },
    {
        "code": "DUPLICATE_RECEIPT_NUMBER",
        "name": "Same vendor, amount and receipt number as an earlier line",
        "category": None,
        "rule_type": "DUPLICATE_RECEIPT_NUMBER",
        "params": {},
        "outcome_on_breach": "MARK_DUPLICATE",
        "reason_template": "Duplicate: same vendor, amount and receipt number as {match}",
        "active": True,
    },
    {
        # Replaced by DUPLICATE_RECEIPT_NUMBER (team decision).
        "code": "DUPLICATE_LINE",
        "name": "Same vendor, amount and date as an earlier line",
        "category": None,
        "rule_type": "DUPLICATE_LINE",
        "params": {},
        "outcome_on_breach": "ROUTE_FOR_APPROVAL",
        "reason_template": "Possible duplicate: same vendor, amount and date as {match}",
        "active": False,
    },
    {
        # Replaced by DUPLICATE_RECEIPT_NUMBER (team decision). Switch it back on to also
        # catch the same receipt file under a different receipt number.
        "code": "DUPLICATE_RECEIPT_HASH",
        "name": "Same receipt file as an earlier receipt",
        "category": None,
        "rule_type": "DUPLICATE_RECEIPT_HASH",
        "params": {},
        "outcome_on_breach": "AUTO_REJECT",
        "reason_template": "Duplicate receipt: the same file was already used on {match}",
        "active": False,
    },
    {
        "code": "WEEKEND_SPEND",
        "name": "Weekend spend flagged for manager attention",
        "category": None,
        "rule_type": "WEEKEND",
        "params": {"days": [5, 6]},
        "outcome_on_breach": "ROUTE_FOR_APPROVAL",
        "reason_template": (
            "Expense on {weekday} {date} is weekend spend; flagged for manager attention"
        ),
        "active": True,
    },
    {
        "code": "SPLIT_CLAIM",
        "name": "Possible claim splitting to stay under an approval threshold",
        "category": None,
        "rule_type": "SPLIT_CLAIM",
        "params": {"window_days": 7, "threshold": "25000"},
        "outcome_on_breach": "ROUTE_FOR_APPROVAL",
        "reason_template": (
            "Claims submitted in the last {window_days} days total {combined} INR, "
            "above {threshold} INR: possible claim splitting"
        ),
        "active": True,
    },
]

DEFAULT_SETTINGS: list[dict[str, Any]] = [
    {
        "key": "tier1_cities",
        "value": [
            "mumbai",
            "delhi",
            "new delhi",
            "bengaluru",
            "bangalore",
            "chennai",
            "hyderabad",
            "kolkata",
            "pune",
            "ahmedabad",
        ],
        "description": "Cities that get the tier-1 hotel limit (matched case-insensitively).",
    },
    {
        "key": "approval_thresholds",
        "value": {"finance_auditor": "25000", "finance_head": "100000"},
        "description": (
            "Claim total (INR) strictly above which the auditor / finance head step is added."
        ),
    },
    {
        "key": "auto_approve_max_total",
        "value": "500",
        "description": (
            "A claim with no rule breach is auto-approved only if its total (INR) is at most this."
        ),
    },
]


def insert_missing_defaults(db: Session) -> int:
    """Add any default rule or setting that is missing; return how many were added.
    Flushes, does not commit."""
    rule_codes = set(db.scalars(select(PolicyRule.code)))
    setting_keys = set(db.scalars(select(PolicySetting.key)))
    added = 0
    from app.services import audit  # local: defaults is imported by app.main

    for rule in DEFAULT_RULES:
        if rule["code"] not in rule_codes:
            row = PolicyRule(**{**rule, "params": dict(rule["params"])})
            db.add(row)
            db.flush()
            audit.record(
                db,
                entity_type="policy_rule",
                entity_id=row.id,
                action=AuditAction.RULE_CREATED,
                actor=None,  # SYSTEM: inserted at startup
                changes={
                    "code": {"old": None, "new": row.code},
                    "params": {"old": None, "new": row.params},
                },
            )
            added += 1
    for setting in DEFAULT_SETTINGS:
        if setting["key"] not in setting_keys:
            db.add(PolicySetting(**setting))
            audit.record(
                db,
                entity_type="policy_setting",
                entity_id=None,
                action=AuditAction.SETTING_CREATED,
                actor=None,  # SYSTEM: inserted at startup
                changes={
                    "key": {"old": None, "new": setting["key"]},
                    "value": {"old": None, "new": setting["value"]},
                },
            )
            added += 1
    db.flush()
    return added


def ensure_policy_defaults(session_factory: Callable[[], Iterator[Session]]) -> None:
    """Startup hook. A database that is down or not yet migrated must not stop the app
    from starting, so failures are logged and the app carries on."""
    try:
        with contextmanager(session_factory)() as db:
            added = insert_missing_defaults(db)
            db.commit()
            if added:
                logger.info("Inserted %d missing default policy rules/settings", added)
    except SQLAlchemyError as exc:
        logger.warning("Default policy rules not checked at startup: %s", exc.__class__.__name__)
