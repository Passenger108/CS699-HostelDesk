from datetime import datetime
from typing import Any

from flask import has_request_context, request
from sqlalchemy import JSON, DateTime, ForeignKey, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import IdMixin, utcnow
from app.extensions import db


class AuditLog(IdMixin, db.Model):
    __tablename__ = "audit_logs"

    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    before_json: Mapped[Any | None] = mapped_column(JSON)
    after_json: Mapped[Any | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


@event.listens_for(AuditLog, "before_update")
def _block_update(_mapper, _connection, _target):
    raise RuntimeError("Audit log entries cannot be changed.")


def record_audit(
    action: str,
    entity_type: str,
    entity_id: Any = None,
    actor=None,
    before: Any = None,
    after: Any = None,
    reason: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor is not None else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before_json=before,
        after_json=after,
        reason=reason,
        ip_address=request.remote_addr if has_request_context() else None,
    )
    db.session.add(entry)
    return entry
