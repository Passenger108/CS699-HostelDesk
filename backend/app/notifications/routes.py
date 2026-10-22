from flask import Blueprint, jsonify, request

from app.auth.guards import current_user, login_required
from app.common.errors import ApiError
from app.notifications.service import (
    get_own_notification,
    list_notifications,
    notification_dict,
    set_read,
    unread_count,
)

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


def _flag(name: str) -> bool:
    value = request.args.get(name, "")
    if value in ("", "0", "false"):
        return False
    if value in ("1", "true"):
        return True
    raise ApiError(400, "INVALID_FILTER", f"{name} must be true or false.")


@bp.get("")
@login_required
def my_notifications():
    user = current_user()
    notifications = list_notifications(
        user, unread_only=_flag("unread"), limit=request.args.get("limit")
    )
    return jsonify(
        {
            "notifications": [notification_dict(item) for item in notifications],
            "unread_count": unread_count(user),
        }
    )


@bp.get("/unread-count")
@login_required
def my_unread_count():
    return jsonify({"unread_count": unread_count(current_user())})


@bp.patch("/<int:notification_id>/read")
@login_required
def mark_read(notification_id: int):
    user = current_user()
    notification = set_read(get_own_notification(notification_id, user), read=True)
    return jsonify(
        {"notification": notification_dict(notification), "unread_count": unread_count(user)}
    )


@bp.patch("/<int:notification_id>/unread")
@login_required
def mark_unread(notification_id: int):
    user = current_user()
    notification = set_read(get_own_notification(notification_id, user), read=False)
    return jsonify(
        {"notification": notification_dict(notification), "unread_count": unread_count(user)}
    )
