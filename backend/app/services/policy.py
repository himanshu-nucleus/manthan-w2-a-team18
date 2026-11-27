"""Expense policy settings: defaults, reading and finance-head updates.

``DEFAULT_POLICY`` is used only to create the settings row when it is missing
(at startup, or on first read). Rules always read the row, so a finance-head
change applies to the next submit without a restart.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import POLICY_ROW_ID, AuditAction, PolicySettings, User
from app.schemas.policy import PolicyUpdate
from app.services import audit

logger = logging.getLogger(__name__)

ENTITY_TYPE = "policy"

DEFAULT_POLICY: dict[str, Any] = {
    "receipt_required_above": Decimal("500.00"),
    "meal_daily_limit": Decimal("1500.00"),
    "hotel_tier1_nightly_limit": Decimal("6000.00"),
    "hotel_other_nightly_limit": Decimal("4000.00"),
    "local_trip_limit": Decimal("2000.00"),
    # Gap decision G6.
    "tier1_cities": [
        "Mumbai",
        "Delhi",
        "Bengaluru",
        "Chennai",
        "Hyderabad",
        "Kolkata",
        "Pune",
        "Ahmedabad",
    ],
}

EDITABLE_FIELDS = tuple(DEFAULT_POLICY)


def get_policy(db: Session) -> PolicySettings:
    """The current settings, creating the default row (flushed, not committed) if missing."""
    policy = db.get(PolicySettings, POLICY_ROW_ID)
    if policy is None:
        policy = PolicySettings(id=POLICY_ROW_ID, **_defaults())
        db.add(policy)
        db.flush()
    return policy


def ensure_default_policy(session_factory: Callable[[], Iterator[Session]]) -> None:
    """Startup hook: insert the default row if missing; never overwrite an existing one.

    A database that is down or not yet migrated must not stop the app from starting,
    so failures are logged and the row is created on first read instead.
    """
    try:
        with contextmanager(session_factory)() as db:
            if db.get(PolicySettings, POLICY_ROW_ID) is None:
                db.add(PolicySettings(id=POLICY_ROW_ID, **_defaults()))
                db.commit()
                logger.info("Inserted the default expense policy")
    except SQLAlchemyError as exc:
        logger.warning("Default expense policy not checked at startup: %s", exc.__class__.__name__)


def update_policy(db: Session, user: User, body: PolicyUpdate) -> PolicySettings:
    policy = get_policy(db)
    before = _snapshot(policy)
    for field, value in body.changes().items():
        setattr(policy, field, value)
    changes = audit.diff(before, _snapshot(policy))
    if changes:
        policy.updated_by = user.id
        policy.updated_at = datetime.now(UTC)
        audit.record(
            db,
            entity_type=ENTITY_TYPE,
            entity_id=POLICY_ROW_ID,
            action=AuditAction.UPDATED,
            changes=changes,
            actor_id=user.id,
        )
    db.commit()
    db.refresh(policy)
    return policy


def is_tier1_city(policy: PolicySettings, city: str) -> bool:
    return city.strip().casefold() in {name.casefold() for name in policy.tier1_cities}


def _defaults() -> dict[str, Any]:
    return {**DEFAULT_POLICY, "tier1_cities": list(DEFAULT_POLICY["tier1_cities"])}


def _snapshot(policy: PolicySettings) -> dict[str, Any]:
    """JSON-safe view; money is quantized so 1500 and 1500.00 compare equal."""
    data: dict[str, Any] = {}
    for field in EDITABLE_FIELDS:
        value = getattr(policy, field)
        if isinstance(value, Decimal):
            value = audit.json_safe(value.quantize(Decimal("0.01")))
        elif isinstance(value, list):
            value = list(value)
        data[field] = value
    return data
