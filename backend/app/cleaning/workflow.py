from datetime import datetime, timedelta
from typing import Any

from app.cleaning.models import ArrivalResponse as R
from app.cleaning.models import CleaningRequest, RequestEvent, RequestStatus
from app.common.errors import ApiError, fail
from app.common.models import as_utc, utcnow
from app.extensions import db

S = RequestStatus

TERMINAL_STATES = frozenset(
    {
        S.CLOSED_SUCCESSFUL,
        S.CLOSED_VALID_AFTER_REVIEW,
        S.CLOSED_UNSATISFACTORY,
        S.STUDENT_UNAVAILABLE,
        S.CANCELLED_BY_STUDENT,
        S.CANCELLED_BY_SUPERVISOR,
        S.EXPIRED,
    }
)

ACTIVE_STATES = frozenset(set(S) - TERMINAL_STATES)

ALLOWED_TRANSITIONS: dict[RequestStatus, frozenset[RequestStatus]] = {
    S.SUBMITTED: frozenset(
        {
            S.AWAITING_ASSIGNMENT,
            S.AWAITING_STUDENT_RESCHEDULE,
            S.CANCELLED_BY_STUDENT,
            S.CANCELLED_BY_SUPERVISOR,
            S.EXPIRED,
        }
    ),
    S.AWAITING_ASSIGNMENT: frozenset(
        {
            S.OFFERED,
            S.AWAITING_STUDENT_RESCHEDULE,
            S.CANCELLED_BY_STUDENT,
            S.CANCELLED_BY_SUPERVISOR,
            S.EXPIRED,
        }
    ),
    S.OFFERED: frozenset(
        {
            S.ACCEPTED_QUEUED,
            S.AWAITING_REASSIGNMENT,
            S.AWAITING_STUDENT_RESCHEDULE,
            S.CANCELLED_BY_STUDENT,
            S.CANCELLED_BY_SUPERVISOR,
            S.EXPIRED,
        }
    ),
    S.AWAITING_REASSIGNMENT: frozenset(
        {
            S.OFFERED,
            S.AWAITING_STUDENT_RESCHEDULE,
            S.CANCELLED_BY_STUDENT,
            S.CANCELLED_BY_SUPERVISOR,
            S.EXPIRED,
        }
    ),
    S.ACCEPTED_QUEUED: frozenset(
        {
            S.EN_ROUTE,
            S.AWAITING_REASSIGNMENT,
            S.AWAITING_STUDENT_RESCHEDULE,
            S.SUPERVISOR_INTERVENTION,
            S.CANCELLED_BY_STUDENT,
            S.CANCELLED_BY_SUPERVISOR,
            S.EXPIRED,
        }
    ),
    S.AWAITING_STUDENT_RESCHEDULE: frozenset(
        {S.SUBMITTED, S.AWAITING_ASSIGNMENT, S.CANCELLED_BY_STUDENT, S.EXPIRED}
    ),
    S.EN_ROUTE: frozenset(
        {
            S.ARRIVED,
            S.AWAITING_REASSIGNMENT,
            S.SUPERVISOR_INTERVENTION,
            S.CANCELLED_BY_STUDENT,
            S.CANCELLED_BY_SUPERVISOR,
        }
    ),
    S.ARRIVED: frozenset(
        {
            S.CLEANING_IN_PROGRESS,
            S.STUDENT_UNAVAILABLE,
            S.AWAITING_REASSIGNMENT,
            S.SUPERVISOR_INTERVENTION,
            S.CANCELLED_BY_STUDENT,
            S.CANCELLED_BY_SUPERVISOR,
        }
    ),
    S.CLEANING_IN_PROGRESS: frozenset(
        {S.AWAITING_STUDENT_CONFIRMATION, S.SUPERVISOR_INTERVENTION, S.CANCELLED_BY_SUPERVISOR}
    ),
    S.SUPERVISOR_INTERVENTION: frozenset(
        {
            S.ACCEPTED_QUEUED,
            S.EN_ROUTE,
            S.ARRIVED,
            S.CLEANING_IN_PROGRESS,
            S.AWAITING_REASSIGNMENT,
            S.CANCELLED_BY_SUPERVISOR,
        }
    ),
    S.AWAITING_STUDENT_CONFIRMATION: frozenset({S.CLOSED_SUCCESSFUL, S.DISPUTED}),
    S.DISPUTED: frozenset({S.CLOSED_VALID_AFTER_REVIEW, S.CLOSED_UNSATISFACTORY}),
    **{state: frozenset() for state in TERMINAL_STATES},
}

STUDENT_CANCELLABLE = frozenset(
    {
        S.SUBMITTED,
        S.AWAITING_ASSIGNMENT,
        S.OFFERED,
        S.AWAITING_REASSIGNMENT,
        S.ACCEPTED_QUEUED,
        S.AWAITING_STUDENT_RESCHEDULE,
        S.EN_ROUTE,
        S.ARRIVED,
    }
)

SUPERVISOR_CHANGEABLE = frozenset({S.SUBMITTED, S.AWAITING_ASSIGNMENT, S.AWAITING_REASSIGNMENT})
ON_SITE_STATES = frozenset({S.EN_ROUTE, S.ARRIVED, S.CLEANING_IN_PROGRESS})
REASSIGNABLE = frozenset({S.OFFERED, S.ACCEPTED_QUEUED, S.EN_ROUTE, S.ARRIVED})
SUPERVISOR_CANCELLABLE = (STUDENT_CANCELLABLE | ON_SITE_STATES | {S.SUPERVISOR_INTERVENTION}) - {
    S.AWAITING_STUDENT_RESCHEDULE
}
OFFERABLE = frozenset({S.AWAITING_ASSIGNMENT, S.AWAITING_REASSIGNMENT})
DELAY_STATES = frozenset({S.ACCEPTED_QUEUED, S.EN_ROUTE})
PRE_TRAVEL = SUPERVISOR_CHANGEABLE | {S.OFFERED, S.ACCEPTED_QUEUED}

STATUS_LABELS: dict[RequestStatus, str] = {
    S.SUBMITTED: "Waiting for supervisor approval",
    S.AWAITING_ASSIGNMENT: "Approved, finding a worker",
    S.OFFERED: "Offered to a worker",
    S.AWAITING_REASSIGNMENT: "Finding another worker",
    S.ACCEPTED_QUEUED: "Worker accepted",
    S.AWAITING_STUDENT_RESCHEDULE: "Waiting for the student to choose a new time",
    S.EN_ROUTE: "Worker on the way",
    S.ARRIVED: "Worker at the room",
    S.CLEANING_IN_PROGRESS: "Cleaning in progress",
    S.AWAITING_STUDENT_CONFIRMATION: "Waiting for the student to confirm",
    S.SUPERVISOR_INTERVENTION: "Supervisor is looking into it",
    S.DISPUTED: "Disputed, under review",
    S.CLOSED_SUCCESSFUL: "Cleaned",
    S.CLOSED_VALID_AFTER_REVIEW: "Closed after review: work was valid",
    S.CLOSED_UNSATISFACTORY: "Closed after review: work was unsatisfactory",
    S.STUDENT_UNAVAILABLE: "Closed: student did not respond",
    S.CANCELLED_BY_STUDENT: "Cancelled by the student",
    S.CANCELLED_BY_SUPERVISOR: "Cancelled by the supervisor",
    S.EXPIRED: "Expired",
}

EVENT_LABELS: dict[str, str] = {
    "SUBMITTED": "Request submitted",
    "CANCELLED_BY_STUDENT": "Cancelled by the student",
    "APPROVED": "Approved by the supervisor",
    "DETAILS_CHANGED": "Priority or time changed by the supervisor",
    "OFFERED": "Offered to a worker",
    "ACCEPTED": "Accepted by the worker",
    "DECLINED": "Declined by the worker",
    "TIMED_OUT": "Offer not answered in time",
    "REASSIGNED": "Taken back from the worker by the supervisor",
    "OFF_DUTY": "Worker went off duty",
    "CANCELLED_BY_SUPERVISOR": "Cancelled by the supervisor",
    "COME_IN": "The student said come in",
    "WAIT_REQUESTED": "The student asked the worker to wait",
    "WAIT_ACCEPTED": "The worker agreed to wait",
    "WAIT_REFUSED": "The worker could not wait",
    "PROBLEM_REPORTED": "The worker reported a problem",
    "STARTED": "Cleaning started",
    "RESUMED": "The supervisor let the work continue",
    "ETA_UPDATED": "The worker changed the arrival time",
    "DELAY_FLAGGED": "The student said the worker is late",
    "DELAY_ESCALATED": "The delay went to the supervisor",
    "DELAY_RESOLVED": "The supervisor dealt with the delay",
    "WINDOW_MISSED": "The time window ended before the worker came",
    "RESCHEDULED": "The student chose a new time",
}


def stale(request_id: int) -> ApiError:
    latest = db.session.scalar(
        db.select(RequestEvent).filter_by(request_id=request_id).order_by(RequestEvent.id.desc())
    )
    who = latest.actor.name if latest and latest.actor else "someone else"
    return fail("STALE_REQUEST", who=who)


def is_terminal(state: RequestStatus) -> bool:
    return state in TERMINAL_STATES


def can_transition(old: RequestStatus, new: RequestStatus) -> bool:
    return new in ALLOWED_TRANSITIONS[old]


def record_event(
    request: CleaningRequest,
    event_type: str,
    actor=None,
    old_state: RequestStatus | None = None,
    payload: dict[str, Any] | None = None,
) -> RequestEvent:
    event = RequestEvent(
        request=request,
        actor_id=actor.id if actor is not None else None,
        event_type=event_type,
        old_state=old_state,
        new_state=request.status,
        payload_json=payload,
    )
    db.session.add(event)
    return event


def transition(
    request: CleaningRequest,
    new_state: RequestStatus,
    actor=None,
    event_type: str | None = None,
    payload: dict[str, Any] | None = None,
    expected_version: int | None = None,
) -> RequestEvent:
    if expected_version is not None and expected_version != request.lock_version:
        raise stale(request.id)
    old_state = request.status
    if not can_transition(old_state, new_state):
        raise fail("ILLEGAL_TRANSITION", old=old_state.value, new=new_state.value)
    request.status = new_state
    if is_terminal(new_state):
        request.active_student_id = None
        request.closed_at = utcnow()
    event = record_event(request, event_type or new_state.value, actor, old_state, payload)
    db.session.flush()
    return event


def can_leave(request: CleaningRequest, tasks: list[CleaningRequest]) -> bool:
    return not any(task.status in ON_SITE_STATES for task in tasks) and tasks[0].id == request.id


def no_answer(request: CleaningRequest, now: datetime) -> bool:
    if request.arrival_response not in (None, R.WAITING):
        return False
    return as_utc(request.response_deadline) <= now


def pause_event(request: CleaningRequest) -> RequestEvent | None:
    if request.status != S.SUPERVISOR_INTERVENTION:
        return None
    return next(
        event
        for event in reversed(request.events)
        if event.new_state == S.SUPERVISOR_INTERVENTION
        and event.old_state != S.SUPERVISOR_INTERVENTION
    )


def late_after(request: CleaningRequest, times: int = 1) -> datetime:
    return as_utc(request.accepted_at) + timedelta(minutes=request.original_eta_minutes * times)


def delay_state(request: CleaningRequest, now: datetime) -> str | None:
    if request.status not in DELAY_STATES or request.accepted_at is None:
        return None
    return request.delay_state or ("DUE" if late_after(request) <= now else "NOT_DUE")


def sweep(query, act) -> int:
    done = 0
    for row in db.session.scalars(query).all():
        try:
            done += bool(act(row))
        except ApiError:
            db.session.rollback()
    return done
