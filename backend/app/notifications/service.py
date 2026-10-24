from datetime import datetime

from app.common.audit import record_security_event
from app.common.errors import fail
from app.common.models import as_utc, utcnow
from app.extensions import db
from app.notifications.models import Notification
from app.users.models import AccountStatus, Role, User

DEFAULT_LIMIT = 50
MAX_LIMIT = 100

TEMPLATES = {
    "REQUEST_SUBMITTED": (
        "Request sent",
        "Your cleaning request for room {room} is waiting for supervisor approval.",
    ),
    "NEW_REQUEST": ("New cleaning request", "Room {room} asked for cleaning."),
    "NEW_URGENT_REQUEST": (
        "New urgent request",
        "Room {room} asked for urgent cleaning: {reason}",
    ),
    "OFFER_RECEIVED": (
        "New cleaning offer",
        "Room {room} needs cleaning. Please accept or decline within {minutes} minutes.",
    ),
    "REQUEST_CANCELLED_BY_STUDENT": (
        "Request cancelled",
        "The student in room {room} cancelled their cleaning request.",
    ),
}


def notify(user: User, notification_type: str, payload: dict) -> Notification:
    if notification_type not in TEMPLATES:
        raise ValueError(f"Unknown notification type {notification_type}")
    notification = Notification(user_id=user.id, type=notification_type, payload_json=payload)
    db.session.add(notification)
    return notification


def supervisors() -> list[User]:
    return list(
        db.session.scalars(
            db.select(User)
            .filter_by(role=Role.SUPERVISOR, account_status=AccountStatus.ACTIVE)
            .order_by(User.id)
        )
    )


def notify_supervisors(notification_type: str, payload: dict) -> list[Notification]:
    return [notify(user, notification_type, payload) for user in supervisors()]


def unread_count(user: User) -> int:
    return db.session.scalar(
        db.select(db.func.count(Notification.id)).filter_by(user_id=user.id, read_at=None)
    )


def _limit(value: str | None) -> int:
    if value is None or value == "":
        return DEFAULT_LIMIT
    try:
        limit = int(value)
    except ValueError:
        raise fail("NOT_WHOLE", label="limit") from None
    if not 1 <= limit <= MAX_LIMIT:
        raise fail("OUT_OF_RANGE", label="limit", low=1, high=MAX_LIMIT)
    return limit


def list_notifications(
    user: User, unread_only: bool = False, limit: str | None = None
) -> list[Notification]:
    query = db.select(Notification).filter_by(user_id=user.id)
    if unread_only:
        query = query.filter_by(read_at=None)
    query = query.order_by(Notification.created_at.desc(), Notification.id.desc())
    return list(db.session.scalars(query.limit(_limit(limit))))


def get_own_notification(notification_id: int, user: User) -> Notification:
    notification = db.session.get(Notification, notification_id)
    if notification is not None and notification.user_id != user.id:
        record_security_event(
            "ACCESS_DENIED",
            "notification",
            notification_id,
            actor=user,
            detail={"role": user.role.value},
        )
        notification = None
    if notification is None:
        raise fail("NOTIFICATION_NOT_FOUND")
    return notification


def set_read(notification: Notification, read: bool, now: datetime | None = None) -> Notification:
    if read and notification.read_at is None:
        notification.read_at = now or utcnow()
    elif not read:
        notification.read_at = None
    db.session.commit()
    return notification


def notification_dict(notification: Notification) -> dict:
    title, body = TEMPLATES[notification.type]
    payload = notification.payload_json or {}
    read_at = as_utc(notification.read_at)
    return {
        "id": notification.id,
        "type": notification.type,
        "title": title,
        "body": body.format_map(_Defaults(payload)),
        "request_id": payload.get("request_id"),
        "is_read": read_at is not None,
        "read_at": read_at.isoformat() if read_at else None,
        "created_at": as_utc(notification.created_at).isoformat(),
    }


class _Defaults(dict):
    def __missing__(self, key: str) -> str:
        return ""
