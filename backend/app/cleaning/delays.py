from datetime import datetime, timedelta
from math import ceil

from app.cleaning.arrival import _payload, _save, _step
from app.cleaning.models import AvailabilityMode, CleaningRequest, DelayState
from app.cleaning.models import RequestStatus as S
from app.cleaning.recommendations import recommend
from app.cleaning.schemas import availability_label
from app.cleaning.service import (
    _approved,
    _free_worker,
    _plain,
    _withdraw_offers,
    availability_from,
    check_eta,
    drop_worker,
    release,
)
from app.cleaning.workflow import (
    DELAY_STATES,
    PRE_TRAVEL,
    delay_state,
    late_after,
    record_event,
    stale,
    sweep,
    transition,
)
from app.common.audit import record_audit
from app.common.errors import clean_text, fail
from app.common.models import as_utc, utcnow
from app.common.settings import get_setting
from app.common.time import clock, day_clock
from app.extensions import db
from app.notifications.service import notify, notify_supervisors
from app.users.models import User

OPEN_DELAYS = (DelayState.FLAGGED, DelayState.ESCALATED)


def update_eta(request: CleaningRequest, worker: User, eta_minutes, now: datetime | None = None):
    now = now or utcnow()
    due = now + timedelta(minutes=check_eta(eta_minutes))
    _step(request, *DELAY_STATES)
    before = request.latest_eta_minutes
    after = ceil((due - as_utc(request.accepted_at)).total_seconds() / 60)

    def work():
        request.latest_eta_minutes = after
        record_event(request, "ETA_UPDATED", worker, request.status, {"eta_minutes": eta_minutes})
        record_audit(
            "ETA_UPDATED",
            "cleaning_request",
            request.id,
            actor=worker,
            before={"latest_eta_minutes": before},
            after={"latest_eta_minutes": after},
        )
        payload = _payload(request, worker=worker.name, time=clock(due))
        notify(request.student, "ETA_UPDATED", payload)
        notify_supervisors("ETA_UPDATED", payload)

    return _save(request, lambda latest: latest.latest_eta_minutes == after, work)


def flag_delay(request: CleaningRequest, student: User, now: datetime | None = None):
    now = now or utcnow()
    if delay_state(request, now) in OPEN_DELAYS:
        return request
    _step(request, *DELAY_STATES)
    if late_after(request) > now:
        raise fail("NOT_LATE_YET", time=clock(late_after(request)))

    def work():
        request.delay_state = DelayState.FLAGGED.value
        record_event(request, "DELAY_FLAGGED", student, request.status)
        record_audit("DELAY_FLAGGED", "cleaning_request", request.id, actor=student)
        notify(request.assigned_worker, "DELAY_FLAGGED", _payload(request))

    return _save(request, lambda latest: latest.delay_state in OPEN_DELAYS, work)


def _escalate_delay(request: CleaningRequest, now: datetime):
    worker = request.assigned_worker
    picks = [pick["worker"] for pick in recommend(request, now)]
    names = [pick["name"] for pick in picks if pick["id"] != worker.id][:3]
    workers = ", ".join(names) or "none right now"

    def work():
        request.delay_state = DelayState.ESCALATED.value
        record_event(request, "DELAY_ESCALATED", None, request.status, {"workers": workers})
        notify_supervisors(
            "DELAY_ESCALATED", _payload(request, worker=worker.name, workers=workers)
        )

    return _save(request, lambda latest: latest.delay_state == DelayState.ESCALATED, work)


def escalate_delays(now: datetime | None = None) -> int:
    now = now or utcnow()
    flagged = db.select(CleaningRequest).filter(
        CleaningRequest.delay_state == DelayState.FLAGGED.value,
        CleaningRequest.status.in_(DELAY_STATES),
    )
    return sweep(
        flagged, lambda request: late_after(request, 2) <= now and _escalate_delay(request, now)
    )


def resolve_delay(request: CleaningRequest, supervisor: User, reason, lock_version):
    reason = clean_text(reason, "reason", "The reason")
    if not reason:
        raise fail("RESOLVE_REASON", "reason")
    if type(lock_version) is not int:
        raise fail("BAD_LOCK_VERSION", "lock_version")
    if request.delay_state == DelayState.RESOLVED:
        return request
    if delay_state(request, utcnow()) not in OPEN_DELAYS:
        raise fail("NO_DELAY")
    if lock_version != request.lock_version:
        raise stale(request.id)

    def work():
        before = request.delay_state
        request.delay_state = DelayState.RESOLVED.value
        record_event(request, "DELAY_RESOLVED", supervisor, request.status, {"reason": reason})
        record_audit(
            "DELAY_RESOLVED",
            "cleaning_request",
            request.id,
            actor=supervisor,
            before={"delay_state": before},
            after={"delay_state": request.delay_state},
            reason=reason,
        )
        for user in (request.student, request.assigned_worker):
            notify(user, "DELAY_RESOLVED", _payload(request, reason=reason))

    return _save(request, lambda latest: latest.delay_state == DelayState.RESOLVED, work)


def _miss_window(request: CleaningRequest, now: datetime):
    def work():
        worker = drop_worker(request)
        request.reschedule_deadline = now + timedelta(hours=get_setting("reschedule_hours"))
        transition(request, S.AWAITING_STUDENT_RESCHEDULE, event_type="WINDOW_MISSED")
        payload = _payload(request, time=day_clock(request.reschedule_deadline))
        notify(request.student, "WINDOW_MISSED", payload)
        notify_supervisors("WINDOW_MISSED", payload)
        if worker:
            _free_worker(worker)
            notify(worker, "TASK_REASSIGNED", _payload(request, reason="The time window ended"))

    return _save(request, lambda latest: latest.status == S.AWAITING_STUDENT_RESCHEDULE, work)


def miss_windows(now: datetime | None = None) -> int:
    now = now or utcnow()
    waiting = db.select(CleaningRequest).filter(
        CleaningRequest.availability_mode == AvailabilityMode.TIME_WINDOW,
        CleaningRequest.status.in_(PRE_TRAVEL),
    )
    return sweep(
        waiting, lambda request: as_utc(request.window_end) <= now and _miss_window(request, now)
    )


def reschedule(request: CleaningRequest, student: User, mode, start=None, end=None, now=None):
    now = now or utcnow()
    if request.events[-1].event_type == "RESCHEDULED":
        return request
    availability = availability_from(mode, start, end, now)
    _step(request, S.AWAITING_STUDENT_RESCHEDULE)
    if as_utc(request.reschedule_deadline) <= now:
        raise fail("RESCHEDULE_CLOSED")
    target = S.AWAITING_ASSIGNMENT if _approved(request) else S.SUBMITTED

    def work():
        for key, value in availability.items():
            setattr(request, key, value)
        request.reschedule_deadline = None
        transition(request, target, student, "RESCHEDULED")
        after = {key: _plain(value) for key, value in availability.items()}
        record_audit(
            "REQUEST_RESCHEDULED", "cleaning_request", request.id, actor=student, after=after
        )
        notify_supervisors("RESCHEDULED", _payload(request, when=availability_label(request, now)))

    return _save(request, lambda latest: latest.status == target, work)


def _expire(request: CleaningRequest, reason: str):
    def work():
        release(request, reason)
        _withdraw_offers(request, accepted=True)
        request.resolution_reason = reason
        transition(request, S.EXPIRED, payload={"reason": reason})
        _free_worker(request.assigned_worker)
        for user in (request.student, request.assigned_worker):
            if user:
                notify(user, "REQUEST_EXPIRED", _payload(request, reason=reason))
        notify_supervisors("REQUEST_EXPIRED", _payload(request, reason=reason))

    return _save(request, lambda latest: latest.status == S.EXPIRED, work)


def _lapsed(request: CleaningRequest, now: datetime):
    if request.status == S.AWAITING_STUDENT_RESCHEDULE:
        due, reason = request.reschedule_deadline, "No new time was chosen in time."
    elif request.availability_mode != AvailabilityMode.TIME_WINDOW:
        due, reason = request.available_until, "The day ended before a worker came."
    else:
        return False
    return as_utc(due) <= now and _expire(request, reason)


def expire_requests(now: datetime | None = None) -> int:
    now = now or utcnow()
    open_requests = db.select(CleaningRequest).filter(
        CleaningRequest.status.in_(PRE_TRAVEL | {S.AWAITING_STUDENT_RESCHEDULE})
    )
    return sweep(open_requests, lambda request: _lapsed(request, now))
