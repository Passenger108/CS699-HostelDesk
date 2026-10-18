from datetime import datetime, time, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.cleaning.models import (
    AvailabilityMode,
    CleaningRequest,
    CreditReservation,
    Priority,
    RequestEvent,
    RequestStatus,
)
from app.cleaning.workflow import (
    EVENT_LABELS,
    STATUS_LABELS,
    STUDENT_CANCELLABLE,
    is_terminal,
    record_event,
    transition,
)
from app.common.audit import record_audit
from app.common.errors import ApiError
from app.common.models import as_utc, utcnow
from app.common.time import HOSTEL_TZ, hostel_now
from app.credits.service import balance, release_credit, reserve_credit
from app.extensions import db
from app.hostel_structure.service import room_dict
from app.users.models import Role, User

TEXT_LIMIT = 500
KEY_LIMIT = 64


def _commit() -> None:
    try:
        db.session.commit()
    except (IntegrityError, StaleDataError):
        db.session.rollback()
        raise ApiError(
            409, "STALE_REQUEST", "This request was updated by someone else. Please refresh."
        ) from None


def _clean_text(value: str | None, field: str, label: str) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > TEXT_LIMIT:
        raise ApiError(400, f"{field}_TOO_LONG", f"{label} can be at most {TEXT_LIMIT} characters.")
    return value or None


def _parse_time(value: str | None, label: str) -> time:
    try:
        return time.fromisoformat(value or "")
    except ValueError:
        raise ApiError(400, "INVALID_AVAILABILITY", f"{label} must be a time like 14:30.") from None


def end_of_day(now: datetime) -> datetime:
    local = hostel_now(now)
    return datetime.combine(local.date(), time(23, 59, 59), tzinfo=HOSTEL_TZ).astimezone(
        timezone.utc
    )


def availability_from(
    mode: str | None, window_start: str | None, window_end: str | None, now: datetime
) -> dict:
    try:
        availability_mode = AvailabilityMode(mode)
    except ValueError:
        raise ApiError(
            400,
            "INVALID_AVAILABILITY",
            "Choose when you are available: now, a time window or any time today.",
        ) from None

    if availability_mode != AvailabilityMode.TIME_WINDOW:
        return {
            "availability_mode": availability_mode,
            "window_start": None,
            "window_end": None,
            "available_until": end_of_day(now),
        }

    local_now = hostel_now(now)
    today = local_now.date()
    start = datetime.combine(today, _parse_time(window_start, "Start time"), tzinfo=HOSTEL_TZ)
    end = datetime.combine(today, _parse_time(window_end, "End time"), tzinfo=HOSTEL_TZ)
    if start >= end:
        raise ApiError(400, "INVALID_AVAILABILITY", "The start time must be before the end time.")
    if start < local_now.replace(second=0, microsecond=0):
        raise ApiError(400, "INVALID_AVAILABILITY", "The time window cannot start in the past.")
    return {
        "availability_mode": availability_mode,
        "window_start": start.astimezone(timezone.utc),
        "window_end": end.astimezone(timezone.utc),
        "available_until": end.astimezone(timezone.utc),
    }


def active_request(student: User) -> CleaningRequest | None:
    return db.session.scalar(db.select(CleaningRequest).filter_by(active_student_id=student.id))


def submit_request(
    student: User,
    availability_mode: str | None,
    window_start: str | None = None,
    window_end: str | None = None,
    priority: str | None = None,
    note: str | None = None,
    urgent_reason: str | None = None,
    client_key: str | None = None,
    now: datetime | None = None,
) -> tuple[CleaningRequest, bool]:
    now = now or utcnow()
    client_key = (client_key or "").strip()[:KEY_LIMIT] or None
    if client_key:
        earlier = db.session.scalar(
            db.select(CleaningRequest).filter_by(student_id=student.id, client_key=client_key)
        )
        if earlier:
            return earlier, False

    try:
        priority_value = Priority(priority or Priority.NORMAL.value)
    except ValueError:
        raise ApiError(400, "INVALID_PRIORITY", "Priority must be normal or urgent.") from None
    if priority_value == Priority.EMERGENCY:
        raise ApiError(
            400, "INVALID_PRIORITY", "Only a supervisor can mark a request as an emergency."
        )
    note = _clean_text(note, "NOTE", "The note")
    urgent_reason = _clean_text(urgent_reason, "URGENT_REASON", "The urgent reason")
    if priority_value == Priority.URGENT and not urgent_reason:
        raise ApiError(400, "URGENT_REASON_REQUIRED", "Tell us why this request is urgent.")
    if priority_value == Priority.NORMAL:
        urgent_reason = None
    availability = availability_from(availability_mode, window_start, window_end, now)

    profile = student.student_profile
    if profile is None or profile.room is None:
        raise ApiError(
            409,
            "PROFILE_INCOMPLETE",
            "Your profile has no room yet. Please contact the hostel office.",
        )
    if not (student.phone or "").strip():
        raise ApiError(
            409,
            "PHONE_REQUIRED",
            "Your profile has no phone number. Please contact the hostel office.",
        )
    if active_request(student):
        raise ApiError(409, "ACTIVE_REQUEST_EXISTS", "You already have an active cleaning request.")

    has_credit = balance(student.id, now)["available"] > 0
    if priority_value == Priority.NORMAL and not has_credit:
        raise ApiError(409, "NO_CREDIT", "You have no cleaning credit available.")

    request = CleaningRequest(
        student=student,
        active_student_id=student.id,
        client_key=client_key,
        room=profile.room,
        room_snapshot=room_dict(profile.room),
        contact_phone=student.phone.strip(),
        status=RequestStatus.SUBMITTED,
        priority=priority_value,
        urgent_reason=urgent_reason,
        note=note,
        credit_reservation=CreditReservation.NONE,
        **availability,
    )
    db.session.add(request)
    try:
        db.session.flush()
        if has_credit:
            reserve_credit(student, request.id, now=now)
            request.credit_reservation = CreditReservation.RESERVED
        record_event(request, "SUBMITTED", student)
        record_audit(
            "REQUEST_SUBMITTED",
            "cleaning_request",
            request.id,
            actor=student,
            after={
                "status": request.status.value,
                "priority": request.priority.value,
                "availability_mode": request.availability_mode.value,
                "credit_reservation": request.credit_reservation.value,
            },
        )
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            409, "ACTIVE_REQUEST_EXISTS", "You already have an active cleaning request."
        ) from None
    except ApiError:
        db.session.rollback()
        raise
    _commit()
    return request, True


def cancel_by_student(request: CleaningRequest, student: User) -> CleaningRequest:
    if request.student_id != student.id:
        raise ApiError(404, "REQUEST_NOT_FOUND", "This request does not exist.")
    if request.status == RequestStatus.CANCELLED_BY_STUDENT:
        return request
    if request.status not in STUDENT_CANCELLABLE:
        raise ApiError(409, "CANNOT_CANCEL", "This request can no longer be cancelled.")

    old_state = request.status
    try:
        if request.credit_reservation == CreditReservation.RESERVED:
            release_credit(student, request.id, "Request cancelled by the student", actor=student)
            request.credit_reservation = CreditReservation.RELEASED
        request.resolution_reason = "Cancelled by the student"
        transition(request, RequestStatus.CANCELLED_BY_STUDENT, actor=student)
        record_audit(
            "REQUEST_CANCELLED",
            "cleaning_request",
            request.id,
            actor=student,
            before={"status": old_state.value},
            after={
                "status": request.status.value,
                "credit_reservation": request.credit_reservation.value,
            },
        )
    except ApiError:
        db.session.rollback()
        raise
    _commit()
    return request


def can_view(request: CleaningRequest, viewer: User) -> bool:
    if viewer.role in (Role.SUPERVISOR, Role.SUPER_ADMIN):
        return True
    if viewer.role == Role.STUDENT:
        return request.student_id == viewer.id
    if viewer.role == Role.WORKER:
        return request.assigned_worker_id == viewer.id
    return False


def get_request_for(request_id: int, viewer: User) -> CleaningRequest:
    request = db.session.get(CleaningRequest, request_id)
    if request is None or not can_view(request, viewer):
        raise ApiError(404, "REQUEST_NOT_FOUND", "This request does not exist.")
    return request


def allowed_actions(request: CleaningRequest, viewer: User) -> list[str]:
    actions = []
    if viewer.id == request.student_id and request.status in STUDENT_CANCELLABLE:
        actions.append("cancel")
    return actions


def _iso(value: datetime | None) -> str | None:
    value = as_utc(value)
    return value.isoformat() if value else None


def _person(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "name": user.name, "role": user.role.value}


def event_dict(event: RequestEvent) -> dict:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "label": EVENT_LABELS.get(event.event_type, STATUS_LABELS[event.new_state]),
        "old_state": event.old_state.value if event.old_state else None,
        "new_state": event.new_state.value,
        "actor": _person(event.actor),
        "occurred_at": _iso(event.occurred_at),
    }


def request_dict(request: CleaningRequest, viewer: User) -> dict:
    return {
        "id": request.id,
        "status": request.status.value,
        "status_label": STATUS_LABELS[request.status],
        "is_active": not is_terminal(request.status),
        "priority": request.priority.value,
        "urgent_reason": request.urgent_reason,
        "note": request.note,
        "availability": {
            "mode": request.availability_mode.value,
            "window_start": _iso(request.window_start),
            "window_end": _iso(request.window_end),
            "available_until": _iso(request.available_until),
        },
        "room": request.room_snapshot,
        "contact_phone": request.contact_phone,
        "credit_reservation": request.credit_reservation.value,
        "student": _person(request.student),
        "assigned_worker": _person(request.assigned_worker),
        "created_at": _iso(request.created_at),
        "closed_at": _iso(request.closed_at),
        "resolution_reason": request.resolution_reason,
        "lock_version": request.lock_version,
        "actions": allowed_actions(request, viewer),
        "timeline": [event_dict(event) for event in request.events],
    }
