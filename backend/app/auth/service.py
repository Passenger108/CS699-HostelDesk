from flask import current_app

from app.auth.passwords import verify_password
from app.common.errors import ApiError
from app.common.models import as_utc, utcnow
from app.extensions import db
from app.users.models import AccountStatus, User

INVALID_CREDENTIALS = ApiError(401, "INVALID_CREDENTIALS", "Invalid login ID or password.")


def _release_expired_lock(user: User) -> None:
    locked_until = as_utc(user.locked_until)
    if user.account_status == AccountStatus.LOCKED and locked_until and locked_until <= utcnow():
        user.account_status = AccountStatus.ACTIVE
        user.locked_until = None
        user.failed_login_count = 0
        user.first_failed_login_at = None


def _record_failure(user: User) -> None:
    cfg = current_app.config
    now = utcnow()
    window_start = as_utc(user.first_failed_login_at)
    if window_start is None or now - window_start > cfg["LOGIN_FAILURE_WINDOW"]:
        user.failed_login_count = 0
        user.first_failed_login_at = now
    user.failed_login_count += 1
    if user.failed_login_count >= cfg["LOGIN_MAX_FAILURES"]:
        user.account_status = AccountStatus.LOCKED
        user.locked_until = now + cfg["LOGIN_LOCK_DURATION"]
        user.token_version += 1


def authenticate(login_id: str, password: str) -> User:
    user = db.session.scalar(db.select(User).filter_by(login_id=login_id))
    if user is None:
        verify_password(None, password)
        raise INVALID_CREDENTIALS

    _release_expired_lock(user)

    if user.account_status == AccountStatus.LOCKED:
        if not verify_password(user.password_hash, password):
            user.locked_until = utcnow() + current_app.config["LOGIN_LOCK_DURATION"]
        db.session.commit()
        raise INVALID_CREDENTIALS

    if user.account_status != AccountStatus.ACTIVE:
        verify_password(user.password_hash, password)
        db.session.commit()
        raise INVALID_CREDENTIALS

    if not verify_password(user.password_hash, password):
        _record_failure(user)
        db.session.commit()
        raise INVALID_CREDENTIALS

    user.failed_login_count = 0
    user.first_failed_login_at = None
    db.session.commit()
    return user
