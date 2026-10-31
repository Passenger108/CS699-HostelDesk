from datetime import datetime, time, timedelta, timezone
from enum import Enum

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.cleaning.models import (
    AssignmentOffer,
    AvailabilityMode,
    CleaningRequest,
    CreditReservation,
    OfferStatus,
    Priority,
    RequestEvent,
    RequestStatus,
)
from app.cleaning.recommendations import recommend
from app.cleaning.workflow import (
    ACTIVE_STATES,
    EVENT_LABELS,
    OFFERABLE,
    ON_SITE_STATES,
    REASSIGNABLE,
    STATUS_LABELS,
    STUDENT_CANCELLABLE,
    SUPERVISOR_CANCELLABLE,
    SUPERVISOR_CHANGEABLE,
    is_terminal,
    record_event,
    stale,
    transition,
)
from app.common.audit import record_audit, record_security_event
from app.common.errors import ApiError, clean_text, fail
from app.common.models import as_utc, utcnow
from app.common.time import HOSTEL_TZ, clock, hostel_now
from app.credits.service import balance, release_credit, reserve_credit
from app.extensions import db
from app.hostel_structure.models import Floor, Room, Wing
from app.hostel_structure.service import room_dict
from app.notifications.service import notify, notify_supervisors
from app.users.models import Role, User, WorkerAvailability
from app.workers.service import get_worker, worker_dict, worker_tasks

KEY_LIMIT = 64
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
OFFER_MINUTES = 5
ETA_STEP, ETA_MAX = 5, 120
S = RequestStatus
SUPERVISOR_ROLES = (Role.SUPERVISOR, Role.SUPER_ADMIN)
PRIORITY_ORDER = {Priority.EMERGENCY: 0, Priority.URGENT: 1, Priority.NORMAL: 2}
FAILED_STATES = frozenset(
    {S.STUDENT_UNAVAILABLE, S.EXPIRED, S.CANCELLED_BY_SUPERVISOR, S.CLOSED_UNSATISFACTORY}
)
BOARD_GROUPS = {
    "urgent": "Urgent and emergency",
    "new": "New, waiting for approval",
    "awaiting_assignment": "Waiting for a worker",
    "offered": "Offered to a worker",
    "active": "Active",
    "delayed": "Delayed",
    "disputed": "Disputed or needs a decision",
    "failed": "Failed or unavailable today",
}


def _parse_time(value: str | None, label: str, field: str) -> time:
    try:
        return time.fromisoformat(value or "")
    except ValueError:
        raise fail("BAD_TIME", field, label=label) from None


def _today_at(now: datetime, at: time) -> datetime:
    local = hostel_now(now)
    return datetime.combine(local.date(), at, tzinfo=HOSTEL_TZ).astimezone(timezone.utc)


def end_of_day(now: datetime) -> datetime:
    return _today_at(now, time(23, 59, 59))


def availability_from(
    mode: str | None, window_start: str | None, window_end: str | None, now: datetime
) -> dict:
    try:
        availability_mode = AvailabilityMode(mode)
    except ValueError:
        raise fail("BAD_MODE", "availability_mode") from None

    if availability_mode != AvailabilityMode.TIME_WINDOW:
        if end_of_day(now) <= now:
            raise fail("DAY_OVER", "availability_mode")
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
        raise fail("WINDOW_ORDER", "window_end")
    if start < local_now.replace(second=0, microsecond=0):
        raise fail("WINDOW_PAST", "window_start")
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
        raise fail("KEY_TOO_LONG", "client_key", limit=KEY_LIMIT)
    if client_key:
        earlier = _earlier_submit(student, client_key)
        if earlier:
            return earlier, False

    try:
        priority_value = Priority(priority or Priority.NORMAL.value)
    except ValueError:
        raise fail("BAD_STUDENT_PRIORITY", "priority") from None
    if priority_value == Priority.EMERGENCY:
        raise fail("EMERGENCY_FOR_STAFF", "priority")
    note = clean_text(note, "note", "The note")
    urgent_reason = clean_text(urgent_reason, "urgent_reason", "The urgent reason")
    if priority_value == Priority.URGENT and not urgent_reason:
        raise fail("URGENT_REASON_REQUIRED", "urgent_reason")
    if priority_value == Priority.NORMAL:
        urgent_reason = None
    availability = availability_from(availability_mode, window_start, window_end, now)

    profile = student.student_profile
    if profile is None or profile.room is None:
        raise fail("PROFILE_INCOMPLETE")
    if not (student.phone or "").strip():
        raise fail("PHONE_REQUIRED")
    if active_request(student):
        raise fail("ACTIVE_REQUEST_EXISTS")

    current = balance(student.id, now)
    is_normal = priority_value == Priority.NORMAL
    has_credit = (current["available"] if is_normal else current["standard_available"]) > 0
    if is_normal and not has_credit:
        raise fail("NO_CREDIT")

    request = CleaningRequest(
        student=student,
        active_student_id=student.id,
        client_key=client_key,
        room=profile.room,
        room_snapshot=room_dict(profile.room),
        contact_phone=student.phone.strip(),
        status=S.SUBMITTED,
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
    raise fail("ACTIVE_REQUEST_EXISTS")


def cancel_request(request: CleaningRequest, actor: User, reason=None) -> CleaningRequest:
    by_student = actor.role == Role.STUDENT
    if by_student and request.student_id != actor.id:
        raise fail("REQUEST_NOT_FOUND")
    status = S.CANCELLED_BY_STUDENT if by_student else S.CANCELLED_BY_SUPERVISOR
    if request.status == status:
        return request
    reason = (
        "Cancelled by the student" if by_student else clean_text(reason, "reason", "The reason")
    )
    if not reason:
        raise fail("CANCEL_REASON", "reason")
    if request.status not in (STUDENT_CANCELLABLE if by_student else SUPERVISOR_CANCELLABLE):
        raise fail("CANNOT_CANCEL")

    old_state = request.status
    try:
        if request.credit_reservation == CreditReservation.RESERVED:
            who = "student" if by_student else "supervisor"
            release_credit(
                request.student, request.id, f"Request cancelled by the {who}", actor=actor
            )
            request.credit_reservation = CreditReservation.RELEASED
        request.resolution_reason = reason
        _withdraw_offers(request)
        transition(request, status, actor=actor, payload=None if by_student else {"reason": reason})
        _free_worker(request.assigned_worker)
        record_audit(
            "REQUEST_CANCELLED",
            "cleaning_request",
            request.id,
            actor=actor,
            before={"status": old_state.value},
            after={
                "status": request.status.value,
                "credit_reservation": request.credit_reservation.value,
            },
            reason=None if by_student else reason,
        )
        payload = {**_notification_payload(request), "reason": reason}
        if by_student:
            notify_supervisors("REQUEST_CANCELLED_BY_STUDENT", payload)
        for user in (request.assigned_worker, None if by_student else request.student):
            if user is not None:
                notify(user, f"REQUEST_{status.value}", payload)
        db.session.commit()
    except ApiError:
        db.session.rollback()
        raise
    except (IntegrityError, StaleDataError):
        db.session.rollback()
        return _settled(request.id, lambda latest: latest.status == status)
    return request


def _settled(request_id: int, done) -> CleaningRequest:
    db.session.expire_all()
    latest = db.session.get(CleaningRequest, request_id)
    if latest is not None and done(latest):
        return latest
    raise stale(request_id)


def _approved(request: CleaningRequest) -> bool:
    return any(event.event_type == "APPROVED" for event in request.events)


def approve_request(request: CleaningRequest, supervisor: User) -> CleaningRequest:
    if _approved(request):
        return request
    if request.status != S.SUBMITTED:
        raise fail("CANNOT_APPROVE")
    try:
        transition(request, S.AWAITING_ASSIGNMENT, actor=supervisor, event_type="APPROVED")
        record_audit(
            "REQUEST_APPROVED",
            "cleaning_request",
            request.id,
            actor=supervisor,
            before={"status": S.SUBMITTED.value},
            after={"status": request.status.value},
        )
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        return _settled(request.id, _approved)
    return request


def _plain(value):
    if isinstance(value, datetime):
        return _iso(value)
    return value.value if isinstance(value, Enum) else value


def change_request(
    request: CleaningRequest,
    supervisor: User,
    lock_version=None,
    reason: str | None = None,
    priority: str | None = None,
    availability_mode: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    now: datetime | None = None,
) -> CleaningRequest:
    now = now or utcnow()
    reason = clean_text(reason, "reason", "The reason")
    if not reason:
        raise fail("CHANGE_REASON", "reason")
    if type(lock_version) is not int:
        raise fail("BAD_LOCK_VERSION", "lock_version")
    changes = {}
    if priority is not None:
        try:
            changes["priority"] = Priority(priority)
        except ValueError:
            raise fail("BAD_PRIORITY", "priority") from None
    if availability_mode is not None or window_start or window_end:
        changes.update(availability_from(availability_mode, window_start, window_end, now))
    if not changes:
        raise fail("NO_CHANGE")
    before = {key: _plain(getattr(request, key)) for key in changes}
    after = {key: _plain(value) for key, value in changes.items()}
    if before == after:
        return request
    if request.status not in SUPERVISOR_CHANGEABLE:
        raise fail("CANNOT_CHANGE")
    if lock_version != request.lock_version:
        raise stale(request.id)
    if (
        changes.get("priority") == Priority.NORMAL
        and request.credit_reservation != CreditReservation.RESERVED
    ):
        raise fail("NORMAL_NEEDS_CREDIT", "priority")
    for key, value in changes.items():
        setattr(request, key, value)
    try:
        record_event(
            request,
            "DETAILS_CHANGED",
            supervisor,
            request.status,
            {"reason": reason, "before": before, "after": after},
        )
        record_audit(
            "REQUEST_DETAILS_CHANGED",
            "cleaning_request",
            request.id,
            actor=supervisor,
            before=before,
            after=after,
            reason=reason,
        )
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        raise stale(request.id) from None
    return request


def _withdraw_offers(request: CleaningRequest) -> None:
    for offer in request.offers:
        if offer.status == OfferStatus.PENDING:
            offer.status = OfferStatus.WITHDRAWN


def _offered_to(worker_id: int):
    return lambda request: request.status == S.OFFERED and request.assigned_worker_id == worker_id


def offer_request(
    request: CleaningRequest, supervisor: User, worker_id, lock_version, now: datetime | None = None
) -> CleaningRequest:
    now = now or utcnow()
    if type(lock_version) is not int:
        raise fail("BAD_LOCK_VERSION", "lock_version")
    worker = get_worker(worker_id)
    if _offered_to(worker.id)(request):
        return request
    if request.status not in OFFERABLE:
        raise fail("CANNOT_OFFER")
    if lock_version != request.lock_version:
        raise stale(request.id)
    if worker.worker_profile.availability == WorkerAvailability.OFF_DUTY:
        raise fail("WORKER_OFF_DUTY", "worker_id")
    pick = next((p for p in recommend(request, now) if p["worker"]["id"] == worker.id), None)
    explanation = pick["reason"] if pick else "Chosen by the supervisor from the full list."
    try:
        request.assigned_worker = worker
        request.offered_at = now
        offer = AssignmentOffer(
            request=request,
            worker=worker,
            offered_by=supervisor,
            status=OfferStatus.PENDING,
            response_deadline=now + timedelta(minutes=OFFER_MINUTES),
            explanation=explanation,
        )
        db.session.add(offer)
        transition(request, S.OFFERED, actor=supervisor, payload={"worker_id": worker.id})
        record_audit(
            "OFFER_CREATED",
            "cleaning_request",
            request.id,
            actor=supervisor,
            after={"worker_id": worker.id, "explanation": explanation},
        )
        payload = {**_notification_payload(request), "minutes": OFFER_MINUTES}
        notify(worker, "OFFER_RECEIVED", payload)
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        return _settled(request.id, _offered_to(worker.id))
    return request


def _free_worker(worker: User | None) -> None:
    profile = worker.worker_profile if worker else None
    if profile and profile.availability == WorkerAvailability.BUSY and not worker_tasks(worker.id):
        profile.availability = WorkerAvailability.AVAILABLE


def get_offer_for(offer_id: int, worker: User) -> AssignmentOffer:
    offer = db.session.get(AssignmentOffer, offer_id)
    if offer is None or offer.worker_id != worker.id:
        raise fail("OFFER_NOT_FOUND")
    return offer


def worker_offers(worker: User) -> list[dict]:
    offers = db.session.scalars(
        db.select(AssignmentOffer)
        .filter_by(worker_id=worker.id, status=OfferStatus.PENDING)
        .order_by(AssignmentOffer.id)
    )
    return [
        {**offer_dict(offer), "request": request_dict(offer.request, worker)} for offer in offers
    ]


def _check_open(offer: AssignmentOffer, now: datetime) -> None:
    if offer.status != OfferStatus.PENDING or offer.request.status != S.OFFERED:
        raise fail("OFFER_CLOSED")
    if as_utc(offer.response_deadline) <= now:
        raise fail("OFFER_EXPIRED")


def accept_offer(
    offer: AssignmentOffer, worker: User, eta_minutes, now: datetime | None = None
) -> CleaningRequest:
    now = now or utcnow()
    request = offer.request
    if offer.status == OfferStatus.ACCEPTED:
        return request
    if type(eta_minutes) is not int or not 0 < eta_minutes <= ETA_MAX or eta_minutes % ETA_STEP:
        raise fail("BAD_ETA", "eta_minutes")
    _check_open(offer, now)
    try:
        offer.status = OfferStatus.ACCEPTED
        request.accepted_at = now
        request.queue_position = 1 + max(
            (task.queue_position or 0 for task in worker_tasks(worker.id)), default=0
        )
        request.original_eta_minutes = request.latest_eta_minutes = eta_minutes
        worker.worker_profile.availability = WorkerAvailability.BUSY
        payload = {"eta_minutes": eta_minutes}
        transition(request, S.ACCEPTED_QUEUED, actor=worker, event_type="ACCEPTED", payload=payload)
        record_audit("OFFER_ACCEPTED", "cleaning_request", request.id, actor=worker, after=payload)
        payload = {**_notification_payload(request), "worker": worker.name, "eta": eta_minutes}
        notify(request.student, "OFFER_ACCEPTED", payload)
        notify_supervisors("OFFER_ACCEPTED", payload)
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        return _settled(request.id, lambda _: offer.status == OfferStatus.ACCEPTED)
    return request


def _end_offer(offer: AssignmentOffer, status: OfferStatus, actor: User | None, reason: str):
    request = offer.request
    try:
        offer.status = status
        request.assigned_worker = None
        payload = {"worker_id": offer.worker_id, "reason": reason}
        transition(
            request, S.AWAITING_REASSIGNMENT, actor=actor, event_type=status.value, payload=payload
        )
        action = f"OFFER_{status.value}"
        record_audit(action, "cleaning_request", request.id, actor=actor, after=payload)
        payload = {**_notification_payload(request), "worker": offer.worker.name, "reason": reason}
        notify_supervisors(action, payload)
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        return _settled(request.id, lambda _: offer.status == status)
    return request


def decline_offer(
    offer: AssignmentOffer, worker: User, reason, now: datetime | None = None
) -> CleaningRequest:
    if offer.status == OfferStatus.DECLINED:
        return offer.request
    reason = clean_text(reason, "reason", "The reason")
    if not reason:
        raise fail("DECLINE_REASON", "reason")
    _check_open(offer, now or utcnow())
    offer.decline_reason = reason
    return _end_offer(offer, OfferStatus.DECLINED, worker, reason)


def time_out_offers(now: datetime | None = None) -> int:
    now = now or utcnow()
    timed_out = 0
    pending = db.select(AssignmentOffer.id).filter_by(status=OfferStatus.PENDING)
    for offer_id in db.session.scalars(pending).all():
        offer = db.session.get(AssignmentOffer, offer_id)
        if offer.status != OfferStatus.PENDING or as_utc(offer.response_deadline) > now:
            continue
        try:
            _end_offer(offer, OfferStatus.TIMED_OUT, None, "NO_RESPONSE")
            timed_out += 1
        except ApiError:
            db.session.rollback()
    return timed_out


def reassign_request(
    request: CleaningRequest, supervisor: User, reason, lock_version, worker_id=None, now=None
) -> CleaningRequest:
    reason = clean_text(reason, "reason", "The reason")
    if not reason:
        raise fail("REASSIGN_REASON", "reason")
    if type(lock_version) is not int:
        raise fail("BAD_LOCK_VERSION", "lock_version")
    if request.status not in REASSIGNABLE:
        raise fail("CANNOT_REASSIGN")
    if lock_version != request.lock_version:
        raise stale(request.id)
    former = request.assigned_worker
    try:
        _take_back(request, supervisor, "REASSIGNED", reason)
        record_audit(
            "REQUEST_REASSIGNED",
            "cleaning_request",
            request.id,
            actor=supervisor,
            before={"worker_id": former.id},
            reason=reason,
        )
        notify(former, "TASK_REASSIGNED", {**_notification_payload(request), "reason": reason})
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        raise stale(request.id) from None
    if worker_id is None:
        return request
    return offer_request(request, supervisor, worker_id, request.lock_version, now)


def _take_back(request: CleaningRequest, actor: User, event: str, reason: str, keep=False) -> None:
    worker = request.assigned_worker
    _withdraw_offers(request)
    if not keep:
        request.assigned_worker = request.accepted_at = request.latest_eta_minutes = None
    payload = {"worker_id": worker.id, "reason": reason}
    target = S.SUPERVISOR_INTERVENTION if keep else S.AWAITING_REASSIGNMENT
    transition(request, target, actor=actor, event_type=event, payload=payload)
    _free_worker(worker)
    notify(request.student, "WORKER_CHANGED", _notification_payload(request))


def reorder_queue(worker: User, actor: User, order) -> list[dict]:
    tasks = {task.id: task for task in worker_tasks(worker.id) if task.status == S.ACCEPTED_QUEUED}
    if type(order) is not list or any(type(item) is not int for item in order):
        raise fail("BAD_QUEUE", "order")
    if sorted(order) != sorted(tasks):
        raise fail("QUEUE_CHANGED")
    before = list(tasks)
    try:
        for position, request_id in enumerate(order, 1):
            tasks[request_id].queue_position = position
        record_audit(
            "QUEUE_REORDERED", "worker", worker.id, actor=actor, before=before, after=order
        )
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        raise fail("QUEUE_CHANGED") from None
    return worker_dict(worker)["tasks"]


def approve_off_duty(worker_id, supervisor: User) -> User:
    worker = get_worker(worker_id)
    profile = worker.worker_profile
    if profile.off_duty_requested_at is None:
        raise fail("NO_OFF_DUTY_REQUEST")
    work = db.session.scalars(
        db.select(CleaningRequest).filter(
            CleaningRequest.assigned_worker_id == worker.id,
            CleaningRequest.status.in_(REASSIGNABLE | ON_SITE_STATES),
        )
    ).all()
    try:
        profile.availability = WorkerAvailability.OFF_DUTY
        profile.off_duty_requested_at = None
        for request in work:
            on_site = request.status in ON_SITE_STATES
            _take_back(request, supervisor, "OFF_DUTY", "The worker went off duty", on_site)
        moved = [request.id for request in work]
        record_audit("OFF_DUTY_APPROVED", "worker", worker.id, actor=supervisor, after=moved)
        notify(worker, "OFF_DUTY_APPROVED", {"count": len(moved)})
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        raise fail("QUEUE_CHANGED") from None
    return worker


def offer_dict(offer: AssignmentOffer | None) -> dict | None:
    if offer is None:
        return None
    return {
        "id": offer.id,
        "worker": _person(offer.worker),
        "status": offer.status.value,
        "response_deadline": _iso(offer.response_deadline),
        "explanation": offer.explanation,
        "summary": f"Offered to {offer.worker.name} until {clock(offer.response_deadline)}. "
        f"{offer.explanation}",
    }


def _notification_payload(request: CleaningRequest) -> dict:
    return {
        "request_id": request.id,
        "room": request.room_snapshot.get("number"),
        "reason": request.urgent_reason,
    }


def can_view(request: CleaningRequest, viewer: User) -> bool:
    if viewer.role in SUPERVISOR_ROLES:
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
        raise fail("REQUEST_NOT_FOUND")
    return request


def allowed_actions(request: CleaningRequest, viewer: User) -> list[str]:
    if viewer.role in SUPERVISOR_ROLES:
        checks = {
            "approve": request.status == S.SUBMITTED,
            "change": request.status in SUPERVISOR_CHANGEABLE,
            "offer": request.status in OFFERABLE,
            "reassign": request.status in REASSIGNABLE,
            "cancel": request.status in SUPERVISOR_CANCELLABLE,
        }
    else:
        checks = {
            "cancel": viewer.id == request.student_id and request.status in STUDENT_CANCELLABLE
        }
    return [action for action, allowed in checks.items() if allowed]


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
        **request_summary(request),
        "urgent_reason": request.urgent_reason,
        "note": request.note,
        "contact_phone": request.contact_phone,
        "lock_version": request.lock_version,
        "actions": allowed_actions(request, viewer),
        "offer": offer_dict(request.offers[-1] if request.offers else None),
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
            raise fail("UNKNOWN_FILTER", label=label, value=part.strip()) from None
    return items


def _whole_number(value: str | None, label: str, default: int, low: int, high: int) -> int:
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except ValueError:
        raise fail("NOT_WHOLE", label=label) from None
    if not low <= number <= high:
        raise fail("OUT_OF_RANGE", label=label, low=low, high=high)
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
        "availability": {
            "mode": request.availability_mode.value,
            "label": availability_label(request, utcnow()),
            "window_start": _iso(request.window_start),
            "window_end": _iso(request.window_end),
            "available_until": _iso(request.available_until),
        },
        "credit_reservation": request.credit_reservation.value,
        "student": _person(request.student),
        "assigned_worker": _person(request.assigned_worker),
        "accepted_at": _iso(request.accepted_at),
        "latest_eta_minutes": request.latest_eta_minutes,
        "eta_label": _eta_label(request),
        "created_at": _iso(request.created_at),
        "closed_at": _iso(request.closed_at),
        "resolution_reason": request.resolution_reason,
    }


def _eta_label(request: CleaningRequest) -> str | None:
    if request.status not in (S.ACCEPTED_QUEUED, S.EN_ROUTE):
        return None
    due = as_utc(request.accepted_at) + timedelta(minutes=request.latest_eta_minutes)
    return f"{request.assigned_worker.name}, expected by {clock(due)}"


def availability_label(request: CleaningRequest, now: datetime) -> str:
    day = hostel_now(as_utc(request.available_until)).date()
    today = day == hostel_now(now).date()
    if request.availability_mode == AvailabilityMode.TIME_WINDOW:
        window = f"{clock(request.window_start)} to {clock(request.window_end)}"
        return f"{'Today' if today else f'{day.day} {day:%b}'}, {window}"
    if request.availability_mode == AvailabilityMode.AVAILABLE_NOW:
        return "Available now" if today else f"Available on {day.day} {day:%b}"
    return "Any time today" if today else f"Any time on {day.day} {day:%b}"


def _is_delayed(request: CleaningRequest, now: datetime) -> bool:
    if request.status not in (S.ACCEPTED_QUEUED, S.EN_ROUTE):
        return False
    if request.accepted_at is None or request.original_eta_minutes is None:
        return False
    return as_utc(request.accepted_at) + timedelta(minutes=request.original_eta_minutes) <= now


def board_group(request: CleaningRequest, now: datetime) -> str | None:
    status = request.status
    if status in SUPERVISOR_CHANGEABLE and request.priority != Priority.NORMAL:
        return "urgent"
    if _is_delayed(request, now):
        return "delayed"
    groups = {
        "new": {S.SUBMITTED},
        "awaiting_assignment": {
            S.AWAITING_ASSIGNMENT,
            S.AWAITING_REASSIGNMENT,
            S.AWAITING_STUDENT_RESCHEDULE,
        },
        "offered": {S.OFFERED},
        "disputed": {S.DISPUTED, S.SUPERVISOR_INTERVENTION},
        "failed": FAILED_STATES,
    }
    for key, states in groups.items():
        if status in states:
            return key
    return "active" if status in ACTIVE_STATES else None


def operations_board(now: datetime | None = None) -> dict:
    now = now or utcnow()
    since = _today_at(now, time.min)
    rows = db.session.scalars(
        db.select(CleaningRequest).filter(
            db.or_(
                CleaningRequest.status.in_(ACTIVE_STATES),
                db.and_(
                    CleaningRequest.status.in_(FAILED_STATES),
                    CleaningRequest.closed_at >= since,
                ),
            )
        )
    ).all()
    rows = sorted(rows, key=lambda row: (PRIORITY_ORDER[row.priority], row.id))
    grouped = {key: [] for key in BOARD_GROUPS}
    for row in rows:
        key = board_group(row, now)
        if key:
            grouped[key].append(request_summary(row))
    return {
        "generated_at": _iso(now),
        "groups": [
            {"key": key, "label": label, "requests": grouped[key]}
            for key, label in BOARD_GROUPS.items()
        ],
    }
