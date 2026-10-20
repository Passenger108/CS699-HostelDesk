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
from app.common.audit import record_audit, record_security_event
from app.common.errors import ApiError
from app.common.models import as_utc, utcnow
from app.common.time import HOSTEL_TZ, hostel_now
from app.credits.service import balance, release_credit, reserve_credit
from app.extensions import db
from app.hostel_structure.models import Floor, Room, Wing
from app.hostel_structure.service import room_dict
from app.notifications.service import notify, notify_supervisors
from app.users.models import Role, User

TEXT_LIMIT = 500
KEY_LIMIT = 64
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _clean_text(value: str | None, field: str, label: str) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > TEXT_LIMIT:
        raise ApiError(
            400,
            f"{field.upper()}_TOO_LONG",
            f"{label} can be at most {TEXT_LIMIT} characters.",
            field=field,
        )
    return value or None


def _parse_time(value: str | None, label: str, field: str) -> time:
    try:
        return time.fromisoformat(value or "")
    except ValueError:
        raise ApiError(
            400, "INVALID_AVAILABILITY", f"{label} must be a time like 14:30.", field=field
        ) from None


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
            field="availability_mode",
        ) from None

    if availability_mode != AvailabilityMode.TIME_WINDOW:
        if end_of_day(now) <= now:
            raise ApiError(
                400,
                "INVALID_AVAILABILITY",
                "Today is over. Please send the request again after midnight.",
                field="availability_mode",
            )
        return {
            "availability_mode": availability_mode,
            "window_start": None,
            "window_end": None,
            "available_until": end_of_day(now),
        }

    local_now = hostel_now(now)
    today = local_now.date()
    start_time = _parse_time(window_start, "Start time", "window_start")
    end_time = _parse_time(window_end, "End time", "window_end")
    start = datetime.combine(today, start_time, tzinfo=HOSTEL_TZ)
    end = datetime.combine(today, end_time, tzinfo=HOSTEL_TZ)
    if start >= end:
        raise ApiError(
            400,
            "INVALID_AVAILABILITY",
            "The start time must be before the end time.",
            field="window_end",
        )
    if start < local_now.replace(second=0, microsecond=0):
        raise ApiError(
            400,
            "INVALID_AVAILABILITY",
            "The time window cannot start in the past.",
            field="window_start",
        )
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
    client_key = (client_key or "").strip() or None
    if client_key and len(client_key) > KEY_LIMIT:
        raise ApiError(
            400,
            "INVALID_FIELD",
            f"client_key can be at most {KEY_LIMIT} characters.",
            field="client_key",
        )
    if client_key:
        earlier = _earlier_submit(student, client_key)
        if earlier:
            return earlier, False

    try:
        priority_value = Priority(priority or Priority.NORMAL.value)
    except ValueError:
        raise ApiError(
            400, "INVALID_PRIORITY", "Priority must be normal or urgent.", field="priority"
        ) from None
    if priority_value == Priority.EMERGENCY:
        raise ApiError(
            400,
            "INVALID_PRIORITY",
            "Only a supervisor can mark a request as an emergency.",
            field="priority",
        )
    note = _clean_text(note, "note", "The note")
    urgent_reason = _clean_text(urgent_reason, "urgent_reason", "The urgent reason")
    if priority_value == Priority.URGENT and not urgent_reason:
        raise ApiError(
            400,
            "URGENT_REASON_REQUIRED",
            "Tell us why this request is urgent.",
            field="urgent_reason",
        )
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

    current = balance(student.id, now)
    is_normal = priority_value == Priority.NORMAL
    has_credit = (current["available"] if is_normal else current["standard_available"]) > 0
    if is_normal and not has_credit:
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
            reserve_credit(student, request.id, now=now, allow_goodwill=is_normal)
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
        payload = _notification_payload(request)
        notify(student, "REQUEST_SUBMITTED", payload)
        notify_supervisors(
            "NEW_URGENT_REQUEST" if request.priority == Priority.URGENT else "NEW_REQUEST",
            payload,
        )
    except IntegrityError:
        db.session.rollback()
        return _after_clash(student, client_key)
    except ApiError:
        db.session.rollback()
        raise
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _after_clash(student, client_key)
    return request, True


def _earlier_submit(student: User, client_key: str) -> CleaningRequest | None:
    return db.session.scalar(
        db.select(CleaningRequest).filter_by(student_id=student.id, client_key=client_key)
    )


def _after_clash(student: User, client_key: str | None) -> tuple[CleaningRequest, bool]:
    if client_key:
        earlier = _earlier_submit(student, client_key)
        if earlier:
            return earlier, False
    raise ApiError(409, "ACTIVE_REQUEST_EXISTS", "You already have an active cleaning request.")


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
        payload = _notification_payload(request)
        notify_supervisors("REQUEST_CANCELLED_BY_STUDENT", payload)
        if request.assigned_worker is not None:
            notify(request.assigned_worker, "REQUEST_CANCELLED_BY_STUDENT", payload)
        db.session.commit()
    except ApiError:
        db.session.rollback()
        raise
    except (IntegrityError, StaleDataError):
        db.session.rollback()
        return _after_cancel_clash(request.id, student)
    return request


def _after_cancel_clash(request_id: int, student: User) -> CleaningRequest:
    db.session.expire_all()
    latest = db.session.get(CleaningRequest, request_id)
    if latest is not None and latest.status == RequestStatus.CANCELLED_BY_STUDENT:
        return latest
    raise ApiError(
        409, "STALE_REQUEST", "This request was updated by someone else. Please refresh."
    )


def _notification_payload(request: CleaningRequest) -> dict:
    return {
        "request_id": request.id,
        "room": request.room_snapshot.get("number"),
        "reason": request.urgent_reason,
    }


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
    if request is not None and not can_view(request, viewer):
        record_security_event(
            "ACCESS_DENIED",
            "cleaning_request",
            request_id,
            actor=viewer,
            detail={"role": viewer.role.value},
        )
        request = None
    if request is None:
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


def _enum_list(value: str | None, enum_type, label: str) -> list:
    if not value:
        return []
    items = []
    for part in value.split(","):
        try:
            items.append(enum_type(part.strip().upper()))
        except ValueError:
            raise ApiError(400, "INVALID_FILTER", f"Unknown {label}: {part.strip()}.") from None
    return items


def _whole_number(value: str | None, label: str, default: int, low: int, high: int) -> int:
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except ValueError:
        raise ApiError(400, "INVALID_FILTER", f"{label} must be a whole number.") from None
    if not low <= number <= high:
        raise ApiError(400, "INVALID_FILTER", f"{label} must be between {low} and {high}.")
    return number


def list_requests(
    viewer: User,
    status: str | None = None,
    floor: str | None = None,
    priority: str | None = None,
    page: str | None = None,
    per_page: str | None = None,
) -> dict:
    statuses = _enum_list(status, RequestStatus, "status")
    priorities = _enum_list(priority, Priority, "priority")
    floor_number = _whole_number(floor, "floor", None, 0, 99) if floor else None
    page_number = _whole_number(page, "page", 1, 1, 100000)
    size = _whole_number(per_page, "per_page", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)

    query = db.select(CleaningRequest)
    if viewer.role == Role.STUDENT:
        query = query.filter(CleaningRequest.student_id == viewer.id)
    elif viewer.role == Role.WORKER:
        query = query.filter(CleaningRequest.assigned_worker_id == viewer.id)
    elif viewer.role not in (Role.SUPERVISOR, Role.SUPER_ADMIN):
        query = query.filter(db.false())
    if statuses:
        query = query.filter(CleaningRequest.status.in_(statuses))
    if priorities:
        query = query.filter(CleaningRequest.priority.in_(priorities))
    if floor_number is not None:
        query = (
            query.join(Room, CleaningRequest.room_id == Room.id)
            .join(Wing, Room.wing_id == Wing.id)
            .join(Floor, Wing.floor_id == Floor.id)
            .filter(Floor.number == floor_number)
        )

    total = db.session.scalar(db.select(db.func.count()).select_from(query.subquery()))
    rows = db.session.scalars(
        query.order_by(CleaningRequest.created_at.desc(), CleaningRequest.id.desc())
        .limit(size)
        .offset((page_number - 1) * size)
    ).all()
    return {
        "requests": [request_summary(row) for row in rows],
        "page": page_number,
        "per_page": size,
        "total": total,
    }


def request_summary(request: CleaningRequest) -> dict:
    return {
        "id": request.id,
        "status": request.status.value,
        "status_label": STATUS_LABELS[request.status],
        "is_active": not is_terminal(request.status),
        "priority": request.priority.value,
        "room": request.room_snapshot,
        "availability_mode": request.availability_mode.value,
        "credit_reservation": request.credit_reservation.value,
        "student": _person(request.student),
        "assigned_worker": _person(request.assigned_worker),
        "created_at": _iso(request.created_at),
        "closed_at": _iso(request.closed_at),
        "resolution_reason": request.resolution_reason,
    }
