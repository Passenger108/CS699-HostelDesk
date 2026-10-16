import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import IdMixin, utcnow
from app.extensions import db


class CreditType(str, enum.Enum):
    STANDARD = "STANDARD"
    GOODWILL = "GOODWILL"


class CreditEntryType(str, enum.Enum):
    WEEKLY_GRANT = "WEEKLY_GRANT"
    WEEKLY_CAPPED = "WEEKLY_CAPPED"
    GOODWILL_GRANT = "GOODWILL_GRANT"
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    CONSUME = "CONSUME"
    EXPIRE = "EXPIRE"


class CreditEntry(IdMixin, db.Model):
    __tablename__ = "credit_ledger"
    __table_args__ = (UniqueConstraint("student_id", "grant_week"),)

    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    entry_type: Mapped[CreditEntryType] = mapped_column(
        Enum(CreditEntryType, name="credit_entry_type"), nullable=False
    )
    credit_type: Mapped[CreditType] = mapped_column(
        Enum(CreditType, name="credit_type"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    request_id: Mapped[int | None] = mapped_column(index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    grant_week: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


@event.listens_for(CreditEntry, "before_update")
def _block_update(_mapper, _connection, _target):
    raise RuntimeError("Credit ledger entries cannot be changed.")
