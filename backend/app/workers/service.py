import math
from datetime import datetime, timedelta

from app.cleaning.models import CleaningRequest, RequestStatus
from app.cleaning.workflow import ON_SITE_STATES, STATUS_LABELS
from app.common.audit import record_audit
from app.common.errors import clean_text, fail
from app.common.models import as_utc, utcnow
from app.common.time import clock
from app.extensions import db
from app.hostel_structure.models import Location
from app.hostel_structure.service import location_dict
from app.notifications.models import Notification
from app.notifications.service import notify, notify_supervisors
from app.users.models import AccountStatus, Role, User, WorkerAvailability, WorkerProfile

FRESH_MINUTES = 30
CLEAN_MINUTES = 20
AVAILABILITY_LABELS = {"AVAILABLE": "Available", "BUSY": "Busy", "OFF_DUTY": "Off duty"}
S = RequestStatus
WORK_STATES = (S.ACCEPTED_QUEUED, S.EN_ROUTE, S.ARRIVED, S.CLEANING_IN_PROGRESS)


def worker_fields(profile: WorkerProfile, now: datetime) -> dict:
    updated_at = as_utc(profile.location_updated_at)
    age = None if updated_at is None else int((now - updated_at).total_seconds() // 60)
    freshness = "UNKNOWN" if age is None else "FRESH" if age < FRESH_MINUTES else "STALE"
    note = {
        "UNKNOWN": "Location not shared yet",
        "FRESH": f"Updated {age} min ago",
        "STALE": f"Updated {age} min ago, may be out of date",
    }[freshness]
    return {
        "employee_id": profile.employee_id,
        "shift": profile.shift,
        "availability": profile.availability.value,
        "availability_label": AVAILABILITY_LABELS[profile.availability.value],
        "last_location": location_dict(profile.last_location),
        "location_updated_at": updated_at.isoformat() if updated_at else None,
        "location_age_minutes": age,
        "freshness": freshness,
        "location_note": note,
    }


def worker_tasks(worker_id: int) -> list[CleaningRequest]:
    return list(
        db.session.scalars(
            db.select(CleaningRequest)
            .filter(
                CleaningRequest.assigned_worker_id == worker_id,
                CleaningRequest.status.in_(WORK_STATES),
            )
            .order_by(
                CleaningRequest.status == S.ACCEPTED_QUEUED,
                db.func.coalesce(CleaningRequest.queue_position, 0),
                CleaningRequest.id,
            )
        )
    )


def busy_minutes(tasks: list[CleaningRequest], now: datetime) -> int:
    ends = [
        as_utc(task.accepted_at) + timedelta(minutes=task.latest_eta_minutes or 0)
        for task in tasks
        if task.accepted_at
    ]
    return max([math.ceil((end - now).total_seconds() / 60) for end in ends] + [0])


def queue_rows(tasks: list[CleaningRequest], now: datetime) -> list[dict]:
    rows, free = [], now
    for task in tasks:
        due = as_utc(task.accepted_at) + timedelta(minutes=task.latest_eta_minutes)
        late = bool(rows) and free > due
        rows.append(
            {
                "id": task.id,
                "room": task.room_snapshot["number"],
                "status": STATUS_LABELS[task.status],
                "movable": task.status == S.ACCEPTED_QUEUED,
                "due_label": f"Promised by {clock(due)}",
                "warning": f"Earlier work ends around {clock(free)}, so this may be late."
                if late
                else None,
            }
        )
        free = max(free, due) + timedelta(minutes=CLEAN_MINUTES)
    return rows


def worker_dict(worker: User, now: datetime | None = None) -> dict:
    now = now or utcnow()
    tasks = worker_tasks(worker.id)
    rows = queue_rows(tasks, now)
    late = sum(1 for row in rows if row["warning"])
    requested = as_utc(worker.worker_profile.off_duty_requested_at)
    return {
        "id": worker.id,
        "name": worker.name,
        "phone": worker.phone,
        **worker_fields(worker.worker_profile, now),
        "tasks": [{key: row[key] for key in ("id", "room", "status")} for row in rows],
        "busy_minutes": busy_minutes(tasks, now),
        "queue_warning": f"{late} of {len(rows)} tasks may be late." if late else None,
        "off_duty_requested_at": requested.isoformat() if requested else None,
    }


def list_workers(now: datetime | None = None) -> list[dict]:
    workers = db.session.scalars(
        db.select(User)
        .filter_by(role=Role.WORKER, account_status=AccountStatus.ACTIVE)
        .order_by(User.name)
    )
    return [worker_dict(worker, now) for worker in workers if worker.worker_profile]


def get_worker(worker_id) -> User:
    worker = db.session.get(User, worker_id) if type(worker_id) is int else None
    if (
        worker is None
        or worker.role != Role.WORKER
        or worker.worker_profile is None
        or worker.account_status != AccountStatus.ACTIVE
    ):
        raise fail("WORKER_NOT_FOUND", "worker_id")
    return worker


def _move(worker: User, location_id, actor: User, reason: str | None, now) -> User:
    location = db.session.get(Location, location_id) if type(location_id) is int else None
    if location is None:
        raise fail("BAD_LOCATION", "location_id")
    profile = worker.worker_profile
    before = profile.last_location.label if profile.last_location else None
    profile.last_location = location
    profile.location_updated_at = now or utcnow()
    record_audit(
        "LOCATION_CORRECTED" if reason else "LOCATION_UPDATED",
        "worker",
        worker.id,
        actor=actor,
        before={"location": before},
        after={"location": location.label},
        reason=reason,
    )
    db.session.commit()
    return worker


def update_location(worker: User, location_id, now: datetime | None = None) -> User:
    return _move(get_worker(worker.id), location_id, worker, None, now)


def correct_location(
    worker_id, supervisor: User, location_id, reason: str | None, now: datetime | None = None
) -> User:
    reason = clean_text(reason, "reason", "The reason")
    if not reason:
        raise fail("LOCATION_REASON", "reason")
    return _move(get_worker(worker_id), location_id, supervisor, reason, now)


def remind_stale_locations(now: datetime | None = None) -> int:
    now = now or utcnow()
    reminded = 0
    workers = db.session.scalars(
        db.select(User).filter_by(role=Role.WORKER, account_status=AccountStatus.ACTIVE)
    )
    for worker in workers.all():
        profile = worker.worker_profile
        if profile is None or profile.availability == WorkerAvailability.OFF_DUTY:
            continue
        fields = worker_fields(profile, now)
        if fields["freshness"] != "STALE":
            continue
        sent = db.session.scalar(
            db.select(Notification.id).filter(
                Notification.user_id == worker.id,
                Notification.type == "LOCATION_STALE",
                Notification.created_at >= profile.location_updated_at,
            )
        )
        if sent is None:
            notify(worker, "LOCATION_STALE", {"minutes": fields["location_age_minutes"]})
            reminded += 1
    db.session.commit()
    return reminded


def request_off_duty(worker: User, now: datetime | None = None) -> User:
    profile = worker.worker_profile
    if profile.availability == WorkerAvailability.OFF_DUTY:
        raise fail("ALREADY_OFF_DUTY")
    if profile.off_duty_requested_at is None:
        if any(task.status in ON_SITE_STATES for task in worker_tasks(worker.id)):
            raise fail("OFF_DUTY_ON_SITE")
        profile.off_duty_requested_at = now or utcnow()
        record_audit("OFF_DUTY_REQUESTED", "worker", worker.id, actor=worker)
        notify_supervisors("OFF_DUTY_REQUESTED", {"worker": worker.name})
        db.session.commit()
    return worker


def return_to_duty(worker: User) -> User:
    if worker.worker_profile.availability == WorkerAvailability.OFF_DUTY:
        worker.worker_profile.availability = WorkerAvailability.AVAILABLE
        record_audit("BACK_ON_DUTY", "worker", worker.id, actor=worker)
        db.session.commit()
    return worker
