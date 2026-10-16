from collections import defaultdict
from datetime import datetime

from sqlalchemy import func

from app.common.audit import record_audit
from app.common.errors import ApiError
from app.common.models import as_utc, utcnow
from app.common.settings import get_setting
from app.common.time import next_week_start_at, week_start
from app.credits.models import CreditEntry, CreditEntryType, CreditType
from app.extensions import db
from app.users.models import AccountStatus, Role, User

E = CreditEntryType


def _totals(student_id: int) -> dict:
    rows = db.session.execute(
        db.select(CreditEntry.entry_type, CreditEntry.credit_type, func.sum(CreditEntry.quantity))
        .where(CreditEntry.student_id == student_id)
        .group_by(CreditEntry.entry_type, CreditEntry.credit_type)
    ).all()
    totals = defaultdict(int)
    for entry_type, credit_type, quantity in rows:
        totals[(entry_type, credit_type)] = quantity or 0
    return totals


def _pool(totals: dict, credit_type: CreditType) -> dict:
    granted_by = E.WEEKLY_GRANT if credit_type == CreditType.STANDARD else E.GOODWILL_GRANT
    granted = totals[(granted_by, credit_type)]
    reserved_total = totals[(E.RESERVE, credit_type)]
    released = totals[(E.RELEASE, credit_type)]
    consumed = totals[(E.CONSUME, credit_type)]
    expired = totals[(E.EXPIRE, credit_type)]
    return {
        "available": granted - reserved_total + released - expired,
        "reserved": reserved_total - released - consumed,
        "consumed": consumed,
    }


def _unexpired_goodwill_grants(student_id: int, now: datetime) -> int:
    grants = db.session.scalars(
        db.select(CreditEntry.expires_at).filter_by(
            student_id=student_id, entry_type=E.GOODWILL_GRANT
        )
    ).all()
    return sum(1 for expires_at in grants if as_utc(expires_at) > now)


def balance(student_id: int, now: datetime | None = None) -> dict:
    now = now or utcnow()
    totals = _totals(student_id)
    standard = _pool(totals, CreditType.STANDARD)
    goodwill = _pool(totals, CreditType.GOODWILL)
    goodwill_available = max(
        0, min(goodwill["available"], _unexpired_goodwill_grants(student_id, now))
    )
    return {
        "available": standard["available"] + goodwill_available,
        "standard_available": standard["available"],
        "goodwill_available": goodwill_available,
        "reserved": standard["reserved"] + goodwill["reserved"],
        "consumed": standard["consumed"] + goodwill["consumed"],
        "cap": get_setting("credit_cap"),
        "next_grant_at": next_week_start_at(now).isoformat(),
    }


def _add(
    student_id: int, entry_type: E, credit_type: CreditType, quantity: int, reason: str, **fields
) -> CreditEntry:
    entry = CreditEntry(
        student_id=student_id,
        entry_type=entry_type,
        credit_type=credit_type,
        quantity=quantity,
        reason=reason,
        **fields,
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def expire_goodwill(student_id: int, now: datetime | None = None) -> int:
    now = now or utcnow()
    raw = _pool(_totals(student_id), CreditType.GOODWILL)["available"]
    expiring = raw - max(0, min(raw, _unexpired_goodwill_grants(student_id, now)))
    for _ in range(max(0, expiring)):
        _add(student_id, E.EXPIRE, CreditType.GOODWILL, 1, "Goodwill credit expired unused")
    return max(0, expiring)


def grant_weekly_credit(student: User, now: datetime | None = None) -> str:
    now = now or utcnow()
    week = week_start(now)
    exists = db.session.scalar(
        db.select(CreditEntry.id).filter_by(student_id=student.id, grant_week=week)
    )
    if exists:
        return "already"

    expire_goodwill(student.id, now)
    standard = _pool(_totals(student.id), CreditType.STANDARD)
    cap = get_setting("credit_cap")
    if standard["available"] + standard["reserved"] >= cap:
        _add(
            student.id,
            E.WEEKLY_CAPPED,
            CreditType.STANDARD,
            0,
            f"Weekly credit not added: limit of {cap} reached",
            grant_week=week,
        )
        return "capped"
    _add(student.id, E.WEEKLY_GRANT, CreditType.STANDARD, 1, "Weekly credit", grant_week=week)
    return "granted"


def grant_weekly_credits(now: datetime | None = None) -> dict:
    now = now or utcnow()
    students = db.session.scalars(
        db.select(User)
        .filter_by(role=Role.STUDENT, account_status=AccountStatus.ACTIVE)
        .order_by(User.id)
    ).all()
    summary = {"granted": 0, "capped": 0, "already": 0}
    for student in students:
        summary[grant_weekly_credit(student, now)] += 1
    return summary


def grant_goodwill(student: User, actor: User, reason: str, now: datetime | None = None):
    if student.role != Role.STUDENT:
        raise ApiError(400, "NOT_A_STUDENT", "Goodwill credits can only be given to students.")
    if not reason or not reason.strip():
        raise ApiError(400, "REASON_REQUIRED", "A reason is required for a goodwill credit.")
    now = now or utcnow()
    entry = _add(
        student.id,
        E.GOODWILL_GRANT,
        CreditType.GOODWILL,
        1,
        reason.strip(),
        actor_id=actor.id,
        expires_at=next_week_start_at(now),
    )
    record_audit(
        "GOODWILL_CREDIT_GRANTED",
        "user",
        student.id,
        actor=actor,
        after={"credit_entry_id": entry.id, "expires_at": entry.expires_at.isoformat()},
        reason=reason.strip(),
    )
    return entry


def _outstanding_reservation(student_id: int, request_id: int) -> CreditType | None:
    entries = db.session.scalars(
        db.select(CreditEntry).filter_by(student_id=student_id, request_id=request_id)
    ).all()
    open_count = defaultdict(int)
    for entry in entries:
        if entry.entry_type == E.RESERVE:
            open_count[entry.credit_type] += entry.quantity
        elif entry.entry_type in (E.RELEASE, E.CONSUME):
            open_count[entry.credit_type] -= entry.quantity
    for credit_type, count in open_count.items():
        if count > 0:
            return credit_type
    return None


def reserve_credit(
    student: User, request_id: int, actor: User | None = None, now: datetime | None = None
) -> CreditType:
    if _outstanding_reservation(student.id, request_id):
        raise ApiError(409, "ALREADY_RESERVED", "A credit is already reserved for this request.")
    current = balance(student.id, now)
    if current["goodwill_available"] > 0:
        credit_type = CreditType.GOODWILL
    elif current["standard_available"] > 0:
        credit_type = CreditType.STANDARD
    else:
        raise ApiError(409, "NO_CREDIT", "You have no cleaning credit available.")
    _add(
        student.id,
        E.RESERVE,
        credit_type,
        1,
        "Reserved for a cleaning request",
        request_id=request_id,
        actor_id=actor.id if actor else student.id,
    )
    return credit_type


def _close_reservation(
    entry_type: E, student: User, request_id: int, reason: str, actor: User | None
) -> CreditType:
    credit_type = _outstanding_reservation(student.id, request_id)
    if credit_type is None:
        raise ApiError(409, "NO_RESERVATION", "No credit is reserved for this request.")
    _add(
        student.id,
        entry_type,
        credit_type,
        1,
        reason,
        request_id=request_id,
        actor_id=actor.id if actor else None,
    )
    return credit_type


def release_credit(student: User, request_id: int, reason: str, actor: User | None = None):
    return _close_reservation(E.RELEASE, student, request_id, reason, actor)


def consume_credit(student: User, request_id: int, reason: str, actor: User | None = None):
    return _close_reservation(E.CONSUME, student, request_id, reason, actor)


def entry_dict(entry: CreditEntry) -> dict:
    expires_at = as_utc(entry.expires_at)
    return {
        "id": entry.id,
        "entry_type": entry.entry_type.value,
        "credit_type": entry.credit_type.value,
        "quantity": entry.quantity,
        "reason": entry.reason,
        "request_id": entry.request_id,
        "created_at": as_utc(entry.created_at).isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "grant_week": entry.grant_week.isoformat() if entry.grant_week else None,
    }


def history(student_id: int, limit: int = 50) -> list[dict]:
    entries = db.session.scalars(
        db.select(CreditEntry)
        .filter_by(student_id=student_id)
        .order_by(CreditEntry.created_at.desc(), CreditEntry.id.desc())
        .limit(limit)
    ).all()
    return [entry_dict(entry) for entry in entries]
