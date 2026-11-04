from datetime import datetime, timedelta

from sqlalchemy.orm.exc import StaleDataError

from app.cleaning.models import ArrivalResponse as R
from app.cleaning.models import AvailabilityMode, CleaningRequest, CreditReservation
from app.cleaning.models import RequestStatus as S
from app.cleaning.service import (
    _free_worker,
    _notification_payload,
    _settled,
    _take_back,
    cancel_request,
)
from app.cleaning.workflow import (
    ON_SITE_STATES,
    STATUS_LABELS,
    no_answer,
    pause_event,
    record_event,
    stale,
    transition,
)
from app.common.audit import record_audit
from app.common.errors import ApiError, clean_text, fail
from app.common.models import as_utc, utcnow
from app.common.time import clock
from app.credits.service import release_credit
from app.extensions import db
from app.notifications.service import notify, notify_supervisors
from app.users.models import User, WorkerAvailability
from app.workers.service import on_site, worker_tasks

RESPONSE_MINUTES = 5
PROBLEM_STATES = ON_SITE_STATES | {S.ACCEPTED_QUEUED}
ANSWERS = {"COME_IN": R.COME_IN, "WAIT": R.WAIT_REQUESTED, "CANCEL": None}


def _save(request: CleaningRequest, done, work) -> CleaningRequest:
    try:
        work()
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        return _settled(request.id, done)
    return request


def _step(request: CleaningRequest, *states: S) -> None:
    if request.status not in states:
        raise fail("WRONG_STEP", status=STATUS_LABELS[request.status].lower())


def _not_before(when: datetime, now: datetime) -> None:
    if now < as_utc(when):
        raise fail("TOO_EARLY", time=clock(when))


def _payload(request: CleaningRequest, **extra) -> dict:
    return {**_notification_payload(request), **extra}


def _wait(request: CleaningRequest, now: datetime) -> None:
    request.arrival_response = R.WAITING.value
    request.response_deadline = now + timedelta(minutes=RESPONSE_MINUTES)


def set_off(request: CleaningRequest, worker: User, now: datetime | None = None):
    now = now or utcnow()
    if request.status == S.EN_ROUTE:
        return request
    _step(request, S.ACCEPTED_QUEUED)
    tasks = worker_tasks(worker.id)
    if any(task.status in ON_SITE_STATES for task in tasks):
        raise fail("ANOTHER_TASK_ACTIVE")
    if tasks[0].id != request.id:
        raise fail("NOT_NEXT_TASK", room=tasks[0].room_snapshot["number"])
    if request.availability_mode == AvailabilityMode.TIME_WINDOW:
        eta = timedelta(minutes=request.latest_eta_minutes)
        _not_before(as_utc(request.window_start) - eta, now)

    def work():
        transition(request, S.EN_ROUTE, actor=worker)
        payload = _payload(request, worker=worker.name)
        notify(request.student, "WORKER_EN_ROUTE", payload)
        notify_supervisors("WORKER_EN_ROUTE", payload)

    return _save(request, lambda latest: latest.status == S.EN_ROUTE, work)


def arrive(request: CleaningRequest, worker: User, now: datetime | None = None):
    now = now or utcnow()
    if request.status == S.ARRIVED:
        return request
    _step(request, S.EN_ROUTE)
    if request.availability_mode == AvailabilityMode.TIME_WINDOW:
        _not_before(request.window_start, now)

    def work():
        request.arrival_response = None
        request.response_deadline = now + timedelta(minutes=RESPONSE_MINUTES)
        transition(request, S.ARRIVED, actor=worker)
        payload = _payload(request, worker=worker.name, minutes=RESPONSE_MINUTES)
        notify(request.student, "WORKER_ARRIVED", payload)

    return _save(request, lambda latest: latest.status == S.ARRIVED, work)


def answer_door(request: CleaningRequest, student: User, answer, now: datetime | None = None):
    now = now or utcnow()
    if answer not in ANSWERS:
        raise fail("BAD_ANSWER", "answer")
    if answer == "CANCEL":
        return cancel_request(request, student)
    response = ANSWERS[answer]
    if request.status == S.ARRIVED and request.arrival_response == response:
        return request
    _step(request, S.ARRIVED)
    if as_utc(request.response_deadline) <= now:
        raise fail("RESPONSE_CLOSED")
    if response == R.WAIT_REQUESTED and request.arrival_response is not None:
        raise fail("WAIT_USED")

    def work():
        request.arrival_response = response.value
        record_event(request, response.value, student, request.status)
        notify(request.assigned_worker, response.value, _payload(request))

    return _save(request, lambda latest: latest.arrival_response == response, work)


def accept_wait(request: CleaningRequest, worker: User, now: datetime | None = None):
    now = now or utcnow()
    if request.status == S.ARRIVED and request.arrival_response == R.WAITING:
        return request
    _step(request, S.ARRIVED)
    if request.arrival_response != R.WAIT_REQUESTED:
        raise fail("NO_WAIT_ASKED")

    def work():
        _wait(request, now)
        record_event(request, "WAIT_ACCEPTED", worker, request.status)
        notify(request.student, "WAIT_ACCEPTED", _payload(request, minutes=RESPONSE_MINUTES))

    return _save(request, lambda latest: latest.arrival_response == R.WAITING, work)


def _escalate(request: CleaningRequest, worker: User, event: str, reason: str):
    def work():
        payload = {"reason": reason}
        transition(request, S.SUPERVISOR_INTERVENTION, worker, event, payload)
        payload = _payload(request, worker=worker.name, reason=reason)
        notify(request.student, "NEEDS_SUPERVISOR", payload)
        notify_supervisors("NEEDS_SUPERVISOR", payload)

    return _save(request, lambda latest: latest.status == S.SUPERVISOR_INTERVENTION, work)


def refuse_wait(request: CleaningRequest, worker: User):
    if request.status == S.SUPERVISOR_INTERVENTION:
        return request
    _step(request, S.ARRIVED)
    if request.arrival_response != R.WAIT_REQUESTED:
        raise fail("NO_WAIT_ASKED")
    return _escalate(request, worker, "WAIT_REFUSED", "The worker could not wait")


def report_problem(request: CleaningRequest, worker: User, reason):
    reason = clean_text(reason, "reason", "The reason")
    if not reason:
        raise fail("PROBLEM_REASON", "reason")
    if request.status == S.SUPERVISOR_INTERVENTION:
        return request
    _step(request, *PROBLEM_STATES)
    return _escalate(request, worker, "PROBLEM_REPORTED", reason)


def start_cleaning(request: CleaningRequest, worker: User):
    if request.status == S.CLEANING_IN_PROGRESS:
        return request
    _step(request, S.ARRIVED)
    if request.arrival_response != R.COME_IN:
        raise fail("NOT_LET_IN")

    def work():
        transition(request, S.CLEANING_IN_PROGRESS, actor=worker, event_type="STARTED")
        record_audit("CLEANING_STARTED", "cleaning_request", request.id, actor=worker)

    return _save(request, lambda latest: latest.status == S.CLEANING_IN_PROGRESS, work)


def mark_unavailable(request: CleaningRequest, worker=None, now: datetime | None = None):
    now = now or utcnow()
    if request.status == S.STUDENT_UNAVAILABLE:
        return request
    _step(request, S.ARRIVED)
    if request.arrival_response not in (None, R.WAITING):
        raise fail("STUDENT_ANSWERED")
    if not no_answer(request, now):
        raise fail("STILL_WAITING", time=clock(request.response_deadline))

    def work():
        reason = "The student did not answer at the door."
        if request.credit_reservation == CreditReservation.RESERVED:
            release_credit(request.student, request.id, reason, actor=worker)
            request.credit_reservation = CreditReservation.RELEASED
        request.resolution_reason = reason
        transition(request, S.STUDENT_UNAVAILABLE, actor=worker)
        _free_worker(request.assigned_worker)
        for user in (request.student, request.assigned_worker):
            notify(user, "STUDENT_UNAVAILABLE", _payload(request))
        notify_supervisors("STUDENT_UNAVAILABLE", _payload(request))

    return _save(request, lambda latest: latest.status == S.STUDENT_UNAVAILABLE, work)


def time_out_arrivals(now: datetime | None = None) -> int:
    now = now or utcnow()
    closed = 0
    arrived = db.select(CleaningRequest).filter_by(status=S.ARRIVED)
    for request in db.session.scalars(arrived).all():
        if not no_answer(request, now):
            continue
        try:
            mark_unavailable(request, None, now)
            closed += 1
        except ApiError:
            db.session.rollback()
    return closed


def resolve_intervention(
    request: CleaningRequest, supervisor: User, decision, reason, lock_version, now=None
):
    now = now or utcnow()
    reason = clean_text(reason, "reason", "The reason")
    if not reason:
        raise fail("RESOLVE_REASON", "reason")
    if decision not in ("resume", "reassign"):
        raise fail("BAD_DECISION", "decision")
    if type(lock_version) is not int:
        raise fail("BAD_LOCK_VERSION", "lock_version")
    _step(request, S.SUPERVISOR_INTERVENTION)
    if lock_version != request.lock_version:
        raise stale(request.id)
    prior, worker = pause_event(request).old_state, request.assigned_worker
    if decision == "reassign" and prior == S.CLEANING_IN_PROGRESS:
        raise fail("CLEANING_STARTED")
    if decision == "resume" and worker.worker_profile.availability == WorkerAvailability.OFF_DUTY:
        raise fail("WORKER_OFF_DUTY")
    if decision == "resume" and on_site(worker.id):
        raise fail("WORKER_AT_OTHER_ROOM")
    target = S.AWAITING_REASSIGNMENT if decision == "reassign" else prior

    def work():
        if decision == "reassign":
            _take_back(request, supervisor, "REASSIGNED", reason)
            notify(worker, "TASK_REASSIGNED", _payload(request, reason=reason))
        else:
            if prior == S.ARRIVED:
                _wait(request, now)
            worker.worker_profile.availability = WorkerAvailability.BUSY
            transition(request, prior, supervisor, "RESUMED", {"reason": reason})
            for user in (worker, request.student):
                notify(user, "WORK_RESUMED", _payload(request, reason=reason))
        record_audit(
            f"INTERVENTION_{decision.upper()}",
            "cleaning_request",
            request.id,
            actor=supervisor,
            after={"status": target.value},
            reason=reason,
        )

    return _save(request, lambda latest: latest.status == target, work)
