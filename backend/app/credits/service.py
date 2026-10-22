from collections import defaultdict
from datetime import datetime

from sqlalchemy import func

from app.common.audit import record_audit
from app.common.errors import fail
from app.common.models import as_utc, utcnow
from app.common.settings import get_setting
from app.common.time import next_week_start_at, week_start
from app.credits.models import CreditEntry, CreditEntryType, CreditType
from app.extensions import db
from app.users.models import AccountStatus, Role, User

E = CreditEntryType
STANDARD, GOODWILL = CreditType.STANDARD, CreditType.GOODWILL


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
    granted_by = E.WEEKLY_GRANT if credit_type == STANDARD else E.GOODWILL_GRANT
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


def _usable_goodwill(student_id: int, now: datetime) -> int:
    entries = db.session.scalars(
        db.select(CreditEntry)
        .filter_by(student_id=student_id, credit_type=GOODWILL)
        .order_by(CreditEntry.id)
    ).all()
    unused: list[datetime] = []
    held: dict[int | None, datetime] = {}
    for entry in entries:
        at = as_utc(entry.created_at)
        if entry.entry_type == E.GOODWILL_GRANT:
            unused.append(as_utc(entry.expires_at))
        elif entry.entry_type == E.RESERVE:
            unused = sorted(expiry for expiry in unused if expiry > at)
            if unused:
                held[entry.request_id] = unused.pop(0)
        elif entry.entry_type == E.RELEASE:
            expiry = held.pop(entry.request_id, None)
            if expiry is not None:
                unused.append(expiry)
        elif entry.entry_type == E.CONSUME:
            held.pop(entry.request_id, None)
    return sum(1 for expiry in unused if expiry > now)


def balance(student_id: int, now: datetime | None = None) -> dict:
    now = now or utcnow()
    totals = _totals(student_id)
    standard = _pool(totals, STANDARD)
    goodwill = _pool(totals, GOODWILL)
    goodwill_available = max(0, min(goodwill["available"], _usable_goodwill(student_id, now)))
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
    student_id: int, entry_type: E, credit_type: CreditType, reason: str, quantity=1, **fields
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
    raw = _pool(_totals(student_id), GOODWILL)["available"]
    expiring = raw - max(0, min(raw, _usable_goodwill(student_id, now)))
    for _ in range(max(0, expiring)):
        _add(student_id, E.EXPIRE, GOODWILL, "Goodwill credit expired unused", created_at=now)
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
    standard = _pool(_totals(student.id), STANDARD)
    cap = get_setting("credit_cap")
    if standard["available"] + standard["reserved"] >= cap:
        reason, quantity, result = f"Weekly credit not added: limit of {cap} reached", 0, "capped"
    else:
        reason, quantity, result = "Weekly credit", 1, "granted"
    entry_type = E.WEEKLY_GRANT if quantity else E.WEEKLY_CAPPED
    _add(student.id, entry_type, STANDARD, reason, quantity, grant_week=week, created_at=now)
    return result


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
        raise fail("NOT_A_STUDENT")
    if not reason or not reason.strip():
        raise fail("GOODWILL_REASON")
    now = now or utcnow()
    entry = _add(
        student.id,
        E.GOODWILL_GRANT,
        GOODWILL,
        reason.strip(),
        actor_id=actor.id,
        expires_at=next_week_start_at(now),
        created_at=now,
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
    student: User,
    request_id: int,
    actor: User | None = None,
    now: datetime | None = None,
    allow_goodwill: bool = True,
) -> CreditType:
    if _outstanding_reservation(student.id, request_id):
        raise fail("ALREADY_RESERVED")
    current = balance(student.id, now)
    if allow_goodwill and current["goodwill_available"] > 0:
        credit_type = GOODWILL
    elif current["standard_available"] > 0:
        credit_type = STANDARD
    else:
        raise fail("NO_CREDIT")
    _add(
        student.id,
        E.RESERVE,
        credit_type,
        "Reserved for a cleaning request",
        request_id=request_id,
        actor_id=actor.id if actor else student.id,
        created_at=now or utcnow(),
    )
    return credit_type


def _close_reservation(
    entry_type: E, student: User, request_id: int, reason: str, actor: User | None
) -> CreditType:
    credit_type = _outstanding_reservation(student.id, request_id)
    if credit_type is None:
        raise fail("NO_RESERVATION")
    actor_id = actor.id if actor else None
    _add(student.id, entry_type, credit_type, reason, request_id=request_id, actor_id=actor_id)
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
