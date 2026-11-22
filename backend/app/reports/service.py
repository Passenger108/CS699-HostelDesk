import csv
import io
import re
from datetime import date, datetime, timedelta

from app.cleaning.models import CleaningRequest
from app.cleaning.models import RequestStatus as S
from app.cleaning.workflow import is_terminal
from app.common.errors import fail
from app.common.time import hostel_now, week_start_at
from app.extensions import db

MONTH_PATTERN = re.compile(r"(\d{4})-(\d{2})")
CLEANED = frozenset({S.CLOSED_SUCCESSFUL, S.CLOSED_VALID_AFTER_REVIEW})
NOT_DONE = frozenset({S.CLOSED_UNSATISFACTORY, S.STUDENT_UNAVAILABLE, S.EXPIRED})
CANCELLED = frozenset({S.CANCELLED_BY_STUDENT, S.CANCELLED_BY_SUPERVISOR})
COUNTS = (
    ("requests", "Requests"),
    ("cleaned", "Cleaned"),
    ("disputed", "Disputed"),
    ("not_done", "Not done"),
    ("cancelled", "Cancelled"),
    ("open", "Still open"),
    ("delayed", "Reported late"),
    ("average_minutes", "Average minutes to finish"),
    ("ratings", "Ratings"),
    ("average_rating", "Average rating"),
)
COLUMNS = {
    "days": (("date_label", "Date"), *COUNTS),
    "workers": (("worker", "Worker"), *COUNTS[1:3], COUNTS[6], *COUNTS[8:]),
}


def parse_month(value: str | None, now: datetime | None = None) -> date:
    if not value:
        return hostel_now(now).date().replace(day=1)
    match = MONTH_PATTERN.fullmatch(value)
    if not match or not 1 <= int(match[2]) <= 12:
        raise fail("BAD_MONTH", "month")
    return date(int(match[1]), int(match[2]), 1)


def _average(values: list[float], digits: int | None) -> float | None:
    return round(sum(values) / len(values), digits) if values else None


def _finished_minutes(request: CleaningRequest) -> float | None:
    done = next((e for e in request.events if e.event_type == "COMPLETED"), None)
    if done is None:
        return None
    return (done.occurred_at - request.created_at).total_seconds() / 60


def _had(request: CleaningRequest, event_type: str) -> bool:
    return any(event.event_type == event_type for event in request.events)


def summarise(requests: list[CleaningRequest]) -> dict:
    minutes = [m for m in map(_finished_minutes, requests) if m is not None]
    ratings = [request.feedback.rating for request in requests if request.feedback]
    return {
        "requests": len(requests),
        "cleaned": sum(request.status in CLEANED for request in requests),
        "disputed": sum(_had(request, "DISPUTED") for request in requests),
        "not_done": sum(request.status in NOT_DONE for request in requests),
        "cancelled": sum(request.status in CANCELLED for request in requests),
        "open": sum(not is_terminal(request.status) for request in requests),
        "delayed": sum(_had(request, "DELAY_FLAGGED") for request in requests),
        "average_minutes": _average(minutes, None),
        "ratings": len(ratings),
        "average_rating": _average(ratings, 1),
    }


def monthly_report(month: str | None = None, now: datetime | None = None) -> dict:
    first = parse_month(month, now)
    after = (first + timedelta(days=32)).replace(day=1)
    rows = db.session.scalars(
        db.select(CleaningRequest)
        .filter(
            CleaningRequest.created_at >= week_start_at(first),
            CleaningRequest.created_at < week_start_at(after),
        )
        .order_by(CleaningRequest.id)
    ).all()
    days, workers = {}, {}
    for row in rows:
        days.setdefault(hostel_now(row.created_at).date(), []).append(row)
        if row.assigned_worker:
            workers.setdefault(row.assigned_worker.name, []).append(row)
    return {
        "month": f"{first:%Y-%m}",
        "label": f"{first:%B %Y}",
        "columns": {
            key: [{"key": k, "label": label} for k, label in cols] for key, cols in COLUMNS.items()
        },
        "totals": summarise(rows),
        "days": [
            {"date": day.isoformat(), "date_label": f"{day.day} {day:%b}", **summarise(group)}
            for day, group in sorted(days.items())
        ],
        "workers": [
            {"worker": name, **summarise(group)} for name, group in sorted(workers.items())
        ],
    }


def report_csv(month: str | None, table: str | None) -> tuple[str, str]:
    table = table or "days"
    if table not in COLUMNS:
        raise fail("BAD_TABLE", "table")
    report = monthly_report(month)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([label for _, label in COLUMNS[table]])
    rows = report[table]
    if table == "days":
        rows = [*rows, {"date_label": "Total", **report["totals"]}]
    for row in rows:
        writer.writerow(["" if row[key] is None else row[key] for key, _ in COLUMNS[table]])
    return out.getvalue(), f"hosteldesk-cleaning-{report['month']}-{table}.csv"
