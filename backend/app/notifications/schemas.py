from app.common.models import as_utc
from app.notifications.models import Notification
from app.notifications.service import TEMPLATES


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
