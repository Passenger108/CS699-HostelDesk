from typing import Any

from app.cleaning.models import CleaningRequest, RequestEvent, RequestStatus
from app.common.errors import ApiError, fail
from app.common.models import utcnow
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
        {S.AWAITING_ASSIGNMENT, S.CANCELLED_BY_STUDENT, S.EXPIRED}
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
OFFERABLE = frozenset({S.AWAITING_ASSIGNMENT, S.AWAITING_REASSIGNMENT})

STATUS_LABELS: dict[RequestStatus, str] = {
    S.SUBMITTED: "Waiting for supervisor approval",
    S.AWAITING_ASSIGNMENT: "Approved, finding a worker",
    S.OFFERED: "Offered to a worker",
    S.AWAITING_REASSIGNMENT: "Finding another worker",
    S.ACCEPTED_QUEUED: "Worker accepted",
    S.AWAITING_STUDENT_RESCHEDULE: "Please choose a new time",
    S.EN_ROUTE: "Worker on the way",
    S.ARRIVED: "Worker at your room",
    S.CLEANING_IN_PROGRESS: "Cleaning in progress",
    S.AWAITING_STUDENT_CONFIRMATION: "Please confirm the cleaning",
    S.SUPERVISOR_INTERVENTION: "Supervisor is looking into it",
    S.DISPUTED: "Disputed, under review",
    S.CLOSED_SUCCESSFUL: "Cleaned",
    S.CLOSED_VALID_AFTER_REVIEW: "Closed after review: work was valid",
    S.CLOSED_UNSATISFACTORY: "Closed after review: work was unsatisfactory",
    S.STUDENT_UNAVAILABLE: "Closed: student did not respond",
    S.CANCELLED_BY_STUDENT: "Cancelled by you",
    S.CANCELLED_BY_SUPERVISOR: "Cancelled by the supervisor",
    S.EXPIRED: "Expired",
}

EVENT_LABELS: dict[str, str] = {
    "SUBMITTED": "Request submitted",
    "CANCELLED_BY_STUDENT": "Cancelled by the student",
    "APPROVED": "Approved by the supervisor",
    "DETAILS_CHANGED": "Priority or time changed by the supervisor",
    "OFFERED": "Offered to a worker",
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
