from datetime import datetime, timedelta

from app.cleaning.models import ArrivalResponse as R
from app.cleaning.models import (
    AssignmentOffer,
    AvailabilityMode,
    CleaningRequest,
    OfferStatus,
    RequestEvent,
    RequestStatus,
)
from app.cleaning.workflow import (
    EVENT_LABELS,
    OFFERABLE,
    ON_SITE_STATES,
    REASSIGNABLE,
    STATUS_LABELS,
    STUDENT_CANCELLABLE,
    SUPERVISOR_CANCELLABLE,
    SUPERVISOR_CHANGEABLE,
    can_leave,
    is_terminal,
    no_answer,
    pause_event,
)
from app.common.models import as_utc, utcnow
from app.common.time import clock, hostel_now
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
SUPERVISOR_ROLES = (Role.SUPERVISOR, Role.SUPER_ADMIN)


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
        }
    else:
        checks = {
            "cancel": status in STUDENT_CANCELLABLE and (status != S.ARRIVED or at_door),
            "come_in": at_door and answer != R.COME_IN,
            "wait": at_door and answer is None,
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
        "created_at": iso(request.created_at),
        "closed_at": iso(request.closed_at),
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
