"""Writing and reading the append-only audit trail.

Events are added to the caller's session, so they commit (or roll back) in the
same transaction as the change they describe.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditAction, AuditEvent


def json_safe(value: Any) -> Any:
    """Convert values the JSON column cannot store as-is."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return ``{field: {"old": x, "new": y}}`` for every field whose value changed."""
    return {
        key: {"old": before.get(key), "new": after.get(key)}
        for key in sorted(before.keys() | after.keys())
        if before.get(key) != after.get(key)
    }


def record(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: AuditAction,
    changes: dict[str, Any],
    actor_id: int,
) -> AuditEvent:
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action.value,
        changes=changes,
        actor_id=actor_id,
    )
    db.add(event)
    return event


def history(db: Session, *, entity_type: str, entity_id: int) -> list[AuditEvent]:
    """All events for one entity, newest first."""
    query = (
        select(AuditEvent)
        .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    )
    return list(db.scalars(query))
