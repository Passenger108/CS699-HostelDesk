from datetime import datetime

from app.common.audit import record_security_event
from app.common.errors import fail
from app.common.models import utcnow
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
    "OFFER_ACCEPTED": (
        "Worker assigned",
        "{worker} will clean room {room}, arriving in about {eta} minutes.",
    ),
    "OFFER_DECLINED": ("Offer declined", "{worker} declined room {room}: {reason}"),
    "OFFER_TIMED_OUT": (
        "Offer not answered",
        "{worker} did not answer the offer for room {room} in time.",
    ),
    "LOCATION_STALE": (
        "Update your location",
        "Your location was last updated {minutes} minutes ago. Please update it.",
    ),
    "REQUEST_CANCELLED_BY_SUPERVISOR": (
        "Request cancelled",
        "The supervisor cancelled the cleaning of room {room}: {reason}",
    ),
    "TASK_REASSIGNED": ("Task taken back", "Room {room} is no longer yours: {reason}"),
    "WORKER_CHANGED": (
        "Worker changed",
        "The worker for room {room} changed. The supervisor is arranging the cleaning.",
    ),
    "OFF_DUTY_REQUESTED": ("Off-duty request", "{worker} asked to go off duty."),
    "OFF_DUTY_APPROVED": (
        "You are off duty",
        "{count} of your tasks went back to the supervisor.",
    ),
    "WORKER_EN_ROUTE": ("Worker on the way", "{worker} is on the way to room {room}."),
    "WORKER_ARRIVED": (
        "Worker at your door",
        "{worker} is at room {room}. Answer within {minutes} minutes: come in, wait or cancel.",
    ),
    "COME_IN": ("You can go in", "The student in room {room} said come in."),
    "WAIT_REQUESTED": ("Please wait", "The student in room {room} asked you to wait 5 minutes."),
    "WAIT_ACCEPTED": ("Worker will wait", "The worker will wait {minutes} more minutes."),
    "NEEDS_SUPERVISOR": ("Supervisor needed", "Room {room} needs the supervisor: {reason}"),
    "STUDENT_UNAVAILABLE": (
        "No answer at the door",
        "Nobody answered at room {room}, so the request was closed.",
    ),
    "WORK_RESUMED": ("Work continues", "The supervisor let work on room {room} go on: {reason}"),
    "ETA_UPDATED": ("New arrival time", "{worker} now expects to reach room {room} by {time}."),
    "DELAY_FLAGGED": (
        "The student says you are late",
        "Room {room} is waiting. Update your arrival time if it changed.",
    ),
    "DELAY_ESCALATED": (
        "Worker very late",
        "{worker} is now twice the promised time late for room {room}. Free workers: {workers}.",
    ),
    "DELAY_RESOLVED": (
        "Delay handled",
        "The supervisor handled the delay for room {room}: {reason}",
    ),
    "WINDOW_MISSED": (
        "Choose a new time",
        "The time window for room {room} ended before a worker came. Choose a new time by {time}.",
    ),
    "RESCHEDULED": ("New time chosen", "Room {room} chose a new time: {when}."),
    "REQUEST_EXPIRED": ("Request expired", "The request for room {room} expired: {reason}"),
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
