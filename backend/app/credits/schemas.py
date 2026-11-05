from app.common.models import as_utc
from app.credits.models import CreditEntry
from app.extensions import db


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
