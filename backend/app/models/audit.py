"""Append-only audit trail shared by every audited entity.

Rows are only ever inserted:
* the service (``app.services.audit``) offers insert and read only;
* ORM guards below refuse any UPDATE or DELETE of an audit row, including bulk ones;
* in PostgreSQL, triggers refuse UPDATE, DELETE (migration 0002) and TRUNCATE (0006);
* each row since 0006 carries ``hash = SHA-256(prev_hash + row content)``, so a change
  made by someone who bypasses all of the above is detectable (``GET /audit-logs/verify``).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import Base

SYSTEM_ROLE = "SYSTEM"


class AuditAction(StrEnum):
    """Actions written from now on. Rows written before 0006 may carry older names:
    POLICY_RULE_UPDATED (= RULE_UPDATED), BATCH_EXPORTED (= CSV_EXPORTED),
    PAID (= MARKED_PAID), DELEGATION_CREATED (= DELEGATED),
    DELEGATION_CANCELLED (= DELEGATION_REVOKED), and UPDATED for an attachment upload."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    SUBMITTED = "SUBMITTED"
    RESUBMITTED = "RESUBMITTED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    CHAIN_BUILT = "CHAIN_BUILT"
    STEP_APPROVED = "STEP_APPROVED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENT_BACK = "SENT_BACK"
    COMMENTED = "COMMENTED"
    DELEGATED = "DELEGATED"
    DELEGATION_REVOKED = "DELEGATION_REVOKED"
    RULE_CREATED = "RULE_CREATED"
    RULE_UPDATED = "RULE_UPDATED"
    SETTING_CREATED = "SETTING_CREATED"
    BATCH_CREATED = "BATCH_CREATED"
    CSV_EXPORTED = "CSV_EXPORTED"
    MARKED_PAID = "MARKED_PAID"
    ATTACHMENT_UPLOADED = "ATTACHMENT_UPLOADED"
    ATTACHMENT_DOWNLOADED = "ATTACHMENT_DOWNLOADED"
    USER_CREATED = "USER_CREATED"
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCESS_DENIED = "ACCESS_DENIED"


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_claim_id", "claim_id"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_actor_id", "actor_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Set whenever the action concerns a claim. No foreign key: history outlives the claim.
    claim_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    # {"field": {"old": ..., "new": ...}}
    changes: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict
    )
    # NULL actor_id with actor_role "SYSTEM" = done by the application itself.
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    on_behalf_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditImmutable(RuntimeError):
    """Raised when code tries to change or delete an audit row."""


@event.listens_for(AuditEvent, "before_update")
def _refuse_update(*_: Any) -> None:
    raise AuditImmutable("audit_events is append-only: UPDATE is not allowed")


@event.listens_for(AuditEvent, "before_delete")
def _refuse_delete(*_: Any) -> None:
    raise AuditImmutable("audit_events is append-only: DELETE is not allowed")


@event.listens_for(Session, "do_orm_execute")
def _refuse_bulk_changes(state: Any) -> None:
    """Bulk ``update(AuditEvent)`` / ``delete(AuditEvent)`` bypass the mapper events."""
    if (state.is_update or state.is_delete) and any(
        getattr(m, "class_", None) is AuditEvent for m in state.all_mappers
    ):
        raise AuditImmutable("audit_events is append-only: bulk UPDATE/DELETE is not allowed")
