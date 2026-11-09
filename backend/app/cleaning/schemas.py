from datetime import datetime, time, timedelta, timezone

from app.cleaning.models import ArrivalResponse as R
from app.cleaning.models import (
    AssignmentOffer,
    AvailabilityMode,
    CleaningRequest,
    OfferStatus,
    Priority,
    RequestEvent,
    RequestStatus,
)
from app.cleaning.workflow import (
    ACTIVE_STATES,
    DELAY_STATES,
    EVENT_LABELS,
    OFFERABLE,
    ON_SITE_STATES,
    REASSIGNABLE,
    STATUS_LABELS,
    STUDENT_CANCELLABLE,
    SUPERVISOR_CANCELLABLE,
    SUPERVISOR_CHANGEABLE,
    can_leave,
    delay_state,
    is_terminal,
    late_after,
    no_answer,
    pause_event,
)
from app.common.models import as_utc, utcnow
from app.common.time import HOSTEL_TZ, clock, day_clock, hostel_now
from app.extensions import db
from app.users.models import Role, User, WorkerAvailability
from app.workers.service import on_site, worker_tasks

S = RequestStatus
DOOR_LABELS = {
    None: "Waiting for the student to answer",
    R.COME_IN.value: "The student said come in",
    R.WAIT_REQUESTED.value: "The student asked the worker to wait 5 minutes",
    R.WAITING.value: "The worker is waiting 5 more minutes",
}
DELAY_LABELS = {
    "NOT_DUE": "On time",
    "DUE": "Running late",
    "FLAGGED": "Running late, reported by the student",
    "ESCALATED": "Very late, sent to the supervisor",
    "RESOLVED": "Late, the supervisor dealt with it",
}
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


def offer_dict(offer: AssignmentOffer | None) -> dict | None:
    if offer is None:
        return None
    return {
        "id": offer.id,
        "worker": person(offer.worker),
        "status": offer.status.value,
        "response_deadline": iso(offer.response_deadline),
        "explanation": offer.explanation,
        "summary": f"Offered to {offer.worker.name} until {clock(offer.response_deadline)}. "
        f"{offer.explanation}",
    }


def worker_offers(worker: User) -> list[dict]:
    offers = db.session.scalars(
        db.select(AssignmentOffer)
        .filter_by(worker_id=worker.id, status=OfferStatus.PENDING)
        .order_by(AssignmentOffer.id)
    )
    return [
        {**offer_dict(offer), "request": request_dict(offer.request, worker)} for offer in offers
    ]


def allowed_actions(request: CleaningRequest, viewer: User) -> list[str]:
    status, answer, now = request.status, request.arrival_response, utcnow()
    at_door = status == S.ARRIVED and as_utc(request.response_deadline) > now
    delay = delay_state(request, now)
    if viewer.role in SUPERVISOR_ROLES:
        paused = pause_event(request)
        worker = request.assigned_worker
        checks = {
            "approve": status == S.SUBMITTED,
            "change": status in SUPERVISOR_CHANGEABLE,
            "offer": status in OFFERABLE,
            "reassign": status in REASSIGNABLE,
            "cancel": status in SUPERVISOR_CANCELLABLE,
            "resume": paused is not None
            and worker.worker_profile.availability != WorkerAvailability.OFF_DUTY
            and not on_site(worker.id),
            "find_new_worker": paused is not None and paused.old_state != S.CLEANING_IN_PROGRESS,
            "resolve_delay": delay in ("FLAGGED", "ESCALATED"),
        }
    elif viewer.role == Role.WORKER:
        if request.assigned_worker_id != viewer.id:
            return []
        checks = {
            "set_off": status == S.ACCEPTED_QUEUED and can_leave(request, worker_tasks(viewer.id)),
            "arrive": status == S.EN_ROUTE,
            "start": status == S.ARRIVED and answer == R.COME_IN,
            "accept_wait": status == S.ARRIVED and answer == R.WAIT_REQUESTED,
            "refuse_wait": status == S.ARRIVED and answer == R.WAIT_REQUESTED,
            "no_answer": status == S.ARRIVED and no_answer(request, now),
            "report_problem": status in ON_SITE_STATES | {S.ACCEPTED_QUEUED},
            "update_eta": status in DELAY_STATES,
        }
    else:
        checks = {
            "cancel": status in STUDENT_CANCELLABLE and (status != S.ARRIVED or at_door),
            "come_in": at_door and answer != R.COME_IN,
            "wait": at_door and answer is None,
            "flag_delay": delay in ("DUE", "RESOLVED"),
            "reschedule": status == S.AWAITING_STUDENT_RESCHEDULE
            and as_utc(request.reschedule_deadline) > now,
        }
    return [action for action, allowed in checks.items() if allowed]


def door_dict(request: CleaningRequest) -> dict | None:
    if request.status != S.ARRIVED:
        return None
    return {
        "answer": request.arrival_response,
        "label": DOOR_LABELS[request.arrival_response],
        "deadline": iso(request.response_deadline),
        "deadline_label": f"Answer by {clock(request.response_deadline)}",
    }


def delay_dict(request: CleaningRequest, now: datetime) -> dict | None:
    state = delay_state(request, now)
    if state is None:
        return None
    return {
        "state": state,
        "label": DELAY_LABELS[state],
        "expected_at": iso(expected_at(request)),
        "late_from": iso(late_after(request)),
        "late_from_label": clock(late_after(request)),
        "escalate_at": iso(late_after(request, 2)),
        "original_eta_minutes": request.original_eta_minutes,
    }


def reschedule_dict(request: CleaningRequest) -> dict | None:
    if request.status != S.AWAITING_STUDENT_RESCHEDULE:
        return None
    return {
        "deadline": iso(request.reschedule_deadline),
        "deadline_label": f"Choose a new time by {day_clock(request.reschedule_deadline)}",
    }


def pause_dict(request: CleaningRequest) -> dict | None:
    event = pause_event(request)
    if event is None:
        return None
    return {
        "from": event.old_state.value,
        "from_label": STATUS_LABELS[event.old_state],
        "reason": (event.payload_json or {}).get("reason"),
        "by": person(event.actor),
    }


def iso(value: datetime | None) -> str | None:
    value = as_utc(value)
    return value.isoformat() if value else None


def person(user: User | None) -> dict | None:
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
        "actor": person(event.actor),
        "occurred_at": iso(event.occurred_at),
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
        "door": door_dict(request),
        "pause": pause_dict(request),
        "reschedule": reschedule_dict(request),
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
            "window_start": iso(request.window_start),
            "window_end": iso(request.window_end),
            "available_until": iso(request.available_until),
        },
        "credit_reservation": request.credit_reservation.value,
        "student": person(request.student),
        "assigned_worker": person(request.assigned_worker),
        "accepted_at": iso(request.accepted_at),
        "latest_eta_minutes": request.latest_eta_minutes,
        "eta_label": _eta_label(request),
        "delay": delay_dict(request, utcnow()),
        "created_at": iso(request.created_at),
        "closed_at": iso(request.closed_at),
        "resolution_reason": request.resolution_reason,
    }


def _eta_label(request: CleaningRequest) -> str | None:
    if request.status not in (S.ACCEPTED_QUEUED, S.EN_ROUTE):
        return None
    return f"{request.assigned_worker.name}, expected by {clock(expected_at(request))}"


def expected_at(request: CleaningRequest) -> datetime:
    return as_utc(request.accepted_at) + timedelta(minutes=request.latest_eta_minutes)


def availability_label(request: CleaningRequest, now: datetime) -> str:
    day = hostel_now(as_utc(request.available_until)).date()
    today = day == hostel_now(now).date()
    if request.availability_mode == AvailabilityMode.TIME_WINDOW:
        window = f"{clock(request.window_start)} to {clock(request.window_end)}"
        return f"{'Today' if today else f'{day.day} {day:%b}'}, {window}"
    if request.availability_mode == AvailabilityMode.AVAILABLE_NOW:
        return "Available now" if today else f"Available on {day.day} {day:%b}"
    return "Any time today" if today else f"Any time on {day.day} {day:%b}"


def board_group(request: CleaningRequest, now: datetime) -> str | None:
    status = request.status
    if status in SUPERVISOR_CHANGEABLE and request.priority != Priority.NORMAL:
        return "urgent"
    if delay_state(request, now) in ("DUE", "FLAGGED", "ESCALATED"):
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
    since = datetime.combine(hostel_now(now).date(), time.min, tzinfo=HOSTEL_TZ)
    since = since.astimezone(timezone.utc)
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
        "generated_at": iso(now),
        "groups": [
            {"key": key, "label": label, "requests": grouped[key]}
            for key, label in BOARD_GROUPS.items()
        ],
    }
