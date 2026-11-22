from datetime import date, timedelta

from app.cleaning.schemas import iso, person
from app.cleaning.service import _whole_number
from app.common.audit import AuditLog
from app.common.errors import fail
from app.common.time import week_start_at
from app.extensions import db
from app.users.models import User

PAGE_SIZE = 50


def _day(value: str | None, label: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise fail("BAD_DATE", label.lower().replace(" ", "_"), label=label) from None


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
    return {
        "entries": [audit_dict(entry, actor) for entry, actor in rows],
        "page": page,
        "per_page": PAGE_SIZE,
        "total": total,
        "actions": list(actions),
    }


def audit_dict(entry: AuditLog, actor: User | None) -> dict:
    return {
        "id": entry.id,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "actor": person(actor),
        "reason": entry.reason,
        "before": entry.before_json,
        "after": entry.after_json,
        "ip_address": entry.ip_address,
        "created_at": iso(entry.created_at),
    }
