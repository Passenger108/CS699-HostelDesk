from datetime import date, timedelta

from app.cleaning.schemas import iso, person
from app.cleaning.service import _whole_number
from app.common.audit import AuditLog
from app.common.errors import fail
from app.common.time import hostel_now, week_start_at
from app.extensions import db
from app.reports.service import FIRST_MONTH
from app.users.models import User

PAGE_SIZE = 50
PEOPLE = ("user", "worker")


def _day(value: str | None, label: str) -> date | None:
    if not value:
        return None
    field = label.lower().replace(" ", "_")
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise fail("BAD_DATE", field, label=label) from None
    last = hostel_now().date()
    if not FIRST_MONTH <= day <= last:
        raise fail("OUT_OF_RANGE", field, label=label, low=FIRST_MONTH, high=last)
    return day


def audit_page(args) -> dict:
    query = db.select(AuditLog, User).outerjoin(User, AuditLog.actor_id == User.id)
    if args.get("action"):
        query = query.filter(AuditLog.action == args["action"].strip().upper())
    if args.get("entity_type"):
        query = query.filter(AuditLog.entity_type == args["entity_type"].strip())
    if args.get("actor"):
        text = f"%{args['actor'].strip()}%"
        query = query.filter(db.or_(User.name.ilike(text), User.login_id.ilike(text)))
    if args.get("request"):
        number = _whole_number(args["request"], "request", None, 1, 10**9)
        query = query.filter(
            AuditLog.entity_type == "cleaning_request", AuditLog.entity_id == str(number)
        )
    start, end = _day(args.get("date_from"), "Date from"), _day(args.get("date_to"), "Date to")
    if start:
        query = query.filter(AuditLog.created_at >= week_start_at(start))
    if end:
        query = query.filter(AuditLog.created_at < week_start_at(end + timedelta(days=1)))
    page = _whole_number(args.get("page"), "page", 1, 1, 100000)
    total = db.session.scalar(db.select(db.func.count()).select_from(query.subquery()))
    rows = db.session.execute(
        query.order_by(AuditLog.id.desc()).limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE)
    ).all()
    actions = db.session.scalars(db.select(AuditLog.action).distinct().order_by(AuditLog.action))
    people = _people(entry for entry, _ in rows)
    return {
        "entries": [audit_dict(entry, actor, people) for entry, actor in rows],
        "first_day": FIRST_MONTH.isoformat(),
        "page": page,
        "per_page": PAGE_SIZE,
        "total": total,
        "actions": list(actions),
    }


def _people(entries) -> dict[str, str]:
    ids = {int(e.entity_id) for e in entries if e.entity_type in PEOPLE and e.entity_id}
    users = db.session.scalars(db.select(User).filter(User.id.in_(ids))) if ids else []
    return {str(user.id): f"{user.name} · {user.login_id}" for user in users}


def entity_label(entry: AuditLog, people: dict[str, str]) -> str:
    kind = entry.entity_type.replace("_", " ").capitalize()
    if entry.entity_type == "cleaning_request":
        kind = "Request"
    if entry.entity_type in PEOPLE:
        return people.get(entry.entity_id, f"{kind} {entry.entity_id}")
    return f"{kind} {entry.entity_id}" if entry.entity_id else kind


def audit_dict(entry: AuditLog, actor: User | None, people: dict[str, str]) -> dict:
    return {
        "id": entry.id,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "entity_label": entity_label(entry, people),
        "actor": person(actor),
        "reason": entry.reason,
        "before": entry.before_json,
        "after": entry.after_json,
        "ip_address": entry.ip_address,
        "created_at": iso(entry.created_at),
    }
