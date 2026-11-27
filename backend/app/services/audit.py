"""The one place audit rows are written and read. Insert and read only: no update, no delete.

``record`` adds the row to the caller's session, so it commits or rolls back with the
action it describes. ``record_detached`` writes in its own transaction: used for
events that must survive the request failing (access denied, failed login).

Every row since migration 0006 joins a hash chain: ``hash = SHA-256(prev_hash +
canonical row content)``. Writers take a PostgreSQL advisory lock until commit, so the
chain is linear; ``verify_chain`` recomputes it.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, event, func, or_, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditAction, AuditEvent, User
from app.models.audit import SYSTEM_ROLE
from app.request_context import client_ip_var, request_id_var

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
CHAIN_LOCK_KEY = 4_270_002  # pg_advisory_xact_lock key for the hash chain
_LAST_HASH = "audit_last_hash"  # Session.info key, valid until the transaction ends


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


# --- hash chain -----------------------------------------------------------------------


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def row_content(row: AuditEvent) -> str:
    """Canonical JSON of everything a row says (not its id, which is assigned later)."""
    return json.dumps(
        {
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "claim_id": row.claim_id,
            "action": row.action,
            "changes": row.changes,
            "actor_id": row.actor_id,
            "actor_role": row.actor_role,
            "on_behalf_of_id": row.on_behalf_of_id,
            "comment": row.comment,
            "ip_address": row.ip_address,
            "request_id": row.request_id,
            "created_at": _utc_iso(row.created_at),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def compute_hash(prev_hash: str, row: AuditEvent) -> str:
    return hashlib.sha256((prev_hash + row_content(row)).encode("utf-8")).hexdigest()


def _previous_hash(db: Session) -> str:
    if _LAST_HASH in db.info:
        return db.info[_LAST_HASH]
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": CHAIN_LOCK_KEY})
    last = db.scalar(
        select(AuditEvent.hash)
        .where(AuditEvent.hash.is_not(None))
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )
    return last or GENESIS_HASH


def _forget_chain_tip(session: Session, *_: Any) -> None:
    session.info.pop(_LAST_HASH, None)


for _name in ("after_commit", "after_rollback", "after_soft_rollback"):
    event.listen(Session, _name, _forget_chain_tip)


# --- writing ----------------------------------------------------------------------------


def record(
    db: Session,
    *,
    entity_type: str,
    entity_id: int | None,
    action: AuditAction,
    actor: User | None,
    changes: dict[str, Any] | None = None,
    claim_id: int | None = None,
    on_behalf_of_id: int | None = None,
    comment: str | None = None,
) -> AuditEvent:
    """Add one audit row to ``db``'s transaction. ``actor=None`` means SYSTEM.

    The actor always comes from the authenticated user object, never from request data.
    Never pass secrets or file contents in ``changes``.
    """
    if entity_type == "claim" and claim_id is None:
        claim_id = entity_id
    row = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        claim_id=claim_id,
        action=action.value,
        changes=changes or {},
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else SYSTEM_ROLE,
        on_behalf_of_id=on_behalf_of_id,
        comment=comment,
        ip_address=client_ip_var.get(),
        request_id=request_id_var.get(),
        created_at=datetime.now(UTC),
    )
    row.prev_hash = _previous_hash(db)
    row.hash = compute_hash(row.prev_hash, row)
    db.info[_LAST_HASH] = row.hash
    db.add(row)
    return row


def record_detached(db: Session, **fields: Any) -> None:
    """Write one audit row in its own transaction, so it is kept even when the
    request that caused it fails and rolls back (access denied, failed login).

    Must run before the request writes audit rows of its own: the chain lock would
    otherwise be held by ``db`` and this separate transaction would wait for it.
    """
    if _LAST_HASH in db.info:
        logger.warning("Audit chain already locked by this request; denial written in-request")
        record(db, **fields)
        return
    try:
        with Session(bind=db.get_bind()) as own:
            record(own, **fields)
            own.commit()
    except Exception:  # never let audit-of-a-denial turn a 403/404 into a 500
        logger.exception("Could not write detached audit row %s", fields.get("action"))


# --- reading ----------------------------------------------------------------------------


def claim_history(db: Session, claim_id: int) -> list[AuditEvent]:
    """Everything that happened to one claim, newest first. Access denials are left out
    (they name other users); finance sees them through the audit search."""
    query = (
        select(AuditEvent)
        .where(
            or_(
                AuditEvent.claim_id == claim_id,
                and_(AuditEvent.entity_type == "claim", AuditEvent.entity_id == claim_id),
            ),
            AuditEvent.action != AuditAction.ACCESS_DENIED.value,
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    )
    return list(db.scalars(query))


def history(db: Session, *, entity_type: str, entity_id: int) -> list[AuditEvent]:
    """All events for one entity, newest first."""
    query = (
        select(AuditEvent)
        .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    )
    return list(db.scalars(query))


def search(
    db: Session,
    *,
    entity_type: str | None,
    action: str | None,
    actor_id: int | None,
    claim_id: int | None,
    from_date: date | None,
    to_date: date | None,
    limit: int,
    offset: int,
) -> tuple[list[AuditEvent], int]:
    """System-wide search, newest first. Dates are business-time-zone days, inclusive."""
    tz = ZoneInfo(get_settings().timezone)
    conditions = []
    if entity_type:
        conditions.append(func.lower(AuditEvent.entity_type) == entity_type.lower())
    if action:
        conditions.append(AuditEvent.action == action.upper())
    if actor_id is not None:
        conditions.append(AuditEvent.actor_id == actor_id)
    if claim_id is not None:
        conditions.append(
            or_(
                AuditEvent.claim_id == claim_id,
                and_(AuditEvent.entity_type == "claim", AuditEvent.entity_id == claim_id),
            )
        )
    if from_date is not None:
        conditions.append(AuditEvent.created_at >= datetime.combine(from_date, time.min, tz))
    if to_date is not None:
        conditions.append(
            AuditEvent.created_at < datetime.combine(to_date + timedelta(days=1), time.min, tz)
        )
    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*conditions)) or 0
    rows = db.scalars(
        select(AuditEvent)
        .where(*conditions)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


@dataclass
class ChainReport:
    checked: int
    valid: bool
    unchained_rows: int
    first_broken_id: int | None
    problem: str | None


def verify_chain(db: Session) -> ChainReport:
    """Recompute every hash in id order. Rows from before migration 0006 have no hash."""
    unchained = (
        db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.hash.is_(None)))
        or 0
    )
    expected_prev = GENESIS_HASH
    checked = 0
    rows = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.hash.is_not(None))
        .order_by(AuditEvent.id)
        .execution_options(yield_per=500)
    )
    for row in rows:
        checked += 1
        if row.prev_hash != expected_prev:
            return ChainReport(checked, False, unchained, row.id, "prev_hash does not link")
        if compute_hash(row.prev_hash, row) != row.hash:
            return ChainReport(checked, False, unchained, row.id, "row content changed")
        expected_prev = row.hash  # type: ignore[assignment]
    return ChainReport(checked, True, unchained, None, None)
