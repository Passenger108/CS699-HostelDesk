import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import IdMixin, TimestampMixin, utcnow
from app.extensions import db
from app.hostel_structure.models import Room
from app.users.models import User


class RequestStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    AWAITING_ASSIGNMENT = "AWAITING_ASSIGNMENT"
    OFFERED = "OFFERED"
    AWAITING_REASSIGNMENT = "AWAITING_REASSIGNMENT"
    ACCEPTED_QUEUED = "ACCEPTED_QUEUED"
    AWAITING_STUDENT_RESCHEDULE = "AWAITING_STUDENT_RESCHEDULE"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    CLEANING_IN_PROGRESS = "CLEANING_IN_PROGRESS"
    AWAITING_STUDENT_CONFIRMATION = "AWAITING_STUDENT_CONFIRMATION"
    SUPERVISOR_INTERVENTION = "SUPERVISOR_INTERVENTION"
    DISPUTED = "DISPUTED"
    CLOSED_SUCCESSFUL = "CLOSED_SUCCESSFUL"
    CLOSED_VALID_AFTER_REVIEW = "CLOSED_VALID_AFTER_REVIEW"
    CLOSED_UNSATISFACTORY = "CLOSED_UNSATISFACTORY"
    STUDENT_UNAVAILABLE = "STUDENT_UNAVAILABLE"
    CANCELLED_BY_STUDENT = "CANCELLED_BY_STUDENT"
    CANCELLED_BY_SUPERVISOR = "CANCELLED_BY_SUPERVISOR"
    EXPIRED = "EXPIRED"


class Priority(str, enum.Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"


class AvailabilityMode(str, enum.Enum):
    AVAILABLE_NOW = "AVAILABLE_NOW"
    TIME_WINDOW = "TIME_WINDOW"
    ANY_TIME_TODAY = "ANY_TIME_TODAY"


class CreditReservation(str, enum.Enum):
    NONE = "NONE"
    RESERVED = "RESERVED"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"


class OfferStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    TIMED_OUT = "TIMED_OUT"
    WITHDRAWN = "WITHDRAWN"


class CleaningRequest(IdMixin, TimestampMixin, db.Model):
    __tablename__ = "cleaning_requests"
    __table_args__ = (
        UniqueConstraint("student_id", "client_key", name="uq_cleaning_requests_client_key"),
    )

    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    active_student_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    client_key: Mapped[str | None] = mapped_column(String(64))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    room_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"), nullable=False, index=True
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="request_priority"), nullable=False
    )
    urgent_reason: Mapped[str | None] = mapped_column(String(500))
    note: Mapped[str | None] = mapped_column(String(500))
    availability_mode: Mapped[AvailabilityMode] = mapped_column(
        Enum(AvailabilityMode, name="availability_mode"), nullable=False
    )
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    credit_reservation: Mapped[CreditReservation] = mapped_column(
        Enum(CreditReservation, name="credit_reservation"), nullable=False
    )
    assigned_worker_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_eta_minutes: Mapped[int | None] = mapped_column()
    latest_eta_minutes: Mapped[int | None] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_reason: Mapped[str | None] = mapped_column(String(500))
    lock_version: Mapped[int] = mapped_column(nullable=False)

    student: Mapped[User] = relationship(foreign_keys=[student_id])
    assigned_worker: Mapped[User | None] = relationship(foreign_keys=[assigned_worker_id])
    room: Mapped[Room] = relationship()
    events: Mapped[list["RequestEvent"]] = relationship(
        back_populates="request", order_by="RequestEvent.id"
    )
    offers: Mapped[list["AssignmentOffer"]] = relationship(
        back_populates="request", order_by="AssignmentOffer.id"
    )

    __mapper_args__ = {"version_id_col": lock_version}


class RequestEvent(IdMixin, db.Model):
    __tablename__ = "request_events"

    request_id: Mapped[int] = mapped_column(
        ForeignKey("cleaning_requests.id"), nullable=False, index=True
    )
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    old_state: Mapped[RequestStatus | None] = mapped_column(
        Enum(RequestStatus, name="request_status")
    )
    new_state: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"), nullable=False
    )
    payload_json: Mapped[Any | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    request: Mapped[CleaningRequest] = relationship(back_populates="events")
    actor: Mapped[User | None] = relationship()


class AssignmentOffer(IdMixin, TimestampMixin, db.Model):
    __tablename__ = "assignment_offers"

    request_id: Mapped[int] = mapped_column(
        ForeignKey("cleaning_requests.id"), nullable=False, index=True
    )
    worker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    offered_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[OfferStatus] = mapped_column(
        Enum(OfferStatus, name="offer_status"), nullable=False
    )
    response_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    explanation: Mapped[str] = mapped_column(String(300), nullable=False)
    decline_reason: Mapped[str | None] = mapped_column(String(500))

    request: Mapped[CleaningRequest] = relationship(back_populates="offers")
    worker: Mapped[User] = relationship(foreign_keys=[worker_id])
    offered_by: Mapped[User] = relationship(foreign_keys=[offered_by_id])


@event.listens_for(RequestEvent, "before_update")
def _block_update(_mapper, _connection, _target):
    raise RuntimeError("Request events cannot be changed.")
