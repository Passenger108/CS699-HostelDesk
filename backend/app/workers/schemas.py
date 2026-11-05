import math
from datetime import datetime, timedelta

from app.cleaning.models import CleaningRequest
from app.cleaning.models import RequestStatus as S
from app.cleaning.workflow import STATUS_LABELS
from app.common.models import as_utc, utcnow
from app.common.time import clock
from app.extensions import db
from app.users.models import AccountStatus, Role, User
from app.workers.service import worker_fields, worker_tasks

CLEAN_MINUTES = 20


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
        "tasks": rows,
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
