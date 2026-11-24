from collections.abc import Callable
from functools import wraps

from flask import request
from flask_jwt_extended import current_user as _jwt_current_user
from flask_jwt_extended import verify_jwt_in_request

from app.common.audit import record_security_event
from app.common.errors import ApiError
from app.extensions import db, jwt
from app.users.models import AccountStatus, Role, User


@jwt.user_identity_loader
def _identity(user: User) -> str:
    return str(user.id)


@jwt.additional_claims_loader
def _claims(user: User) -> dict:
    return {"role": user.role.value, "tv": user.token_version}


@jwt.user_lookup_loader
def _lookup(_header: dict, payload: dict) -> User | None:
    user = db.session.get(User, int(payload["sub"]))
    if user is None or user.account_status != AccountStatus.ACTIVE:
        return None
    if payload.get("tv") != user.token_version:
        return None
    return user


@jwt.user_lookup_error_loader
def _lookup_error(_header: dict, _payload: dict):
    from app.common.errors import error_response

    return error_response(401, "SESSION_INVALID", "Please sign in again.")


@jwt.unauthorized_loader
def _missing(_reason: str):
    from app.common.errors import error_response

    return error_response(401, "AUTH_REQUIRED", "Please sign in.")


@jwt.invalid_token_loader
def _invalid(_reason: str):
    from app.common.errors import error_response

    return error_response(401, "SESSION_INVALID", "Please sign in again.")


@jwt.expired_token_loader
def _expired(_header: dict, _payload: dict):
    from app.common.errors import error_response

    return error_response(401, "SESSION_EXPIRED", "Your session has expired.")


def current_user() -> User:
    return _jwt_current_user


def login_required(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles: Role) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = current_user()
            if user.role not in roles:
                record_security_event(
                    "FORBIDDEN",
                    "route",
                    request.path,
                    actor=user,
                    detail={"method": request.method, "role": user.role.value},
                )
                raise ApiError(403, "FORBIDDEN", "You do not have permission for this action.")
            return fn(*args, **kwargs)

        return wrapper

    return decorator
